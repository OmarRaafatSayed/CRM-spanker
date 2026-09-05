"""
Document Model
Represents uploaded documents for visa applications
"""
from typing import Optional
from datetime import datetime
from pydantic import Field, HttpUrl
from .base import BaseDBModel


class Document(BaseDBModel):
    """Document entity"""
    
    # Relations
    visa_application_id: str = Field(..., description="Visa application ID")
    user_id: str = Field(..., description="Customer ID")
    
    # Document Details
    doc_type: str = Field(
        ...,
        description="Type: PASSPORT, PHOTO, BANK_STATEMENT, HOTEL_BOOKING, FLIGHT_BOOKING, etc."
    )
    
    url: str = Field(..., description="Storage URL for the document")
    file_name: Optional[str] = Field(None, description="Original file name")
    file_size: Optional[int] = Field(None, description="File size in bytes")
    mime_type: Optional[str] = Field(None, description="MIME type of the file")
    
    # Status
    status: str = Field(
        "uploaded",
        description="Status: uploaded, under_review, approved, rejected, expired"
    )
    
    # Review
    reviewed_by: Optional[str] = Field(None, description="Staff ID who reviewed")
    reviewed_at: Optional[datetime] = Field(None, description="Review timestamp")
    rejection_reason: Optional[str] = Field(None, description="Reason if rejected")
    
    # Expiry
    expiry_date: Optional[datetime] = Field(None, description="Document expiry date")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "doc_123",
                "visa_application_id": "visa_123",
                "user_id": "usr_123",
                "doc_type": "PASSPORT",
                "url": "https://storage.example.com/docs/passport_123.pdf",
                "status": "approved"
            }
        }
