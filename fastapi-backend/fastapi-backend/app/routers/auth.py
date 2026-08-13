"""
Auth helper endpoints for user registration and login.

TASK 3: Unified Registration Hook Integration
Every successful signup triggers:
1. Transactional write to customer_profiles (single source of truth)
2. Async event dispatch for CRM provisioning
3. Entity sync queueing for Portal ↔ CRM synchronization

Security note: The Supabase client is NOT initialised at module import time.
It is resolved lazily via dependency injection (get_supabase) so that:
  - Missing environment variables are caught at startup (see main.py fail-fast).
  - Unit tests can substitute a mock client without monkey-patching globals.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from supabase import Client
from datetime import datetime
import os
import asyncio

from app.services.supabase_client import get_supabase
from app.services.registration_hook import init_registration_hooks, RegistrationHook

router = APIRouter()

# Initialize registration hook on module load
_registration_hook: RegistrationHook | None = None

def get_registration_hook() -> RegistrationHook:
    """Get or initialize registration hook"""
    global _registration_hook
    if _registration_hook is None:
        _registration_hook = init_registration_hooks(get_supabase())
    return _registration_hook


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class SignUpRequest(BaseModel):
    email: str
    password: str
    first_name: str = ""
    last_name: str = ""


class LoginRequest(BaseModel):
    email: str
    password: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/signup")
async def signup(
    request: SignUpRequest,
    supabase: Client = Depends(get_supabase),
    registration_hook: RegistrationHook = Depends(get_registration_hook),
) -> dict:
    """
    User signup endpoint — TASK 3 Implementation.
    
    Flow:
    1. Create auth user
    2. Call unified registration hook (transactional write + event dispatch)
    3. Return session with customer profile ID
    
    The registration hook handles:
    - Customer profile creation (main DB source)
    - Entity sync queueing (Portal → CRM)
    - Event logging (audit trail)
    - Async event dispatch (CRM provisioning, welcome email, webhooks)
    """
    try:
        # ── 1. CREATE AUTH USER ────────────────────────────────────────────
        auth_response = supabase.auth.sign_up({
            "email": request.email,
            "password": request.password,
            "options": {
                "data": {
                    "first_name": request.first_name,
                    "last_name": request.last_name,
                    "full_name": f"{request.first_name} {request.last_name}",
                }
            },
        })

        if not auth_response.user:
            raise HTTPException(status_code=400, detail="Signup failed")

        user_id = auth_response.user.id

        # ── 2. CALL UNIFIED REGISTRATION HOOK ──────────────────────────────
        # This triggers:
        # - Transactional customer_profiles write
        # - Entity sync queue (portal_to_crm)
        # - Event logging
        # - Async event dispatch (CRM provisioning, welcome email, etc.)
        try:
            registration_result = await registration_hook.handle_signup(
                auth_user_id=user_id,
                email=request.email,
                first_name=request.first_name,
                last_name=request.last_name,
            )
            customer_profile_id = registration_result.get("customer_profile_id")
            print(f"✅ Unified registration complete: {user_id} → {customer_profile_id}")
        except Exception as reg_err:
            # Registration hook failed — auth user was created but profile setup failed
            # Log the error but continue so the frontend can retry
            print(f"⚠️  Registration hook warning: {reg_err}")
            customer_profile_id = None

        # ── 3. OPTIONAL: Create default organization ───────────────────────
        # (Legacy behavior — keep for backward compatibility)
        organization_id = None
        try:
            default_org_name = (
                f"{request.first_name or request.email.split('@')[0]}'s Organisation"
            )
            org_response = supabase.rpc(
                "create_organization_with_admin",
                {
                    "org_name": default_org_name,
                    "org_slug": request.email.split("@")[0],
                    "org_description": f"Default organisation for {request.email}",
                    "creator_id": user_id,
                },
            ).execute()

            if org_response.data:
                organization_id = (
                    org_response.data[0]["id"]
                    if isinstance(org_response.data, list)
                    else org_response.data.get("id")
                )
                print(f"✅ Default organisation created: {organization_id}")
        except Exception as org_error:
            # Non-fatal — signup continues without an organisation
            print(f"⚠️  Organisation creation warning: {org_error}")

        # ── 4. ATTEMPT AUTO-LOGIN ────────────────────────────────────────
        session_data = None
        email_confirmation_required = False

        if auth_response.user and not auth_response.user.confirmed_at:
            email_confirmation_required = True
            print(f"⚠️  Email confirmation required for {request.email}")
        else:
            try:
                login_response = supabase.auth.sign_in_with_password({
                    "email": request.email,
                    "password": request.password,
                })
                if login_response.session:
                    session_data = {
                        "access_token":  login_response.session.access_token,
                        "refresh_token": login_response.session.refresh_token,
                    }
            except Exception as login_err:
                login_err_msg = str(login_err).lower()
                if "email" in login_err_msg and "confirm" in login_err_msg:
                    email_confirmation_required = True
                    print(f"⚠️  Email not confirmed yet for {request.email}")
                else:
                    print(f"⚠️  Auto-login after signup failed: {login_err}")

        message = (
            "Please check your email and confirm your account before logging in."
            if email_confirmation_required
            else "Signup successful."
        )

        return {
            "success": True,
            "user": {
                "id":    str(user_id),
                "email": request.email,
            },
            "session":                    session_data,
            "organization_id":            organization_id,
            "customer_profile_id":        customer_profile_id,
            "email_confirmation_required": email_confirmation_required,
            "message":                    message,
        }

    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        if "already registered" in error_msg.lower():
            raise HTTPException(status_code=400, detail="Email already registered")
        raise HTTPException(status_code=400, detail=f"Signup failed: {error_msg}")


@router.post("/login")
async def login(
    request: LoginRequest,
    supabase: Client = Depends(get_supabase),
) -> dict:
    """
    User login endpoint.
    Returns auth token if credentials are valid.
    """
    try:
        auth_response = supabase.auth.sign_in_with_password({
            "email": request.email,
            "password": request.password,
        })

        if not auth_response.user:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        return {
            "success": True,
            "user": {
                "id": auth_response.user.id,
                "email": auth_response.user.email,
            },
            "session": {
                "access_token": auth_response.session.access_token,
                "refresh_token": auth_response.session.refresh_token,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        if "invalid" in error_msg.lower():
            raise HTTPException(status_code=401, detail="Invalid email or password")
        raise HTTPException(status_code=400, detail=f"Login failed: {error_msg}")


@router.get("/health")
async def auth_health(supabase: Client = Depends(get_supabase)) -> dict:
    """Health check for auth service — confirms Supabase client is reachable."""
    supabase_url = os.getenv("SUPABASE_URL", "")
    # Only expose the project hostname, never a key
    safe_url = supabase_url.split("//")[-1].split(".")[0] if supabase_url else "unknown"
    return {
        "status": "healthy",
        "service": "auth_service",
        "supabase_project": safe_url,
    }
