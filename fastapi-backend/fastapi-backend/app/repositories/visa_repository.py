"""
Visa Application Repository
Data access layer for visa applications
"""
from typing import List, Optional
from supabase import Client

from app.models.visa_application import VisaApplication
from .base import BaseRepository


class VisaApplicationRepository(BaseRepository[VisaApplication]):
    """Visa application-specific repository operations"""
    
    def __init__(self, supabase: Client):
        super().__init__(supabase, "visa_applications", VisaApplication)
    
    def get_by_user(
        self,
        user_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[VisaApplication]:
        """
        Get visa applications by user
        
        Args:
            user_id: Customer ID
            limit: Maximum records to return
            offset: Number of records to skip
            
        Returns:
            List of VisaApplication instances
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
    ) -> List[VisaApplication]:
        """
        Get visa applications by status
        
        Args:
            status: Application status
            limit: Maximum records to return
            offset: Number of records to skip
            
        Returns:
            List of VisaApplication instances
        """
        return self.find(
            filters={"status": status},
            limit=limit,
            offset=offset,
            order_by="created_at",
            ascending=False
        )
    
    def get_by_country(
        self,
        country_code: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[VisaApplication]:
        """
        Get visa applications by country
        
        Args:
            country_code: Country code
            limit: Maximum records to return
            offset: Number of records to skip
            
        Returns:
            List of VisaApplication instances
        """
        return self.find(
            filters={"country_code": country_code},
            limit=limit,
            offset=offset,
            order_by="created_at",
            ascending=False
        )
    
    def count_by_status(self, status: str) -> int:
        """
        Count visa applications by status
        
        Args:
            status: Application status
            
        Returns:
            Number of applications
        """
        return self.count({"status": status})
