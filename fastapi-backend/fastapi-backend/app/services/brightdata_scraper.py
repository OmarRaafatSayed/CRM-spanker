"""
Flight Scraper – Network Interception Engine (Primary) + Bright Data (Optional)
================================================================================
Primary path  : Network Interception via Playwright (zero-cost, permanent)
Secondary path: Bright Data Cloud Browser (if credentials are configured)

CSS selectors are NOT used anywhere in this module.
All data comes from intercepted XHR/Fetch responses.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class BrightDataFlightScraper:
    """
    Unified flight scraper.

    Priority order:
      1. Network Interception Engine  ← always available, zero cost
      2. Bright Data Cloud Browser    ← optional, used when env vars are set
    """

    def __init__(self) -> None:
        self.customer_id = os.getenv("BRIGHTDATA_CUSTOMER_ID")
        self.zone = os.getenv("BRIGHTDATA_ZONE", "scraping_browser")
        self.password = os.getenv("BRIGHTDATA_PASSWORD")
        self.cache_ttl_hours = int(os.getenv("FLIGHT_CACHE_TTL_HOURS", "12"))

        self.brightdata_enabled = bool(self.customer_id and self.password)

        if self.brightdata_enabled:
            logger.info("Bright Data credentials found – available as secondary provider")
        else:
            logger.info(
                "Bright Data not configured – using Network Interception Engine (primary)"
            )

        # Always enabled – Network Interception requires no credentials
        self.enabled = True

    # ──────────────────────────────────────────
    #  Public search method
    # ──────────────────────────────────────────

    async def search_flights(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: Optional[str] = None,
        passenger_count: int = 1,
        travel_class: str = "economy",
    ) -> Dict[str, Any]:
        """
        Search for flights.

        If USE_MOCK_FLIGHT_DATA=true, returns deterministic mock data immediately
        (no browser launch, no network call, no Supabase cache).

        Otherwise tries: cache → Network Interception → Bright Data.
        """
        # ── Mock mode ────────────────────────────────────────────────────────
        if os.getenv("USE_MOCK_FLIGHT_DATA", "false").lower() == "true":
            logger.info(f"[MOCK] Returning mock flights for {origin}→{destination}")
            return self._build_mock_result(
                origin, destination, departure_date, return_date,
                passenger_count, travel_class
            )
        # 1. Cache check
        try:
            from app.services.flight_cache import get_cached_results
            cached = await get_cached_results(
                origin, destination, departure_date, return_date
            )
            if cached:
                logger.info("Returning cached flight results")
                return cached
        except Exception as e:
            logger.warning(f"Cache check failed (non-fatal): {e}")

        # 2. Primary: Ultra-lightweight HTTP scraper
        logger.info(f"[PRIMARY] Lightweight HTTP scraper: {origin} → {destination}")
        try:
            from app.services.fast_flight_scraper import get_live_flights
            
            flights = await get_live_flights(
                origin=origin,
                destination=destination,
                date=departure_date,
                return_date=return_date,
                passenger_count=passenger_count,
                travel_class=travel_class,
            )

            if flights:
                result = {
                    "success": True,
                    "provider": "lightweight_http",
                    "origin": origin,
                    "destination": destination,
                    "departure_date": departure_date,
                    "return_date": return_date,
                    "flights": flights,
                    "total_results": len(flights),
                    "cached": False,
                    "timestamp": datetime.utcnow().isoformat(),
                }
                
                logger.info(f"[PRIMARY] ✅ Lightweight scraper succeeded: {len(flights)} flights")
                await self._try_cache(origin, destination, departure_date, return_date, result)
                return result
            else:
                logger.warning("[PRIMARY] Lightweight scraper returned no results")

        except Exception as e:
            error_msg = str(e)
            logger.error(f"[PRIMARY] Lightweight scraper failed for {origin}->{destination} on {departure_date}: {error_msg}")

        # 3. Secondary: Bright Data (only if configured)
        # Reached here because interception returned no flights or raised.
        if self.brightdata_enabled:
            logger.info("[SECONDARY] Falling back to Bright Data Cloud Browser")
            try:
                result = await self._scrape_via_brightdata(
                    origin, destination, departure_date,
                    return_date, passenger_count, travel_class
                )
                if result.get("success") and result.get("flights"):
                    await self._try_cache(
                        origin, destination, departure_date, return_date, result
                    )
                    return result
            except Exception as e:
                logger.error(
                    f"[SECONDARY] Bright Data failed for "
                    f"{origin}->{destination}: {e}"
                )

        # All methods exhausted - return with helpful error
        return {
            "success": False,
            "provider": "all_methods_failed",
            "origin": origin,
            "destination": destination,
            "departure_date": departure_date,
            "return_date": return_date,
            "flights": [],
            "total_results": 0,
            "cached": False,
            "error": (
                "Live flight search completed but no results found. This is typically due to "
                "Google Flights bot detection. In production, consider using a dedicated flight API "
                "like Amadeus, Skyscanner, or Kiwi.com for reliable data."
            ),
            "error_type": "all_methods_failed",
            "timestamp": datetime.utcnow().isoformat(),
        }

    # ──────────────────────────────────────────
    #  Bright Data secondary path
    # ──────────────────────────────────────────

    def _get_brightdata_endpoint(self) -> str:
        return (
            f"wss://brd-customer-{self.customer_id}-zone-{self.zone}:"
            f"{self.password}@brd.superproxy.io:9222"
        )

    async def _scrape_via_brightdata(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: Optional[str],
        passenger_count: int,
        travel_class: str,
    ) -> Dict[str, Any]:
        """
        Use Bright Data's remote browser as a proxy layer.
        Still uses Network Interception – no CSS selectors.
        """
        from playwright.async_api import async_playwright
        from app.services.flight_interceptor import (
            _apply_stealth,
            _build_search_url,
            _parse_google_response_body,
            _is_flight_response,
        )

        endpoint = self._get_brightdata_endpoint()
        search_url = _build_search_url(
            origin, destination, departure_date, return_date,
            passenger_count, travel_class
        )
        captured_flights: List[Dict] = []

        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(endpoint)
            try:
                ctx = (
                    browser.contexts[0]
                    if browser.contexts
                    else await browser.new_context()
                )
                page = await ctx.new_page()
                await _apply_stealth(page)

                async def on_response(response) -> None:
                    if not _is_flight_response(response.url):
                        return
                    if not (200 <= response.status < 300):
                        return
                    try:
                        body = await response.text()
                        parsed = _parse_google_response_body(body)
                        captured_flights.extend(parsed)
                    except Exception:
                        pass

                page.on("response", on_response)

                await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(15)  # Bright Data needs more time
            finally:
                await browser.close()

        if captured_flights:
            captured_flights.sort(key=lambda f: f.get("price") or 9999999)
            return {
                "success": True,
                "provider": "brightdata_interception",
                "origin": origin,
                "destination": destination,
                "departure_date": departure_date,
                "return_date": return_date,
                "flights": captured_flights[:20],
                "total_results": len(captured_flights),
                "cached": False,
                "timestamp": datetime.utcnow().isoformat(),
            }

        return {
            "success": False,
            "provider": "brightdata_interception",
            "error": "No flights captured via Bright Data",
            "flights": [],
            "total_results": 0,
            "cached": False,
            "timestamp": datetime.utcnow().isoformat(),
        }

    # ──────────────────────────────────────────
    #  Connection test (for /test-connection endpoint)
    # ──────────────────────────────────────────

    async def test_connection(self) -> Dict[str, Any]:
        """
        Test connectivity.
        Returns status of both interception engine and Bright Data.
        """
        result: Dict[str, Any] = {
            "connected": False,
            "interception_engine": "available",
            "brightdata_configured": self.brightdata_enabled,
        }

        # Quick smoke-test: launch headless Chromium and load a page
        try:
            from playwright.async_api import async_playwright
            import subprocess
            import sys
            
            # Ensure playwright browsers are installed with dependencies
            try:
                install_result = subprocess.run(
                    [sys.executable, "-m", "playwright", "install", "chromium"], 
                    capture_output=True, text=True, timeout=60
                )
                print(f"DEBUG: Playwright install result: {install_result.returncode}")
                if install_result.returncode != 0:
                    print(f"⚠️  Playwright install output: {install_result.stdout}")
                    print(f"⚠️  Playwright install error: {install_result.stderr}")
            except Exception as e:
                print(f"⚠️  Could not auto-install playwright: {e}")

            # Test Chromium with detailed debugging
            print("DEBUG: Testing Chromium launch...")
            async with async_playwright() as p:
                try:
                    chromium_path = p.chromium.executable_path
                    print(f"DEBUG: Chromium executable found at: {chromium_path}")
                except Exception as e:
                    print(f"DEBUG: Cannot get Chromium path: {e}")
                    raise Exception("Chromium not found")

                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox", 
                        "--disable-setuid-sandbox",
                        "--disable-blink-features=AutomationControlled",
                        "--disable-web-security",
                        "--disable-dev-shm-usage",
                        "--no-first-run",
                        "--disable-gpu",
                    ],
                )
                print("DEBUG: Chromium launched successfully")
                page = await browser.new_page()
                await page.goto("https://www.google.com", timeout=15000)
                title = await page.title()
                await browser.close()
                print(f"DEBUG: Test page loaded with title: {title}")

            result.update(
                {
                    "connected": True,
                    "test_page_title": title,
                    "primary_provider": "network_interception",
                    "message": (
                        "Local Chromium reachable. "
                        "Network Interception Engine ready."
                    ),
                }
            )
        except Exception as e:
            result.update(
                {
                    "connected": False,
                    "error": str(e),
                    "message": f"Chromium failed: {str(e)}. Try: playwright install chromium",
                }
            )

        # Also test Bright Data if configured
        if self.brightdata_enabled:
            try:
                from playwright.async_api import async_playwright

                async with async_playwright() as p:
                    browser = await p.chromium.connect_over_cdp(
                        self._get_brightdata_endpoint()
                    )
                    ctx = (
                        browser.contexts[0]
                        if browser.contexts
                        else await browser.new_context()
                    )
                    page = await ctx.new_page()
                    await page.goto("https://www.google.com", timeout=15000)
                    bd_title = await page.title()
                    await browser.close()

                result["brightdata_status"] = "connected"
                result["brightdata_test_page"] = bd_title
            except Exception as e:
                result["brightdata_status"] = f"error: {e}"

        return result

    # ──────────────────────────────────────────
    #  Mock data builder
    # ──────────────────────────────────────────

    def _build_mock_result(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: Optional[str],
        passenger_count: int,
        travel_class: str,
    ) -> Dict[str, Any]:
        """Return realistic-looking mock flights for dev/testing."""
        base_prices = {
            "economy": 1200, "premium_economy": 2400,
            "business": 4800, "first": 9600,
        }
        base = base_prices.get(travel_class, 1200)

        mock_flights = [
            {
                "flight_id":      f"MOCK-{origin}{destination}-001",
                "airline":        "EgyptAir",
                "flight_number":  "MS 701",
                "departure_time": f"{departure_date}T08:00:00",
                "arrival_time":   f"{departure_date}T11:30:00",
                "duration":       "3h 30m",
                "price":          base,
                "price_currency": "EGP",
                "stops":          0,
                "raw_text":       f"EgyptAir {origin}→{destination} direct",
            },
            {
                "flight_id":      f"MOCK-{origin}{destination}-002",
                "airline":        "Nile Air",
                "flight_number":  "NP 100",
                "departure_time": f"{departure_date}T14:00:00",
                "arrival_time":   f"{departure_date}T19:00:00",
                "duration":       "5h 00m",
                "price":          int(base * 0.85),
                "price_currency": "EGP",
                "stops":          1,
                "raw_text":       f"Nile Air {origin}→{destination} 1 stop",
            },
            {
                "flight_id":      f"MOCK-{origin}{destination}-003",
                "airline":        "Air Arabia",
                "flight_number":  "G9 501",
                "departure_time": f"{departure_date}T22:00:00",
                "arrival_time":   f"{departure_date}T23:45:00",
                "duration":       "1h 45m",
                "price":          int(base * 1.20),
                "price_currency": "EGP",
                "stops":          0,
                "raw_text":       f"Air Arabia {origin}→{destination} direct",
            },
        ]

        return {
            "success":        True,
            "provider":       "mock_data",
            "origin":         origin,
            "destination":    destination,
            "departure_date": departure_date,
            "return_date":    return_date,
            "flights":        mock_flights,
            "total_results":  len(mock_flights),
            "cached":         False,
            "timestamp":      datetime.utcnow().isoformat(),
        }

    # ──────────────────────────────────────────
    #  Internal helpers
    # ──────────────────────────────────────────

    async def _try_cache(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: Optional[str],
        result: Dict[str, Any],
    ) -> None:
        """
        Write a successful result to the cache.
        Failed results (success=False) and legacy mock_data are never cached
        so that a transient scraper outage cannot poison the cache.
        """
        if not result.get("success"):
            logger.debug("Skipping cache write: result is not successful")
            return
        if result.get("provider") == "mock_data":
            logger.warning("Refusing to cache result from mock_data provider")
            return
        try:
            from app.services.flight_cache import cache_results
            await cache_results(origin, destination, departure_date, return_date, result)
            logger.info(f"Cached {result.get('total_results', 0)} flight results")
        except Exception as e:
            logger.warning(f"Cache write failed (non-fatal): {e}")


# Singleton
_scraper_instance: Optional[BrightDataFlightScraper] = None


def get_brightdata_scraper() -> BrightDataFlightScraper:
    """Get or create the unified flight scraper instance."""
    global _scraper_instance
    if _scraper_instance is None:
        _scraper_instance = BrightDataFlightScraper()
    return _scraper_instance
