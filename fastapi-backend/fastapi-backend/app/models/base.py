"""
Base Model
Common fields and utilities for all database models
"""
from typing import Optional, Any, Dict
from datetime import datetime
from pydantic import BaseModel, Field


class BaseDBModel(BaseModel):
    """Base model with common database fields"""
    
    id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
        "extra": "allow"
    }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary"""
        return self.model_dump(exclude_none=False)
    
    def to_db_dict(self) -> Dict[str, Any]:
        """Convert model to database dictionary (exclude None values)"""
        return self.model_dump(exclude_none=True, exclude_unset=True)
    
    @classmethod
    def from_db(cls, data: Dict[str, Any]) -> "BaseDBModel":
        """Create model instance from database row"""
        return cls(**data)
