import uuid
import enum
from datetime import datetime
from sqlalchemy import String, Text, Boolean, DateTime, Integer, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base

class LeadStatus(str, enum.Enum):
    NEW = "NEW"
    CONTACTED = "CONTACTED"
    INTERVIEW = "INTERVIEW"
    APPROVED = "APPROVED"
    BOOKED = "BOOKED"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    ARCHIVED = "ARCHIVED"

class DocType(str, enum.Enum):
    RECOMMENDATION_LETTER = "RECOMMENDATION_LETTER"
    PASSPORT = "PASSPORT"
    MEDICAL_NOTES = "MEDICAL_NOTES"
    AGREEMENT = "AGREEMENT"

class EmailStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SENT = "SENT"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    uuid: Mapped[str] = mapped_column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    country: Mapped[str] = mapped_column(String(100), nullable=True)
    language: Mapped[str] = mapped_column(String(10), nullable=True)
    source_page: Mapped[str] = mapped_column(String(255), nullable=True)
    campaign: Mapped[str] = mapped_column(String(255), nullable=True)
    status: Mapped[LeadStatus] = mapped_column(SQLEnum(LeadStatus), default=LeadStatus.NEW)
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    downloaded_editorial: Mapped[bool] = mapped_column(Boolean, default=False)
    downloaded_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    download_token: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=True)
    download_expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    referrer: Mapped[str] = mapped_column(String(512), nullable=True)
    utm_source: Mapped[str] = mapped_column(String(255), nullable=True)
    utm_medium: Mapped[str] = mapped_column(String(255), nullable=True)
    utm_campaign: Mapped[str] = mapped_column(String(255), nullable=True)
    utm_content: Mapped[str] = mapped_column(String(255), nullable=True)
    utm_term: Mapped[str] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str] = mapped_column(Text, nullable=True)

    events: Mapped[list["LeadEvent"]] = relationship(back_populates="lead", cascade="all, delete-orphan")
    documents: Mapped[list["LeadDocument"]] = relationship(back_populates="lead", cascade="all, delete-orphan")
    emails: Mapped[list["EmailQueue"]] = relationship(back_populates="lead", cascade="all, delete-orphan")

class LeadEvent(Base):
    __tablename__ = "lead_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    lead_id: Mapped[int] = mapped_column(Integer, ForeignKey("leads.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    lead: Mapped["Lead"] = relationship(back_populates="events")

class LeadDocument(Base):
    __tablename__ = "lead_documents"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    lead_id: Mapped[int] = mapped_column(Integer, ForeignKey("leads.id"), index=True)
    doc_type: Mapped[DocType] = mapped_column(SQLEnum(DocType))
    file_name: Mapped[str] = mapped_column(String(255), nullable=True)
    file_path: Mapped[str] = mapped_column(String(512), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)

    lead: Mapped["Lead"] = relationship(back_populates="documents")

class EmailQueue(Base):
    __tablename__ = "email_queue"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    lead_id: Mapped[int] = mapped_column(Integer, ForeignKey("leads.id"), index=True)
    email_type: Mapped[str] = mapped_column(String(50))
    subject: Mapped[str] = mapped_column(String(255))
    language: Mapped[str] = mapped_column(String(10))
    status: Mapped[EmailStatus] = mapped_column(SQLEnum(EmailStatus), default=EmailStatus.PENDING)
    template_name: Mapped[str] = mapped_column(String(100))
    payload_json: Mapped[str] = mapped_column(Text, nullable=True)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    lead: Mapped["Lead"] = relationship(back_populates="emails")
