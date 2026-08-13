"""
Hotels Router
=============
Full CRUD implementation for hotel-offer management backed by Supabase.

Table: public.hotel_offers  (defined in single-tenant-migration.sql)
RLS:   authenticated users have full access (auth.role() = 'authenticated')

Authentication & Data Isolation
---------------------------------
Every write operation tags the row with ``created_by`` = the profile UUID
that belongs to the authenticated user.  Search queries are scoped to the
same ``created_by`` value so users only see their own records.

The Supabase service-role key (used by the backend) bypasses RLS, so the
``created_by`` filter is enforced here in application code — not relying
solely on RLS — giving us defence-in-depth.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator

from app.core.security import AuthToken, require_auth
from app.services.supabase_client import get_supabase

logger = logging.getLogger(__name__)
router = APIRouter()


# ─── Constants ────────────────────────────────────────────────────────────────

_TABLE = "hotel_offers"
_PROFILES_TABLE = "profiles"

# Valid source values that match the DB convention
_VALID_SOURCES = frozenset(
    {"manual", "excel_upload", "word_upload", "csv_upload"}
)


# ─── Pydantic schemas ─────────────────────────────────────────────────────────

class HotelOfferCreate(BaseModel):
    """
    Inbound schema for a single hotel offer.
    Field names map 1-to-1 with the hotel_offers table columns.
    """
    # Hotel identity
    hotel_name: str = Field(..., min_length=1, max_length=255)
    hotel_location: str = Field(..., min_length=1, max_length=255)
    hotel_city: str = Field(..., min_length=1, max_length=100)
    hotel_country: str = Field(..., min_length=1, max_length=100)
    hotel_rating: Optional[float] = Field(None, ge=0.0, le=5.0)
    hotel_category: Optional[str] = Field(None, max_length=50)

    # Room details
    room_type: str = Field(..., min_length=1, max_length=100)
    board_basis: Optional[str] = Field(None, max_length=50)

    # Pricing — stored as DECIMAL(10,2) in Postgres
    price_per_night: float = Field(..., gt=0)
    price_currency: str = Field("EGP", min_length=3, max_length=3)
    special_offer_price: Optional[float] = Field(None, gt=0)

    # Availability — stored as DATE in Postgres
    available_from: str = Field(..., description="YYYY-MM-DD")
    available_to: str = Field(..., description="YYYY-MM-DD")
    booking_deadline: Optional[str] = Field(None, description="YYYY-MM-DD")

    # Capacity
    max_occupancy: Optional[int] = Field(None, ge=1)
    available_rooms: Optional[int] = Field(None, ge=0)

    # Rich content
    amenities: Optional[List[str]] = None
    description: Optional[str] = None
    terms_conditions: Optional[str] = None
    cancellation_policy: Optional[str] = None

    # Provenance
    source: str = Field("manual", description="manual | excel_upload | word_upload | csv_upload")
    uploaded_file_reference: Optional[str] = None

    @field_validator("source")
    @classmethod
    def source_must_be_valid(cls, v: str) -> str:
        if v not in _VALID_SOURCES:
            raise ValueError(
                f"Invalid source '{v}'. Must be one of: {sorted(_VALID_SOURCES)}"
            )
        return v

    @field_validator("available_to")
    @classmethod
    def available_to_must_be_after_from(cls, v: str, info: Any) -> str:
        from_val = info.data.get("available_from")
        if from_val and v < from_val:
            raise ValueError("available_to must be on or after available_from")
        return v


class HotelOfferResponse(BaseModel):
    """
    Outbound schema. Mirrors the table columns we return to the caller.
    Extra DB columns (amenities, descriptions, etc.) are included via the
    full ``select('*')`` — Pydantic will pass them through transparently
    because we use ``model_config = {"extra": "allow"}``.
    """
    id: str
    hotel_name: str
    hotel_location: str
    hotel_city: str
    hotel_country: str
    hotel_rating: Optional[float] = None
    hotel_category: Optional[str] = None
    room_type: str
    board_basis: Optional[str] = None
    price_per_night: float
    price_currency: str
    special_offer_price: Optional[float] = None
    available_from: str
    available_to: str
    booking_deadline: Optional[str] = None
    max_occupancy: Optional[int] = None
    available_rooms: Optional[int] = None
    amenities: Optional[List[str]] = None
    description: Optional[str] = None
    terms_conditions: Optional[str] = None
    cancellation_policy: Optional[str] = None
    source: Optional[str] = None
    is_active: bool
    created_by: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = {"extra": "allow"}


class BulkInsertResponse(BaseModel):
    success: bool
    inserted_count: int
    failed_count: int
    message: str
    inserted_ids: List[str]
    errors: List[str]


class SearchResponse(BaseModel):
    results: List[Dict[str, Any]]
    count: int
    filters_applied: Dict[str, Any]


# ─── Internal helpers ─────────────────────────────────────────────────────────

def _get_profile_id(supabase: Any, auth_user_id: str) -> Optional[str]:
    """Get profile ID for user. Returns None if not found."""
    try:
        resp = supabase.table(_PROFILES_TABLE).select("id").eq("user_id", auth_user_id).limit(1).execute()
        return str(resp.data[0]["id"]) if resp.data else None
    except Exception as exc:
        logger.warning(f"Profile lookup failed for {auth_user_id}: {exc}")
        return None


def _build_hotel_record(hotel: HotelOfferCreate, profile_id: Optional[str]) -> Dict[str, Any]:
    """Transform HotelOfferCreate to database record."""
    data = hotel.model_dump(exclude_none=False)
    for col in ("id", "is_active", "created_at", "updated_at"):
        data.pop(col, None)
    data["created_by"] = profile_id
    return data


def _validate_hotel_records(hotels: List[HotelOfferCreate]) -> List[str]:
    """Validate hotel records. Returns list of errors."""
    errors = []
    for idx, hotel in enumerate(hotels):
        try:
            hotel.model_validate(hotel.model_dump())
        except Exception as exc:
            errors.append(f"Row {idx + 1} ({hotel.hotel_name!r}): {exc}")
    return errors


def _map_search_filters(
    query: Any,
    city: Optional[str],
    country: Optional[str],
    min_price: Optional[float],
    max_price: Optional[float],
    hotel_rating: Optional[float],
    available_from: Optional[str],
    available_to: Optional[str],
    source: Optional[str],
    include_inactive: bool,
) -> Any:
    """Apply filters to search query."""
    if not include_inactive:
        query = query.eq("is_active", True)
    if city:
        query = query.ilike("hotel_city", f"%{city}%")
    if country:
        query = query.ilike("hotel_country", f"%{country}%")
    if min_price is not None:
        query = query.gte("price_per_night", min_price)
    if max_price is not None:
        query = query.lte("price_per_night", max_price)
    if hotel_rating is not None:
        query = query.gte("hotel_rating", hotel_rating)
    if available_from:
        query = query.gte("available_to", available_from)
    if available_to:
        query = query.lte("available_from", available_to)
    if source and source in _VALID_SOURCES:
        query = query.eq("source", source)
    return query


def _classify_db_error(exc: Exception, context: str) -> HTTPException:
    """
    Translate Supabase/PostgREST exceptions into meaningful HTTP errors.
    Avoids leaking raw SQL errors to the caller while still being actionable.
    """
    msg = str(exc)
    logger.error(f"[hotels] DB error in {context}: {msg}")

    if "violates foreign key constraint" in msg:
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Insert failed: the created_by user profile does not exist. "
                "Ensure your account profile is fully created before uploading hotels."
            ),
        )
    if "violates not-null constraint" in msg:
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insert failed: a required column has a null value. Detail: {msg}",
        )
    if "duplicate key" in msg or "unique constraint" in msg:
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="One or more records already exist in the database.",
        )
    if "permission denied" in msg or "row-level security" in msg.lower():
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Database permission denied. Check Supabase RLS policies.",
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Database operation failed in {context}: {msg}",
    )


# ─── POST /bulk-insert ────────────────────────────────────────────────────────

@router.post(
    "/bulk-insert",
    response_model=BulkInsertResponse,
    status_code=status.HTTP_201_CREATED,
)
async def bulk_insert_hotels(
    hotels: List[HotelOfferCreate],
    token: AuthToken = Depends(require_auth),
    supabase: Any = Depends(get_supabase),
) -> BulkInsertResponse:
    """Persist list of hotel offers to database."""
    if not hotels:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No hotel records provided. Send at least one offer.",
        )

    if len(hotels) > 500:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Batch too large. Maximum 500 records per request.",
        )

    # Validate records
    row_errors = _validate_hotel_records(hotels)
    if row_errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Validation failed", "errors": row_errors},
        )

    profile_id = _get_profile_id(supabase, token.user_id)
    if profile_id is None:
        logger.warning(f"No profile for {token.user_id}")

    # Build records
    records = [_build_hotel_record(hotel, profile_id) for hotel in hotels]

    try:
        response = supabase.table(_TABLE).insert(records).execute()
    except Exception as exc:
        raise _classify_db_error(exc, "bulk_insert_hotels")

    inserted_ids = [str(row["id"]) for row in (response.data or []) if "id" in row]

    logger.info(f"[hotels] Inserted {len(inserted_ids)} records for user={token.user_id}")

    return BulkInsertResponse(
        success=True,
        inserted_count=len(inserted_ids),
        failed_count=len(hotels) - len(inserted_ids),
        message=f"Successfully inserted {len(inserted_ids)} of {len(hotels)} hotel offers.",
        inserted_ids=inserted_ids,
        errors=[],
    )


# ─── GET /search ──────────────────────────────────────────────────────────────

@router.get("/search", response_model=SearchResponse)
async def search_hotels(
    token: AuthToken = Depends(require_auth),
    supabase: Any = Depends(get_supabase),
    city: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    available_from: Optional[str] = Query(None),
    available_to: Optional[str] = Query(None),
    hotel_rating: Optional[float] = Query(None, ge=0.0, le=5.0),
    source: Optional[str] = Query(None),
    include_inactive: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> SearchResponse:
    """Search hotel offers with filters."""
    profile_id = _get_profile_id(supabase, token.user_id)

    try:
        query = supabase.table(_TABLE).select("*", count="exact")

        if profile_id:
            query = query.eq("created_by", profile_id)
        else:
            logger.warning(f"No profile for {token.user_id}")
            return SearchResponse(
                results=[],
                count=0,
                filters_applied={"warning": "No profile found"},
            )

        # Apply filters
        query = _map_search_filters(
            query, city, country, min_price, max_price, hotel_rating,
            available_from, available_to, source, include_inactive
        )

        # Pagination
        query = query.order("created_at", desc=True).range(offset, offset + limit - 1)

        response = query.execute()
        results = response.data or []
        total_count = response.count if response.count is not None else len(results)

        logger.info(f"[hotels] search: {len(results)} results for user={token.user_id}")

        return SearchResponse(
            results=results,
            count=total_count,
            filters_applied={
                "city": city,
                "country": country,
                "min_price": min_price,
                "max_price": max_price,
                "limit": limit,
                "offset": offset,
            },
        )

    except HTTPException:
        raise
    except Exception as exc:
        raise _classify_db_error(exc, "search_hotels")


# ─── DELETE /offers/{id} ──────────────────────────────────────────────────────

@router.delete("/offers/{offer_id}", status_code=status.HTTP_200_OK)
async def deactivate_hotel_offer(
    offer_id: str,
    token: AuthToken = Depends(require_auth),
    supabase: Any = Depends(get_supabase),
) -> Dict[str, Any]:
    """Soft-delete (deactivate) a hotel offer."""
    profile_id = _get_profile_id(supabase, token.user_id)
    if not profile_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No profile found for this account.",
        )

    try:
        response = (
            supabase.table(_TABLE)
            .update({"is_active": False})
            .eq("id", offer_id)
            .eq("created_by", profile_id)
            .execute()
        )
        updated = response.data or []
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Offer {offer_id!r} not found or not owned by you.",
            )
        logger.info(f"[hotels] Deactivated {offer_id} by {token.user_id}")
        return {"success": True, "deactivated_id": offer_id}

    except HTTPException:
        raise
    except Exception as exc:
        raise _classify_db_error(exc, f"deactivate_hotel_offer({offer_id})")


# ─── Public / monitoring ──────────────────────────────────────────────────────

@router.get("/health")
async def hotels_health() -> Dict[str, Any]:
    """Hotels service health check. Public endpoint — no auth required."""
    return {"status": "operational", "service": "hotels_management"}
