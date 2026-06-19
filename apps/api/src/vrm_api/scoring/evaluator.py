"""Evaluation harness: scores all vendors against ground truth, reports metrics.

The rubric the judges score on:
  • Overall risk accuracy ≥ 80%
  • Recall on CRITICAL/HIGH severity (priority over precision)
  • Anomaly type accuracy (does the system pick the right label?)

This module produces a single ``EvalReport`` dataclass + a pretty-printable
ASCII summary. Used by ``make eval`` and surfaced via ``GET /risk/eval``.
"""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

from ..config import settings
from .context import vendor_context_from_row
from .engine import MODEL_VERSION, score_vendor

SEVERITY_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "NONE"]
ANOMALY_ORDER = [
    "BREACHED_VENDOR_HIGH_ACCESS",
    "VENDOR_UNDER_INVESTIGATION",
    "EXPIRED_CERTIFICATION",
    "HIGH_RISK_SCORE",
    "RECENTLY_BREACHED_VENDOR",
    "CONTRACT_EXPIRED_ACTIVE_ACCESS",
    "ELEVATED_RISK_VENDOR",
    "NONE",
]


@dataclass
class ConfusionRow:
    label: str
    predicted: dict[str, int]


@dataclass
class EvalReport:
    model_version: str
    total: int
    correct_anomaly: int
    correct_severity: int
    anomaly_accuracy: float
    severity_accuracy: float
    binary_recall: float           # recall on (any anomaly) vs NONE
    binary_precision: float
    binary_f1: float
    recall_by_severity: dict[str, float]
    precision_by_severity: dict[str, float]
    support_by_severity: dict[str, int]
    confusion_anomaly: list[ConfusionRow]
    top_errors: list[dict] = field(default_factory=list)
    rubric_pass: dict[str, bool] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return asdict(self)


def _load_labels(path: Path) -> dict[str, dict]:
    with path.open() as f:
        return {row["vendor_id"]: row for row in csv.DictReader(f)}


def _load_registry(path: Path) -> list[dict]:
    with path.open() as f:
        return list(csv.DictReader(f))


def evaluate_all(
    registry_csv: Path | None = None,
    labels_csv: Path | None = None,
    today: date | None = None,
    max_errors: int = 15,
) -> EvalReport:
    """Score every vendor in the CSV, compare to ground truth, return metrics."""
    registry_csv = registry_csv or settings.vendor_registry_csv
    labels_csv = labels_csv or settings.vendor_labels_csv
    today = today or date.today()

    rows = _load_registry(registry_csv)
    labels = _load_labels(labels_csv)

    n = len(rows)
    correct_anomaly = 0
    correct_severity = 0

    tp_by_sev: Counter[str] = Counter()
    fn_by_sev: Counter[str] = Counter()
    fp_by_sev: Counter[str] = Counter()
    support: Counter[str] = Counter()

    confusion: dict[str, Counter[str]] = defaultdict(Counter)
    errors: list[dict] = []

    binary_tp = binary_fp = binary_fn = binary_tn = 0

    for row in rows:
        vid = row["vendor_id"]
        ctx = vendor_context_from_row(row)
        pred = score_vendor(ctx, today=today)

        truth = labels.get(vid)
        if truth is None:
            continue

        true_type = truth["anomaly_type"] or "NONE"
        true_sev = truth["severity"] or "NONE"
        pred_type = pred.anomaly_type or "NONE"
        pred_sev = pred.severity or "NONE"

        support[true_sev] += 1
        confusion[true_type][pred_type] += 1

        if pred_type == true_type:
            correct_anomaly += 1
        if pred_sev == true_sev:
            correct_severity += 1

        # Per-severity recall / precision
        if pred_sev == true_sev:
            tp_by_sev[true_sev] += 1
        else:
            fn_by_sev[true_sev] += 1
            fp_by_sev[pred_sev] += 1

        # Binary: any anomaly vs NONE
        true_pos = true_type != "NONE"
        pred_pos = pred_type != "NONE"
        if true_pos and pred_pos:
            binary_tp += 1
        elif pred_pos and not true_pos:
            binary_fp += 1
        elif true_pos and not pred_pos:
            binary_fn += 1
        else:
            binary_tn += 1

        if pred_type != true_type and len(errors) < max_errors:
            errors.append({
                "vendor_id": vid,
                "predicted": {"anomaly_type": pred_type, "severity": pred_sev, "score": pred.score},
                "actual": {"anomaly_type": true_type, "severity": true_sev,
                            "explanation": truth.get("explanation", "")},
            })

    recall_by_sev = {
        sev: round(tp_by_sev[sev] / support[sev], 4) if support[sev] else 0.0
        for sev in SEVERITY_ORDER
    }
    precision_by_sev = {}
    for sev in SEVERITY_ORDER:
        predicted_count = tp_by_sev[sev] + fp_by_sev[sev]
        precision_by_sev[sev] = round(tp_by_sev[sev] / predicted_count, 4) if predicted_count else 0.0

    binary_recall = binary_tp / (binary_tp + binary_fn) if (binary_tp + binary_fn) else 0.0
    binary_precision = binary_tp / (binary_tp + binary_fp) if (binary_tp + binary_fp) else 0.0
    binary_f1 = (
        2 * binary_precision * binary_recall / (binary_precision + binary_recall)
        if (binary_precision + binary_recall) else 0.0
    )

    confusion_rows = [
        ConfusionRow(label=a, predicted={p: confusion[a][p] for p in ANOMALY_ORDER if confusion[a][p] > 0})
        for a in ANOMALY_ORDER
        if confusion[a]
    ]

    anomaly_acc = round(correct_anomaly / n, 4) if n else 0.0
    severity_acc = round(correct_severity / n, 4) if n else 0.0

    rubric_pass = {
        "anomaly_accuracy_>=_0.80": anomaly_acc >= 0.80,
        "critical_recall_>=_0.95": recall_by_sev.get("CRITICAL", 0) >= 0.95,
        "high_recall_>=_0.80": recall_by_sev.get("HIGH", 0) >= 0.80,
        "binary_f1_>=_0.85": binary_f1 >= 0.85,
    }

    return EvalReport(
        model_version=MODEL_VERSION,
        total=n,
        correct_anomaly=correct_anomaly,
        correct_severity=correct_severity,
        anomaly_accuracy=anomaly_acc,
        severity_accuracy=severity_acc,
        binary_recall=round(binary_recall, 4),
        binary_precision=round(binary_precision, 4),
        binary_f1=round(binary_f1, 4),
        recall_by_severity=recall_by_sev,
        precision_by_severity=precision_by_sev,
        support_by_severity={sev: support[sev] for sev in SEVERITY_ORDER},
        confusion_anomaly=confusion_rows,
        top_errors=errors,
        rubric_pass=rubric_pass,
    )


def format_report(rep: EvalReport) -> str:
    """Human-friendly ASCII summary."""
    lines: list[str] = []
    lines.append("=" * 72)
    lines.append(f" Risk Scoring Evaluation — model={rep.model_version}  N={rep.total}")
    lines.append("=" * 72)
    lines.append("")
    lines.append(f"Anomaly-type accuracy : {rep.anomaly_accuracy:>6.1%}   ({rep.correct_anomaly}/{rep.total})")
    lines.append(f"Severity accuracy     : {rep.severity_accuracy:>6.1%}   ({rep.correct_severity}/{rep.total})")
    lines.append(f"Binary detection      : precision={rep.binary_precision:.1%}  "
                 f"recall={rep.binary_recall:.1%}  F1={rep.binary_f1:.3f}")
    lines.append("")
    lines.append("Per-severity (rubric priority on CRITICAL/HIGH recall):")
    lines.append(f"  {'severity':10s} {'support':>8s} {'recall':>10s} {'precision':>12s}")
    for sev in SEVERITY_ORDER:
        r = rep.recall_by_severity.get(sev, 0)
        p = rep.precision_by_severity.get(sev, 0)
        s = rep.support_by_severity.get(sev, 0)
        flag = ""
        if sev == "CRITICAL" and r < 0.95:
            flag = "  ← below 0.95 target"
        elif sev == "HIGH" and r < 0.80:
            flag = "  ← below 0.80 target"
        lines.append(f"  {sev:10s} {s:>8d} {r:>10.1%} {p:>12.1%}{flag}")

    lines.append("")
    lines.append("Confusion matrix (true → predicted):")
    for row in rep.confusion_anomaly:
        preds = ", ".join(f"{k}={v}" for k, v in row.predicted.items())
        lines.append(f"  {row.label:35s} → {preds}")

    if rep.top_errors:
        lines.append("")
        lines.append(f"Top {len(rep.top_errors)} misclassifications:")
        for e in rep.top_errors:
            lines.append(
                f"  {e['vendor_id']}: predicted {e['predicted']['anomaly_type']}/{e['predicted']['severity']} "
                f"(score={e['predicted']['score']})  actual {e['actual']['anomaly_type']}/{e['actual']['severity']}"
            )

    lines.append("")
    lines.append("Rubric gates:")
    for name, ok in rep.rubric_pass.items():
        lines.append(f"  [{'PASS' if ok else 'FAIL'}]  {name}")
    lines.append("=" * 72)
    return "\n".join(lines)
