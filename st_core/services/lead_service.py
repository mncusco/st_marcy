import json
import secrets
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_
from fastapi import HTTPException
from models import Lead, LeadEvent, LeadStatus, FUNNEL_STAGE_ORDER
from schemas import LeadCreate, LeadUpdate
from services.automation_engine import AutomationEngine
from services.editorial_service import assign_editorial_to_lead, record_download_event

logger = logging.getLogger("st_core.lead_service")

ALLOWED_TRANSITIONS = {
    LeadStatus.NEW: [LeadStatus.EMAIL_SENT, LeadStatus.OPENED, LeadStatus.CLICKED, LeadStatus.DOWNLOADED, LeadStatus.CONTACTED, LeadStatus.REJECTED, LeadStatus.ARCHIVED],
    LeadStatus.EMAIL_SENT: [LeadStatus.OPENED, LeadStatus.CLICKED, LeadStatus.DOWNLOADED, LeadStatus.CONTACTED, LeadStatus.REJECTED, LeadStatus.ARCHIVED],
    LeadStatus.OPENED: [LeadStatus.CLICKED, LeadStatus.DOWNLOADED, LeadStatus.CONTACTED, LeadStatus.REJECTED, LeadStatus.ARCHIVED],
    LeadStatus.CLICKED: [LeadStatus.DOWNLOADED, LeadStatus.CONTACTED, LeadStatus.REJECTED, LeadStatus.ARCHIVED],
    LeadStatus.DOWNLOADED: [LeadStatus.QUALIFIED, LeadStatus.CONTACTED, LeadStatus.INTERVIEW, LeadStatus.REJECTED, LeadStatus.ARCHIVED],
    LeadStatus.QUALIFIED: [LeadStatus.CUSTOMER, LeadStatus.CONTACTED, LeadStatus.INTERVIEW, LeadStatus.APPROVED, LeadStatus.BOOKED, LeadStatus.REJECTED, LeadStatus.ARCHIVED],
    LeadStatus.CUSTOMER: [LeadStatus.COMPLETED, LeadStatus.REJECTED, LeadStatus.ARCHIVED],
    LeadStatus.CONTACTED: [LeadStatus.INTERVIEW, LeadStatus.REJECTED, LeadStatus.ARCHIVED],
    LeadStatus.INTERVIEW: [LeadStatus.APPROVED, LeadStatus.REJECTED, LeadStatus.ARCHIVED],
    LeadStatus.APPROVED: [LeadStatus.BOOKED, LeadStatus.REJECTED, LeadStatus.ARCHIVED],
    LeadStatus.BOOKED: [LeadStatus.COMPLETED, LeadStatus.CUSTOMER, LeadStatus.REJECTED, LeadStatus.ARCHIVED],
    LeadStatus.COMPLETED: [LeadStatus.REJECTED, LeadStatus.ARCHIVED],
    LeadStatus.REJECTED: [LeadStatus.ARCHIVED],
    LeadStatus.ARCHIVED: [],
}

PRIORITY_WEIGHTS = {
    LeadStatus.INTERVIEW: 30,
    LeadStatus.APPROVED: 50,
    LeadStatus.BOOKED: 60,
    LeadStatus.COMPLETED: 80,
    LeadStatus.EMAIL_SENT: 5,
    LeadStatus.OPENED: 15,
    LeadStatus.CLICKED: 25,
    LeadStatus.DOWNLOADED: 35,
    LeadStatus.QUALIFIED: 45,
    LeadStatus.CUSTOMER: 70,
}


def advance_funnel_status(db: Session, lead: Lead, target: LeadStatus) -> Lead:
    """Avanza il lead lungo il funnel (NEW→EMAIL_SENT→OPENED→CLICKED→DOWNLOADED→QUALIFIED→CUSTOMER).

    Muove solo in avanti, non arretra mai, e registra un evento di transizione.
    """
    try:
        current_idx = FUNNEL_STAGE_ORDER.index(lead.status) if lead.status in FUNNEL_STAGE_ORDER else -1
    except ValueError:
        current_idx = -1
    try:
        target_idx = FUNNEL_STAGE_ORDER.index(target)
    except ValueError:
        target_idx = -1

    if target_idx <= current_idx:
        return lead

    allowed = ALLOWED_TRANSITIONS.get(lead.status, [])
    if target not in allowed:
        return lead

    old = lead.status
    lead.status = target
    event = LeadEvent(
        lead_id=lead.id,
        event_type="funnel_status_changed",
        title=f"Funnel: {old.value} → {target.value}",
        description=f"Automatic funnel transition from {old.value} to {target.value}",
        metadata_json=json.dumps({"from": old.value, "to": target.value}),
    )
    db.add(event)
    lead.priority_score = LeadService._compute_priority(lead)
    db.flush()
    logger.info("Lead %d funnel status %s -> %s", lead.id, old.value, target.value)
    return lead


class LeadService:
    @staticmethod
    def _compute_priority(lead: Lead) -> int:
        score = 0
        if lead.downloaded_editorial:
            score += 10
        score += PRIORITY_WEIGHTS.get(lead.status, 0)
        return score

    @staticmethod
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

    @staticmethod
    def create_lead(db: Session, lead_data: LeadCreate) -> Lead:
        if db.query(Lead).filter(Lead.email == lead_data.email).first():
            raise HTTPException(status_code=400, detail="Email già registrata")

        lead_dict = lead_data.model_dump()
        lead_dict["download_token"] = secrets.token_urlsafe(48)
        lead_dict["download_expires_at"] = datetime.now(timezone.utc) + timedelta(days=30)
        db_lead = Lead(**lead_dict)
        db.add(db_lead)
        db.flush()

        LeadService._create_event(db, db_lead.id, "lead_created",
            "Lead created",
            f"Registered via {lead_data.source_page or 'direct'}",
            {"email": lead_data.email, "source_page": lead_data.source_page})
        db.commit()
        db.refresh(db_lead)

        try:
            AutomationEngine(db).on_lead_created(db_lead)
            db.commit()
        except Exception as e:
            db.rollback()
            logger.exception("Automation on_lead_created failed for lead %d: %s", db_lead.id, e)

        try:
            assign_editorial_to_lead(db, db_lead)
            db.commit()
        except Exception as e:
            logger.exception("Editorial assignment failed for lead %d: %s", db_lead.id, e)

        db_lead.priority_score = LeadService._compute_priority(db_lead)
        db.commit()
        db.refresh(db_lead)

        return db_lead

    @staticmethod
    def create_collect_lead(db: Session, lead_data) -> Lead:
        """Crea un lead di SOLA RACCOLTA da un canale esterno dedicato.

        Differenza rispetto a `create_lead`:
        - NON chiama AutomationEngine.on_lead_created → nessuna email accodata
          (né editorial_download né followup_3_days).
        - NON assegna l'editorial né crea reminder automatici.
        - Taggia il lead con `Lead.source` così resta identificabile e filtrabile
          separatamente rispetto alle liste/sequenze esistenti.

        I lead qui creati restano in stato NEW e NON entrano nel funnel fino a
        quando non li attivi esplicitamente in un secondo momento.
        """
        email = lead_data.email.strip().lower()
        if db.query(Lead).filter(Lead.email == email).first():
            raise HTTPException(status_code=409, detail="Email già registrata")

        first_name = (lead_data.first_name or "").strip()
        last_name = (lead_data.last_name or "").strip()
        if not first_name:
            first_name = "Lead"

        db_lead = Lead(
            first_name=first_name,
            last_name=last_name or first_name,
            email=email,
            source=lead_data.source,
            campaign=lead_data.campaign,
            source_page=lead_data.source_page,
            referrer=lead_data.referrer,
            utm_source=lead_data.utm_source,
            utm_medium=lead_data.utm_medium,
            utm_campaign=lead_data.utm_campaign,
            language=lead_data.language,
            country=lead_data.country,
            status=LeadStatus.NEW,
            download_token=secrets.token_urlsafe(48),
            download_expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db.add(db_lead)
        db.flush()

        LeadService._create_event(
            db,
            db_lead.id,
            "lead_collected",
            "Lead collected",
            f"Collected via source={lead_data.source}",
            {"email": email, "source": lead_data.source, "campaign": lead_data.campaign},
        )
        db.commit()
        db.refresh(db_lead)
        logger.info("Collected lead %d from source=%s (email=%s)", db_lead.id, lead_data.source, email)
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
        downloaded: bool = None,
        date_from: str = None,
        date_to: str = None,
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
        if downloaded is True:
            query = query.filter(Lead.downloaded_editorial == True)
        if date_from:
            try:
                dt_from = datetime.strptime(date_from, "%Y-%m-%d")
                query = query.filter(Lead.created_at >= dt_from)
            except ValueError:
                pass
        if date_to:
            try:
                dt_to = datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)
                query = query.filter(Lead.created_at < dt_to)
            except ValueError:
                pass
        if search:
            term = f"%{search}%"
            query = query.filter(
                or_(
                    Lead.first_name.ilike(term),
                    Lead.last_name.ilike(term),
                    Lead.email.ilike(term),
                    Lead.country.ilike(term),
                    Lead.notes.ilike(term),
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
    def update_lead(db: Session, lead_id: int, lead_update: LeadUpdate, created_by: str = None) -> Lead:
        lead = LeadService.get_lead_by_id(db, lead_id)
        update_data = lead_update.model_dump(exclude_unset=True)
        _old_status = lead.status
        _status_changed = False

        if "status" in update_data:
            new_status = update_data["status"]
            if new_status != lead.status:
                allowed = ALLOWED_TRANSITIONS.get(lead.status, [])
                if new_status not in allowed:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Transizione non valida: {lead.status.value} → {new_status.value}"
                    )
                old_status = lead.status
                lead.status = new_status
                _status_changed = True
                LeadService._create_event(db, lead_id, "status_changed",
                    f"Status: {old_status.value} → {new_status.value}",
                    f"Status changed from {old_status.value} to {new_status.value}",
                    {"from": old_status.value, "to": new_status.value},
                    created_by=created_by)

        if "notes" in update_data:
            new_notes = update_data["notes"]
            if new_notes != lead.notes:
                lead.notes = new_notes
                LeadService._create_event(db, lead_id, "notes_updated",
                    "Notes updated",
                    f"Internal notes modified",
                    created_by=created_by)

        for key, value in update_data.items():
            if key not in ("status", "notes"):
                setattr(lead, key, value)

        lead.priority_score = LeadService._compute_priority(lead)
        db.commit()
        db.refresh(lead)

        if _status_changed:
            try:
                AutomationEngine(db).on_status_changed(lead, _old_status, lead.status)
            except Exception as e:
                logger.exception("Automation on_status_changed failed for lead %d: %s", lead.id, e)

        return lead

    @staticmethod
    def get_lead_by_token(db: Session, token: str) -> Lead:
        lead = db.query(Lead).filter(Lead.download_token == token).first()
        if not lead:
            raise HTTPException(status_code=404, detail="Token non valido")
        return lead

    @staticmethod
    def mark_downloaded(db: Session, lead_id: int, ip_address: str = None, user_agent: str = None) -> Lead:
        lead = LeadService.get_lead_by_id(db, lead_id)
        lead.downloaded_editorial = True
        lead.downloaded_at = datetime.now(timezone.utc)
        advance_funnel_status(db, lead, LeadStatus.DOWNLOADED)
        if lead.email_opened and lead.email_clicked:
            advance_funnel_status(db, lead, LeadStatus.QUALIFIED)
        lead.priority_score = LeadService._compute_priority(lead)
        db.commit()
        db.refresh(lead)

        try:
            record_download_event(db, lead, ip_address=ip_address, user_agent=user_agent)
            db.commit()
        except Exception as e:
            logger.exception("Download event recording failed for lead %d: %s", lead.id, e)

        return lead

    @staticmethod
    def mark_downloaded_by_token(db: Session, token: str, ip_address: str = None, user_agent: str = None) -> Lead:
        lead = LeadService.get_lead_by_token(db, token)
        expires = lead.download_expires_at
        if expires is not None:
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > expires:
                raise HTTPException(status_code=410, detail="Token scaduto")
        lead.downloaded_editorial = True
        lead.downloaded_at = datetime.now(timezone.utc)
        advance_funnel_status(db, lead, LeadStatus.DOWNLOADED)
        if lead.email_opened and lead.email_clicked:
            advance_funnel_status(db, lead, LeadStatus.QUALIFIED)
        lead.priority_score = LeadService._compute_priority(lead)
        LeadService._create_event(db, lead.id, "editorial_downloaded",
            "Editorial downloaded",
            f"Language: {lead.language or 'en'}")
        db.commit()
        db.refresh(lead)

        try:
            AutomationEngine(db).on_editorial_download(lead)
        except Exception as e:
            logger.exception("Automation on_editorial_download failed for lead %d: %s", lead.id, e)

        try:
            record_download_event(db, lead, ip_address=ip_address, user_agent=user_agent)
            db.commit()
        except Exception as e:
            logger.exception("Download event recording failed for lead %d: %s", lead.id, e)

        return lead

    @staticmethod
    def get_lead_events(db: Session, lead_id: int):
        return db.query(LeadEvent).filter(
            LeadEvent.lead_id == lead_id
        ).order_by(desc(LeadEvent.created_at)).all()

    @staticmethod
    def get_recent_events(db: Session, limit: int = 10):
        rows = db.query(LeadEvent, Lead.first_name, Lead.last_name, Lead.email).join(
            Lead, LeadEvent.lead_id == Lead.id
        ).order_by(desc(LeadEvent.created_at)).limit(limit).all()

        results = []
        for event, fn, ln, email in rows:
            d = {
                "id": event.id,
                "lead_id": event.lead_id,
                "event_type": event.event_type,
                "title": event.title,
                "description": event.description,
                "metadata_json": event.metadata_json,
                "created_by": event.created_by,
                "created_at": event.created_at,
                "lead_name": f"{fn} {ln}",
                "lead_email": email,
            }
            results.append(d)
        return results

    @staticmethod
    def get_dashboard_stats(db: Session):
        total = db.query(Lead).count()
        new = db.query(Lead).filter(Lead.status == LeadStatus.NEW).count()
        emailed = db.query(Lead).filter(Lead.status == LeadStatus.EMAIL_SENT).count()
        opened = db.query(Lead).filter(Lead.status == LeadStatus.OPENED).count()
        clicked = db.query(Lead).filter(Lead.status == LeadStatus.CLICKED).count()
        downloaded = db.query(Lead).filter(Lead.status == LeadStatus.DOWNLOADED).count()
        qualified = db.query(Lead).filter(Lead.status == LeadStatus.QUALIFIED).count()
        customer = db.query(Lead).filter(Lead.status == LeadStatus.CUSTOMER).count()
        contacted = db.query(Lead).filter(Lead.status == LeadStatus.CONTACTED).count()
        interview = db.query(Lead).filter(Lead.status == LeadStatus.INTERVIEW).count()
        approved = db.query(Lead).filter(Lead.status == LeadStatus.APPROVED).count()
        booked = db.query(Lead).filter(Lead.status == LeadStatus.BOOKED).count()
        completed = db.query(Lead).filter(Lead.status == LeadStatus.COMPLETED).count()
        rejected = db.query(Lead).filter(Lead.status == LeadStatus.REJECTED).count()
        archived = db.query(Lead).filter(Lead.status == LeadStatus.ARCHIVED).count()
        total_downloads = db.query(Lead).filter(Lead.downloaded_editorial == True).count()
        return {
            "total": total,
            "new": new,
            "email_sent": emailed,
            "opened": opened,
            "clicked": clicked,
            "downloaded": downloaded,
            "qualified": qualified,
            "customer": customer,
            "contacted": contacted,
            "interview": interview,
            "approved": approved,
            "booked": booked,
            "completed": completed,
            "rejected": rejected,
            "archived": archived,
            "total_downloads": total_downloads,
        }
