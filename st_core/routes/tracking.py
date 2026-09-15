import logging
from datetime import datetime, timezone
from urllib.parse import unquote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from dependencies import get_db
from core.tracking import client_ip
from models import ClickEvent, EmailQueue, EmailStatus, Lead, LeadStatus, OpenEvent
from services.lead_service import advance_funnel_status

logger = logging.getLogger("st_core.tracking")

router = APIRouter(tags=["Tracking"])

TRANSPARENT_PIXEL = (
    b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00"
    b"\xff\xff\xff\x00\x00\x00\x21\xf9\x04\x00\x00\x00\x00"
    b"\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02"
    b"\x44\x01\x00\x3b"
)


@router.get("/track/open/{queue_id}.png")
def track_open(queue_id: int, request: Request, db: Session = Depends(get_db)):
    entry = db.query(EmailQueue).filter(EmailQueue.id == queue_id).first()
    if entry:
        lead = db.query(Lead).filter(Lead.id == entry.lead_id).first()
        if lead:
            if not lead.email_opened:
                lead.email_opened = True
            if lead.opened_at is None:
                lead.opened_at = datetime.now(timezone.utc)
            db.add(OpenEvent(
                lead_id=lead.id,
                queue_id=queue_id,
                ip_address=client_ip(request),
                user_agent=request.headers.get("user-agent"),
                referrer=request.headers.get("referer"),
            ))
            advance_funnel_status(db, lead, LeadStatus.OPENED)
            db.commit()
            logger.info("TRACK open: queue=%d lead=%d", queue_id, lead.id)
    return Response(content=TRANSPARENT_PIXEL, media_type="image/gif")


@router.get("/track/click/{queue_id}")
def track_click(queue_id: int, request: Request, db: Session = Depends(get_db)):
    entry = db.query(EmailQueue).filter(EmailQueue.id == queue_id).first()
    redirect_url = None
    target = request.query_params.get("url", "")
    if target:
        redirect_url = unquote(target)
    if entry:
        import json
        payload = json.loads(entry.payload_json) if entry.payload_json else {}
        if not redirect_url:
            redirect_url = payload.get("download_url", "")
        lead = db.query(Lead).filter(Lead.id == entry.lead_id).first()
        if lead:
            if not lead.email_clicked:
                lead.email_clicked = True
            if lead.clicked_at is None:
                lead.clicked_at = datetime.now(timezone.utc)
            final_url = redirect_url or ""
            db.add(ClickEvent(
                lead_id=lead.id,
                queue_id=queue_id,
                url=final_url[:1024],
                is_download="/download/" in final_url,
                ip_address=client_ip(request),
                user_agent=request.headers.get("user-agent"),
                referrer=request.headers.get("referer"),
            ))
            advance_funnel_status(db, lead, LeadStatus.CLICKED)
            db.commit()
            logger.info(
                "TRACK click: queue=%d lead=%d is_download=%s",
                queue_id, lead.id, "/download/" in final_url,
            )
    if not redirect_url:
        redirect_url = str(request.base_url)
    return RedirectResponse(url=redirect_url, status_code=302)
