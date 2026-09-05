"""
Visa Application Service
Business logic for visa applications
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from supabase import Client

from app.models.visa_application import VisaApplication
from app.repositories.visa_repository import VisaApplicationRepository
from app.repositories.document_repository import DocumentRepository


class VisaApplicationService:
    """Business logic for visa application operations"""
    
    def __init__(self, supabase: Client):
        self.repository = VisaApplicationRepository(supabase)
        self.document_repository = DocumentRepository(supabase)
    
    def get_application(self, app_id: str) -> Optional[VisaApplication]:
        """
        Get visa application by ID
        
        Args:
            app_id: Application ID
            
        Returns:
            VisaApplication instance or None
        """
        return self.repository.get_by_id(app_id)
    
    def get_application_with_documents(
        self,
        app_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get visa application with documents
        
        Args:
            app_id: Application ID
            
        Returns:
            Dictionary with application and documents
        """
        application = self.repository.get_by_id(app_id)
        if not application:
            return None
        
        documents = self.document_repository.get_by_visa_application(app_id)
        
        result = application.to_dict()
        result["documents"] = [doc.to_dict() for doc in documents]
        
        return result
    
    def list_applications(
        self,
        status: Optional[str] = None,
        country_code: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        List visa applications with filters
        
        Args:
            status: Optional status filter
            country_code: Optional country filter
            user_id: Optional user filter
            limit: Maximum records
            offset: Pagination offset
            
        Returns:
            Dictionary with applications and total
        """
        if user_id:
            applications = self.repository.get_by_user(user_id, limit, offset)
            total = self.repository.count({"user_id": user_id})
        elif status:
            applications = self.repository.get_by_status(status, limit, offset)
            total = self.repository.count_by_status(status)
        elif country_code:
            applications = self.repository.get_by_country(country_code, limit, offset)
            total = self.repository.count({"country_code": country_code})
        else:
            applications = self.repository.get_all(limit, offset)
            total = self.repository.count()
        
        return {
            "applications": [app.to_dict() for app in applications],
            "total": total
        }
    
    def create_application(
        self,
        application_data: Dict[str, Any]
    ) -> VisaApplication:
        """
        Create new visa application
        
        Args:
            application_data: Application data
            
        Returns:
            Created VisaApplication instance
        """
        # Set default status
        if "status" not in application_data:
            application_data["status"] = "DOCS_PENDING"
        
        return self.repository.create(application_data)
    
    def update_application_status(
        self,
        app_id: str,
        new_status: str,
        notes: Optional[str] = None
    ) -> Optional[VisaApplication]:
        """
        Update application status
        
        Args:
            app_id: Application ID
            new_status: New status
            notes: Optional notes
            
        Returns:
            Updated VisaApplication instance or None
        """
        update_data = {"status": new_status}
        
        if notes:
            update_data["notes"] = notes
        
        if new_status == "SUBMITTED_TO_EMBASSY":
            update_data["embassy_submission_date"] = datetime.utcnow().isoformat()
        
        return self.repository.update(app_id, update_data)
    
    def get_application_stats(self) -> Dict[str, int]:
        """
        Get visa application statistics
        
        Returns:
            Dictionary with stats by status
        """
        return {
            "total": self.repository.count(),
            "docs_pending": self.repository.count_by_status("DOCS_PENDING"),
            "under_review": self.repository.count_by_status("UNDER_REVIEW"),
            "submitted": self.repository.count_by_status("SUBMITTED_TO_EMBASSY"),
            "approved": self.repository.count_by_status("APPROVED"),
            "rejected": self.repository.count_by_status("REJECTED")
        }
