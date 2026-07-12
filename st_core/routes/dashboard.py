import json
import os
from typing import Optional
from datetime import datetime, timedelta
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
from schemas import EmailQueueResponse, CandidateAnalysisResponse, LeadNoteCreate
from schemas import LeadUpdate, TaskCreate, TaskUpdate
from models import Lead, LeadStatus, AdminAudit
from services.ai_service import AIService
from services.analytics_service import AnalyticsService
from services.task_service import TaskService

router = APIRouter(prefix="/admin", tags=["Dashboard"])
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))
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

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_leads = db.query(func.count(Lead.id)).filter(Lead.created_at >= today_start).scalar() or 0
    today_downloads = db.query(func.count(Lead.id)).filter(
        Lead.downloaded_editorial == True, Lead.downloaded_at >= today_start
    ).scalar() or 0

    pipeline_value = 0
    stage_values = {LeadStatus.NEW: 0, LeadStatus.CONTACTED: 100, LeadStatus.INTERVIEW: 300,
                    LeadStatus.APPROVED: 500, LeadStatus.BOOKED: 1000, LeadStatus.COMPLETED: 1500}
    for status_enum, val in stage_values.items():
        count = db.query(func.count(Lead.id)).filter(Lead.status == status_enum).scalar() or 0
        pipeline_value += count * val

    high_priority = db.query(func.count(Lead.id)).filter(Lead.priority_score >= 50).scalar() or 0

    note_service = NoteService(db)
    recent_notes = note_service.get_recent_notes(limit=5)

    task_service = TaskService(db)
    today_tasks = task_service.get_today_tasks()
    overdue_tasks = task_service.get_overdue_tasks()
    unread_notifications = task_service.get_unread_notifications(limit=10)
    need_followup = db.query(Lead).filter(Lead.status == LeadStatus.CONTACTED).count()
    need_approval = db.query(Lead).filter(Lead.status == LeadStatus.INTERVIEW).count()
    need_booking = db.query(Lead).filter(Lead.status == LeadStatus.APPROVED).count()

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
    crm_notes = NoteService(db).get_notes(lead_id)
    task_service = TaskService(db)
    lead_tasks = task_service.get_lead_tasks(lead_id)
    lead_reminders = task_service.get_lead_reminders(lead_id)
    return templates.TemplateResponse(
        request,
        "lead_detail.html",
        {"lead": lead, "events": events, "emails": lead_emails, "interviews": lead_interviews,
         "statuses": list(LeadStatus), "analysis": lead_analysis, "crm_notes": crm_notes,
         "tasks": lead_tasks, "reminders": lead_reminders},
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
            except Exception:
                pass
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
            except Exception:
                pass
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


@router.post("/import/leads")
def admin_import_leads(
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
    csv_data: str = Form(...),
):
    import csv, io
    reader = csv.DictReader(io.StringIO(csv_data))
    imported = 0
    errors = []
    for row in reader:
        try:
            lead_data = {
                "first_name": row.get("first_name", "").strip(),
                "last_name": row.get("last_name", "").strip(),
                "email": row.get("email", "").strip(),
            }
            if not lead_data["first_name"] or not lead_data["email"]:
                errors.append(f"Row {imported + 2}: missing first_name or email")
                continue
            from schemas import LeadCreate
            from services.lead_service import LeadService
            create = LeadCreate(**lead_data)
            LeadService.create_lead(db, create)
            imported += 1
        except Exception as e:
            errors.append(f"Row {imported + 2}: {e}")
    _log_audit(db, admin, "csv_import", "lead", None, f"Imported {imported} leads with {len(errors)} errors")
    return {"imported": imported, "errors": errors}


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
        from models import Lead, Task, Reminder, EmailQueue, Interview, LeadNote, AdminAudit
        for model in (Lead, Task, Reminder, EmailQueue, Interview, LeadNote, AdminAudit):
            table_counts[model.__tablename__] = db.query(model).count()
    except Exception:
        pass

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
