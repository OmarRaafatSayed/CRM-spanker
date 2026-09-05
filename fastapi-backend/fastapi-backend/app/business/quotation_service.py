"""
Quotation Service
Business logic for quotation management
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from supabase import Client

from app.models.quotation import Quotation
from app.repositories.quotation_repository import QuotationRepository


class QuotationService:
    """Business logic for quotation operations"""
    
    def __init__(self, supabase: Client):
        self.repository = QuotationRepository(supabase)
    
    def get_quotation(self, quotation_id: str) -> Optional[Quotation]:
        """
        Get quotation by ID
        
        Args:
            quotation_id: Quotation ID
            
        Returns:
            Quotation instance or None
        """
        return self.repository.get_by_id(quotation_id)
    
    def list_quotations(
        self,
        status: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        List quotations with filters
        
        Args:
            status: Optional status filter
            user_id: Optional user filter
            limit: Maximum records
            offset: Pagination offset
            
        Returns:
            Dictionary with quotations and total
        """
        if user_id:
            quotations = self.repository.get_by_user(user_id, limit, offset)
            total = self.repository.count({"user_id": user_id})
        elif status:
            quotations = self.repository.get_by_status(status, limit, offset)
            total = self.repository.count_by_status(status)
        else:
            quotations = self.repository.get_all(limit, offset)
            total = self.repository.count()
        
        return {
            "quotations": [q.to_dict() for q in quotations],
            "total": total
        }
    
    def create_quotation(
        self,
        quotation_data: Dict[str, Any],
        validity_days: int = 7
    ) -> Quotation:
        """
        Create new quotation
        
        Args:
            quotation_data: Quotation data
            validity_days: Number of days the quotation is valid
            
        Returns:
            Created Quotation instance
        """
        # Set default status
        if "status" not in quotation_data:
            quotation_data["status"] = "DRAFT"
        
        # Calculate validity date
        if "valid_until" not in quotation_data:
            quotation_data["valid_until"] = (
                datetime.utcnow() + timedelta(days=validity_days)
            ).isoformat()
        
        # Calculate totals if items provided
        if "items" in quotation_data and quotation_data["items"]:
            subtotal = sum(item.get("total", 0) for item in quotation_data["items"])
            quotation_data["subtotal"] = subtotal
            quotation_data["total_amount"] = subtotal + quotation_data.get("tax_amount", 0)
        
        return self.repository.create(quotation_data)
    
    def update_quotation_status(
        self,
        quotation_id: str,
        new_status: str
    ) -> Optional[Quotation]:
        """
        Update quotation status
        
        Args:
            quotation_id: Quotation ID
            new_status: New status
            
        Returns:
            Updated Quotation instance or None
        """
        update_data = {"status": new_status}
        
        if new_status == "ACCEPTED":
            update_data["accepted_at"] = datetime.utcnow().isoformat()
        elif new_status == "REJECTED":
            update_data["rejected_at"] = datetime.utcnow().isoformat()
        
        return self.repository.update(quotation_id, update_data)
    
    def send_quotation(self, quotation_id: str) -> Optional[Quotation]:
        """
        Mark quotation as sent to customer
        
        Args:
            quotation_id: Quotation ID
            
        Returns:
            Updated Quotation instance or None
        """
        return self.update_quotation_status(quotation_id, "SENT")
    
    def accept_quotation(self, quotation_id: str) -> Optional[Quotation]:
        """
        Mark quotation as accepted by customer
        
        Args:
            quotation_id: Quotation ID
            
        Returns:
            Updated Quotation instance or None
        """
        return self.update_quotation_status(quotation_id, "ACCEPTED")
    
    def reject_quotation(
        self,
        quotation_id: str,
        reason: Optional[str] = None
    ) -> Optional[Quotation]:
        """
        Mark quotation as rejected by customer
        
        Args:
            quotation_id: Quotation ID
            reason: Optional rejection reason
            
        Returns:
            Updated Quotation instance or None
        """
        quotation = self.repository.get_by_id(quotation_id)
        if not quotation:
            return None
        
        update_data = {
            "status": "REJECTED",
            "rejected_at": datetime.utcnow().isoformat()
        }
        
        if reason:
            update_data["rejection_reason"] = reason
        
        return self.repository.update(quotation_id, update_data)
    
    def get_quotation_stats(self) -> Dict[str, int]:
        """
        Get quotation statistics
        
        Returns:
            Dictionary with stats by status
        """
        return {
            "total": self.repository.count(),
            "draft": self.repository.count_by_status("DRAFT"),
            "sent": self.repository.count_by_status("SENT"),
            "accepted": self.repository.count_by_status("ACCEPTED"),
            "expired": self.repository.count_by_status("EXPIRED"),
            "rejected": self.repository.count_by_status("REJECTED")
        }
