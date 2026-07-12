import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from database import engine, Base, SessionLocal
from routes import leads, dashboard, health, download, system
from core.error_handlers import register_error_handlers
from core.logger import setup_logging
from config import settings

logger = logging.getLogger("st_core")


def _validate_startup():
    issues = []

    required_env = ["PROJECT_NAME", "DATABASE_URL", "ADMIN_USERNAME", "ADMIN_PASSWORD", "SECRET_KEY"]
    for var in required_env:
        val = os.getenv(var, "")
        if not val:
            issues.append(f"Missing environment variable: {var}")

    if len(os.getenv("SECRET_KEY", "")) < 16:
        issues.append("SECRET_KEY is too short (min 16 characters)")

    insecure = ("change_me", "dev-secret-key-not-for-production", "CHANGE_THIS")
    if os.getenv("ADMIN_PASSWORD", "") in insecure:
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
    Base.metadata.create_all(bind=engine)
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
    logger.info("ST CORE ready")
    yield
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
        origin = request.headers.get("origin") or ""
        referer = request.headers.get("referer") or ""
        allowed_origins = {
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            request.base_url.rstrip("/"),
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
app.include_router(dashboard.router)
app.include_router(download.router)
app.include_router(system.router)
