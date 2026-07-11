import json
import logging
from datetime import datetime, date
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import desc, and_

from models import Interview, InterviewStatus, LeadEvent, Lead
from fastapi import HTTPException

logger = logging.getLogger("st_core.interview_service")


def _create_event(db: Session, lead_id: int, event_type: str, title: str,
                  description: str = None, metadata_json: dict = None,
                  created_by: str = None):
    event = LeadEvent(
        lead_id=lead_id,
        event_type=event_type,
        title=title,
        description=description,
        metadata_json=json.dumps(metadata_json) if metadata_json else None,
        created_by=created_by,
    )
    db.add(event)
    db.flush()
    return event


def _get_interview_or_404(db: Session, interview_id: int) -> Interview:
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    return interview


def create_interview(db: Session, lead_id: int, created_by: str = None) -> Interview:
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    interview = Interview(lead_id=lead_id, status=InterviewStatus.REQUESTED)
    db.add(interview)
    db.flush()

    _create_event(db, lead_id, "interview_requested",
                  "Interview requested",
                  "Interview has been requested for this lead",
                  created_by=created_by)
    logger.info("Created interview request for lead %d (interview id=%d)", lead_id, interview.id)
    return interview


def schedule_interview(db: Session, interview_id: int, scheduled_at: datetime,
                       duration_minutes: int = 30, meeting_url: str = None,
                       created_by: str = None) -> Interview:
    interview = _get_interview_or_404(db, interview_id)
    interview.scheduled_at = scheduled_at
    interview.duration_minutes = duration_minutes
    interview.meeting_url = meeting_url
    interview.status = InterviewStatus.SCHEDULED
    db.flush()

    _create_event(db, interview.lead_id, "interview_scheduled",
                  "Interview scheduled",
                  f"Scheduled at {scheduled_at.strftime('%d %b %Y, %H:%M')} for {duration_minutes} min",
                  {"scheduled_at": scheduled_at.isoformat(), "duration_minutes": duration_minutes},
                  created_by=created_by)
    logger.info("Scheduled interview %d for lead %d", interview.id, interview.lead_id)
    return interview


def complete_interview(db: Session, interview_id: int, notes: str = None,
                       created_by: str = None) -> Interview:
    interview = _get_interview_or_404(db, interview_id)
    interview.status = InterviewStatus.COMPLETED
    if notes:
        interview.notes = notes
    db.flush()

    _create_event(db, interview.lead_id, "interview_completed",
                  "Interview completed",
                  notes or "Interview marked as completed",
                  created_by=created_by)
    logger.info("Completed interview %d for lead %d", interview.id, interview.lead_id)
    return interview


def cancel_interview(db: Session, interview_id: int, notes: str = None,
                     created_by: str = None) -> Interview:
    interview = _get_interview_or_404(db, interview_id)
    interview.status = InterviewStatus.CANCELLED
    if notes:
        interview.notes = notes
    db.flush()

    _create_event(db, interview.lead_id, "interview_cancelled",
                  "Interview cancelled",
                  notes or "Interview cancelled",
                  created_by=created_by)
    logger.info("Cancelled interview %d for lead %d", interview.id, interview.lead_id)
    return interview


def mark_no_show(db: Session, interview_id: int, notes: str = None,
                 created_by: str = None) -> Interview:
    interview = _get_interview_or_404(db, interview_id)
    interview.status = InterviewStatus.NO_SHOW
    if notes:
        interview.notes = notes
    db.flush()

    _create_event(db, interview.lead_id, "interview_no_show",
                  "Interview no-show",
                  notes or "Lead did not attend interview",
                  created_by=created_by)
    logger.info("Marked no-show for interview %d (lead %d)", interview.id, interview.lead_id)
    return interview


def get_lead_interviews(db: Session, lead_id: int):
    return db.query(Interview).filter(
        Interview.lead_id == lead_id
    ).order_by(desc(Interview.created_at)).all()


def get_upcoming_interviews(db: Session, limit: int = 10):
    now = datetime.utcnow()
    return db.query(Interview, Lead.first_name, Lead.last_name, Lead.email).join(
        Lead, Interview.lead_id == Lead.id
    ).filter(
        Interview.status == InterviewStatus.SCHEDULED,
        Interview.scheduled_at >= now,
    ).order_by(Interview.scheduled_at.asc()).limit(limit).all()


def get_today_interviews(db: Session):
    today_start = datetime.combine(date.today(), datetime.min.time())
    today_end = datetime.combine(date.today(), datetime.max.time())
    return db.query(Interview, Lead.first_name, Lead.last_name, Lead.email).join(
        Lead, Interview.lead_id == Lead.id
    ).filter(
        Interview.status.in_([InterviewStatus.SCHEDULED, InterviewStatus.REQUESTED]),
        Interview.scheduled_at >= today_start,
        Interview.scheduled_at <= today_end,
    ).order_by(Interview.scheduled_at.asc()).all()


def get_interview_stats(db: Session) -> dict:
    total = db.query(Interview).count()
    requested = db.query(Interview).filter(Interview.status == InterviewStatus.REQUESTED).count()
    scheduled = db.query(Interview).filter(Interview.status == InterviewStatus.SCHEDULED).count()
    completed = db.query(Interview).filter(Interview.status == InterviewStatus.COMPLETED).count()
    cancelled = db.query(Interview).filter(Interview.status == InterviewStatus.CANCELLED).count()
    no_show = db.query(Interview).filter(Interview.status == InterviewStatus.NO_SHOW).count()
    return {
        "total": total,
        "requested": requested,
        "scheduled": scheduled,
        "completed": completed,
        "cancelled": cancelled,
        "no_show": no_show,
    }
