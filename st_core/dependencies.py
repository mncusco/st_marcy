import logging
from database import SessionLocal, check_database_health

logger = logging.getLogger("st_core.dependencies")


def get_db():
    health = check_database_health()
    if health["status"] != "ok":
        logger.critical("Database unreachable: %s", health.get("database"))
        raise RuntimeError("Database unavailable")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
