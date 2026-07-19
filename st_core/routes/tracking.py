import logging
from datetime import datetime, timezone
from urllib.parse import unquote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from dependencies import get_db
from models import EmailQueue, EmailStatus, Lead

logger = logging.getLogger("st_core.tracking")

router = APIRouter(tags=["Tracking"])

TRANSPARENT_PIXEL = (
    b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00"
    b"\xff\xff\xff\x00\x00\x00\x21\xf9\x04\x00\x00\x00\x00"
    b"\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02"
    b"\x44\x01\x00\x3b"
)


@router.get("/track/open/{queue_id}.png")
def track_open(queue_id: int, db: Session = Depends(get_db)):
    entry = db.query(EmailQueue).filter(EmailQueue.id == queue_id).first()
    if entry:
        lead = db.query(Lead).filter(Lead.id == entry.lead_id).first()
        if lead:
            lead.email_opened = True
            lead.opened_at = datetime.now(timezone.utc)
            db.commit()
            logger.info("TRACK open: queue=%d lead=%d", queue_id, lead.id)
    return Response(content=TRANSPARENT_PIXEL, media_type="image/gif")


@router.get("/track/click/{queue_id}")
def track_click(queue_id: int, request: Request, db: Session = Depends(get_db)):
    entry = db.query(EmailQueue).filter(EmailQueue.id == queue_id).first()
    redirect_url = None
    if entry:
        lead = db.query(Lead).filter(Lead.id == entry.lead_id).first()
        if lead:
            lead.email_clicked = True
            lead.clicked_at = datetime.now(timezone.utc)
            db.commit()
            logger.info("TRACK click: queue=%d lead=%d", queue_id, lead.id)
    target = request.query_params.get("url", "")
    if target:
        redirect_url = unquote(target)
    if not redirect_url and entry:
        import json
        payload = json.loads(entry.payload_json) if entry.payload_json else {}
        redirect_url = payload.get("download_url", "")
    if not redirect_url:
        redirect_url = str(request.base_url)
    return RedirectResponse(url=redirect_url, status_code=302)
