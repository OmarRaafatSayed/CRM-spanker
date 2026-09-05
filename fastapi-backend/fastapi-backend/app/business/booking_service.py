"""
Booking Service
Business logic for booking management
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from supabase import Client
import secrets

from app.models.booking import Booking
from app.repositories.booking_repository import BookingRepository
from app.repositories.quotation_repository import QuotationRepository


class BookingService:
    """Business logic for booking operations"""
    
    def __init__(self, supabase: Client):
        self.repository = BookingRepository(supabase)
        self.quotation_repository = QuotationRepository(supabase)
    
    def get_booking(self, booking_id: str) -> Optional[Booking]:
        """
        Get booking by ID
        
        Args:
            booking_id: Booking ID
            
        Returns:
            Booking instance or None
        """
        return self.repository.get_by_id(booking_id)
    
    def get_booking_by_reference(
        self,
        booking_reference: str
    ) -> Optional[Booking]:
        """
        Get booking by reference
        
        Args:
            booking_reference: Booking reference
            
        Returns:
            Booking instance or None
        """
        return self.repository.get_by_reference(booking_reference)
    
    def list_bookings(
        self,
        status: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        List bookings with filters
        
        Args:
            status: Optional status filter
            user_id: Optional user filter
            limit: Maximum records
            offset: Pagination offset
            
        Returns:
            Dictionary with bookings and total
        """
        if user_id:
            bookings = self.repository.get_by_user(user_id, limit, offset)
            total = self.repository.count({"user_id": user_id})
        elif status:
            bookings = self.repository.get_by_status(status, limit, offset)
            total = self.repository.count_by_status(status)
        else:
            bookings = self.repository.get_all(limit, offset)
            total = self.repository.count()
        
        return {
            "bookings": [b.to_dict() for b in bookings],
            "total": total
        }
    
    def create_booking(
        self,
        booking_data: Dict[str, Any]
    ) -> Booking:
        """
        Create new booking from accepted quotation
        
        Args:
            booking_data: Booking data
            
        Returns:
            Created Booking instance
        """
        # Generate booking reference if not provided
        if "booking_reference" not in booking_data:
            year = datetime.utcnow().year
            random_part = secrets.token_hex(4).upper()
            booking_data["booking_reference"] = f"BK-{year}-{random_part}"
        
        # Set default status
        if "status" not in booking_data:
            booking_data["status"] = "PENDING_PAYMENT"
        
        # Get quotation details if quotation_id provided
        if "quotation_id" in booking_data:
            quotation = self.quotation_repository.get_by_id(
                booking_data["quotation_id"]
            )
            if quotation:
                booking_data["total_amount"] = quotation.total_amount
                booking_data["currency"] = quotation.currency
                
                # Mark quotation as accepted
                self.quotation_repository.update(
                    quotation.id,
                    {
                        "status": "ACCEPTED",
                        "accepted_at": datetime.utcnow().isoformat()
                    }
                )
        
        return self.repository.create(booking_data)
    
    def update_booking_status(
        self,
        booking_id: str,
        new_status: str
    ) -> Optional[Booking]:
        """
        Update booking status
        
        Args:
            booking_id: Booking ID
            new_status: New status
            
        Returns:
            Updated Booking instance or None
        """
        return self.repository.update(booking_id, {"status": new_status})
    
    def confirm_booking(self, booking_id: str) -> Optional[Booking]:
        """
        Confirm booking (after payment)
        
        Args:
            booking_id: Booking ID
            
        Returns:
            Updated Booking instance or None
        """
        return self.update_booking_status(booking_id, "CONFIRMED")
    
    def cancel_booking(
        self,
        booking_id: str,
        reason: Optional[str] = None
    ) -> Optional[Booking]:
        """
        Cancel booking
        
        Args:
            booking_id: Booking ID
            reason: Optional cancellation reason
            
        Returns:
            Updated Booking instance or None
        """
        update_data = {
            "status": "CANCELLED",
            "cancelled_at": datetime.utcnow().isoformat()
        }
        
        if reason:
            update_data["cancellation_reason"] = reason
        
        return self.repository.update(booking_id, update_data)
    
    def complete_booking(self, booking_id: str) -> Optional[Booking]:
        """
        Mark booking as completed
        
        Args:
            booking_id: Booking ID
            
        Returns:
            Updated Booking instance or None
        """
        return self.update_booking_status(booking_id, "COMPLETED")
    
    def get_booking_stats(self) -> Dict[str, int]:
        """
        Get booking statistics
        
        Returns:
            Dictionary with stats by status
        """
        return {
            "total": self.repository.count(),
            "pending_payment": self.repository.count_by_status("PENDING_PAYMENT"),
            "confirmed": self.repository.count_by_status("CONFIRMED"),
            "cancelled": self.repository.count_by_status("CANCELLED"),
            "completed": self.repository.count_by_status("COMPLETED")
        }
