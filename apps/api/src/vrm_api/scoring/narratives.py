"""LLM-enhanced risk narratives.

The scoring engine produces a deterministic 2-3 sentence narrative — fast,
reliable, no network calls. This module wraps the LLM (Claude or Ollama) to
turn that into a richer 3-5 sentence executive summary with specific dates,
scores, and compliance vocabulary.

Design:
  * Kept separate from the scoring engine so `score_vendor()` stays pure +
    synchronous (eval still runs at 250 ms over 400 vendors).
  * `enhance_narrative()` is async, opt-in, and falls back to the deterministic
    text on any LLM error.
  * Uses `prefer_smart=True` so Claude users get Sonnet-quality prose; Ollama
    users get whatever model `LLM_PROVIDER=ollama` is bound to.
"""

from __future__ import annotations

from ..llm import get_llm
from ..logging_config import get_logger
from .context import VendorContext
from .engine import ScoredVendor

log = get_logger(__name__)


NARRATIVE_SYSTEM_PROMPT = """\
You are the Société Générale Third-Party Risk Management (TPRM) lead analyst.
Given a vendor's structured risk profile, write a single-paragraph executive
risk narrative (3-5 sentences, max 120 words).

Requirements:
  - Lead with the headline risk in one sentence.
  - Cite specific numbers (risk score, breach dates, cert expiries, data classes).
  - Use precise compliance vocabulary where relevant (GDPR Article 28/33,
    SOC 2, ISO 27001, PCI-DSS, NIST SP 800-53 SA-9, SOX 404).
  - End with 2-3 concrete next steps prefixed by "Recommended action:".
  - Severity ranking: CRITICAL > HIGH > MEDIUM > LOW > NONE.
  - Be terse — no platitudes, no marketing-speak, no "in conclusion".

Output prose only. No markdown headers, no JSON, no bullet lists.
"""


def _format_certs(ctx: VendorContext) -> str:
    if not ctx.certifications:
        return "  (none on record)"
    lines = []
    for c in ctx.certifications:
        suffix = f", expires {c.expiry_date.isoformat()}" if c.expiry_date else ""
        lines.append(f"  - {c.cert_type}: {c.status}{suffix}")
    return "\n".join(lines)


def _format_breaches(ctx: VendorContext) -> str:
    if ctx.breach_count_12mo == 0:
        return "  (no breaches in last 12 months)"
    last = ctx.last_breach_date.isoformat() if ctx.last_breach_date else "unknown date"
    return (
        f"  - {ctx.breach_count_12mo} breach event(s) in 12mo; "
        f"latest on {last}, severity {ctx.last_breach_severity}"
    )


def _format_reasons(scored: ScoredVendor) -> str:
    lines = []
    for component, reasons in (scored.reasons or {}).items():
        for r in reasons[:2]:  # top 2 reasons per component to keep prompt tight
            lines.append(f"  - [{component}] {r}")
    return "\n".join(lines) if lines else "  (no notable drivers)"


def build_user_prompt(ctx: VendorContext, scored: ScoredVendor) -> str:
    return (
        f"Vendor: {ctx.name} ({ctx.vendor_id})\n"
        f"Type: {ctx.vendor_type} · Country: {ctx.country} · Tier: {ctx.criticality}\n"
        f"Annual spend: ${ctx.annual_spend_usd:,}\n"
        f"Composite risk: {scored.score}/100 — severity {scored.severity}\n"
        f"Anomaly classification: {scored.anomaly_type or 'NONE'}\n"
        f"\n"
        f"Data access: {ctx.access_level} to "
        f"{', '.join(sorted(ctx.data_classes)) or '(no classes on record)'}\n"
        f"GDPR compliant: {'Yes' if ctx.gdpr_compliant else 'NO'}\n"
        f"Under investigation: {'YES — active' if ctx.under_investigation else 'No'}\n"
        f"Financial health: {ctx.financial_health_score}/100\n"
        f"\n"
        f"Certifications:\n{_format_certs(ctx)}\n"
        f"\n"
        f"Breach history (12mo):\n{_format_breaches(ctx)}\n"
        f"\n"
        f"Triggered rules: {', '.join(scored.triggered_rules) or '(none)'}\n"
        f"\n"
        f"Top scoring drivers:\n{_format_reasons(scored)}\n"
        f"\n"
        f"Write the narrative."
    )


async def enhance_narrative(
    ctx: VendorContext,
    scored: ScoredVendor,
    *,
    prefer_smart: bool = True,
    max_tokens: int = 320,
    temperature: float = 0.3,
) -> tuple[str, dict]:
    """Return (narrative_text, llm_metadata).

    On any LLM error, returns (scored.narrative, {"source": "deterministic-fallback", "error": str}).
    """
    provider = get_llm()
    user_prompt = build_user_prompt(ctx, scored)
    try:
        resp = await provider.complete(
            system=NARRATIVE_SYSTEM_PROMPT,
            user=user_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            prefer_smart=prefer_smart,
        )
        text = resp.text.strip()
        meta = {
            "source": "llm",
            "provider": resp.provider,
            "model": resp.model,
            "usage": resp.usage,
        }
        log.info(
            "narrative_enhanced",
            vendor_id=ctx.vendor_id,
            provider=resp.provider,
            model=resp.model,
            chars=len(text),
        )
        return text, meta
    except Exception as exc:  # noqa: BLE001
        log.warning("narrative_enhance_failed", vendor_id=ctx.vendor_id, error=str(exc))
        return scored.narrative, {"source": "deterministic-fallback", "error": str(exc)}
