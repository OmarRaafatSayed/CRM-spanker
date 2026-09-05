"""
Customer Portal Router
=======================
All endpoints consumed by the external customer-facing website.

Authentication
--------------
Every request must carry a valid Supabase JWT in the Authorization
header (Bearer token).  The customer signs in via the Supabase JS SDK
on the website — same Supabase project as the CRM — so the same token
works for both systems.

Endpoint map
------------
Profile
  POST  /portal/profile/setup         — upsert profile on first login
  GET   /portal/profile               — fetch own profile

Travel Requests
  POST  /portal/requests              — submit a new travel request
  GET   /portal/requests              — list own requests
  GET   /portal/requests/{id}         — request detail + documents + status log
  PATCH /portal/requests/{id}         — update own request (only while status=new)

Documents
  POST  /portal/requests/{id}/documents         — register an uploaded file
  DELETE /portal/requests/{id}/documents/{doc}  — remove an uploaded file

Notifications
  GET   /portal/notifications          — list own notifications
  PATCH /portal/notifications/{id}/read — mark one as read
  POST  /portal/notifications/read-all  — mark all as read

Dashboard
  GET   /portal/dashboard             — summary counters for the portal home page

Public
  GET   /portal/health                — health check (no auth)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator

from app.core.security import AuthContext, require_auth
from app.services.supabase_client import get_supabase
from app.services.notification_service import (
    notify_customer,
    INFO,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# ── helpers ───────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _customer_id(ctx: AuthContext) -> str:
    """Return the auth.users.id for the authenticated customer."""
    return ctx.user_id


def _assert_owns_request(request_row: Dict[str, Any], customer_id: str) -> None:
    """Raise 403 if the request does not belong to this customer."""
    if str(request_row.get("customer_id")) != customer_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Access denied.")


# ── Valid values ──────────────────────────────────────────────────────────────

_REQUEST_TYPES    = frozenset({"visa", "flight", "hotel", "package"})
_REQUEST_STATUSES = frozenset({"new", "in_review", "quoted", "booked", "completed", "cancelled"})
_DOC_TYPES        = frozenset({
    "PASSPORT", "NATIONAL_ID", "PHOTO",
    "BANK_STATEMENT", "SALARY_SLIP",
    "HOTEL_BOOKING", "FLIGHT_BOOKING",
    "TRAVEL_INSURANCE", "OTHER",
})


# ══════════════════════════════════════════════════════════════════════════════
# SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════

# ── Profile ───────────────────────────────────────────────────────────────────

class ProfileSetupRequest(BaseModel):
    first_name: str  = Field(..., min_length=1, max_length=100)
    last_name:  str  = Field(..., min_length=1, max_length=100)
    phone:      Optional[str] = Field(None, max_length=30)

class ProfileResponse(BaseModel):
    id:           str
    user_id:      str
    email:        Optional[str]
    first_name:   Optional[str]
    last_name:    Optional[str]
    phone:        Optional[str]
    role:         str
    created_at:   Optional[str]
    updated_at:   Optional[str]
    model_config = {"extra": "allow"}


# ── Travel requests ───────────────────────────────────────────────────────────

class CreateRequestBody(BaseModel):
    full_name:       str   = Field(..., min_length=1, max_length=200)
    phone:           Optional[str] = Field(None, max_length=30)
    request_type:    str   = Field("visa")
    destination:     str   = Field(..., min_length=1, max_length=200)
    travel_date:     Optional[str] = Field(None, description="YYYY-MM-DD")
    return_date:     Optional[str] = Field(None, description="YYYY-MM-DD")
    num_travelers:   int   = Field(1, ge=1, le=50)
    notes:           Optional[str] = None

    @field_validator("request_type")
    @classmethod
    def valid_type(cls, v: str) -> str:
        if v not in _REQUEST_TYPES:
            raise ValueError(f"request_type must be one of {sorted(_REQUEST_TYPES)}")
        return v


class UpdateRequestBody(BaseModel):
    """Only editable while status = 'new'."""
    full_name:     Optional[str] = Field(None, min_length=1, max_length=200)
    phone:         Optional[str] = Field(None, max_length=30)
    destination:   Optional[str] = Field(None, min_length=1, max_length=200)
    travel_date:   Optional[str] = None
    return_date:   Optional[str] = None
    num_travelers: Optional[int] = Field(None, ge=1, le=50)
    notes:         Optional[str] = None


class RequestResponse(BaseModel):
    id:                  str
    customer_id:         str
    full_name:           str
    phone:               Optional[str]
    email:               Optional[str]
    request_type:        str
    destination:         str
    travel_date:         Optional[str]
    return_date:         Optional[str]
    num_travelers:       int
    notes:               Optional[str]
    status:              str
    visa_application_id: Optional[str]
    created_at:          str
    updated_at:          str
    model_config = {"extra": "allow"}


class RequestDetailResponse(RequestResponse):
    """Extended with documents and status history."""
    documents:   List[Dict[str, Any]] = []
    status_log:  List[Dict[str, Any]] = []


# ── Documents ─────────────────────────────────────────────────────────────────

class RegisterDocumentBody(BaseModel):
    """
    Call this AFTER the website has uploaded the file to Supabase Storage.
    Pass back the resulting public/signed URL so the backend records it.
    """
    doc_type:  str  = Field(..., description="PASSPORT | NATIONAL_ID | PHOTO | …")
    file_url:  str  = Field(..., description="Supabase Storage URL of the uploaded file")
    file_name: str  = Field(..., min_length=1, max_length=255)
    file_size: Optional[int] = Field(None, ge=0, description="Bytes")
    mime_type: Optional[str] = None

    @field_validator("doc_type")
    @classmethod
    def valid_doc_type(cls, v: str) -> str:
        if v.upper() not in _DOC_TYPES:
            raise ValueError(f"doc_type must be one of {sorted(_DOC_TYPES)}")
        return v.upper()


class DocumentResponse(BaseModel):
    id:          str
    customer_id: str
    request_id:  Optional[str]
    doc_type:    str
    file_url:    str
    file_name:   str
    file_size:   Optional[int]
    mime_type:   Optional[str]
    status:      str
    staff_notes: Optional[str]
    created_at:  str
    model_config = {"extra": "allow"}


# ── Notifications ─────────────────────────────────────────────────────────────

class NotificationResponse(BaseModel):
    id:          str
    customer_id: str
    title:       str
    body:        Optional[str]
    type:        str
    is_read:     bool
    data:        Optional[Dict[str, Any]]
    created_at:  str
    model_config = {"extra": "allow"}


# ── Dashboard ─────────────────────────────────────────────────────────────────

class DashboardResponse(BaseModel):
    total_requests:       int
    active_requests:      int   # status in (new, in_review, quoted, booked)
    completed_requests:   int
    total_documents:      int
    pending_documents:    int   # status = uploaded (awaiting review)
    approved_documents:   int
    rejected_documents:   int
    unread_notifications: int
    latest_requests:      List[Dict[str, Any]]   # 3 most recent


# ══════════════════════════════════════════════════════════════════════════════
# HEALTH
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/health")
async def portal_health() -> Dict[str, Any]:
    """Public health check — no auth required."""
    return {"status": "operational", "service": "customer_portal"}


# ══════════════════════════════════════════════════════════════════════════════
# PROFILE
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/profile/setup", response_model=ProfileResponse, status_code=status.HTTP_200_OK)
async def setup_profile(
    body:     ProfileSetupRequest,
    ctx:      AuthContext = Depends(require_auth),
    supabase: Any         = Depends(get_supabase),
) -> ProfileResponse:
    """
    Upsert the customer profile row in `profiles`.

    Call this once when the customer completes registration on the website
    (right after Supabase email confirmation).  Safe to call again to update
    name / phone.

    The profile is given role='customer' so the CRM can distinguish portal
    customers from internal staff accounts.
    """
    uid = _customer_id(ctx)

    upsert_data = {
        "user_id":    uid,
        "email":      ctx.email,
        "first_name": body.first_name,
        "last_name":  body.last_name,
        "phone":      body.phone,
        "role":       "customer",
        "updated_at": _now(),
    }

    try:
        # Try update first — returns data if row exists
        r = (
            supabase.table("profiles")
            .update(upsert_data)
            .eq("user_id", uid)
            .execute()
        )

        if r.data:
            logger.info(f"[portal] Profile updated for {uid[:8]}…")
            return ProfileResponse(**r.data[0])

        # Row doesn't exist yet — insert
        upsert_data["created_at"] = _now()
        r = supabase.table("profiles").insert(upsert_data).execute()

        if not r.data:
            raise HTTPException(status_code=500, detail="Profile creation failed.")

        logger.info(f"[portal] Profile created for {uid[:8]}…")

        # Send welcome notification
        await notify_customer(
            supabase=supabase,
            customer_auth_id=uid,
            title="أهلاً بك! 👋",
            body="تم إنشاء حسابك بنجاح. يمكنك الآن تقديم طلب سفر.",
            notif_type=INFO,
        )

        return ProfileResponse(**r.data[0])

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"[portal] Profile setup failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/profile", response_model=ProfileResponse)
async def get_profile(
    ctx:      AuthContext = Depends(require_auth),
    supabase: Any         = Depends(get_supabase),
) -> ProfileResponse:
    """Return the authenticated customer's profile."""
    uid = _customer_id(ctx)
    try:
        r = supabase.table("profiles").select("*").eq("user_id", uid).limit(1).execute()
        if not r.data:
            raise HTTPException(status_code=404, detail="Profile not found. Call /portal/profile/setup first.")
        return ProfileResponse(**r.data[0])
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ══════════════════════════════════════════════════════════════════════════════
# TRAVEL REQUESTS
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/requests", response_model=RequestResponse, status_code=status.HTTP_201_CREATED)
async def create_request(
    body:     CreateRequestBody,
    ctx:      AuthContext = Depends(require_auth),
    supabase: Any         = Depends(get_supabase),
) -> RequestResponse:
    """
    Submit a new travel request from the website.

    Creates a `customer_requests` row with status='new'.
    The CRM staff will see it in their pipeline as a new lead.
    """
    uid = _customer_id(ctx)
    now = _now()

    row = {
        "customer_id":   uid,
        "full_name":     body.full_name,
        "phone":         body.phone,
        "email":         ctx.email,
        "request_type":  body.request_type,
        "destination":   body.destination,
        "travel_date":   body.travel_date,
        "return_date":   body.return_date,
        "num_travelers": body.num_travelers,
        "notes":         body.notes,
        "status":        "new",
        "created_at":    now,
        "updated_at":    now,
    }

    try:
        r = supabase.table("customer_requests").insert(row).execute()
        if not r.data:
            raise HTTPException(status_code=500, detail="Failed to create request.")

        req = r.data[0]
        logger.info(f"[portal] New request {req['id']} from {uid[:8]}…")

        # Add initial status log entry
        supabase.table("portal_status_log").insert({
            "request_id":  req["id"],
            "customer_id": uid,
            "from_status": None,
            "to_status":   "new",
            "note":        "تم استلام الطلب",
            "created_at":  now,
        }).execute()

        return RequestResponse(**req)

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"[portal] Create request failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/requests", response_model=Dict[str, Any])
async def list_requests(
    ctx:            AuthContext  = Depends(require_auth),
    supabase:       Any          = Depends(get_supabase),
    status_filter:  Optional[str] = Query(None),
    limit:          int           = Query(20, ge=1, le=100),
    offset:         int           = Query(0, ge=0),
) -> Dict[str, Any]:
    """List the authenticated customer's travel requests, newest first."""
    uid = _customer_id(ctx)
    try:
        q = (
            supabase.table("customer_requests")
            .select("*", count="exact")
            .eq("customer_id", uid)
        )
        if status_filter and status_filter in _REQUEST_STATUSES:
            q = q.eq("status", status_filter)

        q = q.order("created_at", desc=True).range(offset, offset + limit - 1)
        r = q.execute()

        return {
            "requests": r.data or [],
            "total":    r.count or 0,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/requests/{request_id}", response_model=RequestDetailResponse)
async def get_request(
    request_id: str,
    ctx:        AuthContext = Depends(require_auth),
    supabase:   Any         = Depends(get_supabase),
) -> RequestDetailResponse:
    """
    Full detail for one request: data + uploaded documents + status history.
    Customers can only view their own requests.
    """
    uid = _customer_id(ctx)
    try:
        # Fetch request
        r = (
            supabase.table("customer_requests")
            .select("*")
            .eq("id", request_id)
            .eq("customer_id", uid)          # ownership enforced here
            .limit(1)
            .execute()
        )
        if not r.data:
            raise HTTPException(status_code=404, detail="Request not found.")

        req = r.data[0]

        # Fetch documents for this request
        docs_r = (
            supabase.table("portal_documents")
            .select("*")
            .eq("request_id", request_id)
            .eq("customer_id", uid)
            .order("created_at", desc=False)
            .execute()
        )

        # Fetch status log
        log_r = (
            supabase.table("portal_status_log")
            .select("*")
            .eq("request_id", request_id)
            .order("created_at", desc=False)
            .execute()
        )

        return RequestDetailResponse(
            **req,
            documents=docs_r.data or [],
            status_log=log_r.data or [],
        )

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.patch("/requests/{request_id}", response_model=RequestResponse)
async def update_request(
    request_id: str,
    body:       UpdateRequestBody,
    ctx:        AuthContext = Depends(require_auth),
    supabase:   Any         = Depends(get_supabase),
) -> RequestResponse:
    """
    Update a travel request.
    Only allowed while status = 'new' (before CRM staff picks it up).
    """
    uid = _customer_id(ctx)
    try:
        # Verify ownership and status
        r = (
            supabase.table("customer_requests")
            .select("*")
            .eq("id", request_id)
            .eq("customer_id", uid)
            .limit(1)
            .execute()
        )
        if not r.data:
            raise HTTPException(status_code=404, detail="Request not found.")

        req = r.data[0]
        if req["status"] != "new":
            raise HTTPException(
                status_code=400,
                detail=f"Cannot edit request in status '{req['status']}'. Only 'new' requests are editable.",
            )

        updates = body.model_dump(exclude_none=True)
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update.")

        updates["updated_at"] = _now()

        upd = (
            supabase.table("customer_requests")
            .update(updates)
            .eq("id", request_id)
            .execute()
        )
        if not upd.data:
            raise HTTPException(status_code=500, detail="Update failed.")

        logger.info(f"[portal] Request {request_id} updated by {uid[:8]}…")
        return RequestResponse(**upd.data[0])

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ══════════════════════════════════════════════════════════════════════════════
# DOCUMENTS
# ══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/requests/{request_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_document(
    request_id: str,
    body:       RegisterDocumentBody,
    ctx:        AuthContext = Depends(require_auth),
    supabase:   Any         = Depends(get_supabase),
) -> DocumentResponse:
    """
    Register a document that was already uploaded to Supabase Storage.

    Upload flow on the website:
      1. Customer picks a file.
      2. Website calls `supabase.storage.from('portal-documents')
             .upload('{uid}/{filename}', file)` directly.
      3. Website gets back the public/signed URL.
      4. Website POSTs that URL to this endpoint.
      5. Backend records the document and triggers a CRM notification.
    """
    uid = _customer_id(ctx)
    try:
        # Verify the request belongs to this customer
        r = (
            supabase.table("customer_requests")
            .select("id, status")
            .eq("id", request_id)
            .eq("customer_id", uid)
            .limit(1)
            .execute()
        )
        if not r.data:
            raise HTTPException(status_code=404, detail="Request not found.")

        now = _now()
        doc_row = {
            "customer_id": uid,
            "request_id":  request_id,
            "doc_type":    body.doc_type,
            "file_url":    body.file_url,
            "file_name":   body.file_name,
            "file_size":   body.file_size,
            "mime_type":   body.mime_type,
            "status":      "uploaded",
            "created_at":  now,
            "updated_at":  now,
        }

        dr = supabase.table("portal_documents").insert(doc_row).execute()
        if not dr.data:
            raise HTTPException(status_code=500, detail="Failed to register document.")

        doc = dr.data[0]
        logger.info(f"[portal] Document {doc['id']} registered for request {request_id}")

        return DocumentResponse(**doc)

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"[portal] Register document failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/requests/{request_id}/documents/{doc_id}", status_code=status.HTTP_200_OK)
async def delete_document(
    request_id: str,
    doc_id:     str,
    ctx:        AuthContext = Depends(require_auth),
    supabase:   Any         = Depends(get_supabase),
) -> Dict[str, Any]:
    """
    Remove an uploaded document.
    Only allowed while document status = 'uploaded' (not yet reviewed by CRM).
    The actual file in Supabase Storage must be deleted separately by the website
    using the Supabase JS SDK.
    """
    uid = _customer_id(ctx)
    try:
        r = (
            supabase.table("portal_documents")
            .select("*")
            .eq("id", doc_id)
            .eq("request_id", request_id)
            .eq("customer_id", uid)
            .limit(1)
            .execute()
        )
        if not r.data:
            raise HTTPException(status_code=404, detail="Document not found.")

        doc = r.data[0]
        if doc["status"] != "uploaded":
            raise HTTPException(
                status_code=400,
                detail=f"Cannot delete a document with status '{doc['status']}'. Only 'uploaded' documents can be deleted.",
            )

        supabase.table("portal_documents").delete().eq("id", doc_id).execute()
        logger.info(f"[portal] Document {doc_id} deleted by {uid[:8]}…")

        return {"success": True, "deleted_id": doc_id}

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ══════════════════════════════════════════════════════════════════════════════
# NOTIFICATIONS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/notifications", response_model=Dict[str, Any])
async def list_notifications(
    ctx:       AuthContext  = Depends(require_auth),
    supabase:  Any          = Depends(get_supabase),
    unread_only: bool       = Query(False),
    limit:     int          = Query(30, ge=1, le=100),
    offset:    int          = Query(0, ge=0),
) -> Dict[str, Any]:
    """
    Fetch the customer's notifications.
    Unread notifications are always returned first, then sorted by newest.
    """
    uid = _customer_id(ctx)
    try:
        q = (
            supabase.table("portal_notifications")
            .select("*", count="exact")
            .eq("customer_id", uid)
        )
        if unread_only:
            q = q.eq("is_read", False)

        # Unread first, then newest
        q = (
            q.order("is_read", desc=False)
             .order("created_at", desc=True)
             .range(offset, offset + limit - 1)
        )

        r = q.execute()

        # Unread count (always returned regardless of filter)
        unread_r = (
            supabase.table("portal_notifications")
            .select("id", count="exact")
            .eq("customer_id", uid)
            .eq("is_read", False)
            .execute()
        )

        return {
            "notifications": r.data or [],
            "total":         r.count or 0,
            "unread_count":  unread_r.count or 0,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.patch("/notifications/{notif_id}/read", status_code=status.HTTP_200_OK)
async def mark_notification_read(
    notif_id: str,
    ctx:      AuthContext = Depends(require_auth),
    supabase: Any         = Depends(get_supabase),
) -> Dict[str, Any]:
    """Mark a single notification as read."""
    uid = _customer_id(ctx)
    try:
        r = (
            supabase.table("portal_notifications")
            .update({"is_read": True})
            .eq("id", notif_id)
            .eq("customer_id", uid)         # ownership enforced
            .execute()
        )
        if not r.data:
            raise HTTPException(status_code=404, detail="Notification not found.")

        return {"success": True, "notification_id": notif_id}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/notifications/read-all", status_code=status.HTTP_200_OK)
async def mark_all_notifications_read(
    ctx:      AuthContext = Depends(require_auth),
    supabase: Any         = Depends(get_supabase),
) -> Dict[str, Any]:
    """Mark ALL unread notifications for this customer as read."""
    uid = _customer_id(ctx)
    try:
        r = (
            supabase.table("portal_notifications")
            .update({"is_read": True})
            .eq("customer_id", uid)
            .eq("is_read", False)
            .execute()
        )
        updated_count = len(r.data) if r.data else 0
        logger.info(f"[portal] Marked {updated_count} notifications read for {uid[:8]}…")
        return {"success": True, "marked_read": updated_count}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

_ACTIVE_STATUSES = ("new", "in_review", "quoted", "booked")

@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    ctx:      AuthContext = Depends(require_auth),
    supabase: Any         = Depends(get_supabase),
) -> DashboardResponse:
    """
    Single-call dashboard summary for the portal home page.

    Returns counters and the 3 most recent requests so the website
    can render a useful home screen without multiple round-trips.
    """
    uid = _customer_id(ctx)
    try:
        # ── Requests ─────────────────────────────────────────────────────────
        all_req_r = (
            supabase.table("customer_requests")
            .select("id, status, destination, request_type, travel_date, updated_at", count="exact")
            .eq("customer_id", uid)
            .order("created_at", desc=True)
            .execute()
        )
        all_reqs      = all_req_r.data or []
        total_req     = all_req_r.count or 0
        active_req    = sum(1 for r in all_reqs if r["status"] in _ACTIVE_STATUSES)
        completed_req = sum(1 for r in all_reqs if r["status"] == "completed")
        latest_reqs   = all_reqs[:3]

        # ── Documents ─────────────────────────────────────────────────────────
        docs_r = (
            supabase.table("portal_documents")
            .select("status", count="exact")
            .eq("customer_id", uid)
            .execute()
        )
        docs           = docs_r.data or []
        total_docs     = docs_r.count or 0
        pending_docs   = sum(1 for d in docs if d["status"] == "uploaded")
        approved_docs  = sum(1 for d in docs if d["status"] == "approved")
        rejected_docs  = sum(1 for d in docs if d["status"] == "rejected")

        # ── Notifications ─────────────────────────────────────────────────────
        notif_r = (
            supabase.table("portal_notifications")
            .select("id", count="exact")
            .eq("customer_id", uid)
            .eq("is_read", False)
            .execute()
        )
        unread_notifs = notif_r.count or 0

        return DashboardResponse(
            total_requests=total_req,
            active_requests=active_req,
            completed_requests=completed_req,
            total_documents=total_docs,
            pending_documents=pending_docs,
            approved_documents=approved_docs,
            rejected_documents=rejected_docs,
            unread_notifications=unread_notifs,
            latest_requests=latest_reqs,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"[portal] Dashboard failed for {uid[:8]}…: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
