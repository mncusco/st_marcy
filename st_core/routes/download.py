import os
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session
from dependencies import get_db
from services.lead_service import LeadService
from config import settings

router = APIRouter(tags=["Download"])

@router.get("/download/{token}")
def download_editorial(token: str, db: Session = Depends(get_db)):
    lead = LeadService.mark_downloaded_by_token(db, token)
    lang = lead.language or "en"
    filename = settings.EDITORIAL_FILES.get(lang, settings.EDITORIAL_FILES["en"])
    filepath = os.path.join(settings.EDITORIAL_FILES_DIR, filename)
    if not os.path.exists(filepath):
        return HTMLResponse(
            content=f"<html><body style='font-family:Georgia;background:#f5f2ec;padding:40px;text-align:center;'><h2 style='color:#b89a5a;'>Editorial not available</h2><p>Please contact us at {settings.CONTACT_EMAIL}</p></body></html>",
            status_code=404,
        )
    return FileResponse(
        path=filepath,
        filename=filename,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
