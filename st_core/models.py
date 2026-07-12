import uuid
import enum
from typing import Optional
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

class InterviewStatus(str, enum.Enum):
    REQUESTED = "REQUESTED"
    SCHEDULED = "SCHEDULED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    NO_SHOW = "NO_SHOW"

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

    editorial_edition_id: Mapped[int] = mapped_column(Integer, ForeignKey("editorial_editions.id"), nullable=True)
    editorial_assigned_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    priority_score: Mapped[int] = mapped_column(Integer, default=0)
    estimated_value: Mapped[float] = mapped_column(Integer, default=0.0)
    owner: Mapped[str] = mapped_column(String(100), nullable=True)

    crm_notes: Mapped[list["LeadNote"]] = relationship(back_populates="lead", cascade="all, delete-orphan")
    events: Mapped[list["LeadEvent"]] = relationship(back_populates="lead", cascade="all, delete-orphan")
    documents: Mapped[list["LeadDocument"]] = relationship(back_populates="lead", cascade="all, delete-orphan")
    emails: Mapped[list["EmailQueue"]] = relationship(back_populates="lead", cascade="all, delete-orphan")
    editorial_edition: Mapped[Optional["EditorialEdition"]] = relationship(back_populates="leads")
    download_events: Mapped[list["DownloadEvent"]] = relationship(back_populates="lead", cascade="all, delete-orphan")
    interviews: Mapped[list["Interview"]] = relationship(back_populates="lead", cascade="all, delete-orphan")
    analysis: Mapped[Optional["CandidateAnalysis"]] = relationship(back_populates="lead", uselist=False, cascade="all, delete-orphan")
    tasks: Mapped[list["Task"]] = relationship(back_populates="lead", cascade="all, delete-orphan")
    reminders: Mapped[list["Reminder"]] = relationship(back_populates="lead", cascade="all, delete-orphan")
    notifications: Mapped[list["Notification"]] = relationship(back_populates="lead", cascade="all, delete-orphan")

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

class EditorialEdition(Base):
    __tablename__ = "editorial_editions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    language: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(512), nullable=True)
    version: Mapped[str] = mapped_column(String(50), default="1.0")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    leads: Mapped[list["Lead"]] = relationship(back_populates="editorial_edition")

class DownloadEvent(Base):
    __tablename__ = "download_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    lead_id: Mapped[int] = mapped_column(Integer, ForeignKey("leads.id"), index=True)
    editorial_id: Mapped[int] = mapped_column(Integer, ForeignKey("editorial_editions.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str] = mapped_column(Text, nullable=True)

    lead: Mapped["Lead"] = relationship(back_populates="download_events")
    editorial: Mapped[Optional["EditorialEdition"]] = relationship()

class Interview(Base):
    __tablename__ = "interviews"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    lead_id: Mapped[int] = mapped_column(Integer, ForeignKey("leads.id"), index=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=30)
    status: Mapped[InterviewStatus] = mapped_column(SQLEnum(InterviewStatus), default=InterviewStatus.REQUESTED)
    meeting_url: Mapped[str] = mapped_column(String(512), nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    lead: Mapped["Lead"] = relationship(back_populates="interviews")


class CandidateAnalysis(Base):
    __tablename__ = "candidate_analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), unique=True)
    score: Mapped[int] = mapped_column()
    summary: Mapped[str] = mapped_column(Text())
    strengths: Mapped[str] = mapped_column(Text(), default="[]")
    concerns: Mapped[str] = mapped_column(Text(), default="[]")
    recommendation: Mapped[str] = mapped_column(default="")
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    lead: Mapped["Lead"] = relationship(back_populates="analysis")

class LeadNote(Base):
    __tablename__ = "lead_notes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    lead_id: Mapped[int] = mapped_column(Integer, ForeignKey("leads.id"), index=True)
    content: Mapped[str] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    lead: Mapped["Lead"] = relationship(back_populates="crm_notes")


class EmailTemplate(Base):
    __tablename__ = "email_templates"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    subject: Mapped[str] = mapped_column(String(255))
    body_html: Mapped[str] = mapped_column(Text, nullable=True)
    body_text: Mapped[str] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(10), default="en")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TaskStatus(str, enum.Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

class ReminderType(str, enum.Enum):
    FOLLOWUP_3D = "FOLLOWUP_3D"
    FOLLOWUP_7D = "FOLLOWUP_7D"
    FOLLOWUP_14D = "FOLLOWUP_14D"
    FOLLOWUP_30D = "FOLLOWUP_30D"
    CUSTOM = "CUSTOM"

class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    lead_id: Mapped[int] = mapped_column(Integer, ForeignKey("leads.id"), index=True, nullable=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[TaskStatus] = mapped_column(SQLEnum(TaskStatus), default=TaskStatus.PENDING)
    priority: Mapped[str] = mapped_column(String(20), default="normal")
    due_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    assigned_to: Mapped[str] = mapped_column(String(100), nullable=True)
    created_by: Mapped[str] = mapped_column(String(100), nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    lead: Mapped[Optional["Lead"]] = relationship(back_populates="tasks")

class Reminder(Base):
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    lead_id: Mapped[int] = mapped_column(Integer, ForeignKey("leads.id"), index=True)
    reminder_type: Mapped[ReminderType] = mapped_column(SQLEnum(ReminderType))
    title: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text, nullable=True)
    remind_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), default="active")
    notified: Mapped[bool] = mapped_column(Boolean, default=False)
    notified_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    lead: Mapped["Lead"] = relationship(back_populates="reminders")

class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    lead_id: Mapped[int] = mapped_column(Integer, ForeignKey("leads.id"), index=True, nullable=True)
    title: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text, nullable=True)
    notification_type: Mapped[str] = mapped_column(String(50))
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    read_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    lead: Mapped[Optional["Lead"]] = relationship(back_populates="notifications")

class AdminAudit(Base):
    __tablename__ = "admin_audit"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    admin_user: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(100))
    resource_type: Mapped[str] = mapped_column(String(50), nullable=True)
    resource_id: Mapped[str] = mapped_column(String(50), nullable=True)
    details: Mapped[str] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
