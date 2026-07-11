from fastapi import APIRouter

router = APIRouter(tags=["System"])

@router.get("/health")
def health_check():
    return {"status": "ok", "service": "ST_CORE"}
