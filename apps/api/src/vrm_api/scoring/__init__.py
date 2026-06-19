"""Risk scoring engine + evaluation harness.

The engine is a pure function over a ``VendorContext`` dataclass — no DB
access, no LLM calls — so it's trivially testable and fast (~10 ms per
vendor). The DB orchestration lives in ``score_all.py``; evaluation against
ground truth in ``evaluator.py``.

Public surface:

    from vrm_api.scoring import score_vendor, evaluate_all, VendorContext
"""

from .engine import score_vendor, ScoredVendor
from .context import VendorContext, vendor_context_from_orm, vendor_context_from_row
from .evaluator import evaluate_all, EvalReport

__all__ = [
    "score_vendor",
    "ScoredVendor",
    "VendorContext",
    "vendor_context_from_orm",
    "vendor_context_from_row",
    "evaluate_all",
    "EvalReport",
]
