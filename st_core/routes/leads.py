from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from dependencies import get_db
from schemas import LeadCreate, LeadResponse, LeadUpdate
from services.lead_service import LeadService
from core.languages import detect_language
from core.tracking import extract_request_context
from security import verify_admin

router = APIRouter(prefix="/api/leads", tags=["Leads"])

@router.post("", response_model=dict)
def create_lead(lead: LeadCreate, request: Request, db: Session = Depends(get_db)):
    detected = detect_language(
        form_lang=lead.language,
        accept_language=request.headers.get("accept-language"),
    )
    if not lead.language:
        lead = lead.model_copy(update={"language": detected})

    ctx = extract_request_context(request)
    if not lead.ip_address:
        lead = lead.model_copy(update={"ip_address": ctx["ip_address"]})
    if not lead.country and ctx["country"]:
        lead = lead.model_copy(update={"country": ctx["country"]})
    if not lead.user_agent:
        lead = lead.model_copy(update={"user_agent": ctx["user_agent"]})
    if not lead.device_type:
        lead = lead.model_copy(update={
            "device_type": ctx["device_type"],
            "browser": ctx["browser"],
            "os_name": ctx["os_name"],
        })

    db_lead = LeadService.create_lead(db, lead)
    return {"success": True, "id": db_lead.id, "download_token": db_lead.download_token}

@router.get("", response_model=List[LeadResponse])
def get_leads(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), admin: str = Depends(verify_admin)):
    return LeadService.get_leads(db, skip=skip, limit=limit)

@router.get("/{lead_id}", response_model=LeadResponse)
def get_lead(lead_id: int, db: Session = Depends(get_db), admin: str = Depends(verify_admin)):
    return LeadService.get_lead_by_id(db, lead_id)

@router.patch("/{lead_id}", response_model=LeadResponse)
def update_lead(lead_id: int, lead_update: LeadUpdate, db: Session = Depends(get_db), admin: str = Depends(verify_admin)):
    return LeadService.update_lead(db, lead_id, lead_update)

@router.post("/{lead_id}/download", response_model=dict)
def track_download(lead_id: int, request: Request, db: Session = Depends(get_db)):
    ctx = extract_request_context(request)
    lead = LeadService.mark_downloaded(
        db, lead_id, ip_address=ctx["ip_address"], user_agent=ctx["user_agent"]
    )
    return {"success": True, "downloaded": True}
