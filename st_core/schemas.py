from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional
from datetime import datetime
from models import LeadStatus, EmailStatus, InterviewStatus

class LeadBase(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., max_length=100)
    email: EmailStr
    country: Optional[str] = None
    language: Optional[str] = None
    source_page: Optional[str] = None
    campaign: Optional[str] = None
    referrer: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    utm_content: Optional[str] = None
    utm_term: Optional[str] = None
    downloaded_editorial: bool = False
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

class LeadCreate(LeadBase):
    pass

class LeadUpdate(BaseModel):
    status: Optional[LeadStatus] = None
    notes: Optional[str] = None

class LeadDownload(BaseModel):
    email: str = Field(...)

class LeadResponse(LeadBase):
    id: int
    uuid: str
    status: LeadStatus
    notes: Optional[str]
    priority_score: int = 0
    download_token: Optional[str] = None
    download_expires_at: Optional[datetime] = None
    downloaded_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class LeadEventResponse(BaseModel):
    id: int
    lead_id: int
    event_type: str
    title: str
    description: Optional[str] = None
    metadata_json: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class LeadEventWithLeadName(LeadEventResponse):
    lead_name: str = ""
    lead_email: str = ""

class EmailQueueResponse(BaseModel):
    id: int
    lead_id: int
    email_type: str
    subject: str
    language: str
    status: EmailStatus
    template_name: str
    payload_json: Optional[str] = None
    scheduled_for: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    attempts: int
    error_message: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class EditorialEditionResponse(BaseModel):
    id: int
    language: str
    name: str
    file_path: Optional[str] = None
    version: str
    active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class DownloadEventResponse(BaseModel):
    id: int
    lead_id: int
    editorial_id: Optional[int] = None
    created_at: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class InterviewResponse(BaseModel):
    id: int
    lead_id: int
    scheduled_at: Optional[datetime] = None
    duration_minutes: int
    status: InterviewStatus
    meeting_url: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class CandidateAnalysisResponse(BaseModel):
    id: int
    lead_id: int
    score: int
    summary: str
    strengths: str
    concerns: str
    recommendation: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class LeadNoteResponse(BaseModel):
    id: int
    lead_id: int
    content: str
    created_by: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class LeadNoteCreate(BaseModel):
    content: str = Field(..., min_length=1)

class EmailTemplateResponse(BaseModel):
    id: int
    name: str
    subject: str
    body_html: Optional[str] = None
    body_text: Optional[str] = None
    language: str
    active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class EmailTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    subject: str = Field(..., min_length=1, max_length=255)
    body_html: Optional[str] = None
    body_text: Optional[str] = None
    language: str = "en"
    active: bool = True

class EmailTemplateUpdate(BaseModel):
    subject: Optional[str] = None
    body_html: Optional[str] = None
    body_text: Optional[str] = None
    language: Optional[str] = None
    active: Optional[bool] = None

class AdminAuditResponse(BaseModel):
    id: int
    admin_user: str
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    details: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class BulkActionRequest(BaseModel):
    lead_ids: list[int] = Field(..., min_length=1)
    action: str = Field(..., pattern="^(status_update|delete|export)$")
    status: Optional[LeadStatus] = None

class DashboardFilters(BaseModel):
    status: Optional[str] = None
    language: Optional[str] = None
    country: Optional[str] = None
    search: Optional[str] = None
    skip: int = 0
    limit: int = 20


class TaskCreate(BaseModel):
    lead_id: Optional[int] = None
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    priority: str = "normal"
    due_at: Optional[datetime] = None
    assigned_to: Optional[str] = None

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    due_at: Optional[datetime] = None
    assigned_to: Optional[str] = None

class TaskResponse(BaseModel):
    id: int
    lead_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    status: str
    priority: str
    due_at: Optional[datetime] = None
    assigned_to: Optional[str] = None
    created_by: Optional[str] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ReminderResponse(BaseModel):
    id: int
    lead_id: int
    reminder_type: str
    title: str
    message: Optional[str] = None
    remind_at: datetime
    status: str
    notified: bool
    notified_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class NotificationResponse(BaseModel):
    id: int
    lead_id: Optional[int] = None
    title: str
    message: Optional[str] = None
    notification_type: str
    read: bool
    read_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RetreatCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    location: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    max_participants: int = 10
    price: float = 0.0
    currency: str = "EUR"
    status: Optional[str] = None


class RetreatResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    location: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    max_participants: int
    price: float
    currency: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BookingCreate(BaseModel):
    lead_id: int
    retreat_id: int
    seats_reserved: int = 1
    notes: Optional[str] = None


class BookingResponse(BaseModel):
    id: int
    lead_id: int
    retreat_id: int
    status: str
    seats_reserved: int
    total_amount: float
    deposit_amount: float
    deposit_paid: bool
    balance_paid: bool
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaymentResponse(BaseModel):
    id: int
    booking_id: int
    amount: float
    payment_type: str
    payment_method: Optional[str] = None
    notes: Optional[str] = None
    paid_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ParticipantResponse(BaseModel):
    id: int
    booking_id: int
    first_name: str
    last_name: str
    email: Optional[str] = None
    passport_number: Optional[str] = None
    nationality: Optional[str] = None
    date_of_birth: Optional[datetime] = None
    special_requirements: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
