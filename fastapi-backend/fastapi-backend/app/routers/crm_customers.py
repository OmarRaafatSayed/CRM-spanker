"""
CRM Customer Management - Full Implementation

Implements the complete data pipeline from CRM-RULES.MD:
1. Customer list with filtering
2. Document tracking and approval
3. Quotation management
4. Booking and payment tracking
5. Real-time metrics
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.security import AuthToken, require_auth
from app.services.supabase_client import get_supabase
from app.services.notification_service import (
    notify_customer,
    get_customer_auth_id_from_users_row,
    visa_status_str_changed,
    quotation_status_changed,
    booking_status_changed,
    booking_confirmed,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ─── Constants ────────────────────────────────────────────────────────────────

_VALID_DOC_STATUSES = frozenset({"uploaded", "under_review", "approved", "rejected", "expired"})
_VALID_REQUEST_STATUSES = frozenset({
    "pending_documents", "documents_review", "docs_approved", "in_progress", "completed", "cancelled"
})

_USER_STATUSES = frozenset({"LEAD", "ACTIVE_CLIENT", "INACTIVE"})
_VISA_STATUSES = frozenset({"DOCS_PENDING", "UNDER_REVIEW", "SUBMITTED_TO_EMBASSY", "APPROVED", "REJECTED"})
_QUOTATION_STATUSES = frozenset({"DRAFT", "SENT", "ACCEPTED", "EXPIRED", "REJECTED"})
_BOOKING_STATUSES = frozenset({"PENDING_PAYMENT", "CONFIRMED", "CANCELLED", "COMPLETED"})
_PAYMENT_METHODS = frozenset({"CASH", "BANK_TRANSFER", "POS"})


# ─── Schemas ──────────────────────────────────────────────────────────────────

class CustomerProfileResponse(BaseModel):
    id: str; auth_user_id: str; email: str; phone: Optional[str] = None
    full_name: Optional[str] = None; passport_number: Optional[str] = None
    status: str; created_at: Optional[str] = None
    model_config = {"extra": "allow"}

class DocumentResponse(BaseModel):
    id: str; visa_application_id: str; doc_type: str; url: str; status: str
    created_at: Optional[str] = None
    model_config = {"extra": "allow"}

class VisaApplicationResponse(BaseModel):
    id: str; user_id: str; country_code: str; status: str
    documents: List[Dict[str, Any]] = []
    created_at: Optional[str] = None
    model_config = {"extra": "allow"}

class QuotationResponse(BaseModel):
    id: str; user_id: str; visa_application_id: Optional[str] = None
    items: List[Dict[str, Any]] = []; total_amount: float; currency: str = "EGP"
    status: str; created_at: Optional[str] = None
    model_config = {"extra": "allow"}

class BookingResponse(BaseModel):
    id: str; user_id: str; quotation_id: str; booking_reference: str
    status: str; created_at: Optional[str] = None
    model_config = {"extra": "allow"}

class TransactionResponse(BaseModel):
    id: str; booking_id: str; user_id: str; amount_paid: float
    remaining_balance: float; payment_method: str; receipt_url: Optional[str] = None
    paid_at: Optional[str] = None
    model_config = {"extra": "allow"}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _require_staff(token: AuthToken) -> AuthToken:
    """Staff-only access"""
    if token.role not in ("staff", "admin"):
        raise HTTPException(status_code=403, detail="Staff access required")
    return token

def _get_profile_id(supabase: Any, auth_user_id: str) -> Optional[str]:
    """Get profile ID from auth user ID"""
    try:
        r = supabase.table("profiles").select("id").eq("user_id", auth_user_id).limit(1).execute()
        return str(r.data[0]["id"]) if r.data else None
    except:
        return None


# ─── CUSTOMERS ENDPOINTS ──────────────────────────────────────────────────────



@router.get("/health")
async def crm_health(supabase: Any = Depends(get_supabase)):
    """Health check for CRM - returns customer count"""
    try:
        # Simple query to check if users table exists and count records
        response = supabase.table("users").select("*", count="exact").execute()
        total_users = response.count or 0
        logger.info(f"[crm_health] Total users: {total_users}")
        return {
            "status": "healthy",
            "service": "crm_customers",
            "total_users": total_users,
            "database": "connected",
            "endpoint": "crm_customers_health"
        }
    except Exception as e:
        logger.error(f"[crm_health] CRM health check failed: {e}")
        return {
            "status": "error",
            "service": "crm_customers",
            "error": str(e),
            "endpoint": "crm_customers_health"
        }

@router.get("/test-endpoint")
async def test_endpoint(supabase: Any = Depends(get_supabase)):
    """Test endpoint to verify routing is working"""
    return {
        "message": "CRM test endpoint working",
        "timestamp": datetime.utcnow().isoformat()
    }

@router.get("/customers", response_model=Dict[str, Any])
async def list_customers(
    token: AuthToken = Depends(require_auth),
    supabase: Any = Depends(get_supabase),
    status_filter: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List all customers with status filter"""
    _require_staff(token)
    try:
        q = supabase.table("users").select("*", count="exact")
        if status_filter and status_filter in _USER_STATUSES:
            q = q.eq("status", status_filter)
        q = q.order("created_at", desc=True).range(offset, offset + limit - 1)
        r = q.execute()
        return {"customers": r.data or [], "total": r.count or 0, "filters": {"status": status_filter}}
    except Exception as e:
        logger.error(f"List customers failed: {e}")
        raise HTTPException(500, str(e))

@router.get("/customers/{customer_id}", response_model=CustomerProfileResponse)
async def get_customer(
    customer_id: str,
    token: AuthToken = Depends(require_auth),
    supabase: Any = Depends(get_supabase),
):
    """Get customer profile"""
    _require_staff(token)
    try:
        r = supabase.table("users").select("*").eq("id", customer_id).limit(1).execute()
        if not r.data:
            raise HTTPException(404, "Customer not found")
        return CustomerProfileResponse(**r.data[0])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


# ─── VISA APPLICATIONS ENDPOINTS ──────────────────────────────────────────────

@router.get("/visa-applications", response_model=Dict[str, Any])
async def list_visa_applications(
    token: AuthToken = Depends(require_auth),
    supabase: Any = Depends(get_supabase),
    status_filter: Optional[str] = Query(None),
    country_code: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List visa applications with filters"""
    _require_staff(token)
    try:
        q = supabase.table("visa_applications").select("*", count="exact")
        if status_filter and status_filter in _VISA_STATUSES:
            q = q.eq("status", status_filter)
        if country_code:
            q = q.eq("country_code", country_code)
        q = q.order("created_at", desc=True).range(offset, offset + limit - 1)
        r = q.execute()
        return {"applications": r.data or [], "total": r.count or 0}
    except Exception as e:
        raise HTTPException(500, str(e))

@router.get("/visa-applications/{app_id}", response_model=VisaApplicationResponse)
async def get_visa_application(
    app_id: str,
    token: AuthToken = Depends(require_auth),
    supabase: Any = Depends(get_supabase),
):
    """Get visa application with documents"""
    _require_staff(token)
    try:
        r = supabase.table("visa_applications").select("*").eq("id", app_id).limit(1).execute()
        if not r.data:
            raise HTTPException(404, "Application not found")
        return VisaApplicationResponse(**r.data[0])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

@router.patch("/visa-applications/{app_id}/status")
async def update_visa_status(
    app_id: str,
    new_status: str = Query(...),
    token: AuthToken = Depends(require_auth),
    supabase: Any = Depends(get_supabase),
):
    """Update visa application status"""
    _require_staff(token)
    if new_status not in _VISA_STATUSES:
        raise HTTPException(400, f"Invalid status: {new_status}")
    try:
        r = supabase.table("visa_applications").update({"status": new_status}).eq("id", app_id).execute()
        if not r.data:
            raise HTTPException(404, "Application not found")
        logger.info(f"[crm] Updated visa {app_id} status to {new_status}")

        # ── Portal notification ───────────────────────────────────────────────
        # visa_applications.user_id points to the CRM 'users' table,
        # which carries auth_user_id → auth.users.id for the customer.
        user_id = r.data[0].get("user_id")
        if user_id:
            customer_auth_id = get_customer_auth_id_from_users_row(supabase, user_id)
            if customer_auth_id:
                await notify_customer(
                    supabase=supabase,
                    customer_auth_id=customer_auth_id,
                    **visa_status_str_changed(app_id, new_status),
                )
        # ─────────────────────────────────────────────────────────────────────

        return {"success": True, "application_id": app_id, "new_status": new_status}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


# ─── QUOTATIONS ENDPOINTS ─────────────────────────────────────────────────────

@router.get("/quotations", response_model=Dict[str, Any])
async def list_quotations(
    token: AuthToken = Depends(require_auth),
    supabase: Any = Depends(get_supabase),
    status_filter: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List quotations"""
    _require_staff(token)
    try:
        q = supabase.table("quotations").select("*", count="exact")
        if status_filter and status_filter in _QUOTATION_STATUSES:
            q = q.eq("status", status_filter)
        q = q.order("created_at", desc=True).range(offset, offset + limit - 1)
        r = q.execute()
        return {"quotations": r.data or [], "total": r.count or 0}
    except Exception as e:
        raise HTTPException(500, str(e))

@router.get("/quotations/{quote_id}", response_model=QuotationResponse)
async def get_quotation(
    quote_id: str,
    token: AuthToken = Depends(require_auth),
    supabase: Any = Depends(get_supabase),
):
    """Get quotation details"""
    _require_staff(token)
    try:
        r = supabase.table("quotations").select("*").eq("id", quote_id).limit(1).execute()
        if not r.data:
            raise HTTPException(404, "Quotation not found")
        return QuotationResponse(**r.data[0])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

@router.patch("/quotations/{quote_id}/status")
async def update_quotation_status(
    quote_id: str,
    new_status: str = Query(...),
    token: AuthToken = Depends(require_auth),
    supabase: Any = Depends(get_supabase),
):
    """Update quotation status"""
    _require_staff(token)
    if new_status not in _QUOTATION_STATUSES:
        raise HTTPException(400, f"Invalid status: {new_status}")
    try:
        r = supabase.table("quotations").update({"status": new_status}).eq("id", quote_id).execute()
        if not r.data:
            raise HTTPException(404, "Quotation not found")
        logger.info(f"[crm] Updated quotation {quote_id} status to {new_status}")

        # ── Portal notification ───────────────────────────────────────────────
        user_id = r.data[0].get("user_id")
        if user_id:
            customer_auth_id = get_customer_auth_id_from_users_row(supabase, user_id)
            if customer_auth_id:
                await notify_customer(
                    supabase=supabase,
                    customer_auth_id=customer_auth_id,
                    **quotation_status_changed(quote_id, new_status),
                )
        # ─────────────────────────────────────────────────────────────────────

        return {"success": True, "quotation_id": quote_id, "new_status": new_status}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


# ─── BOOKINGS ENDPOINTS ───────────────────────────────────────────────────────

@router.get("/bookings", response_model=Dict[str, Any])
async def list_bookings(
    token: AuthToken = Depends(require_auth),
    supabase: Any = Depends(get_supabase),
    status_filter: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List bookings"""
    _require_staff(token)
    try:
        q = supabase.table("bookings").select("*", count="exact")
        if status_filter and status_filter in _BOOKING_STATUSES:
            q = q.eq("status", status_filter)
        q = q.order("created_at", desc=True).range(offset, offset + limit - 1)
        r = q.execute()
        return {"bookings": r.data or [], "total": r.count or 0}
    except Exception as e:
        raise HTTPException(500, str(e))

@router.get("/bookings/{booking_id}", response_model=BookingResponse)
async def get_booking(
    booking_id: str,
    token: AuthToken = Depends(require_auth),
    supabase: Any = Depends(get_supabase),
):
    """Get booking details"""
    _require_staff(token)
    try:
        r = supabase.table("bookings").select("*").eq("id", booking_id).limit(1).execute()
        if not r.data:
            raise HTTPException(404, "Booking not found")
        return BookingResponse(**r.data[0])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

@router.patch("/bookings/{booking_id}/status")
async def update_booking_status(
    booking_id: str,
    new_status: str = Query(...),
    token: AuthToken = Depends(require_auth),
    supabase: Any = Depends(get_supabase),
):
    """Update booking status"""
    _require_staff(token)
    if new_status not in _BOOKING_STATUSES:
        raise HTTPException(400, f"Invalid status: {new_status}")
    try:
        r = supabase.table("bookings").update({"status": new_status}).eq("id", booking_id).execute()
        if not r.data:
            raise HTTPException(404, "Booking not found")
        logger.info(f"[crm] Updated booking {booking_id} status to {new_status}")

        # ── Portal notification ───────────────────────────────────────────────
        user_id = r.data[0].get("user_id")
        if user_id:
            customer_auth_id = get_customer_auth_id_from_users_row(supabase, user_id)
            if customer_auth_id:
                # Use the richer "booking confirmed" message when status = CONFIRMED
                if new_status == "CONFIRMED":
                    booking_ref = r.data[0].get("booking_reference", booking_id[:8])
                    await notify_customer(
                        supabase=supabase,
                        customer_auth_id=customer_auth_id,
                        **booking_confirmed(booking_id, booking_ref),
                    )
                else:
                    await notify_customer(
                        supabase=supabase,
                        customer_auth_id=customer_auth_id,
                        **booking_status_changed(booking_id, new_status),
                    )
        # ─────────────────────────────────────────────────────────────────────

        return {"success": True, "booking_id": booking_id, "new_status": new_status}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


# ─── PAYMENTS ENDPOINTS ───────────────────────────────────────────────────────

@router.get("/transactions", response_model=Dict[str, Any])
async def list_transactions(
    token: AuthToken = Depends(require_auth),
    supabase: Any = Depends(get_supabase),
    booking_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List financial transactions"""
    _require_staff(token)
    try:
        q = supabase.table("financial_transactions").select("*", count="exact")
        if booking_id:
            q = q.eq("booking_id", booking_id)
        q = q.order("created_at", desc=True).range(offset, offset + limit - 1)
        r = q.execute()
        return {"transactions": r.data or [], "total": r.count or 0}
    except Exception as e:
        raise HTTPException(500, str(e))

@router.get("/transactions/{trans_id}", response_model=TransactionResponse)
async def get_transaction(
    trans_id: str,
    token: AuthToken = Depends(require_auth),
    supabase: Any = Depends(get_supabase),
):
    """Get transaction details"""
    _require_staff(token)
    try:
        r = supabase.table("financial_transactions").select("*").eq("id", trans_id).limit(1).execute()
        if not r.data:
            raise HTTPException(404, "Transaction not found")
        return TransactionResponse(**r.data[0])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

@router.patch("/transactions/{trans_id}/payment")
async def record_payment(
    trans_id: str,
    amount_paid: float = Query(..., gt=0),
    payment_method: str = Query(...),
    receipt_url: Optional[str] = Query(None),
    token: AuthToken = Depends(require_auth),
    supabase: Any = Depends(get_supabase),
):
    """Record payment for transaction"""
    _require_staff(token)
    if payment_method not in _PAYMENT_METHODS:
        raise HTTPException(400, f"Invalid payment method: {payment_method}")
    try:
        # Get transaction
        r = supabase.table("financial_transactions").select("*").eq("id", trans_id).limit(1).execute()
        if not r.data:
            raise HTTPException(404, "Transaction not found")
        trans = r.data[0]
        
        remaining = trans.get("remaining_balance", 0) - amount_paid
        remaining = max(0, remaining)  # Don't go below 0
        
        # Update transaction
        update_data = {
            "amount_paid": trans.get("amount_paid", 0) + amount_paid,
            "remaining_balance": remaining,
            "payment_method": payment_method,
            "receipt_url": receipt_url,
            "paid_at": datetime.utcnow().isoformat(),
        }
        
        upd_r = supabase.table("financial_transactions").update(update_data).eq("id", trans_id).execute()
        
        # Update booking status if fully paid
        if remaining <= 0:
            booking_id = trans.get("booking_id")
            supabase.table("bookings").update({"status": "CONFIRMED"}).eq("id", booking_id).execute()
        
        logger.info(f"[crm] Recorded payment {amount_paid} for transaction {trans_id}")
        return {"success": True, "transaction_id": trans_id, "amount_paid": amount_paid}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


# ─── METRICS ENDPOINT ─────────────────────────────────────────────────────────

@router.get("/metrics", response_model=Dict[str, Any])
async def get_crm_metrics(
    token: AuthToken = Depends(require_auth),
    supabase: Any = Depends(get_supabase),
):
    """Get CRM dashboard metrics"""
    _require_staff(token)
    try:
        # Count customers by status
        lead_r = supabase.table("users").select("id", count="exact").eq("status", "LEAD").execute()
        active_r = supabase.table("users").select("id", count="exact").eq("status", "ACTIVE_CLIENT").execute()
        
        # Visa statuses
        docs_r = supabase.table("visa_applications").select("id", count="exact").eq("status", "DOCS_PENDING").execute()
        review_r = supabase.table("visa_applications").select("id", count="exact").eq("status", "UNDER_REVIEW").execute()
        approved_r = supabase.table("visa_applications").select("id", count="exact").eq("status", "APPROVED").execute()
        
        # Quotations
        draft_r = supabase.table("quotations").select("id", count="exact").eq("status", "DRAFT").execute()
        sent_r = supabase.table("quotations").select("id", count="exact").eq("status", "SENT").execute()
        
        # Bookings
        pending_r = supabase.table("bookings").select("id", count="exact").eq("status", "PENDING_PAYMENT").execute()
        confirmed_r = supabase.table("bookings").select("id", count="exact").eq("status", "CONFIRMED").execute()
        
        return {
            "customers": {
                "leads": lead_r.count or 0,
                "active": active_r.count or 0,
            },
            "visa_applications": {
                "docs_pending": docs_r.count or 0,
                "under_review": review_r.count or 0,
                "approved": approved_r.count or 0,
            },
            "quotations": {
                "draft": draft_r.count or 0,
                "sent": sent_r.count or 0,
            },
            "bookings": {
                "pending_payment": pending_r.count or 0,
                "confirmed": confirmed_r.count or 0,
            },
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        raise HTTPException(500, str(e))
