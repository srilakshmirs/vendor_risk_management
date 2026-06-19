import io
import pypdf
import structlog
from fastapi import APIRouter, File, HTTPException, UploadFile, status

from ..llm import get_llm

router = APIRouter(prefix="/contracts", tags=["Contracts"])
logger = structlog.get_logger(__name__)

SCHEMA_HINT = """
{
    "data_access_permissions": ["list of inferred or explicit data access rights"],
    "compliance_obligations": ["list of certifications, audits, or compliance duties mentioned"],
    "sla_uptime_percentage": "extracted SLA uptime % or null if not found",
    "renewal_date": "YYYY-MM-DD or null if not found",
    "termination_conditions": "brief summary of termination rights"
}
"""

SYSTEM_PROMPT = """
You are an expert Third-Party Risk Management (TPRM) legal analyst. 
Your job is to read raw text extracted from a vendor contract, Master Services Agreement (MSA), or Data Processing Agreement (DPA), and extract key risk indicators and obligations.
Be precise. If a value is not found in the text, return null or an empty list rather than hallucinating.
"""

@router.post("/extract")
async def extract_contract_obligations(file: UploadFile = File(...)) -> dict:
    """
    Extracts structured obligations, data access permissions, and SLA details from an uploaded PDF contract.
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Only PDF files are supported."
        )

    try:
        content = await file.read()
        pdf = pypdf.PdfReader(io.BytesIO(content))
        
        # Extract text from all pages
        text_chunks = []
        for page in pdf.pages:
            extracted = page.extract_text()
            if extracted:
                text_chunks.append(extracted)
                
        full_text = "\n\n".join(text_chunks)
        
        # Guard against excessively large PDFs (truncate to ~30k chars to fit within standard context windows)
        if len(full_text) > 30000:
            logger.warning("contract_text_truncated", chars=len(full_text))
            full_text = full_text[:30000] + "\n...[TRUNCATED]..."

        if not full_text.strip():
            raise ValueError("No extractable text found in the PDF.")

        user_prompt = f"Extract structured risk metadata from the following contract text:\n\n{full_text}"

        logger.info("extracting_contract_nlp", filename=file.filename, length=len(full_text))
        
        provider = get_llm()
        result = await provider.extract_json(
            system=SYSTEM_PROMPT,
            user=user_prompt,
            schema_hint=SCHEMA_HINT,
            max_tokens=1024,
            prefer_smart=True  # Use the smarter model for accurate extraction
        )

        return result

    except Exception as e:
        logger.error("contract_extraction_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process contract: {str(e)}"
        )
