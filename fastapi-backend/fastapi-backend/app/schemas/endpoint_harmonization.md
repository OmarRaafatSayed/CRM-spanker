# TASK 7: API Endpoint Schema Harmonization Guide

## Overview

All Portal and CRM endpoints now use strict, uniform type contracts enforced at the schema level:

```python
from app.schemas.unified_types import (
    FlightID, Price, Timestamp, EntityID,
    CustomerDetailsResponse, TravelRequestResponse, PaymentRecordResponse
)
```

---

## Type Contracts

### 1. Entity IDs: `EntityID`
**Format:** UUID v4 (lowercase)  
**Example:** `"550e8400-e29b-41d4-a716-446655440000"`  
**Validation:** Enforced by `EntityID` class

```python
# ✅ Valid
entity_id = EntityID("550e8400-e29b-41d4-a716-446655440000")

# ❌ Invalid
entity_id = EntityID("invalid-id")  # ValueError
```

### 2. Flight IDs: `FlightID`
**Format:** Airline code (2-3 letters) + Flight number (3-5 digits)  
**Example:** `"AA123"`, `"EK456"`, `"BA1234"`  
**Validation:** Regex enforced by `FlightID` class

```python
# ✅ Valid
flight_id = FlightID("AA123")
flight_id = FlightID("EK456")

# ❌ Invalid
flight_id = FlightID("invalid")  # ValueError
```

### 3. Prices: `Price`
**Format:** Decimal with up to 2 decimal places  
**Example:** `999.99`, `50.00`, `0.01`  
**Validation:** Enforced by `Price` class

```python
# ✅ Valid
price = Price("999.99")
price = Price(50)

# ❌ Invalid
price = Price("-50")  # ValueError (negative)
price = Price("999.999")  # ValueError (too many decimals)
```

### 4. Timestamps: `Timestamp`
**Format:** ISO 8601 UTC  
**Example:** `"2026-08-12T15:30:45Z"` or `"2026-08-12T15:30:45+00:00"`  
**Validation:** Always converted to UTC

```python
# ✅ Valid
ts = Timestamp.now()
ts = Timestamp.from_datetime(datetime.now())

# Serialization
ts.to_iso()  # "2026-08-12T15:30:45Z"
```

### 5. Dates: `str` (YYYY-MM-DD)
**Format:** `"2026-08-12"`  
**Validation:** Regex pattern enforced in request schemas

```python
# ✅ Valid in requests
{"departure_date": "2026-08-12"}

# ❌ Invalid
{"departure_date": "08-12-2026"}  # Wrong format
{"departure_date": "2026/08/12"}  # Wrong format
```

---

## Portal Endpoints (Customers)

### POST /api/v1/auth/signup
```python
# Request
{
  "email": "customer@example.com",  # str, required
  "password": "secure_password",    # str, required
  "first_name": "John",             # str, required
  "last_name": "Doe"                # str, required
}

# Response (201 Created)
{
  "success": true,
  "user": {
    "id": "550e8400-e29b-41d4-a716-446655440000",  # EntityID
    "email": "customer@example.com"
  },
  "session": {
    "access_token": "eyJ...",
    "refresh_token": "eyJ..."
  },
  "customer_profile_id": "550e8400-e29b-41d4-a716-446655440001",  # EntityID
  "email_confirmation_required": false,
  "message": "Signup successful."
}
```

### GET /api/v1/flights/search
```python
# Request
GET /api/v1/flights/search?origin_code=NYC&destination_code=LDN&departure_date=2026-09-01

# Response (200 OK)
{
  "success": true,
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",  # EntityID
      "outbound_segments": [
        {
          "flight_id": "AA123",                        # FlightID
          "airline_code": "AA",
          "airline_name": "American Airlines",
          "departure_time": "2026-09-01T08:00:00Z",  # Timestamp
          "arrival_time": "2026-09-01T22:00:00Z",    # Timestamp
          "duration_minutes": 480,
          "aircraft_type": "Boeing 777"
        }
      ],
      "price": {
        "amount": "999.99",                           # Price (Decimal string)
        "currency": "USD",
        "tax_amount": "99.99",
        "total_amount": "1099.98"
      },
      "seats_available": 5,
      "validity": "2026-08-20T23:59:59Z",           # Timestamp
      "booking_url": "https://..."
    }
  ],
  "pagination": {
    "limit": 50,
    "offset": 0,
    "total_count": 120
  }
}
```

### POST /api/v1/travel-requests
```python
# Request
{
  "destination_country": "Egypt",
  "travel_type": "visa_only",
  "departure_date": "2026-09-01",     # YYYY-MM-DD
  "return_date": "2026-09-15",        # YYYY-MM-DD
  "traveler_count": 2
}

# Response (201 Created)
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",    # EntityID
    "client_user_id": "550e8400-e29b-41d4-a716-446655440001",  # EntityID
    "destination_country": "Egypt",
    "travel_type": "visa_only",
    "status": "pending_documents",
    "departure_date": "2026-09-01",
    "return_date": "2026-09-15",
    "documents_completion_percent": 0,
    "created_at": "2026-08-12T15:30:45Z",           # Timestamp
    "updated_at": "2026-08-12T15:30:45Z"            # Timestamp
  }
}
```

### GET /api/v1/travel-requests/{request_id}
```python
# Response (200 OK)
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",    # EntityID
    "client_user_id": "550e8400-e29b-41d4-a716-446655440001",  # EntityID
    "destination_country": "Egypt",
    "travel_type": "visa_only",
    "status": "documents_review",
    "documents_completion_percent": 50,
    "created_at": "2026-08-12T15:30:45Z",           # Timestamp
    "updated_at": "2026-08-12T16:45:00Z"            # Timestamp
  }
}
```

### POST /api/v1/documents/upload
```python
# Request (multipart/form-data)
{
  "travel_request_id": "550e8400-e29b-41d4-a716-446655440000",  # EntityID
  "document_type": "passport",
  "file": <binary>
}

# Response (201 Created)
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",    # EntityID
    "travel_request_id": "550e8400-e29b-41d4-a716-446655440001",  # EntityID
    "client_user_id": "550e8400-e29b-41d4-a716-446655440002",  # EntityID
    "document_type": "passport",
    "file_name": "passport.pdf",
    "file_size": 1024000,
    "status": "uploaded",
    "created_at": "2026-08-12T15:30:45Z"            # Timestamp
  }
}
```

---

## CRM Endpoints (Staff)

### GET /api/v1/crm/customers
```python
# Request
GET /api/v1/crm/customers?status=active&kyc_status=pending&limit=50&offset=0

# Response (200 OK)
{
  "success": true,
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",    # EntityID
      "auth_user_id": "550e8400-e29b-41d4-a716-446655440001",  # EntityID
      "email": "customer@example.com",
      "first_name": "John",
      "last_name": "Doe",
      "phone": "+201234567890",
      "country": "Egypt",
      "status": "active",
      "kyc_status": "pending",
      "profile_completion_percent": 45,
      "crm_customer_id": "CRM-12345",  # EntityID (CRM reference)
      "created_at": "2026-08-12T15:30:45Z",           # Timestamp
      "updated_at": "2026-08-12T15:30:45Z"            # Timestamp
    }
  ],
  "pagination": {
    "total_count": 1250,
    "limit": 50,
    "offset": 0
  }
}
```

### GET /api/v1/crm/documents
```python
# Request
GET /api/v1/crm/documents?status=uploaded&limit=50

# Response (200 OK)
{
  "success": true,
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",    # EntityID
      "travel_request_id": "550e8400-e29b-41d4-a716-446655440001",  # EntityID
      "client_user_id": "550e8400-e29b-41d4-a716-446655440002",  # EntityID
      "document_type": "passport",
      "file_name": "passport.pdf",
      "file_size": 1024000,
      "status": "uploaded",
      "reviewed_by": null,
      "reviewed_at": null,
      "created_at": "2026-08-12T15:30:45Z"            # Timestamp
    }
  ],
  "pagination": {
    "total_count": 450,
    "pending_review_count": 120
  }
}
```

### PATCH /api/v1/crm/documents/{document_id}/status
```python
# Request
{
  "status": "approved"
}

# Response (200 OK)
{
  "success": true,
  "data": {
    "document_id": "550e8400-e29b-41d4-a716-446655440000",  # EntityID
    "new_status": "approved",
    "reviewed_by": "550e8400-e29b-41d4-a716-446655440099",  # EntityID (staff)
    "reviewed_at": "2026-08-12T16:00:00Z"                  # Timestamp
  }
}
```

### PATCH /api/v1/crm/travel-requests/{request_id}/status
```python
# Request
{
  "status": "in_progress",
  "staff_notes": "All documents approved. Processing visa now."
}

# Response (200 OK)
{
  "success": true,
  "data": {
    "request_id": "550e8400-e29b-41d4-a716-446655440000",  # EntityID
    "new_status": "in_progress",
    "updated_at": "2026-08-12T16:00:00Z"                  # Timestamp
  }
}
```

### GET /api/v1/crm/metrics
```python
# Response (200 OK)
{
  "success": true,
  "data": {
    "total_customers": 1250,
    "active_customers": 1150,
    "pending_kyc": 120,
    "total_travel_requests": 2500,
    "pending_documents": 450,
    "in_progress_requests": 280,
    "completed_requests": 1500,
    "pending_webhooks": 12,
    "pending_crm_syncs": 5,
    "snapshot_time": "2026-08-12T16:00:00Z"           # Timestamp
  }
}
```

---

## Error Response Format

All errors follow consistent format:

```python
# 400 Bad Request
{
  "success": false,
  "error_code": "VALIDATION_ERROR",
  "message": "Validation failed",
  "error_details": {
    "email": "Invalid email format",
    "departure_date": "Date must be YYYY-MM-DD format"
  }
}

# 401 Unauthorized
{
  "success": false,
  "error_code": "UNAUTHORIZED",
  "message": "Authentication required"
}

# 403 Forbidden
{
  "success": false,
  "error_code": "FORBIDDEN",
  "message": "Staff access required"
}

# 404 Not Found
{
  "success": false,
  "error_code": "NOT_FOUND",
  "message": "Customer not found",
  "error_details": {
    "customer_id": "550e8400-e29b-41d4-a716-446655440000"
  }
}

# 500 Internal Server Error
{
  "success": false,
  "error_code": "INTERNAL_ERROR",
  "message": "Internal server error"
}
```

---

## Schema Validation Rules

### Customer Details
- `first_name`: 1-100 chars, required
- `last_name`: 1-100 chars, required
- `email`: Valid format, lowercase, required, unique across system
- `phone`: Optional, 10-20 chars, only digits/+/-/()/, spaces
- `country`: Optional, 2-100 chars

### Travel Request
- `destination_country`: Required, 2-100 chars
- `travel_type`: One of: visa_only, visa_flight, visa_hotel, full_package
- `departure_date`: YYYY-MM-DD format, optional
- `return_date`: YYYY-MM-DD format, optional, must be >= departure_date
- `traveler_count`: 1-50 (default: 1)

### Payment Record
- `amount`: Positive, ≤ 2 decimal places, required
- `currency`: 3-char ISO code (default: USD)
- `payment_method`: One of: cash, bank, pos, cheque, card
- `status`: One of: pending, partial, full, refunded, cancelled

### Document
- `document_type`: One of: passport, photo, bank_statement, salary_certificate, hotel_booking, travel_insurance, visa, employment_letter
- `file_name`: Optional, max 255 chars
- `file_size`: Optional, 0-50MB
- `status`: One of: uploaded, under_review, approved, rejected, expired

---

## Integration Checklist

- [x] Type contracts defined in `app/schemas/unified_types.py`
- [x] Auth context with role-based access in `app/core/auth_context.py`
- [x] Portal endpoints updated to use schemas
- [x] CRM endpoints updated to use schemas
- [x] Error responses standardized
- [x] API documentation generated from schemas
- [x] Request validation enforced at schema level
- [x] Response serialization consistent across all endpoints

---

## Usage in Endpoints

```python
from fastapi import APIRouter, Depends, HTTPException
from app.core.auth_context import AuthContext, check_permission
from app.schemas.unified_types import (
    EntityID, Price, Timestamp,
    CustomerDetailsResponse, TravelRequestResponse
)

router = APIRouter()

@router.get("/customers/{customer_id}", response_model=CustomerDetailsResponse)
async def get_customer(
    customer_id: EntityID,  # Automatically validated
    context: AuthContext = Depends(require_auth)
) -> CustomerDetailsResponse:
    """Get customer profile with unified types"""
    
    # Access control
    if not context.can_view_customer(customer_id):
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Return response (automatically serialized with correct types)
    return CustomerDetailsResponse(
        id=customer_id,
        auth_user_id=customer.auth_user_id,
        email=customer.email,
        first_name=customer.first_name,
        last_name=customer.last_name,
        status="active",
        kyc_status="verified",
        created_at=Timestamp.from_datetime(customer.created_at),
        updated_at=Timestamp.from_datetime(customer.updated_at)
    )
```

---

## Migration Guide

### Updating Existing Endpoints

**Before:**
```python
@router.get("/customers/{customer_id}")
async def get_customer(customer_id: str) -> dict:
    return {
        "id": customer_id,
        "email": "test@example.com",
        "price": 999.99,  # float
        "created_at": "2026-08-12 15:30:45"  # inconsistent format
    }
```

**After:**
```python
from app.schemas.unified_types import (
    EntityID, Price, Timestamp, CustomerDetailsResponse
)

@router.get("/customers/{customer_id}", response_model=CustomerDetailsResponse)
async def get_customer(customer_id: EntityID) -> CustomerDetailsResponse:  # Validated
    return CustomerDetailsResponse(
        id=customer_id,
        email="test@example.com",
        price=Price("999.99"),  # Decimal
        created_at=Timestamp.now()  # UTC ISO 8601
    )
```

---

## Frontend Integration

### Type Safety

```typescript
// TypeScript types auto-generated from Pydantic schemas
interface CustomerDetailsResponse {
  id: string;  // UUID v4
  auth_user_id: string;  // UUID v4
  email: string;
  first_name: string;
  last_name: string;
  status: "active" | "inactive" | "suspended";
  kyc_status: "pending" | "verified" | "rejected";
  created_at: string;  // ISO 8601
  updated_at: string;  // ISO 8601
}

// Type-safe API calls
const customer: CustomerDetailsResponse = await fetch(
  `/api/v1/crm/customers/${customerId}`
).then(r => r.json());
```

### Validation on Frontend

```typescript
function validatePrice(price: string): Price {
  const amount = parseFloat(price);
  if (amount < 0 || amount % 0.01 !== 0) {
    throw new Error("Invalid price format");
  }
  return amount.toFixed(2) as Price;
}

function formatPrice(price: string | number): string {
  return `${parseFloat(price).toFixed(2)}`;
}
```

