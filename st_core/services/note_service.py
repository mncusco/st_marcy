from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from models import LeadNote, Lead, LeadEvent


class NoteService:
    def __init__(self, db: Session):
        self.db = db

    def add_note(self, lead_id: int, content: str, created_by: str = None) -> LeadNote:
        lead = self.db.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            raise ValueError("Lead not found")

        note = LeadNote(lead_id=lead_id, content=content, created_by=created_by)
        self.db.add(note)
        self.db.flush()

        event = LeadEvent(
            lead_id=lead_id,
            event_type="note_added",
            title="CRM note added",
            description=content[:200],
            created_by=created_by,
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(note)
        return note

    def get_notes(self, lead_id: int, limit: int = 50) -> list[LeadNote]:
        return (
            self.db.query(LeadNote)
            .filter(LeadNote.lead_id == lead_id)
            .order_by(desc(LeadNote.created_at))
            .limit(limit)
            .all()
        )

    def get_recent_notes(self, limit: int = 10) -> list[dict]:
        rows = (
            self.db.query(LeadNote, Lead.first_name, Lead.last_name, Lead.email)
            .join(Lead, LeadNote.lead_id == Lead.id)
            .order_by(desc(LeadNote.created_at))
            .limit(limit)
            .all()
        )
        return [
            {
                "id": n.id,
                "lead_id": n.lead_id,
                "content": n.content,
                "created_by": n.created_by,
                "created_at": n.created_at,
                "lead_name": f"{fn} {ln}",
                "lead_email": email,
            }
            for n, fn, ln, email in rows
        ]
