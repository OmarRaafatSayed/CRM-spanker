"""
Security Middleware
JWT validation, rate limiting, and API key authentication
"""
from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
import os
from datetime import datetime, timedelta
from typing import Optional, Dict
import hashlib
import time

# Security configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-this-in-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")

# Rate limiting configuration
RATE_LIMIT_REQUESTS = 100  # requests per window
RATE_LIMIT_WINDOW = 60  # seconds
rate_limit_store: Dict[str, list] = {}

security = HTTPBearer()

def verify_supabase_jwt(token: str) -> Optional[Dict]:
    """
    Verify JWT token from Supabase Auth
    
    Args:
        token: JWT token string
    
    Returns:
        Decoded token payload or None if invalid
    """
    try:
        # Decode and verify token
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET or JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
            options={"verify_aud": False}  # Supabase tokens may not have audience
        )
        
        # Check expiration
        exp = payload.get("exp")
        if exp and datetime.fromtimestamp(exp) < datetime.utcnow():
            return None
        
        return payload
    
    except JWTError as e:
        print(f"JWT verification failed: {e}")
        return None

async def validate_jwt_token(credentials: HTTPAuthorizationCredentials) -> Dict:
    """
    Dependency for protected endpoints - validates JWT token
    
    Usage:
        @router.get("/protected")
        async def protected_route(user: Dict = Depends(validate_jwt_token)):
            return {"user_id": user["sub"]}
    """
    token = credentials.credentials
    payload = verify_supabase_jwt(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return payload

def get_client_ip(request: Request) -> str:
    """Extract client IP address from request"""
    # Check for proxied IP first
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    
    # Fallback to direct connection IP
    return request.client.host if request.client else "unknown"

def check_rate_limit(ip: str) -> bool:
    """
    Check if IP is within rate limit
    
    Args:
        ip: Client IP address
    
    Returns:
        True if within limit, False if exceeded
    """
    current_time = time.time()
    
    # Initialize IP tracking if not exists
    if ip not in rate_limit_store:
        rate_limit_store[ip] = []
    
    # Remove old timestamps outside window
    rate_limit_store[ip] = [
        timestamp for timestamp in rate_limit_store[ip]
        if current_time - timestamp < RATE_LIMIT_WINDOW
    ]
    
    # Check if limit exceeded
    if len(rate_limit_store[ip]) >= RATE_LIMIT_REQUESTS:
        return False
    
    # Add current request
    rate_limit_store[ip].append(current_time)
    return True

async def rate_limit_middleware(request: Request, call_next):
    """
    Rate limiting middleware
    Limits requests per IP address to prevent abuse
    """
    import logging
    import traceback
    from fastapi.responses import JSONResponse
    
    logger = logging.getLogger("rate_limit_middleware")
    
    try:
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/", "/docs", "/redoc"]:
            return await call_next(request)
        
        client_ip = get_client_ip(request)
        
        if not check_rate_limit(client_ip):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Max {RATE_LIMIT_REQUESTS} requests per {RATE_LIMIT_WINDOW} seconds."
            )
        
        response = await call_next(request)
        return response
    
    except HTTPException:
        # Re-raise HTTP exceptions (like 429) - they're intentional
        raise
    
    except Exception as e:
        # Log unexpected errors
        logger.error(f"❌ CRITICAL: rate_limit_middleware failed!")
        logger.error(f"Request: {request.method} {request.url.path}")
        logger.error(f"Client IP: {get_client_ip(request)}")
        logger.error(f"Error Type: {type(e).__name__}")
        logger.error(f"Error Message: {str(e)}")
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        
        # Return detailed error response
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal Server Error in rate_limit_middleware",
                "error_type": type(e).__name__,
                "error_message": str(e),
                "path": request.url.path
            }
        )

def generate_api_key() -> str:
    """
    Generate secure API key for service-to-service authentication
    
    Returns:
        32-character hex string
    """
    return hashlib.sha256(os.urandom(32)).hexdigest()

def verify_api_key(api_key: str) -> bool:
    """
    Verify API key against stored keys
    
    Args:
        api_key: API key to verify
    
    Returns:
        True if valid, False otherwise
    """
    # In production, store keys in secure vault (e.g., AWS Secrets Manager)
    valid_keys = os.getenv("VALID_API_KEYS", "").split(",")
    return api_key in valid_keys

async def api_key_auth(request: Request):
    """
    Dependency for API key authentication
    
    Usage:
        @router.post("/bulk-insert")
        async def bulk_insert(data: List[Dict], auth: None = Depends(api_key_auth)):
            return {"success": True}
    """
    api_key = request.headers.get("X-API-Key")
    
    if not api_key or not verify_api_key(api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

