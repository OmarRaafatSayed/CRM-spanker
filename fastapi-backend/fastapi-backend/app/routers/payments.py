"""
Payments Router - Financial Transactions Management

Implements payment tracking from CRM-RULES.MD:
- financial_transactions table
- amount_paid, remaining_balance
- payment_method: CASH, BANK_TRANSFER, POS
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from app.core.security import AuthToken, require_auth
from app.services.supabase_client import get_supabase

logger = logging.getLogger(__name__)
router = APIRouter()

_VALID_METHODS = {"CASH", "BANK_TRANSFER", "POS"}


# ── Schemas ───────────────────────────────────────────────────────────────────

class TransactionCreate(BaseModel):
    booking_id: str; user_id: str; amount_paid: float = Field(..., gt=0)
    remaining_balance: float = Field(..., ge=0)
    payment_method: str; receipt_url: Optional[str] = None

    @field_validator("payment_method")
    @classmethod
    def method_valid(cls, v: str) -> str:
        if v not in _VALID_METHODS:
            raise ValueError(f"payment_method must be one of {_VALID_METHODS}")
        return v

class TransactionResponse(BaseModel):
    id: str; booking_id: str; user_id: str; amount_paid: float
    remaining_balance: float; payment_method: str
    receipt_url: Optional[str] = None; paid_at: Optional[str] = None
    model_config = {"extra": "allow"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _require_staff(token: AuthToken) -> AuthToken:
    if token.role not in ("staff", "admin"):
        raise HTTPException(403, "Staff access required")
    return token


# ── POST /transactions ────────────────────────────────────────────────────────

@router.post("/transactions", response_model=TransactionResponse, status_code=201)
async def create_transaction(
    body: TransactionCreate,
    token: AuthToken = Depends(require_auth),
    supabase: Any = Depends(get_supabase),
):
    """Create financial transaction for booking"""
    _require_staff(token)
    data = body.model_dump(exclude_none=False)
    try:
        r = supabase.table("financial_transactions").insert(data).execute()
        row = r.data[0] if r.data else None
        if not row:
            raise HTTPException(500, "Insert failed")
        logger.info(f"[payments] Created transaction {row['id']} by {token.user_id}")
        return TransactionResponse(**row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


# ── GET /transactions ─────────────────────────────────────────────────────────

@router.get("/transactions", response_model=Dict[str, Any])
async def list_transactions(
    token: AuthToken = Depends(require_auth),
    supabase: Any = Depends(get_supabase),
    booking_id: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List financial transactions"""
    _require_staff(token)
    try:
        q = supabase.table("financial_transactions").select("*", count="exact")
        if booking_id:
            q = q.eq("booking_id", booking_id)
        if user_id:
            q = q.eq("user_id", user_id)
        q = q.order("created_at", desc=True).range(offset, offset + limit - 1)
        r = q.execute()
        return {"transactions": r.data or [], "total": r.count or 0}
    except Exception as e:
        raise HTTPException(500, str(e))

@router.get("/transactions/{trans_id}", response_model=TransactionResponse)
async def get_transaction(
    trans_id: str,
    token: AuthToken = Depends(require_auth),
    supabase: Any = Depends(get_supabase),
):
    """Get transaction details"""
    _require_staff(token)
    try:
        r = supabase.table("financial_transactions").select("*").eq("id", trans_id).limit(1).execute()
        if not r.data:
            raise HTTPException(404, "Transaction not found")
        return TransactionResponse(**r.data[0])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


# ── PATCH /transactions/{id}/payment ──────────────────────────────────────────

@router.patch("/transactions/{trans_id}/payment")
async def record_payment(
    trans_id: str,
    amount: float = Query(..., gt=0),
    method: str = Query(...),
    receipt_url: Optional[str] = Query(None),
    token: AuthToken = Depends(require_auth),
    supabase: Any = Depends(get_supabase),
):
    """Record payment for transaction"""
    _require_staff(token)
    if method not in _VALID_METHODS:
        raise HTTPException(400, f"Invalid method: {method}")
    
    try:
        # Get transaction
        r = supabase.table("financial_transactions").select("*").eq("id", trans_id).limit(1).execute()
        if not r.data:
            raise HTTPException(404, "Transaction not found")
        trans = r.data[0]
        
        # Calculate new remaining balance
        new_paid = trans.get("amount_paid", 0) + amount
        new_remaining = max(0, trans.get("remaining_balance", 0) - amount)
        
        # Update transaction
        upd = supabase.table("financial_transactions").update({
            "amount_paid": new_paid,
            "remaining_balance": new_remaining,
            "payment_method": method,
            "receipt_url": receipt_url,
            "paid_at": __import__("datetime").datetime.utcnow().isoformat(),
        }).eq("id", trans_id).execute()
        
        # If fully paid, update booking status
        if new_remaining <= 0:
            booking_id = trans.get("booking_id")
            supabase.table("bookings").update({"status": "CONFIRMED"}).eq("id", booking_id).execute()
        
        logger.info(f"[payments] Payment {amount} recorded for {trans_id}")
        return {"success": True, "transaction_id": trans_id, "amount": amount, "remaining": new_remaining}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/health")
async def health():
    return {"status": "operational", "service": "payments"}
