"""
Financial Transaction Model
Represents payment transactions for bookings
"""
from typing import Optional
from datetime import datetime
from pydantic import Field, HttpUrl
from .base import BaseDBModel


class Transaction(BaseDBModel):
    """Financial Transaction entity"""
    
    # Relations
    booking_id: str = Field(..., description="Related booking")
    user_id: str = Field(..., description="Customer ID")
    
    # Payment Details
    total_amount: float = Field(..., description="Total amount to be paid")
    amount_paid: float = Field(0.0, description="Amount already paid")
    remaining_balance: float = Field(..., description="Remaining balance")
    currency: str = Field("EGP", description="Currency code")
    
    # Payment Method
    payment_method: str = Field(..., description="Method: CASH, BANK_TRANSFER, POS, CREDIT_CARD")
    
    # Payment Status
    payment_status: str = Field(
        "PENDING",
        description="Status: PENDING, PARTIAL, PAID, REFUNDED"
    )
    
    # Payment Evidence
    receipt_url: Optional[str] = Field(None, description="Receipt/proof of payment URL")
    transaction_reference: Optional[str] = Field(None, description="Bank/payment reference")
    
    # Timestamps
    paid_at: Optional[datetime] = Field(None, description="Payment completion timestamp")
    
    # Refund
    refund_amount: Optional[float] = Field(None, description="Refund amount if applicable")
    refunded_at: Optional[datetime] = Field(None, description="Refund timestamp")
    refund_reason: Optional[str] = Field(None, description="Reason for refund")
    
    # Metadata
    notes: Optional[str] = Field(None, description="Internal notes")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "txn_123",
                "booking_id": "book_123",
                "user_id": "usr_123",
                "total_amount": 1500.0,
                "amount_paid": 750.0,
                "remaining_balance": 750.0,
                "currency": "EGP",
                "payment_method": "BANK_TRANSFER",
                "payment_status": "PARTIAL"
            }
        }
