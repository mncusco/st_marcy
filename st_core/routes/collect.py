from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from dependencies import get_db
from schemas import CollectLeadCreate, ALLOWED_COLLECT_SOURCES
from services.lead_service import LeadService
from core.languages import detect_language
from core.tracking import extract_request_context

router = APIRouter(prefix="/api/collect", tags=["Collect"])


@router.post("", response_model=dict)
def create_collect_lead(lead: CollectLeadCreate, request: Request, db: Session = Depends(get_db)):
    """Endpoint di SOLA RACCOLTA per canali esterni dedicati.

    Accetta email (+ source obbligatorio) e salva il lead taggato per fonte,
    SENZA attivare le sequenze email di ST Core. I lead restano separati e
    filtrabili per `source` (es. 'the-last-call', 'la-montagna-che-portiamo-dentro').
    """
    source = (lead.source or "").strip().lower()
    if source not in ALLOWED_COLLECT_SOURCES:
        raise HTTPException(
            status_code=422,
            detail=f"Source non autorizzato: '{lead.source}'. Consentiti: {', '.join(ALLOWED_COLLECT_SOURCES)}",
        )
    lead = lead.model_copy(update={"source": source})

    lang = detect_language(
        form_lang=lead.language,
        accept_language=request.headers.get("accept-language"),
    )
    if not lead.language:
        lead = lead.model_copy(update={"language": lang})

    ctx = extract_request_context(request)
    updates = {}
    if not lead.country and ctx["country"]:
        updates["country"] = ctx["country"]
    if updates:
        lead = lead.model_copy(update=updates)

    db_lead = LeadService.create_collect_lead(db, lead)
    return {"success": True, "id": db_lead.id, "source": db_lead.source}
