"""
Customer/User Model
Represents a customer in the CRM system
"""
from typing import Optional
from datetime import datetime
from pydantic import EmailStr, Field
from .base import BaseDBModel


class Customer(BaseDBModel):
    """Customer (User) entity"""
    
    # Auth & Identity
    auth_user_id: str = Field(..., description="Supabase auth user ID")
    email: EmailStr = Field(..., description="Customer email")
    phone: Optional[str] = Field(None, description="Customer phone number")
    full_name: Optional[str] = Field(None, description="Customer full name")
    
    # Travel Documents
    passport_number: Optional[str] = Field(None, description="Passport number")
    passport_expiry: Optional[datetime] = Field(None, description="Passport expiry date")
    nationality: Optional[str] = Field(None, description="Customer nationality")
    
    # CRM Status
    status: str = Field("LEAD", description="Customer status: LEAD, ACTIVE_CLIENT, INACTIVE")
    
    # Metadata
    notes: Optional[str] = Field(None, description="Internal staff notes")
    profile_completed: bool = Field(False, description="Whether profile is complete")
    
    # Timestamps (inherited from BaseDBModel)
    # id, created_at, updated_at
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "usr_123",
                "auth_user_id": "auth0_abc123",
                "email": "customer@example.com",
                "phone": "+20123456789",
                "full_name": "Ahmed Mohamed",
                "passport_number": "A12345678",
                "status": "ACTIVE_CLIENT",
                "nationality": "EG"
            }
        }
