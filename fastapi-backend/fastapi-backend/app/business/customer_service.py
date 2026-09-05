"""
Customer Service
Business logic for customer management
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from supabase import Client

from app.models.customer import Customer
from app.repositories.customer_repository import CustomerRepository


class CustomerService:
    """Business logic for customer operations"""
    
    def __init__(self, supabase: Client):
        self.repository = CustomerRepository(supabase)
    
    def get_customer(self, customer_id: str) -> Optional[Customer]:
        """
        Get customer by ID
        
        Args:
            customer_id: Customer ID
            
        Returns:
            Customer instance or None
        """
        return self.repository.get_by_id(customer_id)
    
    def get_customer_by_email(self, email: str) -> Optional[Customer]:
        """
        Get customer by email
        
        Args:
            email: Customer email
            
        Returns:
            Customer instance or None
        """
        return self.repository.get_by_email(email)
    
    def get_customer_by_auth_id(self, auth_user_id: str) -> Optional[Customer]:
        """
        Get customer by auth user ID
        
        Args:
            auth_user_id: Supabase auth user ID
            
        Returns:
            Customer instance or None
        """
        return self.repository.get_by_auth_user_id(auth_user_id)
    
    def list_customers(
        self,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        List customers with optional filters
        
        Args:
            status: Optional status filter
            limit: Maximum records
            offset: Pagination offset
            
        Returns:
            Dictionary with customers list and total count
        """
        if status:
            customers = self.repository.get_by_status(status, limit, offset)
            total = self.repository.count_by_status(status)
        else:
            customers = self.repository.get_all(limit, offset)
            total = self.repository.count()
        
        return {
            "customers": [c.to_dict() for c in customers],
            "total": total,
            "filters": {"status": status}
        }
    
    def search_customers(self, search_term: str, limit: int = 100) -> List[Customer]:
        """
        Search customers by name, email, or phone
        
        Args:
            search_term: Search term
            limit: Maximum records
            
        Returns:
            List of Customer instances
        """
        return self.repository.search_customers(search_term, limit)
    
    def create_customer(self, customer_data: Dict[str, Any]) -> Customer:
        """
        Create a new customer
        
        Args:
            customer_data: Customer data
            
        Returns:
            Created Customer instance
        """
        # Set default status if not provided
        if "status" not in customer_data:
            customer_data["status"] = "LEAD"
        
        return self.repository.create(customer_data)
    
    def update_customer(
        self,
        customer_id: str,
        update_data: Dict[str, Any]
    ) -> Optional[Customer]:
        """
        Update customer
        
        Args:
            customer_id: Customer ID
            update_data: Update data
            
        Returns:
            Updated Customer instance or None
        """
        return self.repository.update(customer_id, update_data)
    
    def update_customer_status(
        self,
        customer_id: str,
        new_status: str
    ) -> Optional[Customer]:
        """
        Update customer status
        
        Args:
            customer_id: Customer ID
            new_status: New status
            
        Returns:
            Updated Customer instance or None
        """
        return self.repository.update(customer_id, {"status": new_status})
    
    def get_customer_stats(self) -> Dict[str, int]:
        """
        Get customer statistics
        
        Returns:
            Dictionary with stats by status
        """
        return {
            "total": self.repository.count(),
            "leads": self.repository.count_by_status("LEAD"),
            "active": self.repository.count_by_status("ACTIVE_CLIENT"),
            "inactive": self.repository.count_by_status("INACTIVE")
        }
