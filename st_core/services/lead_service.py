from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_
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
    def get_filtered_leads(
        db: Session,
        status: str = None,
        language: str = None,
        country: str = None,
        search: str = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        skip: int = 0,
        limit: int = 20
    ):
        query = db.query(Lead)

        if status:
            query = query.filter(Lead.status == LeadStatus(status.upper()))
        if language:
            query = query.filter(Lead.language == language.lower())
        if country:
            query = query.filter(Lead.country.ilike(f"%{country}%"))
        if search:
            query = query.filter(
                or_(
                    Lead.first_name.ilike(f"%{search}%"),
                    Lead.last_name.ilike(f"%{search}%"),
                    Lead.email.ilike(f"%{search}%")
                )
            )

        total = query.count()

        sort_col = getattr(Lead, sort_by, Lead.created_at)
        if sort_order == "asc":
            query = query.order_by(sort_col.asc())
        else:
            query = query.order_by(desc(sort_col))

        leads = query.offset(skip).limit(limit).all()
        return leads, total

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
    def mark_downloaded(db: Session, lead_id: int) -> Lead:
        lead = LeadService.get_lead_by_id(db, lead_id)
        lead.downloaded_editorial = True
        lead.downloaded_at = datetime.utcnow()
        db.commit()
        db.refresh(lead)
        return lead

    @staticmethod
    def get_dashboard_stats(db: Session):
        total = db.query(Lead).count()
        new = db.query(Lead).filter(Lead.status == LeadStatus.NEW).count()
        contacted = db.query(Lead).filter(Lead.status == LeadStatus.CONTACTED).count()
        interview = db.query(Lead).filter(Lead.status == LeadStatus.INTERVIEW).count()
        approved = db.query(Lead).filter(Lead.status == LeadStatus.APPROVED).count()
        rejected = db.query(Lead).filter(Lead.status == LeadStatus.REJECTED).count()
        archived = db.query(Lead).filter(Lead.status == LeadStatus.ARCHIVED).count()
        total_downloads = db.query(Lead).filter(Lead.downloaded_editorial == True).count()
        return {
            "total": total,
            "new": new,
            "contacted": contacted,
            "interview": interview,
            "approved": approved,
            "rejected": rejected,
            "archived": archived,
            "total_downloads": total_downloads,
        }
