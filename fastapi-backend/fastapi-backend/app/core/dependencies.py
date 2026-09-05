"""
Dependency Injection
FastAPI dependencies for services and repositories
"""
from typing import Generator
from fastapi import Depends
from supabase import Client

from app.services.supabase_client import get_supabase

# Business Services
from app.business.customer_service import CustomerService
from app.business.visa_service import VisaApplicationService
from app.business.quotation_service import QuotationService
from app.business.booking_service import BookingService
from app.business.payment_service import PaymentService

# Repositories
from app.repositories.customer_repository import CustomerRepository
from app.repositories.visa_repository import VisaApplicationRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.quotation_repository import QuotationRepository
from app.repositories.booking_repository import BookingRepository
from app.repositories.transaction_repository import TransactionRepository


# ═══════════════════════════════════════════════════════════════════════════
# BUSINESS SERVICES - Dependency Injection
# ═══════════════════════════════════════════════════════════════════════════

def get_customer_service(
    supabase: Client = Depends(get_supabase)
) -> CustomerService:
    """Get customer service instance"""
    return CustomerService(supabase)


def get_visa_service(
    supabase: Client = Depends(get_supabase)
) -> VisaApplicationService:
    """Get visa application service instance"""
    return VisaApplicationService(supabase)


def get_quotation_service(
    supabase: Client = Depends(get_supabase)
) -> QuotationService:
    """Get quotation service instance"""
    return QuotationService(supabase)


def get_booking_service(
    supabase: Client = Depends(get_supabase)
) -> BookingService:
    """Get booking service instance"""
    return BookingService(supabase)


def get_payment_service(
    supabase: Client = Depends(get_supabase)
) -> PaymentService:
    """Get payment service instance"""
    return PaymentService(supabase)


# ═══════════════════════════════════════════════════════════════════════════
# REPOSITORIES - Dependency Injection (if needed directly in controllers)
# ═══════════════════════════════════════════════════════════════════════════

def get_customer_repository(
    supabase: Client = Depends(get_supabase)
) -> CustomerRepository:
    """Get customer repository instance"""
    return CustomerRepository(supabase)


def get_visa_repository(
    supabase: Client = Depends(get_supabase)
) -> VisaApplicationRepository:
    """Get visa application repository instance"""
    return VisaApplicationRepository(supabase)


def get_document_repository(
    supabase: Client = Depends(get_supabase)
) -> DocumentRepository:
    """Get document repository instance"""
    return DocumentRepository(supabase)


def get_quotation_repository(
    supabase: Client = Depends(get_supabase)
) -> QuotationRepository:
    """Get quotation repository instance"""
    return QuotationRepository(supabase)


def get_booking_repository(
    supabase: Client = Depends(get_supabase)
) -> BookingRepository:
    """Get booking repository instance"""
    return BookingRepository(supabase)


def get_transaction_repository(
    supabase: Client = Depends(get_supabase)
) -> TransactionRepository:
    """Get transaction repository instance"""
    return TransactionRepository(supabase)
