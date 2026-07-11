from sqlalchemy.orm import Session
from sqlalchemy import desc
from fastapi import HTTPException
from models import Lead, LeadStatus
from schemas import LeadCreate, LeadUpdate

class LeadService:
    @staticmethod
    def create_lead(db: Session, lead_data: LeadCreate) -> Lead:
        if db.query(Lead).filter(Lead.email == lead_data.email).first():
            raise HTTPException(status_code=400, detail="Email già registrata")
        
        db_lead = Lead(**lead_data.model_dump())
        db.add(db_lead)
        db.commit()
        db.refresh(db_lead)
        return db_lead

    @staticmethod
    def get_leads(db: Session, skip: int = 0, limit: int = 100):
        return db.query(Lead).order_by(desc(Lead.created_at)).offset(skip).limit(limit).all()

    @staticmethod
    def get_lead_by_id(db: Session, lead_id: int) -> Lead:
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead non trovato")
        return lead

    @staticmethod
    def update_lead(db: Session, lead_id: int, lead_update: LeadUpdate) -> Lead:
        lead = LeadService.get_lead_by_id(db, lead_id)
        update_data = lead_update.model_dump(exclude_unset=True)
        
        for key, value in update_data.items():
            setattr(lead, key, value)
            
        db.commit()
        db.refresh(lead)
        return lead

    @staticmethod
    def get_dashboard_stats(db: Session):
        total = db.query(Lead).count()
        new = db.query(Lead).filter(Lead.status == LeadStatus.NEW).count()
        contacted = db.query(Lead).filter(Lead.status == LeadStatus.CONTACTED).count()
        return {"total": total, "new": new, "contacted": contacted}
