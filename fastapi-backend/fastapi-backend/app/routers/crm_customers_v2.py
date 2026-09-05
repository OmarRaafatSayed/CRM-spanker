"""
CRM Customers Router V2 - Using Layered Architecture
Demonstrates proper separation of concerns with Services and Repositories
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.security import AuthToken, require_auth
from app.core.dependencies import (
    get_customer_service,
    get_visa_service,
    get_quotation_service,
    get_booking_service,
    get_payment_service
)
from app.business.customer_service import CustomerService
from app.business.visa_service import VisaApplicationService
from app.business.quotation_service import QuotationService
from app.business.booking_service import BookingService
from app.business.payment_service import PaymentService


router = APIRouter()


# ═══════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def _require_staff(token: AuthToken) -> AuthToken:
    """Staff-only access"""
    if token.role not in ("staff", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff access required"
        )
    return token


# ═══════════════════════════════════════════════════════════════════════════
# CUSTOMERS ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/customers")
async def list_customers(
    token: AuthToken = Depends(require_auth),
    customer_service: CustomerService = Depends(get_customer_service),
    status_filter: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List all customers with status filter"""
    _require_staff(token)
    
    try:
        result = customer_service.list_customers(
            status=status_filter,
            limit=limit,
            offset=offset
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/customers/{customer_id}")
async def get_customer(
    customer_id: str,
    token: AuthToken = Depends(require_auth),
    customer_service: CustomerService = Depends(get_customer_service),
):
    """Get customer profile"""
    _require_staff(token)
    
    customer = customer_service.get_customer(customer_id)
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
    
    return customer.to_dict()


@router.get("/customers/search")
async def search_customers(
    token: AuthToken = Depends(require_auth),
    customer_service: CustomerService = Depends(get_customer_service),
    q: str = Query(..., min_length=2),
    limit: int = Query(50, ge=1, le=200),
):
    """Search customers by name, email, or phone"""
    _require_staff(token)
    
    customers = customer_service.search_customers(q, limit)
    
    return {
        "customers": [c.to_dict() for c in customers],
        "total": len(customers)
    }


@router.patch("/customers/{customer_id}/status")
async def update_customer_status(
    customer_id: str,
    new_status: str = Query(...),
    token: AuthToken = Depends(require_auth),
    customer_service: CustomerService = Depends(get_customer_service),
):
    """Update customer status"""
    _require_staff(token)
    
    customer = customer_service.update_customer_status(customer_id, new_status)
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
    
    return {
        "success": True,
        "customer_id": customer_id,
        "new_status": new_status
    }


# ═══════════════════════════════════════════════════════════════════════════
# VISA APPLICATIONS ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/visa-applications")
async def list_visa_applications(
    token: AuthToken = Depends(require_auth),
    visa_service: VisaApplicationService = Depends(get_visa_service),
    status_filter: Optional[str] = Query(None),
    country_code: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List visa applications with filters"""
    _require_staff(token)
    
    result = visa_service.list_applications(
        status=status_filter,
        country_code=country_code,
        limit=limit,
        offset=offset
    )
    
    return result


@router.get("/visa-applications/{app_id}")
async def get_visa_application(
    app_id: str,
    token: AuthToken = Depends(require_auth),
    visa_service: VisaApplicationService = Depends(get_visa_service),
):
    """Get visa application with documents"""
    _require_staff(token)
    
    application = visa_service.get_application_with_documents(app_id)
    
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    return application


@router.patch("/visa-applications/{app_id}/status")
async def update_visa_status(
    app_id: str,
    new_status: str = Query(...),
    notes: Optional[str] = Query(None),
    token: AuthToken = Depends(require_auth),
    visa_service: VisaApplicationService = Depends(get_visa_service),
):
    """Update visa application status"""
    _require_staff(token)
    
    application = visa_service.update_application_status(app_id, new_status, notes)
    
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    return {
        "success": True,
        "application_id": app_id,
        "new_status": new_status
    }


# ═══════════════════════════════════════════════════════════════════════════
# QUOTATIONS ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/quotations")
async def list_quotations(
    token: AuthToken = Depends(require_auth),
    quotation_service: QuotationService = Depends(get_quotation_service),
    status_filter: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List quotations"""
    _require_staff(token)
    
    result = quotation_service.list_quotations(
        status=status_filter,
        limit=limit,
        offset=offset
    )
    
    return result


@router.get("/quotations/{quote_id}")
async def get_quotation(
    quote_id: str,
    token: AuthToken = Depends(require_auth),
    quotation_service: QuotationService = Depends(get_quotation_service),
):
    """Get quotation details"""
    _require_staff(token)
    
    quotation = quotation_service.get_quotation(quote_id)
    
    if not quotation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quotation not found"
        )
    
    return quotation.to_dict()


@router.patch("/quotations/{quote_id}/send")
async def send_quotation(
    quote_id: str,
    token: AuthToken = Depends(require_auth),
    quotation_service: QuotationService = Depends(get_quotation_service),
):
    """Send quotation to customer"""
    _require_staff(token)
    
    quotation = quotation_service.send_quotation(quote_id)
    
    if not quotation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quotation not found"
        )
    
    return {
        "success": True,
        "quotation_id": quote_id,
        "status": "SENT"
    }


# ═══════════════════════════════════════════════════════════════════════════
# BOOKINGS ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/bookings")
async def list_bookings(
    token: AuthToken = Depends(require_auth),
    booking_service: BookingService = Depends(get_booking_service),
    status_filter: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List bookings"""
    _require_staff(token)
    
    result = booking_service.list_bookings(
        status=status_filter,
        limit=limit,
        offset=offset
    )
    
    return result


@router.get("/bookings/{booking_id}")
async def get_booking(
    booking_id: str,
    token: AuthToken = Depends(require_auth),
    booking_service: BookingService = Depends(get_booking_service),
):
    """Get booking details"""
    _require_staff(token)
    
    booking = booking_service.get_booking(booking_id)
    
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    
    return booking.to_dict()


# ═══════════════════════════════════════════════════════════════════════════
# PAYMENTS ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/transactions")
async def list_transactions(
    token: AuthToken = Depends(require_auth),
    payment_service: PaymentService = Depends(get_payment_service),
    booking_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List financial transactions"""
    _require_staff(token)
    
    result = payment_service.list_transactions(
        booking_id=booking_id,
        limit=limit,
        offset=offset
    )
    
    return result


@router.post("/transactions/{trans_id}/payment")
async def record_payment(
    trans_id: str,
    amount_paid: float = Query(..., gt=0),
    payment_method: str = Query(...),
    receipt_url: Optional[str] = Query(None),
    token: AuthToken = Depends(require_auth),
    payment_service: PaymentService = Depends(get_payment_service),
):
    """Record payment for transaction"""
    _require_staff(token)
    
    transaction = payment_service.record_payment(
        transaction_id=trans_id,
        amount_paid=amount_paid,
        payment_method=payment_method,
        receipt_url=receipt_url
    )
    
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )
    
    return {
        "success": True,
        "transaction_id": trans_id,
        "amount_paid": amount_paid,
        "remaining_balance": transaction.remaining_balance
    }


# ═══════════════════════════════════════════════════════════════════════════
# METRICS ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/metrics")
async def get_crm_metrics(
    token: AuthToken = Depends(require_auth),
    customer_service: CustomerService = Depends(get_customer_service),
    visa_service: VisaApplicationService = Depends(get_visa_service),
    quotation_service: QuotationService = Depends(get_quotation_service),
    booking_service: BookingService = Depends(get_booking_service),
    payment_service: PaymentService = Depends(get_payment_service),
):
    """Get CRM dashboard metrics"""
    _require_staff(token)
    
    return {
        "customers": customer_service.get_customer_stats(),
        "visa_applications": visa_service.get_application_stats(),
        "quotations": quotation_service.get_quotation_stats(),
        "bookings": booking_service.get_booking_stats(),
        "payments": payment_service.get_payment_stats(),
    }
