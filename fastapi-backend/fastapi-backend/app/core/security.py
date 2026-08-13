"""
app/core/security.py
====================
JWT authentication — supports both ES256 (Supabase JWKS) and HS256 fallback.

TASK 6 Integration:
- JWT token verification (ES256/HS256)
- Unified AuthContext building
- Role-based access control
- Database profile resolution

Supabase now issues ES256 tokens (P-256 elliptic curve).
We fetch the public key from the JWKS endpoint and cache it in memory.
HS256 with SUPABASE_JWT_SECRET is kept as a fallback for legacy tokens.
"""
from __future__ import annotations

import os
import json
import threading
import urllib.request
from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from jose.backends import ECKey
from pydantic import BaseModel

from app.core.auth_context import AuthContext, AuthContextBuilder

# ── Config ────────────────────────────────────────────────────────────────────
_SUPABASE_URL: str  = os.getenv("SUPABASE_URL", "").rstrip("/")
_HS256_SECRET: str  = os.getenv("SUPABASE_JWT_SECRET",
                                 os.getenv("JWT_SECRET_KEY", ""))
_bearer_scheme = HTTPBearer(auto_error=False)
_auth_context_builder: AuthContextBuilder | None = None

# ── JWKS cache ────────────────────────────────────────────────────────────────
_jwks_cache: dict[str, Any] = {}   # kid → JWK dict
_jwks_lock  = threading.Lock()
_jwks_loaded = False


def _load_jwks() -> None:
    """Fetch JWKS once from Supabase and cache by kid."""
    global _jwks_loaded
    if _jwks_loaded:
        return
    with _jwks_lock:
        if _jwks_loaded:
            return
        try:
            url = f"{_SUPABASE_URL}/auth/v1/.well-known/jwks.json"
            with urllib.request.urlopen(url, timeout=5) as r:
                data = json.loads(r.read())
            for key in data.get("keys", []):
                _jwks_cache[key["kid"]] = key
            print(f"[auth] JWKS loaded — {len(_jwks_cache)} key(s)")
            _jwks_loaded = True
        except Exception as exc:
            print(f"[auth] ⚠️  JWKS load failed: {exc}")


# ── Token payload ─────────────────────────────────────────────────────────────
class TokenPayload(BaseModel):
    sub:   str
    email: str = ""
    role:  str = ""

    @property
    def user_id(self) -> str:
        return self.sub


# ── Decode ────────────────────────────────────────────────────────────────────
def _decode_token(token: str) -> dict:
    """
    1. Parse the JWT header to detect algorithm.
    2. For ES256: verify with the matching JWKS public key.
    3. For HS256: verify with SUPABASE_JWT_SECRET (plain string).
    """
    # Peek at header without full verification
    try:
        header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise JWTError(f"Malformed token header: {exc}")

    alg = header.get("alg", "HS256")

    # ── ES256 path ────────────────────────────────────────────────────────────
    if alg == "ES256":
        _load_jwks()
        kid = header.get("kid", "")
        jwk = _jwks_cache.get(kid)

        if not jwk:
            # Try to reload once (key rotation)
            global _jwks_loaded
            _jwks_loaded = False
            _load_jwks()
            jwk = _jwks_cache.get(kid)

        if not jwk:
            raise JWTError(f"No JWKS key found for kid={kid}")

        # Build a public key object from the JWK and decode
        ec_key = ECKey(jwk, algorithm="ES256")
        return jwt.decode(
            token,
            ec_key.public_key(),
            algorithms=["ES256"],
            options={"verify_aud": False},
        )

    # ── HS256 path (fallback) ─────────────────────────────────────────────────
    if not _HS256_SECRET:
        raise JWTError("No HS256 secret configured.")

    return jwt.decode(
        token,
        _HS256_SECRET,
        algorithms=["HS256"],
        options={"verify_aud": False},
    )


# ── Dependency ────────────────────────────────────────────────────────────────
def require_auth(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(_bearer_scheme),
    ],
    supabase: Any = Depends(lambda: None),  # Will be injected by caller
) -> AuthContext:
    """
    Authenticate and return unified AuthContext.
    
    TASK 6: Returns AuthContext with role + permissions instead of just TokenPayload.
    """
    _401 = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Provide a valid Bearer token.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise _401

    try:
        payload = _decode_token(credentials.credentials)
    except JWTError as exc:
        print(f"[auth] ❌ Token rejected: {exc}")
        raise _401

    sub = payload.get("sub")
    email = payload.get("email", "")
    token_role = payload.get("role", "customer")

    if not sub:
        raise _401

    # Build unified AuthContext
    try:
        from app.services.supabase_client import get_supabase
        supabase = get_supabase()
        
        global _auth_context_builder
        if _auth_context_builder is None:
            _auth_context_builder = AuthContextBuilder(supabase)
        
        context = _auth_context_builder.build_from_token(sub, email, token_role)
        print(f"[auth] ✅ Authenticated: {context}")
        return context
    except Exception as exc:
        print(f"[auth] ⚠️  Failed to build auth context: {exc}")
        # Fallback to basic context
        return AuthContext(user_id=sub, email=email, role=token_role)


def optional_auth(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(_bearer_scheme),
    ],
) -> AuthContext | None:
    """Like require_auth but returns None instead of 401 when no token is provided."""
    if credentials is None:
        return None
    try:
        payload = _decode_token(credentials.credentials)
        sub = payload.get("sub")
        email = payload.get("email", "")
        token_role = payload.get("role", "customer")

        if not sub:
            return None

        # Build unified AuthContext
        try:
            from app.services.supabase_client import get_supabase
            supabase = get_supabase()
            
            global _auth_context_builder
            if _auth_context_builder is None:
                _auth_context_builder = AuthContextBuilder(supabase)
            
            return _auth_context_builder.build_from_token(sub, email, token_role)
        except Exception:
            # Fallback to basic context
            return AuthContext(user_id=sub, email=email, role=token_role)

    except JWTError:
        return None


# Keep legacy types for backward compatibility
class TokenPayload(BaseModel):
    """Legacy token payload — use AuthContext instead"""
    sub:   str
    email: str = ""
    role:  str = ""

    @property
    def user_id(self) -> str:
        return self.sub


AuthToken = AuthContext
