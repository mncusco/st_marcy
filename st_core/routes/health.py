from fastapi import APIRouter
from core.version import VERSION, APP_NAME
from database import check_database_health

router = APIRouter(tags=["System"])


@router.get("/health")
@router.get("/api/health")
def health_check():
    db_health = check_database_health()
    return {
        "status": "ok" if db_health["status"] == "ok" else "degraded",
        "service": APP_NAME,
        "version": VERSION,
        "database": db_health["status"],
    }
