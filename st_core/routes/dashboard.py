from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Request, Form, Query
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

PERIOD_MAP = {
    "today": (datetime.utcnow().strftime("%Y-%m-%d"), None),
    "7d": ((datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d"), None),
    "30d": ((datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d"), None),
}

@router.get("", response_class=HTMLResponse)
def admin_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
    status: Optional[str] = Query(None),
    language: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    downloaded: Optional[bool] = Query(None),
    period: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    if period and period in PERIOD_MAP:
        date_from, date_to = PERIOD_MAP[period]

    skip = (page - 1) * per_page
    leads, total = LeadService.get_filtered_leads(
        db,
        status=status,
        language=language,
        country=country,
        search=search,
        downloaded=downloaded,
        date_from=date_from,
        date_to=date_to,
        sort_by=sort_by,
        sort_order=sort_order,
        skip=skip,
        limit=per_page,
    )
    stats = LeadService.get_dashboard_stats(db)
    total_pages = (total + per_page - 1) // per_page
    recent_events = LeadService.get_recent_events(db, limit=15)

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "leads": leads,
            "stats": stats,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
            "status_filter": status,
            "language_filter": language,
            "country_filter": country,
            "search_filter": search,
            "downloaded_filter": downloaded,
            "period_filter": period,
            "date_from": date_from,
            "date_to": date_to,
            "sort_by": sort_by,
            "sort_order": sort_order,
            "status_list": list(LeadStatus),
            "recent_events": recent_events,
            "now": datetime.utcnow,
        },
    )

@router.get("/lead/{lead_id}", response_class=HTMLResponse)
def admin_lead_detail(
    request: Request,
    lead_id: int,
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    lead = LeadService.get_lead_by_id(db, lead_id)
    events = LeadService.get_lead_events(db, lead_id)
    return templates.TemplateResponse(
        request,
        "lead_detail.html",
        {"lead": lead, "events": events, "statuses": list(LeadStatus)},
    )

@router.post("/lead/{lead_id}")
def admin_update_lead(
    lead_id: int,
    status: LeadStatus = Form(...),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    update_data = LeadUpdate(status=status, notes=notes)
    LeadService.update_lead(db, lead_id, update_data, created_by=admin)
    return RedirectResponse(url=f"/admin/lead/{lead_id}", status_code=303)
