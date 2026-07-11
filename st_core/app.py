import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from database import engine, Base, SessionLocal
from routes import leads, dashboard, health, download
from core.error_handlers import register_error_handlers
from core.logger import setup_logging
from config import settings

logger = logging.getLogger("st_core")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("ST CORE starting")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        from services.editorial_service import seed_editorials
        seed_editorials(db)
        db.commit()
    except Exception:
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
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and request.url.path.startswith("/admin"):
        if not settings.DEBUG:
            origin = request.headers.get("origin") or ""
            referer = request.headers.get("referer") or ""
            if origin or referer:
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
                    return JSONResponse(status_code=403, content={"detail": "CSRF check failed"})
    return await call_next(request)


if not os.path.exists("static"):
    os.makedirs("static")
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(health.router)
app.include_router(leads.router)
app.include_router(dashboard.router)
app.include_router(download.router)
