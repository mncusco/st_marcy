import uuid
import enum
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy import String, Text, Boolean, DateTime, Integer, Float, ForeignKey, Index, Enum as SQLEnum
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
    __table_args__ = (
        Index("ix_leads_status", "status"),
        Index("ix_leads_created_at", "created_at"),
        Index("ix_leads_source_page", "source_page"),
        Index("ix_leads_country", "country"),
        Index("ix_leads_language", "language"),
        Index("ix_leads_downloaded_editorial", "downloaded_editorial"),
        Index("ix_leads_priority_score", "priority_score"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    uuid: Mapped[str] = mapped_column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    country: Mapped[str] = mapped_column(String(100), nullable=True)
    language: Mapped[str] = mapped_column(String(10), nullable=True)
    source_page: Mapped[str] = mapped_column(String(255), nullable=True)
    campaign: Mapped[str] = mapped_column(String(255), nullable=True)
    campaign_sent_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    email_opened: Mapped[bool] = mapped_column(Boolean, default=False)
    email_clicked: Mapped[bool] = mapped_column(Boolean, default=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    clicked_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    ip_address: Mapped[str] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str] = mapped_column(Text, nullable=True)

    editorial_edition_id: Mapped[int] = mapped_column(Integer, ForeignKey("editorial_editions.id"), nullable=True)
    editorial_assigned_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    priority_score: Mapped[int] = mapped_column(Integer, default=0)
    estimated_value: Mapped[float] = mapped_column(Float, default=0.0)
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
    bookings: Mapped[list["Booking"]] = relationship(back_populates="lead", cascade="all, delete-orphan")

class LeadEvent(Base):
    __tablename__ = "lead_events"
    __table_args__ = (
        Index("ix_lead_events_lead_id", "lead_id"),
        Index("ix_lead_events_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    lead_id: Mapped[int] = mapped_column(Integer, ForeignKey("leads.id"))
    event_type: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

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
    __table_args__ = (
        Index("ix_email_queue_status", "status"),
        Index("ix_email_queue_created_at", "created_at"),
        Index("ix_email_queue_scheduled_for", "scheduled_for"),
        Index("ix_email_queue_email_type", "email_type"),
    )

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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    lead: Mapped["Lead"] = relationship(back_populates="emails")

class EditorialEdition(Base):
    __tablename__ = "editorial_editions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    language: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(512), nullable=True)
    version: Mapped[str] = mapped_column(String(50), default="1.0")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    leads: Mapped[list["Lead"]] = relationship(back_populates="editorial_edition")

class DownloadEvent(Base):
    __tablename__ = "download_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    lead_id: Mapped[int] = mapped_column(Integer, ForeignKey("leads.id"), index=True)
    editorial_id: Mapped[int] = mapped_column(Integer, ForeignKey("editorial_editions.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    ip_address: Mapped[str] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str] = mapped_column(Text, nullable=True)

    lead: Mapped["Lead"] = relationship(back_populates="download_events")
    editorial: Mapped[Optional["EditorialEdition"]] = relationship()

class Interview(Base):
    __tablename__ = "interviews"
    __table_args__ = (
        Index("ix_interviews_lead_id", "lead_id"),
        Index("ix_interviews_status", "status"),
        Index("ix_interviews_scheduled_at", "scheduled_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    lead_id: Mapped[int] = mapped_column(Integer, ForeignKey("leads.id"))
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=30)
    status: Mapped[InterviewStatus] = mapped_column(SQLEnum(InterviewStatus), default=InterviewStatus.REQUESTED)
    meeting_url: Mapped[str] = mapped_column(String(512), nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

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
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))

    lead: Mapped["Lead"] = relationship(back_populates="analysis")

class LeadNote(Base):
    __tablename__ = "lead_notes"
    __table_args__ = (
        Index("ix_lead_notes_lead_id", "lead_id"),
        Index("ix_lead_notes_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    lead_id: Mapped[int] = mapped_column(Integer, ForeignKey("leads.id"))
    content: Mapped[str] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


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
    __table_args__ = (
        Index("ix_tasks_lead_id", "lead_id"),
        Index("ix_tasks_assigned_to", "assigned_to"),
        Index("ix_tasks_status", "status"),
        Index("ix_tasks_due_at", "due_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    lead_id: Mapped[int] = mapped_column(Integer, ForeignKey("leads.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[TaskStatus] = mapped_column(SQLEnum(TaskStatus), default=TaskStatus.PENDING)
    priority: Mapped[str] = mapped_column(String(20), default="normal")
    due_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    assigned_to: Mapped[str] = mapped_column(String(100), nullable=True)
    created_by: Mapped[str] = mapped_column(String(100), nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    lead: Mapped[Optional["Lead"]] = relationship(back_populates="tasks")

class Reminder(Base):
    __tablename__ = "reminders"
    __table_args__ = (
        Index("ix_reminders_lead_id", "lead_id"),
        Index("ix_reminders_remind_at", "remind_at"),
        Index("ix_reminders_notified", "notified"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    lead_id: Mapped[int] = mapped_column(Integer, ForeignKey("leads.id"))
    reminder_type: Mapped[ReminderType] = mapped_column(SQLEnum(ReminderType))
    title: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text, nullable=True)
    remind_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), default="active")
    notified: Mapped[bool] = mapped_column(Boolean, default=False)
    notified_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    lead: Mapped["Lead"] = relationship(back_populates="reminders")

class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_lead_id", "lead_id"),
        Index("ix_notifications_read", "read"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    lead_id: Mapped[int] = mapped_column(Integer, ForeignKey("leads.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text, nullable=True)
    notification_type: Mapped[str] = mapped_column(String(50))
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    read_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    lead: Mapped[Optional["Lead"]] = relationship(back_populates="notifications")

class RetreatStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

class BookingStatus(str, enum.Enum):
    RESERVED = "RESERVED"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    WAITING = "WAITING"

class PaymentType(str, enum.Enum):
    DEPOSIT = "DEPOSIT"
    BALANCE = "BALANCE"
    REFUND = "REFUND"

class PaymentMethod(str, enum.Enum):
    CASH = "CASH"
    TRANSFER = "TRANSFER"
    CARD = "CARD"
    OTHER = "OTHER"

class Retreat(Base):
    __tablename__ = "retreats"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, nullable=True)
    location: Mapped[str] = mapped_column(String(255), nullable=True)
    start_date: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    end_date: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    max_participants: Mapped[int] = mapped_column(Integer, default=10)
    price: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String(10), default="EUR")
    status: Mapped[RetreatStatus] = mapped_column(SQLEnum(RetreatStatus), default=RetreatStatus.DRAFT)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    bookings: Mapped[list["Booking"]] = relationship(back_populates="retreat", cascade="all, delete-orphan")


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        Index("ix_bookings_lead_id", "lead_id"),
        Index("ix_bookings_retreat_id", "retreat_id"),
        Index("ix_bookings_status", "status"),
        Index("ix_bookings_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    lead_id: Mapped[int] = mapped_column(Integer, ForeignKey("leads.id"))
    retreat_id: Mapped[int] = mapped_column(Integer, ForeignKey("retreats.id"))
    status: Mapped[BookingStatus] = mapped_column(SQLEnum(BookingStatus), default=BookingStatus.RESERVED)
    seats_reserved: Mapped[int] = mapped_column(Integer, default=1)
    total_amount: Mapped[float] = mapped_column(Float, default=0.0)
    deposit_amount: Mapped[float] = mapped_column(Float, default=0.0)
    deposit_paid: Mapped[bool] = mapped_column(Boolean, default=False)
    balance_paid: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    lead: Mapped["Lead"] = relationship(back_populates="bookings")
    retreat: Mapped["Retreat"] = relationship(back_populates="bookings")
    payments: Mapped[list["Payment"]] = relationship(back_populates="booking", cascade="all, delete-orphan")
    participants: Mapped[list["Participant"]] = relationship(back_populates="booking", cascade="all, delete-orphan")
    room_assignments: Mapped[list["RoomAssignment"]] = relationship(back_populates="booking", cascade="all, delete-orphan")


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    booking_id: Mapped[int] = mapped_column(Integer, ForeignKey("bookings.id"), index=True)
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    payment_type: Mapped[PaymentType] = mapped_column(SQLEnum(PaymentType), default=PaymentType.DEPOSIT)
    payment_method: Mapped[PaymentMethod] = mapped_column(SQLEnum(PaymentMethod), nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    paid_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    booking: Mapped["Booking"] = relationship(back_populates="payments")


class Participant(Base):
    __tablename__ = "participants"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    booking_id: Mapped[int] = mapped_column(Integer, ForeignKey("bookings.id"), index=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), nullable=True)
    passport_number: Mapped[str] = mapped_column(String(50), nullable=True)
    nationality: Mapped[str] = mapped_column(String(100), nullable=True)
    date_of_birth: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    special_requirements: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    booking: Mapped["Booking"] = relationship(back_populates="participants")


class RoomAssignment(Base):
    __tablename__ = "room_assignments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    participant_id: Mapped[int] = mapped_column(Integer, ForeignKey("participants.id"), index=True, nullable=True)
    booking_id: Mapped[int] = mapped_column(Integer, ForeignKey("bookings.id"), index=True)
    room_type: Mapped[str] = mapped_column(String(50), nullable=True)
    room_number: Mapped[str] = mapped_column(String(50), nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    booking: Mapped["Booking"] = relationship(back_populates="room_assignments")


class AdminAudit(Base):
    __tablename__ = "admin_audit"
    __table_args__ = (
        Index("ix_admin_audit_admin_user", "admin_user"),
        Index("ix_admin_audit_action", "action"),
        Index("ix_admin_audit_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    admin_user: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(100))
    resource_type: Mapped[str] = mapped_column(String(50), nullable=True)
    resource_id: Mapped[str] = mapped_column(String(50), nullable=True)
    details: Mapped[str] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
