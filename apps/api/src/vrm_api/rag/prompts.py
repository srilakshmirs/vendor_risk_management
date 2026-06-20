"""System + context prompts for the /ask endpoint."""

from __future__ import annotations

from .retriever import RetrievedChunk

ASK_SYSTEM_PROMPT = """\
You are the Société Générale Third-Party Risk Management (TPRM) analyst assistant.
Your job is to answer questions about the vendor portfolio using ONLY the vendor
context blocks provided below. Each block is a single vendor profile.

Rules:
1. Cite every vendor you reference using its ID in square brackets, e.g. [V0123].
2. If the answer requires data not present in the context, say so explicitly —
   do not invent vendors, breaches, scores, or certifications.
3. Be terse and structured: a short summary sentence, then a bullet list when
   listing multiple vendors.
4. Severity ranking: CRITICAL > HIGH > MEDIUM > LOW > NONE. Prioritise
   higher-severity vendors when answering "which vendors are at risk" questions.
5. Compliance vocabulary: SOC 2, ISO 27001, PCI-DSS, GDPR Article 28/33,
   NIST SP 800-53 SA-9, SOX 404. Use them precisely.
"""


def build_user_prompt(question: str, chunks: list[RetrievedChunk]) -> str:
    """Compose the user turn — question + retrieved vendor context blocks."""
    if not chunks:
        return f"Question: {question}\n\n(No vendor context retrieved.)"

    blocks: list[str] = []
    for i, c in enumerate(chunks, start=1):
        blocks.append(
            f"--- Vendor context #{i} (id={c.entity_id}, similarity={c.similarity:.3f}) ---\n{c.chunk}"
        )
    context = "\n\n".join(blocks)
    return f"Question: {question}\n\nVendor context:\n{context}"
