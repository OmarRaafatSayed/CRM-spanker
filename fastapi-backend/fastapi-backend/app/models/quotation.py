"""
Quotation Model
Represents a price quotation for travel services
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from .base import BaseDBModel


class QuotationItem(BaseModel):
    """Single item in a quotation"""
    description: str
    quantity: int = 1
    unit_price: float
    total: float
    item_type: Optional[str] = None  # VISA, FLIGHT, HOTEL, etc.


class Quotation(BaseDBModel):
    """Quotation entity"""
    
    # Relations
    user_id: str = Field(..., description="Customer ID")
    visa_application_id: Optional[str] = Field(None, description="Related visa application")
    
    # Items
    items: List[Dict[str, Any]] = Field(default_factory=list, description="Quotation line items")
    
    # Pricing
    subtotal: float = Field(0.0, description="Subtotal before tax")
    tax_amount: float = Field(0.0, description="Tax amount")
    total_amount: float = Field(..., description="Total amount")
    currency: str = Field("EGP", description="Currency code")
    
    # Status
    status: str = Field(
        "DRAFT",
        description="Status: DRAFT, SENT, ACCEPTED, EXPIRED, REJECTED"
    )
    
    # Validity
    valid_until: Optional[datetime] = Field(None, description="Quotation validity date")
    
    # Customer Response
    accepted_at: Optional[datetime] = Field(None, description="When customer accepted")
    rejected_at: Optional[datetime] = Field(None, description="When customer rejected")
    rejection_reason: Optional[str] = Field(None, description="Rejection reason")
    
    # Metadata
    notes: Optional[str] = Field(None, description="Internal notes")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "quote_123",
                "user_id": "usr_123",
                "visa_application_id": "visa_123",
                "items": [
                    {
                        "description": "UAE Tourist Visa",
                        "quantity": 1,
                        "unit_price": 1500.0,
                        "total": 1500.0,
                        "item_type": "VISA"
                    }
                ],
                "subtotal": 1500.0,
                "tax_amount": 0.0,
                "total_amount": 1500.0,
                "currency": "EGP",
                "status": "SENT"
            }
        }
