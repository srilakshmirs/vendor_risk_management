"""Risk endpoints — score one, score all, get eval metrics."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..db import get_db
from ..models import AuditLog, RiskAssessment, Vendor
from ..scoring import evaluate_all, score_vendor, vendor_context_from_orm
from ..scoring.engine import ScoredVendor
from ..scoring.narratives import enhance_narrative
from ..scoring.score_all import run as run_score_all
from ..services.email_service import notify_critical_high, notify_resolution

router = APIRouter(prefix="/risk", tags=["risk"])


# ── Schemas ───────────────────────────────────────────────────────────
class ScoredVendorOut(BaseModel):
    vendor_id: str
    score: int
    traffic_light: str
    severity: str
    anomaly_type: str | None
    components: dict[str, int]
    weighted_components: dict[str, float]
    triggered_rules: list[str]
    rule_hits: list[dict]
    narrative: str
    reasons: dict[str, list[str]]
    model_version: str
    # Provenance of the narrative — populated when LLM enhancement has run
    narrative_source: str | None = None         # "llm" | "deterministic-fallback" | None
    narrative_provider: str | None = None       # "claude" | "ollama" | "mock"
    narrative_model: str | None = None          # actual model id

    @classmethod
    def from_engine(cls, s: ScoredVendor) -> "ScoredVendorOut":
        return cls(**s.as_dict())


class ScoreAllOut(BaseModel):
    status: str
    vendors: int
    assessments_written: int


class EnhanceOut(BaseModel):
    vendor_id: str
    narrative: str
    source: str            # "llm" | "deterministic-fallback"
    provider: str | None = None
    model: str | None = None
    usage: dict[str, Any] | None = None
    deterministic_narrative: str | None = None  # kept for fallback / comparison
    persisted: bool = False


class EvalOut(BaseModel):
    model_version: str
    total: int
    anomaly_accuracy: float
    severity_accuracy: float
    binary_recall: float
    binary_precision: float
    binary_f1: float
    recall_by_severity: dict[str, float]
    precision_by_severity: dict[str, float]
    support_by_severity: dict[str, int]
    rubric_pass: dict[str, bool]


# ── Helpers ───────────────────────────────────────────────────────────
def _load_vendor_with_relations(db: Session, vendor_id: str) -> Vendor:
    stmt = (
        select(Vendor)
        .where(Vendor.vendor_id == vendor_id)
        .options(
            selectinload(Vendor.certifications),
            selectinload(Vendor.data_access),
            selectinload(Vendor.contracts),
            selectinload(Vendor.breaches),
            selectinload(Vendor.risk_assessments),
        )
    )
    vendor = db.execute(stmt).scalar_one_or_none()
    if vendor is None:
        raise HTTPException(status_code=404, detail=f"Vendor {vendor_id} not found")
    return vendor


def _persist(db: Session, vendor: Vendor, scored: ScoredVendor) -> None:
    db.add(RiskAssessment(
        vendor_id=vendor.id,
        score=scored.score,
        traffic_light=scored.traffic_light,
        severity=scored.severity,
        anomaly_type=scored.anomaly_type if scored.anomaly_type != "NONE" else None,
        components={
            "raw": scored.components,
            "weighted": scored.weighted_components,
            "reasons": scored.reasons,
        },
        narrative=scored.narrative,
        triggered_rules=scored.triggered_rules,
        model_version=scored.model_version,
    ))
    db.add(AuditLog(
        actor="api", action="score_vendor", entity_type="vendor", entity_id=vendor.vendor_id,
        payload={"score": scored.score, "severity": scored.severity, "anomaly": scored.anomaly_type},
    ))


# ── Endpoints ─────────────────────────────────────────────────────────
@router.post("/score/{vendor_id}", response_model=ScoredVendorOut)
def score_one(vendor_id: str, persist: bool = True, db: Session = Depends(get_db)) -> ScoredVendorOut:
    """Score one vendor synchronously. `persist=false` for dry-run (no DB writes)."""
    vendor = _load_vendor_with_relations(db, vendor_id)

    # Capture previous severity for resolution detection
    prev_assessment = max(vendor.risk_assessments, key=lambda r: r.created_at, default=None)
    prev_severity = prev_assessment.severity if prev_assessment else None
    prev_score = prev_assessment.score if prev_assessment else None

    ctx = vendor_context_from_orm(vendor)
    scored = score_vendor(ctx)
    if persist:
        _persist(db, vendor, scored)
        db.commit()

    # Email notifications
    notify_critical_high(scored, vendor)
    # Resolution detection: severity dropped from CRITICAL/HIGH to lower
    if prev_severity in {"CRITICAL", "HIGH"} and scored.severity not in {"CRITICAL", "HIGH"}:
        notify_resolution(vendor, prev_severity, scored.severity, scored.score, prev_score)

    return ScoredVendorOut.from_engine(scored)


@router.get("/score/{vendor_id}/latest", response_model=ScoredVendorOut | None)
def latest_score(vendor_id: str, db: Session = Depends(get_db)) -> ScoredVendorOut | None:
    """Return the most recent persisted RiskAssessment (no recompute)."""
    vendor = _load_vendor_with_relations(db, vendor_id)
    latest = max(vendor.risk_assessments, key=lambda r: r.created_at, default=None)
    if latest is None:
        return None
    components = latest.components or {}
    meta = components.get("meta") or {}
    return ScoredVendorOut(
        vendor_id=vendor.vendor_id,
        score=latest.score,
        traffic_light=latest.traffic_light,
        severity=latest.severity,
        anomaly_type=latest.anomaly_type,
        components=components.get("raw", {}),
        weighted_components=components.get("weighted", {}),
        triggered_rules=latest.triggered_rules or [],
        rule_hits=[],
        narrative=latest.narrative or "",
        reasons=components.get("reasons", {}),
        model_version=latest.model_version,
        narrative_source=meta.get("narrative_source"),
        narrative_provider=meta.get("narrative_provider"),
        narrative_model=meta.get("narrative_model"),
    )


@router.post("/score-all", response_model=ScoreAllOut)
def score_all_endpoint(background: BackgroundTasks, async_mode: bool = False) -> ScoreAllOut:
    """Score every vendor in the DB. Set ``async_mode=true`` to run in the background."""
    if async_mode:
        background.add_task(run_score_all, replace=True)
        return ScoreAllOut(status="queued", vendors=0, assessments_written=0)
    counts = run_score_all(replace=True)
    return ScoreAllOut(status="complete", **counts)


@router.post("/score/{vendor_id}/enhance", response_model=EnhanceOut)
async def enhance_one(
    vendor_id: str,
    persist: bool = True,
    db: Session = Depends(get_db),
) -> EnhanceOut:
    """Re-generate the risk narrative for a vendor via the LLM.

    Uses the most recent RiskAssessment as input. If there is no assessment
    on record yet, scores the vendor first (deterministic, fast) and then
    enhances. Falls back to the deterministic narrative if the LLM errors.
    """
    vendor = _load_vendor_with_relations(db, vendor_id)
    ctx = vendor_context_from_orm(vendor)

    # Score (or re-score) deterministically — cheap, gives us the baseline narrative.
    scored = score_vendor(ctx)

    # Async LLM call (can take a few seconds with Ollama)
    enhanced_text, meta = await enhance_narrative(ctx, scored, prefer_smart=True)
    deterministic = scored.narrative

    if persist:
        # Find the most recent assessment (if any) and update its narrative in-place,
        # OR insert a new one if none exists. This keeps the timeline tidy: enhancing
        # an existing assessment doesn't create a duplicate row.
        latest = max(vendor.risk_assessments, key=lambda r: r.created_at, default=None)
        if latest is None:
            _persist(db, vendor, scored)
            db.flush()
            latest = max(vendor.risk_assessments, key=lambda r: r.created_at)

        latest.narrative = enhanced_text
        # Stash both the deterministic version and LLM metadata in components.meta
        components = dict(latest.components or {})
        meta_block = dict(components.get("meta", {}))
        meta_block.update({
            "narrative_source": meta.get("source"),
            "narrative_provider": meta.get("provider"),
            "narrative_model": meta.get("model"),
            "narrative_usage": meta.get("usage"),
            "deterministic_narrative": deterministic,
        })
        components["meta"] = meta_block
        latest.components = components

        db.add(AuditLog(
            actor="api",
            action="narrative_enhance",
            entity_type="risk_assessment",
            entity_id=str(latest.id),
            payload={"vendor": vendor_id, "source": meta.get("source"), "model": meta.get("model")},
        ))
        db.commit()

    return EnhanceOut(
        vendor_id=vendor_id,
        narrative=enhanced_text,
        source=str(meta.get("source", "unknown")),
        provider=meta.get("provider"),
        model=meta.get("model"),
        usage=meta.get("usage"),
        deterministic_narrative=deterministic if deterministic != enhanced_text else None,
        persisted=persist,
    )


@router.get("/eval", response_model=EvalOut)
def eval_endpoint() -> EvalOut:
    """Run the eval harness against vendor_labels.csv (synchronous, ~250 ms for 400 vendors)."""
    rep = evaluate_all()
    return EvalOut(
        model_version=rep.model_version,
        total=rep.total,
        anomaly_accuracy=rep.anomaly_accuracy,
        severity_accuracy=rep.severity_accuracy,
        binary_recall=rep.binary_recall,
        binary_precision=rep.binary_precision,
        binary_f1=rep.binary_f1,
        recall_by_severity=rep.recall_by_severity,
        precision_by_severity=rep.precision_by_severity,
        support_by_severity=rep.support_by_severity,
        rubric_pass=rep.rubric_pass,
    )
