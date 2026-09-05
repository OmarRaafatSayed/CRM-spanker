"""
Payment Service
Business logic for payment and transaction management
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from supabase import Client

from app.models.transaction import Transaction
from app.repositories.transaction_repository import TransactionRepository
from app.repositories.booking_repository import BookingRepository


class PaymentService:
    """Business logic for payment operations"""
    
    def __init__(self, supabase: Client):
        self.repository = TransactionRepository(supabase)
        self.booking_repository = BookingRepository(supabase)
    
    def get_transaction(self, transaction_id: str) -> Optional[Transaction]:
        """
        Get transaction by ID
        
        Args:
            transaction_id: Transaction ID
            
        Returns:
            Transaction instance or None
        """
        return self.repository.get_by_id(transaction_id)
    
    def list_transactions(
        self,
        payment_status: Optional[str] = None,
        user_id: Optional[str] = None,
        booking_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        List transactions with filters
        
        Args:
            payment_status: Optional payment status filter
            user_id: Optional user filter
            booking_id: Optional booking filter
            limit: Maximum records
            offset: Pagination offset
            
        Returns:
            Dictionary with transactions and total
        """
        if booking_id:
            transactions = self.repository.get_by_booking(booking_id)
            total = self.repository.count({"booking_id": booking_id})
        elif user_id:
            transactions = self.repository.get_by_user(user_id, limit, offset)
            total = self.repository.count({"user_id": user_id})
        elif payment_status:
            transactions = self.repository.get_by_payment_status(
                payment_status, limit, offset
            )
            total = self.repository.count({"payment_status": payment_status})
        else:
            transactions = self.repository.get_all(limit, offset)
            total = self.repository.count()
        
        return {
            "transactions": [t.to_dict() for t in transactions],
            "total": total
        }
    
    def create_transaction(
        self,
        booking_id: str,
        user_id: str,
        total_amount: float,
        payment_method: str = "CASH",
        currency: str = "EGP"
    ) -> Transaction:
        """
        Create new transaction for a booking
        
        Args:
            booking_id: Booking ID
            user_id: Customer ID
            total_amount: Total amount
            payment_method: Payment method
            currency: Currency code
            
        Returns:
            Created Transaction instance
        """
        transaction_data = {
            "booking_id": booking_id,
            "user_id": user_id,
            "total_amount": total_amount,
            "amount_paid": 0.0,
            "remaining_balance": total_amount,
            "currency": currency,
            "payment_method": payment_method,
            "payment_status": "PENDING"
        }
        
        return self.repository.create(transaction_data)
    
    def record_payment(
        self,
        transaction_id: str,
        amount_paid: float,
        payment_method: str,
        receipt_url: Optional[str] = None,
        transaction_reference: Optional[str] = None
    ) -> Optional[Transaction]:
        """
        Record a payment for a transaction
        
        Args:
            transaction_id: Transaction ID
            amount_paid: Amount being paid
            payment_method: Payment method
            receipt_url: Optional receipt URL
            transaction_reference: Optional bank/payment reference
            
        Returns:
            Updated Transaction instance or None
        """
        transaction = self.repository.get_by_id(transaction_id)
        if not transaction:
            return None
        
        # Calculate new totals
        new_amount_paid = transaction.amount_paid + amount_paid
        new_remaining = max(0, transaction.total_amount - new_amount_paid)
        
        # Determine payment status
        if new_remaining <= 0:
            payment_status = "PAID"
        elif new_amount_paid > 0:
            payment_status = "PARTIAL"
        else:
            payment_status = "PENDING"
        
        update_data = {
            "amount_paid": new_amount_paid,
            "remaining_balance": new_remaining,
            "payment_method": payment_method,
            "payment_status": payment_status,
            "paid_at": datetime.utcnow().isoformat()
        }
        
        if receipt_url:
            update_data["receipt_url"] = receipt_url
        
        if transaction_reference:
            update_data["transaction_reference"] = transaction_reference
        
        # Update transaction
        updated_transaction = self.repository.update(transaction_id, update_data)
        
        # If fully paid, confirm booking
        if payment_status == "PAID" and transaction.booking_id:
            self.booking_repository.update(
                transaction.booking_id,
                {"status": "CONFIRMED"}
            )
        
        return updated_transaction
    
    def process_refund(
        self,
        transaction_id: str,
        refund_amount: float,
        reason: str
    ) -> Optional[Transaction]:
        """
        Process a refund for a transaction
        
        Args:
            transaction_id: Transaction ID
            refund_amount: Refund amount
            reason: Refund reason
            
        Returns:
            Updated Transaction instance or None
        """
        transaction = self.repository.get_by_id(transaction_id)
        if not transaction:
            return None
        
        # Validate refund amount
        if refund_amount > transaction.amount_paid:
            raise ValueError("Refund amount cannot exceed paid amount")
        
        update_data = {
            "refund_amount": refund_amount,
            "refunded_at": datetime.utcnow().isoformat(),
            "refund_reason": reason,
            "payment_status": "REFUNDED"
        }
        
        return self.repository.update(transaction_id, update_data)
    
    def get_payment_stats(self) -> Dict[str, Any]:
        """
        Get payment statistics
        
        Returns:
            Dictionary with payment stats
        """
        total_revenue = self.repository.calculate_total_revenue()
        pending_transactions = self.repository.get_pending_payments()
        
        return {
            "total_revenue": total_revenue,
            "pending_payments": len(pending_transactions),
            "pending_amount": sum(t.remaining_balance for t in pending_transactions)
        }
