import uuid
import enum
from datetime import datetime
from sqlalchemy import String, Text, Boolean, DateTime, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column
from database import Base

class LeadStatus(str, enum.Enum):
    NEW = "NEW"
    CONTACTED = "CONTACTED"
    INTERVIEW = "INTERVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ARCHIVED = "ARCHIVED"

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
