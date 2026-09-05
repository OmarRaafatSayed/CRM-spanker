"""
Visa Application Model
Represents a visa application request
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import Field
from .base import BaseDBModel


class VisaApplication(BaseDBModel):
    """Visa Application entity"""
    
    # Relations
    user_id: str = Field(..., description="Customer ID")
    
    # Visa Details
    country_code: str = Field(..., description="Destination country code (ISO 3166-1 alpha-2)")
    visa_type: Optional[str] = Field(None, description="Type of visa: TOURIST, BUSINESS, STUDENT, etc.")
    
    # Status
    status: str = Field(
        "DOCS_PENDING",
        description="Status: DOCS_PENDING, UNDER_REVIEW, SUBMITTED_TO_EMBASSY, APPROVED, REJECTED"
    )
    
    # Travel Dates
    travel_date: Optional[datetime] = Field(None, description="Planned travel date")
    return_date: Optional[datetime] = Field(None, description="Planned return date")
    
    # Embassy Details
    embassy_submission_date: Optional[datetime] = Field(None, description="Date submitted to embassy")
    embassy_reference: Optional[str] = Field(None, description="Embassy reference number")
    
    # Documents (relation handled by documents table)
    # Will be loaded separately with documents
    
    # Metadata
    notes: Optional[str] = Field(None, description="Internal staff notes")
    rejection_reason: Optional[str] = Field(None, description="Reason if rejected")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "visa_123",
                "user_id": "usr_123",
                "country_code": "AE",
                "visa_type": "TOURIST",
                "status": "UNDER_REVIEW",
                "travel_date": "2024-06-15T00:00:00Z",
                "return_date": "2024-06-25T00:00:00Z"
            }
        }
