"""
Base Repository
Generic CRUD operations for database access
"""
from typing import TypeVar, Generic, List, Optional, Dict, Any, Type
from datetime import datetime

from supabase import Client
from pydantic import BaseModel

from app.models.base import BaseDBModel


T = TypeVar('T', bound=BaseDBModel)


class BaseRepository(Generic[T]):
    """Base repository with generic CRUD operations"""
    
    def __init__(self, supabase: Client, table_name: str, model_class: Type[T]):
        """
        Initialize repository
        
        Args:
            supabase: Supabase client instance
            table_name: Database table name
            model_class: Pydantic model class
        """
        self.supabase = supabase
        self.table_name = table_name
        self.model_class = model_class
    
    # ──────────────────────────────────────────────────────────────────────
    # CREATE
    # ──────────────────────────────────────────────────────────────────────
    
    def create(self, data: Dict[str, Any]) -> T:
        """
        Create a new record
        
        Args:
            data: Record data
            
        Returns:
            Created model instance
            
        Raises:
            Exception: If creation fails
        """
        response = self.supabase.table(self.table_name).insert(data).execute()
        
        if not response.data:
            raise Exception(f"Failed to create {self.table_name} record")
        
        return self.model_class.from_db(response.data[0])
    
    def create_many(self, records: List[Dict[str, Any]]) -> List[T]:
        """
        Create multiple records
        
        Args:
            records: List of record data
            
        Returns:
            List of created model instances
        """
        response = self.supabase.table(self.table_name).insert(records).execute()
        
        return [self.model_class.from_db(record) for record in (response.data or [])]
    
    # ──────────────────────────────────────────────────────────────────────
    # READ
    # ──────────────────────────────────────────────────────────────────────
    
    def get_by_id(self, record_id: str) -> Optional[T]:
        """
        Get record by ID
        
        Args:
            record_id: Record ID
            
        Returns:
            Model instance or None if not found
        """
        response = (
            self.supabase.table(self.table_name)
            .select("*")
            .eq("id", record_id)
            .limit(1)
            .execute()
        )
        
        if not response.data:
            return None
        
        return self.model_class.from_db(response.data[0])
    
    def get_all(
        self,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "created_at",
        ascending: bool = False
    ) -> List[T]:
        """
        Get all records with pagination
        
        Args:
            limit: Maximum records to return
            offset: Number of records to skip
            order_by: Field to order by
            ascending: Order direction
            
        Returns:
            List of model instances
        """
        query = self.supabase.table(self.table_name).select("*")
        
        query = query.order(order_by, desc=not ascending)
        query = query.range(offset, offset + limit - 1)
        
        response = query.execute()
        
        return [self.model_class.from_db(record) for record in (response.data or [])]
    
    def find(
        self,
        filters: Dict[str, Any],
        limit: int = 100,
        offset: int = 0,
        order_by: str = "created_at",
        ascending: bool = False
    ) -> List[T]:
        """
        Find records with filters
        
        Args:
            filters: Dictionary of field:value filters
            limit: Maximum records to return
            offset: Number of records to skip
            order_by: Field to order by
            ascending: Order direction
            
        Returns:
            List of model instances
        """
        query = self.supabase.table(self.table_name).select("*")
        
        # Apply filters
        for field, value in filters.items():
            query = query.eq(field, value)
        
        query = query.order(order_by, desc=not ascending)
        query = query.range(offset, offset + limit - 1)
        
        response = query.execute()
        
        return [self.model_class.from_db(record) for record in (response.data or [])]
    
    def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """
        Count records
        
        Args:
            filters: Optional filters
            
        Returns:
            Number of records
        """
        query = self.supabase.table(self.table_name).select("id", count="exact")
        
        if filters:
            for field, value in filters.items():
                query = query.eq(field, value)
        
        response = query.execute()
        
        return response.count or 0
    
    # ──────────────────────────────────────────────────────────────────────
    # UPDATE
    # ──────────────────────────────────────────────────────────────────────
    
    def update(self, record_id: str, data: Dict[str, Any]) -> Optional[T]:
        """
        Update record by ID
        
        Args:
            record_id: Record ID
            data: Update data
            
        Returns:
            Updated model instance or None if not found
        """
        # Add updated_at timestamp
        data["updated_at"] = datetime.utcnow().isoformat()
        
        response = (
            self.supabase.table(self.table_name)
            .update(data)
            .eq("id", record_id)
            .execute()
        )
        
        if not response.data:
            return None
        
        return self.model_class.from_db(response.data[0])
    
    def update_many(
        self,
        filters: Dict[str, Any],
        data: Dict[str, Any]
    ) -> List[T]:
        """
        Update multiple records matching filters
        
        Args:
            filters: Dictionary of field:value filters
            data: Update data
            
        Returns:
            List of updated model instances
        """
        data["updated_at"] = datetime.utcnow().isoformat()
        
        query = self.supabase.table(self.table_name).update(data)
        
        for field, value in filters.items():
            query = query.eq(field, value)
        
        response = query.execute()
        
        return [self.model_class.from_db(record) for record in (response.data or [])]
    
    # ──────────────────────────────────────────────────────────────────────
    # DELETE
    # ──────────────────────────────────────────────────────────────────────
    
    def delete(self, record_id: str) -> bool:
        """
        Delete record by ID
        
        Args:
            record_id: Record ID
            
        Returns:
            True if deleted, False if not found
        """
        response = (
            self.supabase.table(self.table_name)
            .delete()
            .eq("id", record_id)
            .execute()
        )
        
        return bool(response.data)
    
    def delete_many(self, filters: Dict[str, Any]) -> int:
        """
        Delete multiple records matching filters
        
        Args:
            filters: Dictionary of field:value filters
            
        Returns:
            Number of deleted records
        """
        query = self.supabase.table(self.table_name).delete()
        
        for field, value in filters.items():
            query = query.eq(field, value)
        
        response = query.execute()
        
        return len(response.data or [])
    
    # ──────────────────────────────────────────────────────────────────────
    # UTILITY
    # ──────────────────────────────────────────────────────────────────────
    
    def exists(self, record_id: str) -> bool:
        """
        Check if record exists
        
        Args:
            record_id: Record ID
            
        Returns:
            True if exists, False otherwise
        """
        return self.count({"id": record_id}) > 0
