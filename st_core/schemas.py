from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional
from datetime import datetime
from models import LeadStatus

class LeadBase(BaseModel):
    first_name: str = Field(..., max_length=100)
    last_name: str = Field(..., max_length=100)
    email: EmailStr
    country: Optional[str] = None
    language: Optional[str] = None
    source_page: Optional[str] = None
    campaign: Optional[str] = None
    downloaded_editorial: bool = False
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

class LeadCreate(LeadBase):
    pass

class LeadUpdate(BaseModel):
    status: Optional[LeadStatus] = None
    notes: Optional[str] = None

class LeadResponse(LeadBase):
    id: int
    uuid: str
    status: LeadStatus
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
