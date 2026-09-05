"""
Portal API — Pydantic Schemas Reference
========================================
This file is the single source of truth for all request / response
shapes used by the Customer Portal router (portal.py).

It is intentionally kept as a plain reference module (no imports from
other app modules) so it can be read in isolation, copy-pasted, or
used to auto-generate TypeScript types with tools like datamodel-code-generator.

TypeScript equivalent types are included as docstring comments above
each class for the frontend developer.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator

# ── valid sets ────────────────────────────────────────────────────────────────
REQUEST_TYPES    = ["visa", "flight", "hotel", "package"]
REQUEST_STATUSES = ["new", "in_review", "quoted", "booked", "completed", "cancelled"]
DOC_TYPES        = [
    "PASSPORT", "NATIONAL_ID", "PHOTO",
    "BANK_STATEMENT", "SALARY_SLIP",
    "HOTEL_BOOKING", "FLIGHT_BOOKING",
    "TRAVEL_INSURANCE", "OTHER",
]
DOC_STATUSES     = ["uploaded", "under_review", "approved", "rejected", "expired"]
NOTIF_TYPES      = [
    "status_update", "document_approved", "document_rejected",
    "payment_due", "payment_confirmed", "message", "info",
]


# ══════════════════════════════════════════════════════════════════════════════
# PROFILE
# TypeScript:
#   interface ProfileSetupRequest { first_name: string; last_name: string; phone?: string }
#   interface ProfileResponse {
#     id: string; user_id: string; email?: string; first_name?: string;
#     last_name?: string; phone?: string; role: string;
#     created_at?: string; updated_at?: string;
#   }
# ══════════════════════════════════════════════════════════════════════════════

class ProfileSetupRequest(BaseModel):
    first_name: str           = Field(..., min_length=1, max_length=100)
    last_name:  str           = Field(..., min_length=1, max_length=100)
    phone:      Optional[str] = Field(None, max_length=30)

class ProfileResponse(BaseModel):
    id:         str;  user_id:    str;  email:      Optional[str]
    first_name: Optional[str];   last_name:  Optional[str]
    phone:      Optional[str];   role:       str
    created_at: Optional[str];   updated_at: Optional[str]
    model_config = {"extra": "allow"}


# ══════════════════════════════════════════════════════════════════════════════
# TRAVEL REQUESTS
# TypeScript:
#   type RequestType    = "visa" | "flight" | "hotel" | "package"
#   type RequestStatus  = "new"|"in_review"|"quoted"|"booked"|"completed"|"cancelled"
#
#   interface CreateRequestBody {
#     full_name: string; phone?: string;
#     request_type: RequestType; destination: string;
#     travel_date?: string; return_date?: string;
#     num_travelers?: number; notes?: string;
#   }
#
#   interface RequestResponse {
#     id: string; customer_id: string; full_name: string; phone?: string;
#     email?: string; request_type: RequestType; destination: string;
#     travel_date?: string; return_date?: string; num_travelers: number;
#     notes?: string; status: RequestStatus;
#     visa_application_id?: string;
#     created_at: string; updated_at: string;
#   }
#
#   interface RequestDetailResponse extends RequestResponse {
#     documents: DocumentResponse[];
#     status_log: StatusLogEntry[];
#   }
#
#   interface StatusLogEntry {
#     id: string; request_id: string; customer_id: string;
#     from_status?: string; to_status: string;
#     changed_by?: string; note?: string; created_at: string;
#   }
# ══════════════════════════════════════════════════════════════════════════════

class CreateRequestBody(BaseModel):
    full_name:     str           = Field(..., min_length=1, max_length=200)
    phone:         Optional[str] = Field(None, max_length=30)
    request_type:  str           = Field("visa")
    destination:   str           = Field(..., min_length=1, max_length=200)
    travel_date:   Optional[str] = Field(None, description="YYYY-MM-DD")
    return_date:   Optional[str] = Field(None, description="YYYY-MM-DD")
    num_travelers: int           = Field(1, ge=1, le=50)
    notes:         Optional[str] = None

    @field_validator("request_type")
    @classmethod
    def valid_type(cls, v: str) -> str:
        if v not in REQUEST_TYPES:
            raise ValueError(f"Must be one of {REQUEST_TYPES}")
        return v

class UpdateRequestBody(BaseModel):
    full_name:     Optional[str] = Field(None, min_length=1, max_length=200)
    phone:         Optional[str] = Field(None, max_length=30)
    destination:   Optional[str] = Field(None, min_length=1, max_length=200)
    travel_date:   Optional[str] = None
    return_date:   Optional[str] = None
    num_travelers: Optional[int] = Field(None, ge=1, le=50)
    notes:         Optional[str] = None

class RequestResponse(BaseModel):
    id: str; customer_id: str; full_name: str
    phone: Optional[str]; email: Optional[str]
    request_type: str; destination: str
    travel_date: Optional[str]; return_date: Optional[str]
    num_travelers: int; notes: Optional[str]; status: str
    visa_application_id: Optional[str]
    created_at: str; updated_at: str
    model_config = {"extra": "allow"}

class RequestDetailResponse(RequestResponse):
    documents:  List[Dict[str, Any]] = []
    status_log: List[Dict[str, Any]] = []

class ListRequestsResponse(BaseModel):
    requests: List[Dict[str, Any]]
    total:    int


# ══════════════════════════════════════════════════════════════════════════════
# DOCUMENTS
# TypeScript:
#   type DocType   = "PASSPORT"|"NATIONAL_ID"|"PHOTO"|"BANK_STATEMENT"|
#                    "SALARY_SLIP"|"HOTEL_BOOKING"|"FLIGHT_BOOKING"|
#                    "TRAVEL_INSURANCE"|"OTHER"
#   type DocStatus = "uploaded"|"under_review"|"approved"|"rejected"|"expired"
#
#   interface RegisterDocumentBody {
#     doc_type: DocType; file_url: string; file_name: string;
#     file_size?: number; mime_type?: string;
#   }
#
#   interface DocumentResponse {
#     id: string; customer_id: string; request_id?: string;
#     doc_type: DocType; file_url: string; file_name: string;
#     file_size?: number; mime_type?: string;
#     status: DocStatus; staff_notes?: string; created_at: string;
#   }
# ══════════════════════════════════════════════════════════════════════════════

class RegisterDocumentBody(BaseModel):
    doc_type:  str           = Field(..., description="PASSPORT | PHOTO | …")
    file_url:  str           = Field(..., description="Supabase Storage URL")
    file_name: str           = Field(..., min_length=1, max_length=255)
    file_size: Optional[int] = Field(None, ge=0)
    mime_type: Optional[str] = None

    @field_validator("doc_type")
    @classmethod
    def valid_doc_type(cls, v: str) -> str:
        if v.upper() not in DOC_TYPES:
            raise ValueError(f"Must be one of {DOC_TYPES}")
        return v.upper()

class DocumentResponse(BaseModel):
    id: str; customer_id: str; request_id: Optional[str]
    doc_type: str; file_url: str; file_name: str
    file_size: Optional[int]; mime_type: Optional[str]
    status: str; staff_notes: Optional[str]; created_at: str
    model_config = {"extra": "allow"}


# ══════════════════════════════════════════════════════════════════════════════
# NOTIFICATIONS
# TypeScript:
#   type NotifType = "status_update"|"document_approved"|"document_rejected"|
#                    "payment_due"|"payment_confirmed"|"message"|"info"
#
#   interface NotificationResponse {
#     id: string; customer_id: string; title: string; body?: string;
#     type: NotifType; is_read: boolean; data?: Record<string,any>;
#     created_at: string;
#   }
#
#   interface ListNotificationsResponse {
#     notifications: NotificationResponse[];
#     total: number;
#     unread_count: number;
#   }
# ══════════════════════════════════════════════════════════════════════════════

class NotificationResponse(BaseModel):
    id: str; customer_id: str; title: str
    body: Optional[str]; type: str; is_read: bool
    data: Optional[Dict[str, Any]]; created_at: str
    model_config = {"extra": "allow"}

class ListNotificationsResponse(BaseModel):
    notifications: List[NotificationResponse]
    total:         int
    unread_count:  int


# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# TypeScript:
#   interface DashboardResponse {
#     total_requests: number;    active_requests: number;
#     completed_requests: number;
#     total_documents: number;   pending_documents: number;
#     approved_documents: number; rejected_documents: number;
#     unread_notifications: number;
#     latest_requests: Partial<RequestResponse>[];
#   }
# ══════════════════════════════════════════════════════════════════════════════

class DashboardResponse(BaseModel):
    total_requests:       int
    active_requests:      int
    completed_requests:   int
    total_documents:      int
    pending_documents:    int
    approved_documents:   int
    rejected_documents:   int
    unread_notifications: int
    latest_requests:      List[Dict[str, Any]]
