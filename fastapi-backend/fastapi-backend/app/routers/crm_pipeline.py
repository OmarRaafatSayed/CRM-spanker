"""
CRM Data Pipeline Router

معالجة كل مراحل Data Pipeline:
1. User Registration (Lead Ingestion)
2. Visa Document Upload & Status Updates
3. Quotation Generation & Approval
4. Booking Creation from Quotation
5. Payment Recording & Voucher Generation

State Machine Transitions مع Real-time Notifications
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.security import AuthContext, require_auth
from app.services.supabase_client import get_supabase

logger = logging.getLogger(__name__)
router = APIRouter()


# ─── Request/Response Schemas ─────────────────────────────────────────────────

class DocumentUpload(BaseModel):
    """تحميل مستند"""
    doc_type: str = Field(..., description="PASSPORT, ID_CARD, BANK_STATEMENT, etc.")
    file_url: str = Field(..., description="URL of uploaded file in storage")
    file_size: int = Field(..., ge=0)


class VisaApplicationRequest(BaseModel):
    """طلب تأشيرة جديد"""
    country_code: str = Field(..., description="AE, DE, TR, EG, KSA")
    visa_type: Optional[str] = None
    documents: List[DocumentUpload] = []


class VisaApplicationResponse(BaseModel):
    """استجابة طلب التأشيرة"""
    id: str
    user_id: str
    country_code: str
    status: str
    documents: List[Dict[str, Any]]
    created_at: str
    updated_at: str


class QuotationItem(BaseModel):
    """عنصر في العرض"""
    type: str = Field(..., description="FLIGHT, VISA_FEE, SERVICE_FEE, HOTEL")
    description: str
    amount: float


class CreateQuotationRequest(BaseModel):
    """إنشاء عرض سعر"""
    visa_application_id: Optional[str] = None
    items: List[QuotationItem]
    total_amount: float
    currency: str = "EGP"
    notes: Optional[str] = None


class QuotationResponse(BaseModel):
    """استجابة العرض"""
    id: str
    user_id: str
    status: str
    items: List[Dict[str, Any]]
    total_amount: float
    currency: str
    created_at: str
    valid_until: Optional[str] = None


class BookingResponse(BaseModel):
    """استجابة الحجز"""
    id: str
    user_id: str
    booking_reference: str
    status: str
    voucher_url: Optional[str] = None
    created_at: str


class PaymentRequest(BaseModel):
    """تسجيل دفع"""
    amount_paid: float
    payment_method: str = Field(..., description="CASH, BANK_TRANSFER, POS, CREDIT_CARD, CHEQUE")
    receipt_url: Optional[str] = None
    receipt_number: Optional[str] = None


class PaymentResponse(BaseModel):
    """استجابة الدفع"""
    transaction_id: str
    amount_paid: float
    remaining_balance: float
    booking_status: str
    voucher_url: Optional[str] = None


class StateTransitionLog(BaseModel):
    """سجل انتقال الحالة"""
    entity_type: str
    entity_id: str
    previous_state: Optional[str]
    new_state: str
    event_type: str
    triggered_by: str
    created_at: str


# ─── Endpoints ───────────────────────────────────────────────────────────────

# 1. USER REGISTRATION - Lead Ingestion
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/users/register")
async def register_user(
    context: AuthContext = Depends(require_auth),
    supabase: Any = Depends(get_supabase),
) -> Dict[str, Any]:
    """
    Create lead from user registration
    
    Status: LEAD
    Trigger: UserRegistered event
    Notification: Welcome message
    """
    try:
        # Call PostgreSQL function
        response = supabase.rpc(
            "create_lead_from_user",
            {
                "p_auth_user_id": context.user_id,
                "p_email": context.email,
                "p_first_name": context.first_name,
                "p_last_name": context.last_name,
            }
        ).execute()

        user_id = response.data if response.data else None

        logger.info(f"✅ Lead created: {user_id} ({context.email})")

        return {
            "success": True,
            "user_id": user_id,
            "status": "LEAD",
            "message": "Welcome! Your profile has been created."
        }

    except Exception as exc:
        logger.error(f"❌ Lead creation failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user profile"
        )


# 2. VISA APPLICATION - Document Upload & Status Tracking
# ─────────────────────────────────────────────────────────────────────────────

# ─── Helper Functions (Single Responsibility) ────────────────────────────────

async def _get_user_id_by_auth_user(
    auth_user_id: str,
    supabase: Any,
) -> str:
    """Get user_id from auth_user_id. Raises 404 if not found."""
    user_response = supabase.table("users").select("id").eq(
        "auth_user_id", auth_user_id
    ).limit(1).execute()

    if not user_response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return user_response.data[0]["id"]


def _build_document_records(documents: List[DocumentUpload]) -> List[Dict[str, Any]]:
    """Transform DocumentUpload objects into JSONB-ready records."""
    return [
        {
            "doc_type": doc.doc_type,
            "file_url": doc.file_url,
            "file_size": doc.file_size,
            "status": "UPLOADED",
            "uploaded_at": datetime.now(timezone.utc).isoformat()
        }
        for doc in documents
    ]


# ─────────────────────────────────────────────────────────────────────────────

@router.post("/visa-applications", response_model=VisaApplicationResponse)
async def create_visa_application(
    request: VisaApplicationRequest,
    context: AuthContext = Depends(require_auth),
    supabase: Any = Depends(get_supabase),
) -> VisaApplicationResponse:
    """
    Create visa application with initial documents
    
    Status: DOCS_PENDING
    Trigger: Documents stored as JSONB array
    Notification: Confirmation sent to user
    """
    try:
        # Step 1: Get user_id
        user_id = await _get_user_id_by_auth_user(context.user_id, supabase)

        # Step 2: Build documents array
        documents = _build_document_records(request.documents)

        # Step 3: Create visa application
        response = supabase.table("visa_applications").insert({
            "user_id": user_id,
            "country_code": request.country_code,
            "visa_type": request.visa_type,
            "documents": documents,
            "status": "DOCS_PENDING",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).execute()

        if not response.data:
            raise Exception("No data returned from insert")

        visa_app = response.data[0]

        logger.info(f"✅ Visa application created: {visa_app['id']}")

        return VisaApplicationResponse(**visa_app)

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"❌ Visa application creation failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create visa application"
        )


@router.get("/visa-applications/{visa_id}")
async def get_visa_application(
    visa_id: str,
    context: AuthContext = Depends(require_auth),
    supabase: Any = Depends(get_supabase),
) -> VisaApplicationResponse:
    """
    Get visa application with current status
    """
    try:
        response = supabase.table("visa_applications").select("*").eq(
            "id", visa_id
        ).limit(1).execute()

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Visa application not found"
            )

        visa_app = response.data[0]

        # Check authorization
        if not context.can_view_customer(visa_app["user_id"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        return VisaApplicationResponse(**visa_app)

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"❌ Failed to get visa application: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve visa application"
        )


@router.patch("/visa-applications/{visa_id}/status")
async def update_visa_status(
    visa_id: str,
    new_status: str = Query(..., description="DOCS_PENDING, UNDER_REVIEW, SUBMITTED_TO_EMBASSY, APPROVED, REJECTED"),
    context: AuthContext = Depends(require_auth),
    supabase: Any = Depends(get_supabase),
) -> Dict[str, Any]:
    """
    Update visa status (Staff only)
    
    State Transitions:
    DOCS_PENDING → UNDER_REVIEW → SUBMITTED_TO_EMBASSY → APPROVED/REJECTED
    
    Trigger: update_visa_status() function
    Notification: Sent to user automatically
    """
    if not context.is_staff:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff access required"
        )

    try:
        # Call PostgreSQL function
        supabase.rpc(
            "update_visa_status",
            {
                "p_visa_id": visa_id,
                "p_new_status": new_status,
                "p_triggered_by": "CRM_STAFF"
            }
        ).execute()

        logger.info(f"✅ Visa status updated: {visa_id} → {new_status}")

        return {
            "success": True,
            "visa_id": visa_id,
            "new_status": new_status,
            "message": "Status updated and notification sent to user"
        }

    except Exception as exc:
        logger.error(f"❌ Failed to update visa status: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update visa status"
        )


# 3. QUOTATION - Generation & Approval
# ─────────────────────────────────────────────────────────────────────────────

# ─── Helper: Extract Quotation Response ───────────────────────────────────

async def _fetch_quotation_response(
    quote_id: str,
    supabase: Any,
) -> QuotationResponse:
    """Fetch a quotation by ID and transform to response model."""
    response = supabase.table("quotations").select("*").eq(
        "id", quote_id
    ).limit(1).execute()

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quotation not found"
        )

    return QuotationResponse(**response.data[0])


# ─────────────────────────────────────────────────────────────────────────────

@router.post("/quotations", response_model=QuotationResponse)
async def create_quotation(
    request: CreateQuotationRequest,
    context: AuthContext = Depends(require_auth),
    supabase: Any = Depends(get_supabase),
) -> QuotationResponse:
    """
    Create quotation (Staff)
    
    Status: DRAFT
    Trigger: Quotation stored with itemized pricing
    Notification: None until sent
    """
    if not context.is_staff:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff access required"
        )

    try:
        # Get user_id
        user_id = await _get_user_id_by_auth_user(context.user_id, supabase)

        # Call PostgreSQL function to create quotation
        quote_response = supabase.rpc(
            "create_quotation",
            {
                "p_user_id": user_id,
                "p_visa_app_id": request.visa_application_id,
                "p_items": [item.model_dump() for item in request.items],
                "p_total_amount": request.total_amount,
                "p_currency": request.currency
            }
        ).execute()

        quote_id = quote_response.data if quote_response.data else None
        if not quote_id:
            raise Exception("No quotation ID returned")

        logger.info(f"✅ Quotation created: {quote_id}")

        # Fetch and return full quotation
        return await _fetch_quotation_response(quote_id, supabase)

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"❌ Failed to create quotation: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create quotation"
        )


@router.post("/quotations/{quote_id}/send")
async def send_quotation(
    quote_id: str,
    context: AuthContext = Depends(require_auth),
    supabase: Any = Depends(get_supabase),
) -> Dict[str, Any]:
    """
    Send quotation to customer
    
    Status: DRAFT → SENT
    Trigger: send_quotation() function
    Notification: "Quotation sent - Review and accept"
    """
    if not context.is_staff:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff access required"
        )

    try:
        supabase.rpc(
            "send_quotation",
            {"p_quote_id": quote_id}
        ).execute()

        logger.info(f"✅ Quotation sent: {quote_id}")

        return {
            "success": True,
            "quote_id": quote_id,
            "status": "SENT",
            "message": "Quotation sent to customer"
        }

    except Exception as exc:
        logger.error(f"❌ Failed to send quotation: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send quotation"
        )


@router.post("/quotations/{quote_id}/accept")
async def accept_quotation(
    quote_id: str,
    context: AuthContext = Depends(require_auth),
    supabase: Any = Depends(get_supabase),
) -> BookingResponse:
    """
    Accept quotation and create booking
    
    Status: SENT → ACCEPTED → BOOKING CREATED (PENDING_PAYMENT)
    Trigger: accept_quotation_and_create_booking() function
    Notification: "Booking confirmed - Proceed with payment"
    """
    try:
        # Call PostgreSQL function - returns booking_id
        booking_response = supabase.rpc(
            "accept_quotation_and_create_booking",
            {"p_quote_id": quote_id}
        ).execute()

        booking_id = booking_response.data if booking_response.data else None
        if not booking_id:
            raise Exception("No booking ID returned from RPC")

        logger.info(f"✅ Booking created from quotation: {booking_id}")

        # Fetch and return booking response
        booking_data = supabase.table("bookings").select("*").eq(
            "id", booking_id
        ).limit(1).execute()

        if booking_data.data:
            return BookingResponse(**booking_data.data[0])

        raise Exception("Booking not found after creation")

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"❌ Failed to accept quotation: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to accept quotation"
        )


# 4. BOOKING & PAYMENT - Confirmation & Voucher Generation
# ─────────────────────────────────────────────────────────────────────────────

# ─── Helper: Extract Payment Data ─────────────────────────────────────────

async def _fetch_payment_response(
    transaction_id: str,
    booking_id: str,
    supabase: Any,
) -> PaymentResponse:
    """Fetch payment and booking data, transform to response."""
    trans_data = supabase.table("financial_transactions").select("*").eq(
        "id", transaction_id
    ).limit(1).execute()

    booking_data = supabase.table("bookings").select("*").eq(
        "id", booking_id
    ).limit(1).execute()

    if not trans_data.data or not booking_data.data:
        raise Exception("Transaction or booking not found after payment")

    transaction = trans_data.data[0]
    booking = booking_data.data[0]

    return PaymentResponse(
        transaction_id=transaction_id,
        amount_paid=transaction.get("amount_paid", 0),
        remaining_balance=transaction.get("remaining_balance", 0),
        booking_status=booking.get("status"),
        voucher_url=booking.get("voucher_url")
    )


# ─────────────────────────────────────────────────────────────────────────────

@router.post("/bookings/{booking_id}/payment")
async def record_payment(
    booking_id: str,
    request: PaymentRequest,
    context: AuthContext = Depends(require_auth),
    supabase: Any = Depends(get_supabase),
) -> PaymentResponse:
    """
    Record payment and generate voucher
    
    Status: PENDING_PAYMENT → CONFIRMED (if fully paid)
    Trigger: record_payment_and_generate_voucher() function
    Notification: "Payment received - Voucher ready"
    """
    if not context.is_staff:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff access required"
        )

    try:
        # Get financial transaction linked to booking
        trans_response = supabase.table("financial_transactions").select("*").eq(
            "booking_id", booking_id
        ).limit(1).execute()

        if not trans_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transaction not found"
            )

        transaction_id = trans_response.data[0]["id"]

        # Call PostgreSQL function to record payment and generate voucher
        supabase.rpc(
            "record_payment_and_generate_voucher",
            {
                "p_transaction_id": transaction_id,
                "p_amount_paid": request.amount_paid,
                "p_payment_method": request.payment_method,
                "p_receipt_url": request.receipt_url
            }
        ).execute()

        logger.info(f"✅ Payment recorded for booking: {booking_id}")

        # Fetch and return updated payment response
        return await _fetch_payment_response(transaction_id, booking_id, supabase)

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"❌ Failed to record payment: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record payment"
        )


# 5. STATE MACHINE & AUDIT LOG
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/state-transitions")
async def get_state_transitions(
    entity_type: str = Query(...),
    entity_id: str = Query(...),
    context: AuthContext = Depends(require_auth),
    supabase: Any = Depends(get_supabase),
    limit: int = Query(50, ge=1, le=200)
) -> List[StateTransitionLog]:
    """
    Get state transition audit trail for any entity
    """
    try:
        response = supabase.table("state_machine_events").select("*").eq(
            "entity_type", entity_type
        ).eq("entity_id", entity_id).order(
            "created_at", desc=True
        ).limit(limit).execute()

        return [StateTransitionLog(**event) for event in response.data or []]

    except Exception as exc:
        logger.error(f"❌ Failed to get state transitions: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve state transitions"
        )


@router.get("/health")
async def crm_pipeline_health() -> Dict[str, Any]:
    """Health check for CRM pipeline"""
    return {"status": "operational", "service": "crm_pipeline"}
