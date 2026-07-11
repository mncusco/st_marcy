from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional
from datetime import datetime
from models import LeadStatus

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

class DashboardFilters(BaseModel):
    status: Optional[str] = None
    language: Optional[str] = None
    country: Optional[str] = None
    search: Optional[str] = None
    skip: int = 0
    limit: int = 20
