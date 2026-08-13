"""
TASK 7: Unified API Schema & Type Contracts

Strict, uniform type contracts for all Portal/CRM API endpoints:
- Flight IDs, Prices, Customer Details, Timestamps
- Consistent serialization/deserialization
- Validation rules enforced at schema level
- Compatible with both Portal and CRM clients

Usage:
  from app.schemas.unified_types import FlightID, Price, CustomerDetails, Timestamp
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Pattern
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, field_serializer
import re


# ─────────────────────────────────────────────────────────────────────────────
# Primitive Type Contracts
# ─────────────────────────────────────────────────────────────────────────────

class FlightID(str):
    """
    Flight ID type contract.
    
    Format: GDS provider + Flight number
    Examples: 'AA123', 'EK456', 'TK789'
    """
    PATTERN = re.compile(r'^[A-Z0-9]{2,3}\d{3,5}$')

    def __new__(cls, value: str):
        value = str(value).upper().strip()
        if not cls.PATTERN.match(value):
            raise ValueError(
                f"Invalid FlightID format: {value}. "
                f"Must match pattern (e.g., 'AA123', 'EK456')"
            )
        return str.__new__(cls, value)


class Price(Decimal):
    """
    Price type contract.
    
    Stored as Decimal for precision (no float rounding errors).
    Always positive, up to 2 decimal places.
    Examples: 999.99, 50.00, 0.01
    """

    def __new__(cls, value: str | int | float | Decimal):
        decimal_value = Decimal(str(value))

        if decimal_value < 0:
            raise ValueError("Price must be positive")

        if decimal_value.as_tuple().exponent < -2:
            raise ValueError("Price must have at most 2 decimal places")

        return Decimal.__new__(cls, decimal_value)


class Timestamp(datetime):
    """
    Timestamp type contract.
    
    Always UTC, ISO 8601 format.
    Examples: '2026-08-12T15:30:45Z', '2026-08-12T15:30:45+00:00'
    """

    @classmethod
    def now(cls) -> Timestamp:
        """Get current UTC timestamp"""
        return cls.from_datetime(datetime.now(timezone.utc))

    @classmethod
    def from_datetime(cls, dt: datetime) -> Timestamp:
        """Convert datetime to UTC Timestamp"""
        if dt.tzinfo is None:
            # Assume UTC if no timezone
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            # Convert to UTC
            dt = dt.astimezone(timezone.utc)
        return cls(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second,
                   dt.microsecond, tzinfo=timezone.utc)

    def to_iso(self) -> str:
        """ISO 8601 format"""
        return self.isoformat().replace('+00:00', 'Z')


class EntityID(str):
    """
    Universal entity ID contract.
    
    All entities use UUID v4 format.
    """
    PATTERN = re.compile(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
        re.IGNORECASE
    )

    def __new__(cls, value: str | UUID):
        value_str = str(value).lower()
        if not cls.PATTERN.match(value_str):
            raise ValueError(f"Invalid EntityID format: {value}. Must be UUID v4.")
        return str.__new__(cls, value_str)


# ─────────────────────────────────────────────────────────────────────────────
# Customer & User Schemas
# ─────────────────────────────────────────────────────────────────────────────

class CustomerDetailsBase(BaseModel):
    """Base customer details — common across Portal & CRM"""
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., min_length=5, max_length=255)
    phone: Optional[str] = Field(None, min_length=10, max_length=20)
    country: Optional[str] = Field(None, min_length=2, max_length=100)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Validate email format"""
        if "@" not in v or "." not in v.split("@")[1]:
            raise ValueError("Invalid email format")
        return v.lower()

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        """Validate phone (only digits, +, -)"""
        if v and not re.match(r'^[\d\+\-\(\)\s]+$', v):
            raise ValueError("Phone must contain only digits, +, -, (, ), or spaces")
        return v


class CustomerDetailsResponse(CustomerDetailsBase):
    """Customer details response — includes IDs"""
    id: EntityID
    auth_user_id: EntityID
    status: str = Field(..., description="active | inactive | suspended")
    kyc_status: str = Field(..., description="pending | verified | rejected")
    crm_customer_id: Optional[EntityID] = None
    created_at: Timestamp
    updated_at: Timestamp


# ─────────────────────────────────────────────────────────────────────────────
# Flight Booking Schemas
# ─────────────────────────────────────────────────────────────────────────────

class FlightSearchRequest(BaseModel):
    """Unified flight search request"""
    origin_code: str = Field(..., min_length=3, max_length=3, description="IATA code")
    destination_code: str = Field(..., min_length=3, max_length=3, description="IATA code")
    departure_date: str = Field(..., description="YYYY-MM-DD")
    return_date: Optional[str] = Field(None, description="YYYY-MM-DD")
    passenger_count: int = Field(default=1, ge=1, le=9)
    trip_type: str = Field(default="round_trip", description="one_way | round_trip")

    @field_validator("departure_date", "return_date")
    @classmethod
    def validate_date_format(cls, v: Optional[str]) -> Optional[str]:
        """Validate YYYY-MM-DD format"""
        if v and not re.match(r'^\d{4}-\d{2}-\d{2}$', v):
            raise ValueError("Date must be YYYY-MM-DD format")
        return v


class FlightSegmentResponse(BaseModel):
    """Single flight segment"""
    flight_id: FlightID
    airline_code: str = Field(..., min_length=2, max_length=3)
    airline_name: str
    departure_time: Timestamp
    arrival_time: Timestamp
    duration_minutes: int = Field(..., ge=0)
    aircraft_type: Optional[str] = None


class FlightPriceResponse(BaseModel):
    """Flight price with currency"""
    amount: Price = Field(..., description="Price in specified currency")
    currency: str = Field(default="USD", min_length=3, max_length=3)
    tax_amount: Optional[Price] = None
    total_amount: Optional[Price] = None


class FlightOfferResponse(BaseModel):
    """Complete flight offer"""
    id: EntityID
    outbound_segments: list[FlightSegmentResponse]
    return_segments: Optional[list[FlightSegmentResponse]] = None
    price: FlightPriceResponse
    seats_available: int = Field(..., ge=0)
    validity: Timestamp
    booking_url: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Booking & Payment Schemas
# ─────────────────────────────────────────────────────────────────────────────

class TravelRequestBase(BaseModel):
    """Base travel request"""
    destination_country: str = Field(..., min_length=2, max_length=100)
    travel_type: str = Field(..., description="visa_only | visa_flight | visa_hotel | full_package")
    departure_date: Optional[str] = None
    return_date: Optional[str] = None
    traveler_count: int = Field(default=1, ge=1, le=50)


class TravelRequestResponse(TravelRequestBase):
    """Travel request response"""
    id: EntityID
    client_user_id: EntityID
    status: str = Field(
        ...,
        description="pending_documents | documents_review | docs_approved | in_progress | completed | cancelled"
    )
    documents_completion_percent: int = Field(..., ge=0, le=100)
    created_at: Timestamp
    updated_at: Timestamp


class PaymentRecordBase(BaseModel):
    """Base payment record"""
    amount: Price
    currency: str = Field(default="USD", min_length=3, max_length=3)
    payment_method: str = Field(..., description="cash | bank | pos | cheque | card")
    notes: Optional[str] = None


class PaymentRecordResponse(PaymentRecordBase):
    """Payment record response"""
    id: EntityID
    booking_reference: Optional[str] = None
    status: str = Field(..., description="pending | partial | full | refunded | cancelled")
    payment_date: Optional[Timestamp] = None
    created_at: Timestamp
    updated_at: Timestamp


# ─────────────────────────────────────────────────────────────────────────────
# Document Schemas
# ─────────────────────────────────────────────────────────────────────────────

class DocumentBase(BaseModel):
    """Base document"""
    document_type: str = Field(
        ...,
        description="passport | photo | bank_statement | salary_certificate | hotel_booking | travel_insurance | visa | employment_letter"
    )
    file_name: Optional[str] = None
    file_size: Optional[int] = Field(None, ge=0, le=50_000_000)  # 50MB max


class DocumentResponse(DocumentBase):
    """Document response"""
    id: EntityID
    travel_request_id: EntityID
    client_user_id: EntityID
    status: str = Field(..., description="uploaded | under_review | approved | rejected | expired")
    reviewed_by: Optional[EntityID] = None
    reviewed_at: Optional[Timestamp] = None
    rejection_reason: Optional[str] = None
    created_at: Timestamp
    updated_at: Timestamp


# ─────────────────────────────────────────────────────────────────────────────
# Standard API Response Envelope
# ─────────────────────────────────────────────────────────────────────────────

class APIResponseMeta(BaseModel):
    """Response metadata"""
    timestamp: Timestamp = Field(default_factory=Timestamp.now)
    request_id: Optional[str] = None
    version: str = "1.0"


class APIResponseBase(BaseModel):
    """Base API response wrapper"""
    success: bool
    meta: APIResponseMeta = Field(default_factory=APIResponseMeta)
    message: Optional[str] = None


class APIListResponse(APIResponseBase):
    """List response with pagination"""
    data: list[dict]
    pagination: dict = Field(default_factory=dict)
    filters_applied: Optional[dict] = None


class APIErrorResponse(APIResponseBase):
    """Error response"""
    success: bool = False
    error_code: Optional[str] = None
    error_details: Optional[dict] = None


# ─────────────────────────────────────────────────────────────────────────────
# Serialization Helpers
# ─────────────────────────────────────────────────────────────────────────────

def serialize_price(price: Price | Decimal | float | int) -> str:
    """Serialize price to string with 2 decimal places"""
    return f"{Decimal(str(price)):.2f}"


def serialize_timestamp(ts: Timestamp | datetime) -> str:
    """Serialize timestamp to ISO 8601 format"""
    if isinstance(ts, Timestamp):
        return ts.to_iso()
    return Timestamp.from_datetime(ts).to_iso()


def serialize_entity_id(entity_id: EntityID | UUID | str) -> str:
    """Serialize entity ID to lowercase UUID string"""
    return str(entity_id).lower()
