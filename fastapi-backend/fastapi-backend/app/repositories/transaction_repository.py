"""
Transaction Repository
Data access layer for financial transactions
"""
from typing import List, Optional
from supabase import Client

from app.models.transaction import Transaction
from .base import BaseRepository


class TransactionRepository(BaseRepository[Transaction]):
    """Transaction-specific repository operations"""
    
    def __init__(self, supabase: Client):
        super().__init__(supabase, "financial_transactions", Transaction)
    
    def get_by_user(
        self,
        user_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Transaction]:
        """
        Get transactions by user
        
        Args:
            user_id: Customer ID
            limit: Maximum records to return
            offset: Number of records to skip
            
        Returns:
            List of Transaction instances
        """
        return self.find(
            filters={"user_id": user_id},
            limit=limit,
            offset=offset,
            order_by="created_at",
            ascending=False
        )
    
    def get_by_booking(
        self,
        booking_id: str
    ) -> List[Transaction]:
        """
        Get transactions for a booking
        
        Args:
            booking_id: Booking ID
            
        Returns:
            List of Transaction instances
        """
        return self.find(
            filters={"booking_id": booking_id},
            order_by="created_at",
            ascending=True
        )
    
    def get_by_payment_status(
        self,
        payment_status: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Transaction]:
        """
        Get transactions by payment status
        
        Args:
            payment_status: Payment status
            limit: Maximum records to return
            offset: Number of records to skip
            
        Returns:
            List of Transaction instances
        """
        return self.find(
            filters={"payment_status": payment_status},
            limit=limit,
            offset=offset,
            order_by="created_at",
            ascending=False
        )
    
    def get_pending_payments(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[Transaction]:
        """
        Get pending payment transactions
        
        Args:
            limit: Maximum records to return
            offset: Number of records to skip
            
        Returns:
            List of Transaction instances
        """
        return self.get_by_payment_status("PENDING", limit, offset)
    
    def calculate_total_revenue(self) -> float:
        """
        Calculate total revenue from paid transactions
        
        Returns:
            Total revenue amount
        """
        response = (
            self.supabase.table(self.table_name)
            .select("amount_paid")
            .eq("payment_status", "PAID")
            .execute()
        )
        
        if not response.data:
            return 0.0
        
        return sum(record.get("amount_paid", 0) for record in response.data)
