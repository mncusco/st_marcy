from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from dependencies import get_db
from security import verify_admin
from services.lead_service import LeadService
from schemas import LeadUpdate
from models import LeadStatus

router = APIRouter(prefix="/admin", tags=["Dashboard"])
templates = Jinja2Templates(directory="templates")

@router.get("", response_class=HTMLResponse)
def admin_dashboard(request: Request, db: Session = Depends(get_db), admin: str = Depends(verify_admin)):
    leads = LeadService.get_leads(db)
    stats = LeadService.get_dashboard_stats(db)
    return templates.TemplateResponse(
        "dashboard.html", 
        {"request": request, "leads": leads, "stats": stats}
    )

@router.get("/lead/{lead_id}", response_class=HTMLResponse)
def admin_lead_detail(request: Request, lead_id: int, db: Session = Depends(get_db), admin: str = Depends(verify_admin)):
    lead = LeadService.get_lead_by_id(db, lead_id)
    return templates.TemplateResponse(
        "lead_detail.html", 
        {"request": request, "lead": lead, "statuses": LeadStatus}
    )

@router.post("/lead/{lead_id}")
def admin_update_lead(
    lead_id: int, 
    status: LeadStatus = Form(...), 
    notes: str = Form(""), 
    db: Session = Depends(get_db), 
    admin: str = Depends(verify_admin)
):
    update_data = LeadUpdate(status=status, notes=notes)
    LeadService.update_lead(db, lead_id, update_data)
    return RedirectResponse(url=f"/admin/lead/{lead_id}", status_code=303)
