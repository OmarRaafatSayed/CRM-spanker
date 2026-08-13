"""
FastAPI Travel Agency CRM Backend
Main application entry point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# FAIL-FAST: Validate required secrets at startup before anything else loads.
# If any required variable is missing the app will refuse to start, preventing
# accidental runs with None credentials.
# ---------------------------------------------------------------------------
_REQUIRED_ENV_VARS = [
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_JWT_SECRET",
    "JWT_SECRET_KEY",
]

_missing = [var for var in _REQUIRED_ENV_VARS if not os.getenv(var)]
if _missing:
    raise ValueError(
        f"[STARTUP ERROR] Missing required environment variables: {_missing}. "
        "Copy .env.example to .env and fill in all required values before starting."
    )

# Import routers
from app.routers import flights, documents, hotels, auth, visa, payments, crm_customers, crm_pipeline

# Import middleware
from app.middleware.security import rate_limit_middleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events"""
    print("🚀 FastAPI Travel Agency Backend Starting...")
    print(f"✅ Environment: {os.getenv('ENVIRONMENT', 'unknown')}")
    print("✅ All required secrets loaded from environment.")
    yield
    print("🛑 FastAPI Travel Agency Backend Shutting Down...")

# Initialize FastAPI app
app = FastAPI(
    title="Travel Agency CRM Backend",
    description="FastAPI backend for flight scraping, document processing, and hotel data management",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if os.getenv("ENVIRONMENT") == "development" else None,
    redoc_url="/redoc" if os.getenv("ENVIRONMENT") == "development" else None,
    openapi_url="/openapi.json" if os.getenv("ENVIRONMENT") == "development" else None
)

# Configure CORS - Allow both development ports (4000 for current, 5173 for default)
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:4000,http://localhost:5173").split(",")
# Clean up whitespace from environment variable
cors_origins = [origin.strip() for origin in cors_origins if origin.strip()]

print(f"🔐 CORS Allowed Origins: {cors_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],  # Expose all response headers for debugging
    max_age=3600,  # Cache preflight requests for 1 hour
)

# Add rate limiting middleware
app.middleware("http")(rate_limit_middleware)

# Include routers
app.include_router(flights.router, prefix="/api/v1/flights", tags=["Flights"])
app.include_router(documents.router, prefix="/api/v1/documents", tags=["Documents"])
app.include_router(hotels.router, prefix="/api/v1/hotels", tags=["Hotels"])
app.include_router(visa.router,     prefix="/api/v1/visa",     tags=["Visa"])
app.include_router(payments.router, prefix="/api/v1",           tags=["Payments"])
app.include_router(auth.router,     prefix="/api/v1/auth",      tags=["Auth"])
app.include_router(crm_customers.router, prefix="/api/v1/crm",  tags=["CRM Customers"])
app.include_router(crm_pipeline.router, prefix="/api/v1/pipeline", tags=["CRM Pipeline"])

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Travel Agency CRM Backend",
        "version": "1.0.0",
        "status": "operational"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", 8000)),
        reload=os.getenv("ENVIRONMENT") == "development"
    )
