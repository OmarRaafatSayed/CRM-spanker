# Travel Agency CRM — FastAPI Backend
# Playwright/Chromium included for live flight scraping

FROM python:3.11-slim

WORKDIR /app

# ── 1. System dependencies ────────────────────────────────────────────────────
# Basic system dependencies - removed heavy Chromium libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    # healthcheck
    curl \
    # Postgres client lib
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# ── 2. Python dependencies ────────────────────────────────────────────────────
COPY fastapi-backend/fastapi-backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── 3. Lightweight Dependencies ──────────────────────────────────────────────────
# No browser installation needed - fast-flights is lightweight

# ── 4. Application source ─────────────────────────────────────────────────────
COPY fastapi-backend/fastapi-backend/ .

# Lightweight scraping - no browser needed
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
ENV USE_REMOTE_BROWSER=false

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
