import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from database import engine, Base, SessionLocal
from routes import leads, collect, dashboard, health, download, system, tracking
from core.error_handlers import register_error_handlers
from core.logger import setup_logging
from config import settings

logger = logging.getLogger("st_core")


def _migrate_schema():
    from sqlalchemy import text as _text
    from database import engine as _engine
    dialect = _engine.dialect.name
    try:
        with _engine.connect() as conn:
            if dialect == "sqlite":
                result = conn.execute(_text("PRAGMA table_info(leads)")).fetchall()
                cols = {row[1] for row in result}
                if "campaign_sent_at" not in cols:
                    conn.execute(_text("ALTER TABLE leads ADD COLUMN campaign_sent_at TIMESTAMP"))
                    conn.execute(_text("ALTER TABLE leads ADD COLUMN email_opened BOOLEAN DEFAULT 0"))
                    conn.execute(_text("ALTER TABLE leads ADD COLUMN email_clicked BOOLEAN DEFAULT 0"))
                    logger.info("Schema migration: added campaign tracking columns to leads (SQLite)")
                for col, dtype in [("source", "VARCHAR(50)"), ("device_type", "VARCHAR(20)"),
                                   ("browser", "VARCHAR(50)"), ("os_name", "VARCHAR(50)")]:
                    if col not in cols:
                        conn.execute(_text(f"ALTER TABLE leads ADD COLUMN {col} {dtype}"))
                        logger.info("Schema migration: added %s to leads (SQLite)", col)

                eq_result = conn.execute(_text("PRAGMA table_info(email_queue)")).fetchall()
                eq_cols = {row[1] for row in eq_result}
                for col, dtype in [("provider_message_id", "VARCHAR(128)"),
                                   ("last_provider_response", "TEXT"),
                                   ("last_attempt_at", "TIMESTAMP")]:
                    if col not in eq_cols:
                        conn.execute(_text(f"ALTER TABLE email_queue ADD COLUMN {col} {dtype}"))
                        logger.info("Schema migration: added %s to email_queue (SQLite)", col)

                conn.execute(_text("DROP INDEX IF EXISTS uq_email_queue_active_lead_type"))
                conn.execute(_text(
                    "CREATE UNIQUE INDEX uq_email_queue_active_lead_type "
                    "ON email_queue (lead_id, email_type) "
                    "WHERE status IN ('PENDING', 'PROCESSING', 'RETRY')"
                ))
                logger.info("Schema migration: rebuilt email_queue unique index (SQLite)")
            else:
                for col, dtype in [("campaign_sent_at", "TIMESTAMP"), ("email_opened", "BOOLEAN DEFAULT FALSE"), ("email_clicked", "BOOLEAN DEFAULT FALSE"), ("source", "VARCHAR(50)"), ("device_type", "VARCHAR(20)"), ("browser", "VARCHAR(50)"), ("os_name", "VARCHAR(50)")]:
                    try:
                        conn.execute(_text(f"ALTER TABLE leads ADD COLUMN IF NOT EXISTS {col} {dtype}"))
                    except Exception:
                        conn.execute(_text(f"ALTER TABLE leads ADD COLUMN {col} {dtype}"))
                for col, dtype in [("provider_message_id", "VARCHAR(128)"),
                                   ("last_provider_response", "TEXT"),
                                   ("last_attempt_at", "TIMESTAMP")]:
                    try:
                        conn.execute(_text(f"ALTER TABLE email_queue ADD COLUMN IF NOT EXISTS {col} {dtype}"))
                    except Exception:
                        conn.execute(_text(f"ALTER TABLE email_queue ADD COLUMN {col} {dtype}"))

                has_retry = conn.execute(_text(
                    "SELECT 1 FROM pg_enum WHERE enumtypid = 'emailstatus'::regtype AND enumlabel = 'RETRY'"
                )).fetchone()
                if not has_retry:
                    try:
                        conn.execute(_text("ALTER TYPE emailstatus ADD VALUE IF NOT EXISTS 'RETRY'"))
                        logger.info("Schema migration: added EmailStatus.RETRY to emailstatus enum")
                    except Exception:
                        conn.execute(_text("ALTER TYPE emailstatus ADD VALUE 'RETRY'"))
                        logger.info("Schema migration: added EmailStatus.RETRY to emailstatus enum (fallback)")

                from models import LeadStatus as _LeadStatus
                existing_lead = {
                    row[0] for row in conn.execute(_text(
                        "SELECT enumlabel FROM pg_enum WHERE enumtypid = 'leadstatus'::regtype"
                    )).fetchall()
                }
                expected_lead = {s.value for s in _LeadStatus}
                missing_lead = sorted(expected_lead - existing_lead)
                for label in missing_lead:
                    try:
                        conn.execute(_text(f"ALTER TYPE leadstatus ADD VALUE IF NOT EXISTS '{label}'"))
                        logger.info("Schema migration: added LeadStatus.%s to leadstatus enum", label)
                    except Exception:
                        conn.execute(_text(f"ALTER TYPE leadstatus ADD VALUE '{label}'"))
                        logger.info("Schema migration: added LeadStatus.%s to leadstatus enum (fallback)", label)

                # Postgres: i nuovi valori di enum devono essere COMMITTATI prima di
                # poter essere usati nelle query della stessa connessione.
                conn.commit()

                conn.execute(_text("DROP INDEX IF EXISTS uq_email_queue_active_lead_type"))
                conn.execute(_text(
                    "CREATE UNIQUE INDEX uq_email_queue_active_lead_type "
                    "ON email_queue (lead_id, email_type) "
                    "WHERE status IN ('PENDING', 'PROCESSING', 'RETRY')"
                ))
                logger.info("Schema migration: rebuilt email_queue unique index")
            conn.commit()
    except Exception as e:
        logger.warning("Schema migration skipped: %s", e)


def _validate_pdf_files():
    issues = []
    import os
    min_size = 1024
    pdf_dir = settings.EDITORIAL_FILES_DIR
    for lang, fname in settings.EDITORIAL_FILES.items():
        path = os.path.join(pdf_dir, fname)
        if not os.path.exists(path):
            issues.append(f"PDF missing: {fname} for language {lang}")
        else:
            size = os.path.getsize(path)
            if size < min_size:
                issues.append(f"PDF too small ({size} bytes, expected >= {min_size}): {fname} for language {lang}")
    for issue in issues:
        logger.warning("PDF VALIDATION: %s", issue)
    return issues


def _validate_startup():
    issues = []

    required_env = ["PROJECT_NAME", "DATABASE_URL", "ADMIN_USERNAME", "ADMIN_PASSWORD", "SECRET_KEY"]
    for var in required_env:
        val = getattr(settings, var, "")
        if not val:
            issues.append(f"Missing environment variable: {var}")

    sk = getattr(settings, "SECRET_KEY", "")
    if len(sk) < 16:
        issues.append("SECRET_KEY is too short (min 16 characters)")

    insecure = ("change_me", "dev-secret-key-not-for-production", "CHANGE_THIS")
    if getattr(settings, "ADMIN_PASSWORD", "") in insecure:
        issues.append("ADMIN_PASSWORD is set to an insecure default value")

    _dirs = ["./database", "./uploads", settings.EDITORIAL_FILES_DIR, "./logs", settings.EDITORIAL_DIRECTORY]
    for d in _dirs:
        try:
            os.makedirs(d, exist_ok=True)
        except Exception as e:
            issues.append(f"Cannot create directory {d}: {e}")

    db_ok = False
    try:
        from database import check_database_health
        db_health = check_database_health()
        db_ok = db_health["status"] == "ok"
        if not db_ok:
            issues.append(f"Database health check failed: {db_health}")
    except Exception as e:
        issues.append(f"Database connection failed: {e}")

    for issue in issues:
        logger.warning("STARTUP VALIDATION: %s", issue)

    if not db_ok:
        logger.warning("Database unavailable - some features may be degraded")

    return issues


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("ST CORE starting")
    _validate_startup()
    _validate_pdf_files()
    Base.metadata.create_all(bind=engine)
    _migrate_schema()
    db = SessionLocal()
    try:
        from services.editorial_service import seed_editorials
        seed_editorials(db)
        db.commit()
    except Exception as e:
        logger.warning("Seed editorials failed: %s", e)
        db.rollback()
    finally:
        db.close()
    if settings.EMAIL_BACKEND.lower() in ("smtp", "resend", "sendgrid"):
        from worker.email_worker import start_worker
        start_worker()
    else:
        logger.info("Email backend is '%s' — worker not started", settings.EMAIL_BACKEND)
    logger.info("ST CORE ready")
    yield
    from worker.email_worker import stop_worker
    stop_worker()
    logger.info("ST CORE shutting down")


app = FastAPI(
    title="ST CORE",
    description="Shamanic Travels Backend Core",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if os.getenv("DEBUG", "").lower() in ("1", "true") else None,
    redoc_url=None,
)

register_error_handlers(app)


@app.middleware("http")
async def csrf_middleware(request: Request, call_next):
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and request.url.path.startswith("/admin") and not settings.DEBUG:
        authorization = request.headers.get("authorization") or ""
        if authorization.startswith("Basic "):
            return await call_next(request)
        origin = request.headers.get("origin") or ""
        referer = request.headers.get("referer") or ""
        allowed_origins = {
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            str(request.base_url).rstrip("/"),
        }
        ok = False
        if origin and origin in allowed_origins:
            ok = True
        if referer:
            ref_origin = "/".join(referer.rstrip("/").split("/")[:3])
            if ref_origin in allowed_origins:
                ok = True
        if not ok:
            logger.warning("CSRF check failed: origin=%s referer=%s", origin, referer)
            return JSONResponse(status_code=403, content={"detail": "CSRF check failed"})
    return await call_next(request)


if not os.path.exists("static"):
    os.makedirs("static")
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(health.router)
app.include_router(leads.router)
app.include_router(collect.router)
app.include_router(dashboard.router)
app.include_router(download.router)
app.include_router(system.router)
app.include_router(tracking.router)
