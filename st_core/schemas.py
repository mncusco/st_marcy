from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional
from datetime import datetime
from models import LeadStatus, EmailStatus

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

class DashboardFilters(BaseModel):
    status: Optional[str] = None
    language: Optional[str] = None
    country: Optional[str] = None
    search: Optional[str] = None
    skip: int = 0
    limit: int = 20
