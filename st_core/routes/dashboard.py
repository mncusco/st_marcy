import json
from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse, Response
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
from schemas import EmailQueueResponse, CandidateAnalysisResponse
from schemas import LeadUpdate
from models import LeadStatus
from services.ai_service import AIService
from services.analytics_service import AnalyticsService

router = APIRouter(prefix="/admin", tags=["Dashboard"])
templates = Jinja2Templates(directory="templates")
templates.env.filters["from_json"] = lambda v: json.loads(v) if v else []

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
    ai_service = AIService(db)
    ai_stats = ai_service.get_analysis_stats()
    recent_analyses = ai_service.get_recent_analyses(limit=5)
    analytics = AnalyticsService(db)
    bi_metrics = analytics.get_conversion_metrics()
    bi_sources = analytics.get_lead_sources()
    bi_pipeline = analytics.get_pipeline_value()
    bi_monthly = analytics.get_monthly_leads()
    bi_downloads = analytics.get_download_statistics()

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
            "ai_stats": ai_stats,
            "recent_analyses": recent_analyses,
            "bi_metrics": bi_metrics,
            "bi_sources": bi_sources,
            "bi_pipeline": bi_pipeline,
            "bi_monthly": bi_monthly,
            "bi_downloads": bi_downloads,
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
    ai_service = AIService(db)
    lead_analysis = ai_service.get_analysis(lead_id)
    return templates.TemplateResponse(
        request,
        "lead_detail.html",
        {"lead": lead, "events": events, "emails": lead_emails, "interviews": lead_interviews, "statuses": list(LeadStatus), "analysis": lead_analysis},
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

@router.post("/lead/{lead_id}/analyze")
def admin_analyze_lead(
    lead_id: int,
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    lead = LeadService.get_lead_by_id(db, lead_id)
    AIService(db).analyze_candidate(lead)
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

@router.get("/export/leads")
def admin_export_leads(
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    import csv, io
    leads = db.query(Lead).order_by(Lead.created_at.desc()).all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "uuid", "first_name", "last_name", "email", "country",
                     "language", "status", "source_page", "campaign", "referrer",
                     "utm_source", "utm_medium", "utm_campaign", "downloaded_editorial",
                     "created_at", "updated_at"])
    for l in leads:
        writer.writerow([
            l.id, l.uuid, l.first_name, l.last_name, l.email, l.country,
            l.language, l.status.value, l.source_page, l.campaign, l.referrer,
            l.utm_source, l.utm_medium, l.utm_campaign,
            "yes" if l.downloaded_editorial else "no",
            l.created_at.isoformat() if l.created_at else "",
            l.updated_at.isoformat() if l.updated_at else "",
        ])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=leads_export.csv"},
    )


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
