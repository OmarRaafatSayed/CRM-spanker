"""
Quotation Repository
Data access layer for quotations
"""
from typing import List, Optional
from supabase import Client

from app.models.quotation import Quotation
from .base import BaseRepository


class QuotationRepository(BaseRepository[Quotation]):
    """Quotation-specific repository operations"""
    
    def __init__(self, supabase: Client):
        super().__init__(supabase, "quotations", Quotation)
    
    def get_by_user(
        self,
        user_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Quotation]:
        """
        Get quotations by user
        
        Args:
            user_id: Customer ID
            limit: Maximum records to return
            offset: Number of records to skip
            
        Returns:
            List of Quotation instances
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
    ) -> List[Quotation]:
        """
        Get quotations by status
        
        Args:
            status: Quotation status
            limit: Maximum records to return
            offset: Number of records to skip
            
        Returns:
            List of Quotation instances
        """
        return self.find(
            filters={"status": status},
            limit=limit,
            offset=offset,
            order_by="created_at",
            ascending=False
        )
    
    def get_by_visa_application(
        self,
        visa_application_id: str
    ) -> List[Quotation]:
        """
        Get quotations for a visa application
        
        Args:
            visa_application_id: Visa application ID
            
        Returns:
            List of Quotation instances
        """
        return self.find(
            filters={"visa_application_id": visa_application_id},
            order_by="created_at",
            ascending=False
        )
    
    def count_by_status(self, status: str) -> int:
        """
        Count quotations by status
        
        Args:
            status: Quotation status
            
        Returns:
            Number of quotations
        """
        return self.count({"status": status})
