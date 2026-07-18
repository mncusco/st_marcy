import json
import os
import logging
from typing import Optional
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Request, Form, Query, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from dependencies import get_db
from security import verify_admin
from services.lead_service import LeadService
from services.email_engine import EmailEngine
from services.note_service import NoteService
from services.backup_service import BackupService
from services.interview_service import (
    get_upcoming_interviews, get_today_interviews, get_interview_stats,
    create_interview, schedule_interview, complete_interview,
    cancel_interview, mark_no_show, get_lead_interviews,
)
from schemas import TaskCreate, TaskUpdate, LeadUpdate
from models import Lead, LeadStatus, AdminAudit, EmailQueue
from services.ai_service import AIService
from services.analytics_service import AnalyticsService
from services.task_service import TaskService
from services.booking_service import BookingService

logger = logging.getLogger("st_core.dashboard")

router = APIRouter(prefix="/admin", tags=["Dashboard"])
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))
templates.env.filters["from_json"] = lambda v: json.loads(v) if v else []

PERIOD_MAP = {
    "today": (datetime.now(timezone.utc).strftime("%Y-%m-%d"), None),
    "7d": ((datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d"), None),
    "30d": ((datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d"), None),
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

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_counts = dict(
        db.query(Lead.downloaded_editorial, func.count(Lead.id))
        .filter(Lead.created_at >= today_start)
        .group_by(Lead.downloaded_editorial)
        .all()
    )
    today_leads = today_counts.get(False, 0) + today_counts.get(True, 0)
    today_downloads = today_counts.get(True, 0)

    status_counts = dict(
        db.query(Lead.status, func.count(Lead.id))
        .group_by(Lead.status)
        .all()
    )
    pipeline_value = sum(
        status_counts.get(s, 0) * v
        for s, v in {
            LeadStatus.NEW: 0, LeadStatus.CONTACTED: 100, LeadStatus.INTERVIEW: 300,
            LeadStatus.APPROVED: 500, LeadStatus.BOOKED: 1000, LeadStatus.COMPLETED: 1500,
        }.items()
    )

    high_priority = db.query(func.count(Lead.id)).filter(Lead.priority_score >= 50).scalar() or 0

    note_service = NoteService(db)
    recent_notes = note_service.get_recent_notes(limit=5)

    task_service = TaskService(db)
    today_tasks = task_service.get_today_tasks()
    overdue_tasks = task_service.get_overdue_tasks()
    unread_notifications = task_service.get_unread_notifications(limit=10)
    need_followup = status_counts.get(LeadStatus.CONTACTED, 0)
    need_approval = status_counts.get(LeadStatus.INTERVIEW, 0)
    need_booking = status_counts.get(LeadStatus.APPROVED, 0)

    bsvc = BookingService(db)
    booking_stats = bsvc.get_booking_stats()
    upcoming_retreats = bsvc.get_upcoming_retreats(limit=10)

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
            "today_leads": today_leads,
            "today_downloads": today_downloads,
            "pipeline_value": pipeline_value,
            "high_priority": high_priority,
            "recent_notes": recent_notes,
            "today_tasks": today_tasks,
            "overdue_tasks": overdue_tasks,
            "unread_notifications": unread_notifications,
            "need_followup": need_followup,
            "need_approval": need_approval,
            "need_booking": need_booking,
            "now": lambda: datetime.now(timezone.utc),
            "booking_stats": booking_stats,
            "upcoming_retreats": upcoming_retreats,
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
    crm_notes = NoteService(db).get_notes(lead_id)
    task_service = TaskService(db)
    lead_tasks = task_service.get_lead_tasks(lead_id)
    lead_reminders = task_service.get_lead_reminders(lead_id)
    bsvc = BookingService(db)
    lead_bookings = bsvc.get_lead_bookings(lead_id)
    return templates.TemplateResponse(
        request,
        "lead_detail.html",
        {"lead": lead, "events": events, "emails": lead_emails, "interviews": lead_interviews,
         "statuses": list(LeadStatus), "analysis": lead_analysis, "crm_notes": crm_notes,
         "tasks": lead_tasks, "reminders": lead_reminders, "bookings": lead_bookings},
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
    _log_audit(db, admin, "status_update", "lead", str(lead_id),
               f"Status changed to {status.value}")
    return RedirectResponse(url=f"/admin/lead/{lead_id}", status_code=303)

@router.post("/email/process")
def admin_process_email_queue(
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    count = EmailEngine(db).process_pending()
    _log_audit(db, admin, "email_process_queue", "email", None, f"Processed {count} emails")
    return RedirectResponse(url="/admin", status_code=303)

@router.post("/email/process/json")
def admin_process_email_queue_json(
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    count = EmailEngine(db).process_pending()
    _log_audit(db, admin, "email_process_queue", "email", None, f"Processed {count} emails")
    return {"success": True, "sent": count}

@router.post("/email/test")
def admin_test_email(
    test_email: str = Form(...),
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    result = EmailEngine(db).send_test_email(to=test_email)
    _log_audit(db, admin, "email_test", "email", None,
               f"Test email to {test_email}: {'OK' if result.get('success') else 'FAILED'}")
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

@router.post("/lead/{lead_id}/reactivate")
def admin_reactivate_lead(
    lead_id: int,
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    from services.automation_engine import AutomationEngine
    lead = LeadService.get_lead_by_id(db, lead_id)
    queued = AutomationEngine(db).on_campaign_reactivation(lead)
    db.commit()
    _log_audit(db, admin, "campaign_reactivation", "lead", str(lead_id),
               f"Queued {len(queued)} reactivation emails")
    return {"success": True, "queued": len(queued)}

@router.post("/campaign/reactivate-all")
def admin_reactivate_all(
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    from services.automation_engine import AutomationEngine
    leads = db.query(Lead).order_by(Lead.id).all()
    total = len(leads)
    queued = 0
    skipped = 0
    for lead in leads:
        existing = db.query(EmailQueue).filter(
            EmailQueue.lead_id == lead.id,
            EmailQueue.email_type == "editorial_reactivation",
            EmailQueue.status.in_(["PENDING", "PROCESSING"]),
        ).count()
        if existing:
            skipped += 1
            continue
        result = AutomationEngine(db).on_campaign_reactivation(lead)
        if result:
            queued += 1
        db.commit()
    _log_audit(db, admin, "campaign_reactivate_all", "lead", None,
               f"Queued {queued}, skipped {skipped} of {total} leads")
    return {"success": True, "total": total, "queued": queued, "skipped": skipped}

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


# ── Booking / Retreat Endpoints ─────────────────

@router.post("/retreat/create")
def admin_create_retreat(
    name: str = Form(...),
    description: str = Form(""),
    location: str = Form(""),
    start_date: Optional[str] = Form(None),
    end_date: Optional[str] = Form(None),
    max_participants: int = Form(10),
    price: float = Form(0.0),
    currency: str = Form("EUR"),
    status: str = Form("DRAFT"),
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    parsed_start = None
    parsed_end = None
    if start_date:
        try:
            parsed_start = datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            pass
    if end_date:
        try:
            parsed_end = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            pass
    bsvc = BookingService(db)
    retreat = bsvc.create_retreat(
        name=name, description=description or None,
        location=location or None, start_date=parsed_start,
        end_date=parsed_end, max_participants=max_participants,
        price=price, currency=currency, status=status,
    )
    _log_audit(db, admin, "retreat_created", "retreat", str(retreat.id), f"Created retreat: {name}")
    return RedirectResponse(url="/admin", status_code=303)


@router.post("/booking/create")
def admin_create_booking(
    lead_id: int = Form(...),
    retreat_id: int = Form(...),
    seats_reserved: int = Form(1),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    bsvc = BookingService(db)
    try:
        booking = bsvc.create_booking(
            lead_id=lead_id, retreat_id=retreat_id,
            seats_reserved=seats_reserved, notes=notes or None,
        )
        _log_audit(db, admin, "booking_created", "booking", str(booking.id),
                   f"Booking for retreat {retreat_id} (status: {booking.status.value})")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return RedirectResponse(url=f"/admin/lead/{lead_id}", status_code=303)


@router.post("/booking/{booking_id}/confirm")
def admin_confirm_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    bsvc = BookingService(db)
    booking = bsvc.confirm_booking(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found or cannot be confirmed")
    _log_audit(db, admin, "booking_confirmed", "booking", str(booking_id), "Booking confirmed")
    return RedirectResponse(url=f"/admin/lead/{booking.lead_id}", status_code=303)


@router.post("/booking/{booking_id}/cancel")
def admin_cancel_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    bsvc = BookingService(db)
    booking = bsvc.cancel_booking(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    _log_audit(db, admin, "booking_cancelled", "booking", str(booking_id), "Booking cancelled")
    return RedirectResponse(url=f"/admin/lead/{booking.lead_id}", status_code=303)


@router.post("/booking/{booking_id}/complete")
def admin_complete_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    bsvc = BookingService(db)
    booking = bsvc.complete_booking(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    _log_audit(db, admin, "booking_completed", "booking", str(booking_id), "Booking completed")
    return RedirectResponse(url=f"/admin/lead/{booking.lead_id}", status_code=303)


@router.post("/booking/{booking_id}/payment")
def admin_record_payment(
    booking_id: int,
    amount: float = Form(...),
    payment_type: str = Form("DEPOSIT"),
    payment_method: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    bsvc = BookingService(db)
    try:
        payment = bsvc.record_payment(
            booking_id=booking_id, amount=amount,
            payment_type=payment_type,
            payment_method=payment_method or None,
            notes=notes or None,
        )
        _log_audit(db, admin, "payment_recorded", "booking", str(booking_id),
                   f"{payment_type} payment of {amount}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    booking = bsvc.get_booking(booking_id)
    return RedirectResponse(url=f"/admin/lead/{booking.lead_id}", status_code=303)


@router.post("/booking/{booking_id}/participant/add")
def admin_add_participant(
    booking_id: int,
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(""),
    passport_number: str = Form(""),
    nationality: str = Form(""),
    date_of_birth: Optional[str] = Form(None),
    special_requirements: str = Form(""),
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    bsvc = BookingService(db)
    dob = None
    if date_of_birth:
        try:
            dob = datetime.strptime(date_of_birth, "%Y-%m-%d")
        except ValueError:
            pass
    bsvc.add_participant(
        booking_id=booking_id, first_name=first_name, last_name=last_name,
        email=email or None, passport_number=passport_number or None,
        nationality=nationality or None, date_of_birth=dob,
        special_requirements=special_requirements or None,
    )
    _log_audit(db, admin, "participant_added", "booking", str(booking_id),
               f"Added participant {first_name} {last_name}")
    booking = bsvc.get_booking(booking_id)
    return RedirectResponse(url=f"/admin/lead/{booking.lead_id}", status_code=303)


# ── Admin Audit Helper ──────────────────────────

def _log_audit(db: Session, admin_user: str, action: str, resource_type: str = None,
               resource_id: str = None, details: str = None, ip_address: str = None):
    entry = AdminAudit(
        admin_user=admin_user,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id else None,
        details=details,
        ip_address=ip_address,
    )
    db.add(entry)
    db.commit()


# ── CRM Notes ───────────────────────────────────

@router.post("/lead/{lead_id}/notes/add")
def admin_add_note(
    lead_id: int,
    content: str = Form(...),
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    NoteService(db).add_note(lead_id, content, created_by=admin)
    _log_audit(db, admin, "note_added", "lead", str(lead_id), f"Added CRM note")
    return RedirectResponse(url=f"/admin/lead/{lead_id}", status_code=303)

@router.get("/lead/{lead_id}/notes", response_class=JSONResponse)
def admin_get_notes(
    lead_id: int,
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    notes = NoteService(db).get_notes(lead_id)
    return [{"id": n.id, "content": n.content, "created_by": n.created_by,
             "created_at": n.created_at.isoformat()} for n in notes]


# ── Bulk Actions ────────────────────────────────

@router.post("/bulk")
def admin_bulk_action(
    lead_ids: str = Form(...),
    bulk_action: str = Form(...),
    bulk_status: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    try:
        ids = [int(x.strip()) for x in lead_ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid lead IDs")

    if not ids:
        raise HTTPException(status_code=400, detail="No lead IDs provided")

    if bulk_action == "status_update":
        if not bulk_status:
            raise HTTPException(status_code=400, detail="Status required for status_update")
        new_status = LeadStatus(bulk_status.upper())
        updated = 0
        for lid in ids:
            try:
                lead = LeadService.get_lead_by_id(db, lid)
                update = LeadUpdate(status=new_status)
                LeadService.update_lead(db, lid, update, created_by=admin)
                updated += 1
            except Exception as e:
                logger.warning("Bulk status update: lead %d failed: %s", lid, e)
        _log_audit(db, admin, "bulk_status_update", "lead", ",".join(str(i) for i in ids),
                   f"Set {updated}/{len(ids)} leads to {new_status.value}")
        return RedirectResponse(url="/admin", status_code=303)

    elif bulk_action == "delete":
        from models import Lead
        deleted = 0
        for lid in ids:
            try:
                lead = LeadService.get_lead_by_id(db, lid)
                db.delete(lead)
                db.commit()
                deleted += 1
            except Exception as e:
                logger.warning("Bulk delete: lead %d failed: %s", lid, e)
        _log_audit(db, admin, "bulk_delete", "lead", ",".join(str(i) for i in ids),
                   f"Deleted {deleted}/{len(ids)} leads")
        return RedirectResponse(url="/admin", status_code=303)

    raise HTTPException(status_code=400, detail="Unknown action")

@router.post("/bulk/export")
def admin_bulk_export(
    lead_ids: str = Form(...),
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    try:
        ids = [int(x.strip()) for x in lead_ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid lead IDs")
    leads = db.query(Lead).filter(Lead.id.in_(ids)).order_by(Lead.created_at.desc()).all()
    import csv, io
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "first_name", "last_name", "email", "country",
                     "language", "status", "source_page", "downloaded_editorial",
                     "priority_score", "created_at"])
    for l in leads:
        writer.writerow([
            l.id, l.first_name, l.last_name, l.email, l.country,
            l.language, l.status.value, l.source_page,
            "yes" if l.downloaded_editorial else "no",
            l.priority_score,
            l.created_at.isoformat() if l.created_at else "",
        ])
    _log_audit(db, admin, "bulk_export", "lead", ",".join(str(i) for i in ids),
               f"Exported {len(leads)} leads")
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=leads_bulk_export.csv"},
    )


# ── Task CRUD ────────────────────────────────────

@router.post("/task")
def admin_create_task(
    title: str = Form(...),
    lead_id: Optional[int] = Form(None),
    description: str = Form(""),
    priority: str = Form("normal"),
    due_at: Optional[str] = Form(None),
    assigned_to: str = Form(""),
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    parsed_due = None
    if due_at:
        try:
            parsed_due = datetime.strptime(due_at, "%Y-%m-%dT%H:%M")
        except ValueError:
            parsed_due = datetime.strptime(due_at, "%Y-%m-%d")
    svc = TaskService(db)
    task = svc.create_task(
        title=title, lead_id=lead_id, description=description or None,
        priority=priority, due_at=parsed_due,
        assigned_to=assigned_to or None, created_by=admin,
    )
    _log_audit(db, admin, "task_created", "task", str(task.id), f"Task: {title}")
    if lead_id:
        return RedirectResponse(url=f"/admin/lead/{lead_id}", status_code=303)
    return RedirectResponse(url="/admin", status_code=303)

@router.post("/task/{task_id}/update")
def admin_update_task(
    task_id: int,
    title: str = Form(None),
    description: str = Form(None),
    status: str = Form(None),
    priority: str = Form(None),
    due_at: Optional[str] = Form(None),
    assigned_to: str = Form(None),
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    svc = TaskService(db)
    task = svc.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    parsed_due = None
    if due_at:
        try:
            parsed_due = datetime.strptime(due_at, "%Y-%m-%dT%H:%M")
        except ValueError:
            parsed_due = datetime.strptime(due_at, "%Y-%m-%d")
    kwargs = {}
    if title: kwargs["title"] = title
    if description: kwargs["description"] = description
    if status: kwargs["status"] = status
    if priority: kwargs["priority"] = priority
    if parsed_due: kwargs["due_at"] = parsed_due
    if assigned_to: kwargs["assigned_to"] = assigned_to
    svc.update_task(task_id, **kwargs)
    _log_audit(db, admin, "task_updated", "task", str(task_id), f"Updated task {task_id}")
    if task.lead_id:
        return RedirectResponse(url=f"/admin/lead/{task.lead_id}", status_code=303)
    return RedirectResponse(url="/admin", status_code=303)

@router.post("/task/{task_id}/delete")
def admin_delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    svc = TaskService(db)
    task = svc.get_task(task_id)
    lead_id = task.lead_id if task else None
    svc.delete_task(task_id)
    _log_audit(db, admin, "task_deleted", "task", str(task_id), "Deleted task")
    if lead_id:
        return RedirectResponse(url=f"/admin/lead/{lead_id}", status_code=303)
    return RedirectResponse(url="/admin", status_code=303)

@router.post("/lead/{lead_id}/create-reminders")
def admin_create_lead_reminders(
    lead_id: int,
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    from models import Lead
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    svc = TaskService(db)
    svc.auto_create_followup_reminders(lead)
    _log_audit(db, admin, "reminders_created", "lead", str(lead_id), "Generated follow-up reminders")
    return RedirectResponse(url=f"/admin/lead/{lead_id}", status_code=303)


# ── Backup Management ───────────────────────────

@router.get("/backups", response_class=HTMLResponse)
def admin_backups(
    request: Request,
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    backup_service = BackupService()
    backups = backup_service.list_backups()
    return templates.TemplateResponse(
        request,
        "backups.html",
        {"backups": backups},
    )

@router.post("/backups/create")
def admin_create_backup(
    label: str = Form(""),
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    backup_service = BackupService()
    result = backup_service.create_backup(label=label)
    _log_audit(db, admin, "backup_create", "backup", result.get("path"),
               f"Created backup with label '{label}'")
    return RedirectResponse(url="/admin/backups", status_code=303)

@router.post("/backups/restore")
def admin_restore_backup(
    backup_name: str = Form(...),
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    backup_service = BackupService()
    result = backup_service.restore_backup(backup_name)
    _log_audit(db, admin, "backup_restore", "backup", backup_name,
               f"Restored backup: {result.get('success')}")
    return RedirectResponse(url="/admin/backups", status_code=303)

@router.post("/backups/delete")
def admin_delete_backup(
    backup_name: str = Form(...),
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    backup_service = BackupService()
    result = backup_service.delete_backup(backup_name)
    _log_audit(db, admin, "backup_delete", "backup", backup_name,
               f"Deleted backup: {result.get('success')}")
    return RedirectResponse(url="/admin/backups", status_code=303)


# ── Admin Audit Log ─────────────────────────────

@router.post("/reminders/process")
def admin_process_reminders(
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    svc = TaskService(db)
    active = svc.get_active_reminders()
    count = 0
    for r in active:
        svc.create_notification(
            lead_id=r.lead_id,
            title=r.title,
            message=r.message,
            notification_type="reminder",
        )
        svc.mark_reminder_notified(r.id)
        count += 1
    _log_audit(db, admin, "reminders_processed", "reminder", None, f"Processed {count} reminders")
    return RedirectResponse(url="/admin", status_code=303)

@router.post("/notification/{notification_id}/read")
def admin_mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    TaskService(db).mark_notification_read(notification_id)
    return RedirectResponse(url="/admin", status_code=303)


MAILCHIMP_COLUMN_MAP = {
    "Email Address": "email",
    "First Name": "first_name",
    "Last Name": "last_name",
    "Source": "source_page",
    "Campaign Name": "campaign",
    "Most Recent Subscriber Source": "referrer",
}

MAILCHIMP_EXTRA_FIELDS = [
    "Source", "Tags", "Outreach Stage", "Last Activity Date",
    "Member Rating", "Signup Source", "GDPR Status",
    "Most Recent Campaign", "Last Campaign Sent At",
]

def _normalize_row(row: dict, fmt: str) -> dict:
    if fmt == "mailchimp":
        out = {}
        extra = []
        for k, v in row.items():
            key = k.strip()
            val = v.strip() if v else ""
            if key in MAILCHIMP_COLUMN_MAP:
                out[MAILCHIMP_COLUMN_MAP[key]] = val
            elif key not in MAILCHIMP_EXTRA_FIELDS:
                if key.lower() in ("country", "language"):
                    out[key.lower()] = val
            if key in MAILCHIMP_EXTRA_FIELDS and val:
                extra.append(f"{key}: {val}")
        if extra:
            out["notes"] = "; ".join(extra)
        return out
    out = {}
    for k, v in row.items():
        key = k.strip().lower().replace(" ", "_")
        val = v.strip() if v else ""
        out[key] = val
    return out

@router.post("/import/leads")
def admin_import_leads(
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
    csv_data: str = Form(...),
    format: str = Form("generic"),
    strategy: str = Form("skip"),
):
    import csv, io, re
    from schemas import LeadCreate
    from services.lead_service import LeadService

    reader = csv.DictReader(io.StringIO(csv_data))
    imported = 0
    skipped = 0
    errors = []

    EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

    for idx, row in enumerate(reader):
        line = idx + 2
        try:
            data = _normalize_row(row, format)
            email = data.get("email", "").strip().lower()
            first_name = data.get("first_name", "").strip()
            last_name = data.get("last_name", "").strip()

            if not email or not EMAIL_RE.match(email):
                errors.append(f"Row {line}: invalid or missing email")
                continue
            if not first_name:
                errors.append(f"Row {line}: missing first name")
                continue

            if db.query(Lead).filter(Lead.email == email).first():
                if strategy == "skip":
                    skipped += 1
                    continue
                elif strategy == "error":
                    errors.append(f"Row {line}: duplicate email {email}")
                    continue

            lead_data = {
                "first_name": first_name,
                "last_name": last_name or first_name,
                "email": email,
            }
            for field in ("country", "language", "source_page", "campaign", "referrer",
                          "utm_source", "utm_medium", "utm_campaign", "notes"):
                if field in data and data[field]:
                    lead_data[field] = data[field]

            create = LeadCreate(**lead_data)
            LeadService.create_lead(db, create)
            imported += 1
        except Exception as e:
            errors.append(f"Row {line}: {e}")

    _log_audit(db, admin, "csv_import", "lead", None,
               f"Format={format} imported={imported} skipped={skipped} errors={len(errors)}")
    return {"imported": imported, "skipped": skipped, "errors": errors}


@router.post("/import/mailchimp")
def admin_import_mailchimp(
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
    csv_data: str = Form(...),
    strategy: str = Form("skip"),
):
    return admin_import_leads(db=db, admin=admin, csv_data=csv_data, format="mailchimp", strategy=strategy)


@router.get("/diagnostics")
def admin_diagnostics(
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    from database import check_database_health
    from core.version import VERSION, APP_NAME
    import os

    db_health = check_database_health()
    table_counts = {}
    try:
        from models import Lead, Task, Reminder, EmailQueue, Interview, LeadNote, AdminAudit, Retreat, Booking, Payment
        for model in (Lead, Task, Reminder, EmailQueue, Interview, LeadNote, AdminAudit, Retreat, Booking, Payment):
            table_counts[model.__tablename__] = db.query(model).count()
    except Exception as e:
        logger.warning("Diagnostics table count failed: %s", e)

    env_check = {
        "PROJECT_NAME": bool(os.getenv("PROJECT_NAME")),
        "DATABASE_URL": bool(os.getenv("DATABASE_URL")),
        "ADMIN_USERNAME": bool(os.getenv("ADMIN_USERNAME")),
        "SECRET_KEY_OK": len(os.getenv("SECRET_KEY", "")) >= 16,
    }

    return {
        "service": APP_NAME,
        "version": VERSION,
        "debug": bool(os.getenv("DEBUG", "")),
        "database": db_health,
        "table_counts": table_counts,
        "environment": env_check,
    }


@router.get("/audit-log", response_class=HTMLResponse)
def admin_audit_log(
    request: Request,
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    entries = db.query(AdminAudit).order_by(AdminAudit.created_at.desc()).limit(100).all()
    return templates.TemplateResponse(
        request,
        "audit_log.html",
        {"entries": entries},
    )
