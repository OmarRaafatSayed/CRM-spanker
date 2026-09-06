"""
app/core/security.py
====================
JWT authentication — supports both ES256 (Supabase JWKS) and HS256 fallback.

FIX: All os.getenv() calls are now lazy (inside functions) so load_dotenv()
     in main.py runs before any env var is read.
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

# Lazy config — read AFTER load_dotenv() in main.py
def _supabase_url() -> str:
    return os.getenv("SUPABASE_URL", "").rstrip("/")

def _hs256_secret() -> str:
    return os.getenv("SUPABASE_JWT_SECRET", os.getenv("JWT_SECRET_KEY", ""))

_bearer_scheme = HTTPBearer(auto_error=False)
_auth_context_builder: AuthContextBuilder | None = None

# JWKS cache
_jwks_cache: dict[str, Any] = {}
_jwks_lock   = threading.Lock()
_jwks_loaded = False


def _load_jwks() -> None:
    global _jwks_loaded
    if _jwks_loaded:
        return
    with _jwks_lock:
        if _jwks_loaded:
            return
        try:
            url = f"{_supabase_url()}/auth/v1/.well-known/jwks.json"
            with urllib.request.urlopen(url, timeout=5) as r:
                data = json.loads(r.read())
            for key in data.get("keys", []):
                _jwks_cache[key["kid"]] = key
            print(f"[auth] JWKS loaded — {len(_jwks_cache)} key(s)")
            _jwks_loaded = True
        except Exception as exc:
            print(f"[auth] JWKS load failed: {exc}")


def _decode_token(token: str) -> dict:
    try:
        header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise JWTError(f"Malformed token header: {exc}")

    alg = header.get("alg", "HS256")

    if alg == "ES256":
        _load_jwks()
        kid = header.get("kid", "")
        jwk = _jwks_cache.get(kid)
        if not jwk:
            global _jwks_loaded
            _jwks_loaded = False
            _load_jwks()
            jwk = _jwks_cache.get(kid)
        if not jwk:
            raise JWTError(f"No JWKS key found for kid={kid}")
        ec_key = ECKey(jwk, algorithm="ES256")
        return jwt.decode(token, ec_key.public_key(), algorithms=["ES256"], options={"verify_aud": False})

    secret = _hs256_secret()
    if not secret:
        raise JWTError("No HS256 secret configured.")
    return jwt.decode(token, secret, algorithms=["HS256"], options={"verify_aud": False})


def require_auth(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    supabase: Any = Depends(lambda: None),
) -> AuthContext:
    _401 = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                         detail="Authentication required.",
                         headers={"WWW-Authenticate": "Bearer"})
    if credentials is None:
        raise _401
    try:
        payload = _decode_token(credentials.credentials)
    except JWTError as exc:
        print(f"[auth] Token rejected: {exc}")
        raise _401

    sub        = payload.get("sub")
    email      = payload.get("email", "")
    token_role = payload.get("role", "customer")
    if not sub:
        raise _401

    try:
        from app.services.supabase_client import get_supabase
        sb = get_supabase()
        global _auth_context_builder
        if _auth_context_builder is None:
            _auth_context_builder = AuthContextBuilder(sb)
        context = _auth_context_builder.build_from_token(sub, email, token_role)
        print(f"[auth] Authenticated: {context}")
        return context
    except Exception as exc:
        print(f"[auth] Auth context fallback: {exc}")
        return AuthContext(user_id=sub, email=email, role=token_role)


def optional_auth(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> AuthContext | None:
    if credentials is None:
        return None
    try:
        payload    = _decode_token(credentials.credentials)
        sub        = payload.get("sub")
        email      = payload.get("email", "")
        token_role = payload.get("role", "customer")
        if not sub:
            return None
        try:
            from app.services.supabase_client import get_supabase
            sb = get_supabase()
            global _auth_context_builder
            if _auth_context_builder is None:
                _auth_context_builder = AuthContextBuilder(sb)
            return _auth_context_builder.build_from_token(sub, email, token_role)
        except Exception:
            return AuthContext(user_id=sub, email=email, role=token_role)
    except JWTError:
        return None


class TokenPayload(BaseModel):
    sub:   str
    email: str = ""
    role:  str = ""

    @property
    def user_id(self) -> str:
        return self.sub

AuthToken = AuthContext
