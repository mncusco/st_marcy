from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from dependencies import get_db
from security import verify_admin
from services.lead_service import LeadService
from services.email_engine import EmailEngine
from services.interview_service import (
    get_upcoming_interviews, get_today_interviews, get_interview_stats,
    create_interview, schedule_interview, complete_interview,
    cancel_interview, mark_no_show, get_lead_interviews,
)
from schemas import EmailQueueResponse
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
    email_stats = EmailEngine(db).get_queue_stats()
    recent_emails = EmailEngine(db).get_recent_emails(limit=10)
    interview_stats = get_interview_stats(db)
    upcoming_interviews = get_upcoming_interviews(db, limit=10)
    today_interviews = get_today_interviews(db)

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
            "email_stats": email_stats,
            "recent_emails": recent_emails,
            "interview_stats": interview_stats,
            "upcoming_interviews": upcoming_interviews,
            "today_interviews": today_interviews,
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
    emails = EmailEngine(db).get_recent_emails()
    lead_emails = [e for e in emails if e.lead_id == lead_id]
    lead_interviews = get_lead_interviews(db, lead_id)
    return templates.TemplateResponse(
        request,
        "lead_detail.html",
        {"lead": lead, "events": events, "emails": lead_emails, "interviews": lead_interviews, "statuses": list(LeadStatus)},
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

@router.post("/email/process")
def admin_process_email_queue(
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    count = EmailEngine(db).process_pending()
    return RedirectResponse(url="/admin", status_code=303)

@router.post("/email/{email_id}/cancel")
def admin_cancel_email(
    email_id: int,
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    EmailEngine(db).cancel_email(email_id)
    return RedirectResponse(url="/admin", status_code=303)

@router.post("/email/{email_id}/retry")
def admin_retry_email(
    email_id: int,
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    EmailEngine(db).retry_email(email_id)
    return RedirectResponse(url="/admin", status_code=303)

@router.post("/lead/{lead_id}/reprocess-automation")
def admin_reprocess_automation(
    lead_id: int,
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    from services.automation_engine import AutomationEngine
    lead = LeadService.get_lead_by_id(db, lead_id)
    AutomationEngine(db).on_lead_created(lead)
    AutomationEngine(db).on_status_changed(lead, lead.status, lead.status)
    return RedirectResponse(url=f"/admin/lead/{lead_id}", status_code=303)

@router.post("/lead/{lead_id}/interview/create")
def admin_create_interview(
    lead_id: int,
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    create_interview(db, lead_id, created_by=admin)
    db.commit()
    return RedirectResponse(url=f"/admin/lead/{lead_id}", status_code=303)

@router.post("/interview/{interview_id}/schedule")
def admin_schedule_interview(
    interview_id: int,
    scheduled_at: str = Form(...),
    duration_minutes: int = Form(30),
    meeting_url: str = Form(""),
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    from datetime import datetime
    try:
        dt = datetime.strptime(scheduled_at, "%Y-%m-%dT%H:%M")
    except ValueError:
        dt = datetime.strptime(scheduled_at, "%Y-%m-%d %H:%M")
    interview = schedule_interview(db, interview_id, dt, duration_minutes,
                                    meeting_url=meeting_url or None, created_by=admin)
    db.commit()
    return RedirectResponse(url=f"/admin/lead/{interview.lead_id}", status_code=303)

@router.post("/interview/{interview_id}/complete")
def admin_complete_interview(
    interview_id: int,
    notes: str = Form(""),
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    interview = complete_interview(db, interview_id, notes=notes or None, created_by=admin)
    db.commit()
    return RedirectResponse(url=f"/admin/lead/{interview.lead_id}", status_code=303)

@router.post("/interview/{interview_id}/cancel")
def admin_cancel_interview(
    interview_id: int,
    notes: str = Form(""),
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    interview = cancel_interview(db, interview_id, notes=notes or None, created_by=admin)
    db.commit()
    return RedirectResponse(url=f"/admin/lead/{interview.lead_id}", status_code=303)

@router.post("/interview/{interview_id}/no-show")
def admin_no_show_interview(
    interview_id: int,
    notes: str = Form(""),
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    interview = mark_no_show(db, interview_id, notes=notes or None, created_by=admin)
    db.commit()
    return RedirectResponse(url=f"/admin/lead/{interview.lead_id}", status_code=303)
