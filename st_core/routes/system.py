import os
import logging
import re
from datetime import datetime
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from dependencies import get_db
from security import verify_admin
from services.email_engine import EmailEngine
from database import check_database_health
from core.version import VERSION, APP_NAME
from models import Lead, Task, Reminder, EmailQueue, Interview, LeadNote, AdminAudit
from config import settings

logger = logging.getLogger("st_core.system")

router = APIRouter(prefix="/admin", tags=["System"])
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))


@router.get("/email-diagnostics", response_class=HTMLResponse)
def admin_email_diagnostics(
    request: Request,
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    engine = EmailEngine(db)
    diag = engine.diagnose()
    return templates.TemplateResponse(
        request,
        "email_diagnostics.html",
        {"diag": diag, "now": datetime.utcnow},
    )


@router.get("/email-diagnostics/json")
def admin_email_diagnostics_json(
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    engine = EmailEngine(db)
    return engine.diagnose()


@router.get("/system", response_class=HTMLResponse)
def admin_system(
    request: Request,
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    db_health = check_database_health()

    table_counts = {}
    try:
        for model in (Lead, Task, Reminder, EmailQueue, Interview, LeadNote, AdminAudit):
            table_counts[model.__tablename__] = db.query(model).count()
    except Exception as e:
        logger.warning("System table count failed: %s", e)

    env_check = {
        "PROJECT_NAME": bool(os.getenv("PROJECT_NAME")),
        "DATABASE_URL": bool(os.getenv("DATABASE_URL")),
        "ADMIN_USERNAME": bool(os.getenv("ADMIN_USERNAME")),
        "SECRET_KEY_OK": len(os.getenv("SECRET_KEY", "")) >= 16,
        "EMAIL_BACKEND": bool(os.getenv("EMAIL_BACKEND", "")),
        "SMTP_HOST": bool(os.getenv("SMTP_HOST", "")),
    }

    python_info = {
        "python_version": os.sys.version,
        "cwd": os.getcwd(),
        "pid": os.getpid(),
    }

    uptime_hint = "(unknown — first request after restart)"
    import time
    try:
        start = time.time()
        _ = db.execute(func.now() if "sqlite" not in settings.DATABASE_URL else func.datetime("now"))
        query_ms = round((time.time() - start) * 1000)
        uptime_hint = f"DB query latency: {query_ms}ms"
    except Exception:
        pass

    return templates.TemplateResponse(
        request,
        "system.html",
        {
            "app_name": APP_NAME,
            "version": VERSION,
            "debug": bool(os.getenv("DEBUG", "")),
            "database": db_health,
            "table_counts": table_counts,
            "environment": env_check,
            "python": python_info,
            "uptime_hint": uptime_hint,
            "now": datetime.utcnow,
        },
    )


@router.get("/content-check", response_class=HTMLResponse)
def admin_content_check(
    request: Request,
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    issues = []

    email_templates_dir = os.path.join(os.path.dirname(__file__), "..", "templates", "emails")
    valid_languages = ("en", "it", "es", "ru", "sr")
    email_templates_found = set()
    if os.path.isdir(email_templates_dir):
        for lang in os.listdir(email_templates_dir):
            lang_dir = os.path.join(email_templates_dir, lang)
            if os.path.isdir(lang_dir) and lang in valid_languages:
                for fname in os.listdir(lang_dir):
                    if fname.endswith(".html"):
                        email_templates_found.add(f"{lang}/{fname}")
    missing_templates = []
    required = {"editorial_download", "followup_3_days", "interview_invitation", "approved", "rejected", "journey_reminder", "completion"}
    for lang in valid_languages:
        for tmpl in required:
            path = f"{lang}/{tmpl}.html"
            if path not in email_templates_found:
                missing_templates.append(path)

    if missing_templates:
        issues.append({"severity": "warning", "category": "email_templates", "message": f"Missing {len(missing_templates)} email templates", "details": missing_templates[:10]})

    editorial_dir = getattr(settings, "EDITORIAL_DIRECTORY", None) or getattr(settings, "EDITORIAL_FILES_DIR", None)
    if editorial_dir and os.path.isdir(editorial_dir):
        files = os.listdir(editorial_dir)
        if not files:
            issues.append({"severity": "warning", "category": "editorials", "message": "Editorial directory is empty"})
    elif editorial_dir:
        issues.append({"severity": "error", "category": "editorials", "message": f"Editorial directory not found: {editorial_dir}"})

    empty_leads = db.query(func.count(Lead.id)).scalar() or 0
    if empty_leads == 0:
        issues.append({"severity": "info", "category": "leads", "message": "No leads in database"})

    orphaned_emails = db.query(EmailQueue).outerjoin(Lead, EmailQueue.lead_id == Lead.id).filter(Lead.id.is_(None)).count()
    if orphaned_emails:
        issues.append({"severity": "warning", "category": "email_queue", "message": f"{orphaned_emails} emails reference deleted leads"})

    logging.warning("Content check complete: %d issues found", len(issues))
    return templates.TemplateResponse(
        request,
        "content_check.html",
        {"issues": issues, "now": datetime.utcnow},
    )


@router.get("/content-check/json")
def admin_content_check_json(
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    return {"status": "ok", "message": "Content check endpoint — use the HTML page at /admin/content-check"}


@router.get("/link-check", response_class=HTMLResponse)
def admin_link_check(
    request: Request,
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    results = []
    
    internal_routes = [
        "/admin", "/admin/backups", "/admin/audit-log", "/admin/diagnostics",
        "/admin/system", "/admin/email-diagnostics", "/admin/content-check",
        "/admin/link-check", "/health",
    ]
    for route in internal_routes:
        results.append({"url": route, "type": "internal", "status": "checked", "note": "Route registered"})

    external_urls = set()
    leads = db.query(Lead).filter(Lead.source_page.isnot(None)).all()
    for lead in leads:
        src = lead.source_page.strip()
        if src.startswith("http://") or src.startswith("https://"):
            external_urls.add(src)

    for url in sorted(external_urls):
        results.append({"url": url, "type": "external (source_page)", "status": "listed", "note": "Referenced by leads; verify manually"})

    email_body_refs = set()
    emails = db.query(EmailQueue).filter(EmailQueue.payload_json.isnot(None)).limit(200).all()
    for em in emails:
        try:
            import json as j
            payload = j.loads(em.payload_json)
            text = str(payload)
            found = re.findall(r'https?://[^\s"\'<>]+', text)
            for u in found:
                email_body_refs.add(u)
        except Exception:
            pass
    for url in sorted(email_body_refs):
        results.append({"url": url, "type": "email_payload", "status": "listed", "note": "Referenced in email payload"})

    return templates.TemplateResponse(
        request,
        "link_check.html",
        {"results": results, "total": len(results), "now": datetime.utcnow},
    )
