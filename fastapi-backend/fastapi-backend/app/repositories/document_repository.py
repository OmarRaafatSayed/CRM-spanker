"""
Document Repository
Data access layer for documents
"""
from typing import List, Optional
from supabase import Client

from app.models.document import Document
from .base import BaseRepository


class DocumentRepository(BaseRepository[Document]):
    """Document-specific repository operations"""
    
    def __init__(self, supabase: Client):
        super().__init__(supabase, "visa_documents", Document)
    
    def get_by_visa_application(
        self,
        visa_application_id: str
    ) -> List[Document]:
        """
        Get documents for a visa application
        
        Args:
            visa_application_id: Visa application ID
            
        Returns:
            List of Document instances
        """
        return self.find(
            filters={"visa_application_id": visa_application_id},
            order_by="created_at",
            ascending=True
        )
    
    def get_by_user(
        self,
        user_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Document]:
        """
        Get documents by user
        
        Args:
            user_id: Customer ID
            limit: Maximum records to return
            offset: Number of records to skip
            
        Returns:
            List of Document instances
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
    ) -> List[Document]:
        """
        Get documents by status
        
        Args:
            status: Document status
            limit: Maximum records to return
            offset: Number of records to skip
            
        Returns:
            List of Document instances
        """
        return self.find(
            filters={"status": status},
            limit=limit,
            offset=offset,
            order_by="created_at",
            ascending=False
        )
    
    def get_by_type(
        self,
        visa_application_id: str,
        doc_type: str
    ) -> Optional[Document]:
        """
        Get document by type for a visa application
        
        Args:
            visa_application_id: Visa application ID
            doc_type: Document type
            
        Returns:
            Document instance or None
        """
        results = self.find(
            filters={
                "visa_application_id": visa_application_id,
                "doc_type": doc_type
            },
            limit=1
        )
        
        return results[0] if results else None
