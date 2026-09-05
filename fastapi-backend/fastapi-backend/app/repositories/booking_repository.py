"""
Booking Repository
Data access layer for bookings
"""
from typing import List, Optional
from supabase import Client

from app.models.booking import Booking
from .base import BaseRepository


class BookingRepository(BaseRepository[Booking]):
    """Booking-specific repository operations"""
    
    def __init__(self, supabase: Client):
        super().__init__(supabase, "bookings", Booking)
    
    def get_by_user(
        self,
        user_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Booking]:
        """
        Get bookings by user
        
        Args:
            user_id: Customer ID
            limit: Maximum records to return
            offset: Number of records to skip
            
        Returns:
            List of Booking instances
        """
        return self.find(
            filters={"user_id": user_id},
            limit=limit,
            offset=offset,
            order_by="created_at",
            ascending=False
        )
    
    def get_by_status(
        self,
        status: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Booking]:
        """
        Get bookings by status
        
        Args:
            status: Booking status
            limit: Maximum records to return
            offset: Number of records to skip
            
        Returns:
            List of Booking instances
        """
        return self.find(
            filters={"status": status},
            limit=limit,
            offset=offset,
            order_by="created_at",
            ascending=False
        )
    
    def get_by_reference(self, booking_reference: str) -> Optional[Booking]:
        """
        Get booking by reference
        
        Args:
            booking_reference: Booking reference
            
        Returns:
            Booking instance or None
        """
        response = (
            self.supabase.table(self.table_name)
            .select("*")
            .eq("booking_reference", booking_reference)
            .limit(1)
            .execute()
        )
        
        if not response.data:
            return None
        
        return Booking.from_db(response.data[0])
    
    def get_by_quotation(self, quotation_id: str) -> Optional[Booking]:
        """
        Get booking by quotation
        
        Args:
            quotation_id: Quotation ID
            
        Returns:
            Booking instance or None
        """
        results = self.find(
            filters={"quotation_id": quotation_id},
            limit=1
        )
        
        return results[0] if results else None
    
    def count_by_status(self, status: str) -> int:
        """
        Count bookings by status
        
        Args:
            status: Booking status
            
        Returns:
            Number of bookings
        """
        return self.count({"status": status})
