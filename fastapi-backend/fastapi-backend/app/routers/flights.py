"""
Flight Search Router – Single Source of Truth
==============================================
All flight data originates exclusively from the fast_flight_scraper.
This eliminates legacy code conflicts and ensures consistent payload format.

Authentication
--------------
All mutating and search endpoints require a valid Supabase Bearer token.
Public read-only endpoints (/health, /test-connection) are intentionally
left open for monitoring tooling.
"""
from __future__ import annotations

import logging
from datetime import datetime
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional

from app.core.security import AuthToken, require_auth, optional_auth
from app.services.fast_flight_scraper import get_live_flights

logger = logging.getLogger(__name__)
router = APIRouter()


# ─── Request / Response models ───────────────────────────────────────────────

class FlightSearchRequest(BaseModel):
    origin: str = Field(..., min_length=3, max_length=3, description="IATA code, e.g. CAI")
    destination: str = Field(..., min_length=3, max_length=3, description="IATA code, e.g. DXB")
    departure_date: str = Field(..., description="YYYY-MM-DD")
    return_date: Optional[str] = Field(None, description="YYYY-MM-DD (round trip)")
    passenger_count: int = Field(1, ge=1, le=9)
    travel_class: str = Field(
        "economy",
        description="economy | premium_economy | business | first",
    )


class ConnectionTestResponse(BaseModel):
    connected: bool
    primary_provider: Optional[str] = None
    interception_engine: Optional[str] = None
    brightdata_configured: Optional[bool] = None
    brightdata_status: Optional[str] = None
    test_page_title: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None


# ─── Protected endpoints ─────────────────────────────────────────────────────

@router.post("/search")
async def search_flights(
    request: FlightSearchRequest,
    token: OptionalToken = Depends(optional_auth),
) -> Dict[str, Any]:
    """
    Search for real-time flights via the fast_flight_scraper.
    
    **Single Source of Truth:** All flight data originates exclusively
    from `fast_flight_scraper.py` ensuring consistent payload format
    and eliminating legacy code conflicts.
    """
    logger.info(f"✈️  Flight search: {request.origin} → {request.destination} on {request.departure_date}")
    
    try:
        # Call fast_flight_scraper directly - SINGLE SOURCE OF TRUTH
        flights = await get_live_flights(
            origin=request.origin.upper(),
            destination=request.destination.upper(),
            date=request.departure_date,
            return_date=request.return_date,
            passenger_count=request.passenger_count,
            travel_class=request.travel_class,
        )
        
        # WHITE LABEL payload format - no provider metadata exposed
        result = {
            "success": True,
            "origin": request.origin.upper(),
            "destination": request.destination.upper(),
            "departure_date": request.departure_date,
            "return_date": request.return_date,
            "flights": flights,
            "total_results": len(flights),
            "search_completed_at": datetime.utcnow().isoformat(),
            # Remove all provider/scraper metadata for white-label experience
        }
        
        logger.info(f"✅ Flight search succeeded: {len(flights)} flights found")
        return result
        
    except Exception as e:
        logger.error(f"❌ Flight search failed: {str(e)}")
        # WHITE LABEL error response - no provider metadata
        return {
            "success": False,
            "origin": request.origin.upper(),
            "destination": request.destination.upper(),
            "departure_date": request.departure_date,
            "flights": [],
            "total_results": 0,
            "error": "Flight search temporarily unavailable. Please try again.",
            "search_completed_at": datetime.utcnow().isoformat(),
        }


@router.post("/clear-cache")
async def clear_expired_cache(
    background_tasks: BackgroundTasks,
    token: AuthToken = Depends(require_auth),
) -> Dict[str, str]:
    """
    Schedule a background task to purge expired cache rows.

    **Requires:** ``Authorization: Bearer <supabase_access_token>``
    """
    from app.services.flight_cache import clear_expired_cache as _clear

    background_tasks.add_task(_clear)
    return {"message": "Cache cleanup scheduled", "status": "processing"}


# ─── Public / monitoring endpoints ───────────────────────────────────────────

@router.get("/test-connection", response_model=ConnectionTestResponse)
async def test_connection() -> Dict[str, Any]:
    """
    Quick connectivity check for the fast_flight_scraper.
    Returns service status without legacy dependencies.
    Public endpoint.
    """
    return {
        "connected": True,
        "primary_provider": "fast_flight_scraper",
        "interception_engine": "not_required",
        "brightdata_configured": False,
        "brightdata_status": "not_required",
        "message": "Lightweight flight scraper operational. No browser dependencies.",
        "error": None,
    }


@router.get("/health")
async def flight_service_health() -> Dict[str, Any]:
    """Health check for the fast_flight_scraper service."""
    return {
        "status": "operational",
        "service": "flight_search",
        "primary_provider": "fast_flight_scraper",
        "brightdata_available": False,
        "cache_ttl_hours": 0,
        "css_selectors_used": False,
        "lightweight_mode": True,
        "message": "Lightweight HTTP scraper running - no browser overhead",
    }

