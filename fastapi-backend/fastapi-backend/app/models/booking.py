"""
Booking Model
Represents a confirmed travel booking
"""
from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import Field
from .base import BaseDBModel


class Booking(BaseDBModel):
    """Booking entity"""
    
    # Relations
    user_id: str = Field(..., description="Customer ID")
    quotation_id: str = Field(..., description="Related quotation")
    visa_application_id: Optional[str] = Field(None, description="Related visa application")
    
    # Booking Details
    booking_reference: str = Field(..., description="Unique booking reference")
    booking_type: str = Field(..., description="Type: VISA, FLIGHT, HOTEL, PACKAGE, etc.")
    
    # Status
    status: str = Field(
        "PENDING_PAYMENT",
        description="Status: PENDING_PAYMENT, CONFIRMED, CANCELLED, COMPLETED"
    )
    
    # Travel Dates
    travel_date: Optional[datetime] = Field(None, description="Travel start date")
    return_date: Optional[datetime] = Field(None, description="Travel end date")
    
    # Pricing
    total_amount: float = Field(..., description="Total booking amount")
    currency: str = Field("EGP", description="Currency code")
    
    # Cancellation
    cancelled_at: Optional[datetime] = Field(None, description="Cancellation timestamp")
    cancellation_reason: Optional[str] = Field(None, description="Reason for cancellation")
    
    # Metadata
    booking_details: Optional[Dict[str, Any]] = Field(None, description="Additional booking details")
    notes: Optional[str] = Field(None, description="Internal notes")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "book_123",
                "user_id": "usr_123",
                "quotation_id": "quote_123",
                "booking_reference": "BK-2024-001",
                "booking_type": "VISA",
                "status": "CONFIRMED",
                "total_amount": 1500.0,
                "currency": "EGP"
            }
        }
