"""
Customer Repository
Data access layer for customers/users
"""
from typing import List, Optional, Dict, Any
from supabase import Client

from app.models.customer import Customer
from .base import BaseRepository


class CustomerRepository(BaseRepository[Customer]):
    """Customer-specific repository operations"""
    
    def __init__(self, supabase: Client):
        super().__init__(supabase, "users", Customer)
    
    def get_by_email(self, email: str) -> Optional[Customer]:
        """
        Get customer by email
        
        Args:
            email: Customer email
            
        Returns:
            Customer instance or None
        """
        response = (
            self.supabase.table(self.table_name)
            .select("*")
            .eq("email", email)
            .limit(1)
            .execute()
        )
        
        if not response.data:
            return None
        
        return Customer.from_db(response.data[0])
    
    def get_by_auth_user_id(self, auth_user_id: str) -> Optional[Customer]:
        """
        Get customer by auth user ID
        
        Args:
            auth_user_id: Supabase auth user ID
            
        Returns:
            Customer instance or None
        """
        response = (
            self.supabase.table(self.table_name)
            .select("*")
            .eq("auth_user_id", auth_user_id)
            .limit(1)
            .execute()
        )
        
        if not response.data:
            return None
        
        return Customer.from_db(response.data[0])
    
    def get_by_status(
        self,
        status: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Customer]:
        """
        Get customers by status
        
        Args:
            status: Customer status (LEAD, ACTIVE_CLIENT, INACTIVE)
            limit: Maximum records to return
            offset: Number of records to skip
            
        Returns:
            List of Customer instances
        """
        return self.find(
            filters={"status": status},
            limit=limit,
            offset=offset,
            order_by="created_at",
            ascending=False
        )
    
    def search_customers(
        self,
        search_term: str,
        limit: int = 100
    ) -> List[Customer]:
        """
        Search customers by name, email, or phone
        
        Args:
            search_term: Search term
            limit: Maximum records to return
            
        Returns:
            List of Customer instances
        """
        # Supabase text search
        response = (
            self.supabase.table(self.table_name)
            .select("*")
            .or_(f"email.ilike.%{search_term}%,full_name.ilike.%{search_term}%,phone.ilike.%{search_term}%")
            .limit(limit)
            .execute()
        )
        
        return [Customer.from_db(record) for record in (response.data or [])]
    
    def count_by_status(self, status: str) -> int:
        """
        Count customers by status
        
        Args:
            status: Customer status
            
        Returns:
            Number of customers
        """
        return self.count({"status": status})
