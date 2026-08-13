"""
Flight Interceptor — Enhanced Google Flights Network Interception
================================================================
Production-ready flight scraper that intercepts Google Flights API calls
to extract real-time pricing and flight data.

UPDATED: Enhanced parsing logic that can handle Google Flights' complex
nested JSON structure and extract actual flight details.
"""
from __future__ import annotations

import json
import os
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

logger = logging.getLogger(__name__)

USE_REMOTE_BROWSER = os.getenv("USE_REMOTE_BROWSER", "true").lower() == "true"
SKIP_BROWSER       = os.getenv("PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD", "0") == "1"  # Fixed: 1 means skip
USE_MOCK_FLIGHTS   = os.getenv("USE_MOCK_FLIGHT_DATA", "false").lower() == "true"


def _build_search_url(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: Optional[str],
    passenger_count: int = 1,
    travel_class: str = "economy",
) -> str:
    """Build a proper Google Flights search URL."""
    # Format date as YYYY-MM-DD for Google Flights
    dep_date = departure_date.replace("-", "")
    
    # Travel class mapping
    class_map = {
        "economy": "1",
        "premium_economy": "2", 
        "business": "3",
        "first": "4"
    }
    cls = class_map.get(travel_class, "1")
    
    # Build the URL with proper parameters - simpler approach
    url = (f"https://www.google.com/travel/flights?"
           f"q=Flights%20from%20{origin}%20to%20{destination}%20"
           f"departing%20{departure_date}"
           f"&curr=USD&hl=en&gl=US")
    
    return url


def _is_flight_response(url: str) -> bool:
    """Check if the response URL is related to flight data."""
    flight_indicators = [
        "travel/flights",
        "google.com/travel",
        "rpc/travel",
        "frontend/travel",
        "_/travel",
        "gen_204",
        "flights"
    ]
    return any(indicator in url.lower() for indicator in flight_indicators)


def _extract_price_from_text(text: str) -> Tuple[Optional[float], Optional[str]]:
    """Extract price and currency from text."""
    # Common currency patterns
    currency_patterns = [
        (r'([A-Z]{3})\s*[\$\£\€\¥]?\s*([\d,]+\.?\d*)', r'\1', r'\2'),  # USD $1,234.56
        (r'[\$\£\€\¥]\s*([\d,]+\.?\d*)\s*([A-Z]{3})?', 'USD', r'\1'),     # $1,234.56 USD
        (r'([\d,]+\.?\d*)\s*([A-Z]{3})', r'\2', r'\1'),                   # 1234.56 USD
        (r'([\d,]+)', 'USD', r'\1')                                       # 1234 (default USD)
    ]
    
    for pattern, currency_group, price_group in currency_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                price_text = match.group(2) if isinstance(price_group, str) and price_group.startswith('\\') else match.group(1)
                price = float(price_text.replace(',', ''))
                
                if isinstance(currency_group, str) and not currency_group.startswith('\\'):
                    currency = currency_group
                else:
                    currency = match.group(1) if currency_group == r'\1' else 'USD'
                    
                return price, currency
            except (ValueError, IndexError):
                continue
    
    return None, None


def _parse_google_response_body(body: str) -> List[Dict]:
    """
    Enhanced parser for Google Flights JSON responses.
    
    Google Flights uses a complex nested array structure. This parser
    searches for flight-like data patterns recursively and extracts
    real pricing and flight information.
    """
    flights = []
    
    try:
        # Remove Google's XSSI protection prefix
        if body.startswith(")]}'"):
            body = body[4:]
        
        # Try to parse as JSON
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            logger.debug(f"Failed to parse response body as JSON (length: {len(body)})")
            return []
        
        def extract_flights_recursive(obj, depth=0):
            """Recursively search for flight data structures."""
            if depth > 15 or len(flights) > 50:  # Prevent infinite loops
                return
            
            if isinstance(obj, list):
                for item in obj:
                    extract_flights_recursive(item, depth + 1)
                    
            elif isinstance(obj, dict):
                # Look for flight-like dictionaries
                if _is_flight_dict(obj):
                    flight = _extract_flight_data(obj)
                    if flight:
                        flights.append(flight)
                        return
                
                # Continue searching in nested objects
                for value in obj.values():
                    extract_flights_recursive(value, depth + 1)
        
        extract_flights_recursive(data)
        
        # Deduplicate flights
        unique_flights = {}
        for flight in flights:
            flight_id = flight.get('flight_id', '')
            if flight_id and flight_id not in unique_flights:
                unique_flights[flight_id] = flight
        
        result = list(unique_flights.values())
        logger.info(f"[parser] Extracted {len(result)} unique flights from response")
        
        return result
        
    except Exception as exc:
        logger.warning(f"[parser] Failed to parse response: {exc}")
        return []


def _is_flight_dict(obj: dict) -> bool:
    """Check if a dictionary looks like flight data."""
    if not isinstance(obj, dict):
        return False
    
    # Look for combinations of flight-related keys
    price_keys = {'price', 'cost', 'fare', 'amount', 'total'}
    time_keys = {'departure', 'arrival', 'depart', 'arrive', 'time', 'duration'}
    airline_keys = {'airline', 'carrier', 'operator', 'flight'}
    
    has_price = any(key in obj for key in price_keys)
    has_time = any(key in obj for key in time_keys) 
    has_airline = any(key in obj for key in airline_keys)
    
    # Also check for numeric values that could be prices
    has_numeric_price = any(
        isinstance(v, (int, float)) and 50 <= v <= 50000 
        for k, v in obj.items() 
        if any(price_word in str(k).lower() for price_word in ['price', 'cost', 'fare'])
    )
    
    return (has_price or has_numeric_price) and (has_time or has_airline)


def _extract_flight_data(obj: dict) -> Optional[Dict]:
    """Extract flight data from a flight-like dictionary."""
    try:
        flight_id = _find_value(obj, ['id', 'flight_id', 'offer_id']) or f"gf_{hash(str(obj)) % 100000}"
        airline = _find_value(obj, ['airline', 'carrier', 'operator']) or "Unknown"
        flight_number = _find_value(obj, ['flight_number', 'number', 'flight']) or ""
        
        # Extract times
        departure = _find_value(obj, ['departure', 'depart', 'departure_time'])
        arrival = _find_value(obj, ['arrival', 'arrive', 'arrival_time'])
        duration = _find_value(obj, ['duration', 'flight_time'])
        
        # Extract price
        price_raw = _find_value(obj, ['price', 'cost', 'fare', 'amount', 'total'])
        price = 0
        currency = "USD"
        
        if isinstance(price_raw, (int, float)):
            price = float(price_raw)
        elif isinstance(price_raw, str):
            extracted_price, extracted_currency = _extract_price_from_text(price_raw)
            if extracted_price is not None:
                price = extracted_price
                currency = extracted_currency or "USD"
        
        # Extract stops
        stops = _find_value(obj, ['stops', 'connections', 'layovers']) or 0
        if isinstance(stops, str):
            stops = 1 if 'stop' in stops.lower() else 0
        
        # Format duration
        duration_formatted = _parse_duration(str(duration)) if duration else ""
        
        flight = {
            "flight_id": str(flight_id),
            "airline": str(airline)[:50],  # Limit length
            "flight_number": str(flight_number)[:20],
            "departure_time": str(departure) if departure else "",
            "arrival_time": str(arrival) if arrival else "",
            "duration": duration_formatted,
            "price": int(price) if price > 0 else 0,
            "price_currency": currency,
            "stops": int(stops) if isinstance(stops, (int, float)) else 0,
            "raw_text": str(obj)[:200],
        }
        
        # Only return if we have meaningful data
        if flight["price"] > 0 or flight["airline"] != "Unknown":
            return flight
            
    except Exception as exc:
        logger.debug(f"Failed to extract flight data: {exc}")
    
    return None


def _parse_duration(duration_text: str) -> str:
    """Parse duration text into standardized format."""
    if not duration_text:
        return ""
    
    # Look for patterns like "3h 45m", "2hr 30min", "1 hour 15 minutes"
    patterns = [
        r'(\d+)h\s*(\d+)m',
        r'(\d+)\s*hr?\s*(\d+)\s*m(?:in)?',
        r'(\d+)\s*hours?\s*(\d+)\s*minutes?',
        r'(\d+):(\d+)',  # 3:45 format
    ]
    
    for pattern in patterns:
        match = re.search(pattern, duration_text, re.IGNORECASE)
        if match:
            hours, minutes = match.groups()
            return f"{hours}h {minutes}m"
    
    # Single hour pattern
    hour_match = re.search(r'(\d+)h(?:our)?', duration_text, re.IGNORECASE)
    if hour_match:
        return f"{hour_match.group(1)}h 0m"
    
    # Single minute pattern 
    min_match = re.search(r'(\d+)m(?:in)?', duration_text, re.IGNORECASE)
    if min_match:
        return f"0h {min_match.group(1)}m"
    
    return duration_text


def _find_value(obj: dict, keys: List[str]) -> Any:
    """Find the first matching key in the object (case-insensitive)."""
    for key in keys:
        # Direct match
        if key in obj:
            return obj[key]
        
        # Case-insensitive match
        for obj_key in obj.keys():
            if isinstance(obj_key, str) and obj_key.lower() == key.lower():
                return obj[obj_key]
    
    return None


async def _apply_stealth(page: Any) -> None:
    """Apply comprehensive anti-detection measures."""
    # Set realistic user agent
    await page.set_extra_http_headers({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    })
    
    # Stealth script injection
    await page.add_init_script("""
        // Remove webdriver property
        delete navigator.__proto__.webdriver;
        
        // Mock plugins and languages
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5]
        });
        
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en']
        });
        
        // Mock screen properties
        Object.defineProperty(screen, 'width', { get: () => 1920 });
        Object.defineProperty(screen, 'height', { get: () => 1080 });
    """)


async def intercept_google_flights(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: Optional[str] = None,
    passenger_count: int = 1,
    travel_class: str = "economy",
    max_retries: int = 3,
) -> Dict[str, Any]:
    """
    Enhanced Google Flights interceptor with improved parsing.
    
    Returns real flight data by intercepting Google Flights API responses
    and parsing the complex nested JSON structure.
    """
    
    # Mock mode check
    if USE_MOCK_FLIGHTS:
        logger.info(f"[mock] Generating mock flight data for {origin} → {destination}")
        mock_flights = _generate_mock_flights(origin, destination, departure_date, count=8)
        return {
            "success": True,
            "provider": "mock_data",
            "origin": origin,
            "destination": destination,
            "departure_date": departure_date,
            "return_date": return_date,
            "flights": mock_flights,
            "total_results": len(mock_flights),
            "cached": False,
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    # Check Playwright availability - Fixed logic
    if SKIP_BROWSER:
        logger.warning("Playwright browser download is being skipped (PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1)")
        return {
            "success": False,
            "provider": "network_interception",
            "error": "Playwright browser installation is disabled. Set PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=0 to enable",
            "flights": [],
            "total_results": 0,
            "cached": False,
            "error_type": "scraper_unavailable",
            "timestamp": datetime.utcnow().isoformat(),
        }

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {
            "success": False,
            "provider": "network_interception",
            "error": "Playwright is not installed. Run: pip install playwright",
            "flights": [],
            "total_results": 0,
            "cached": False,
            "error_type": "scraper_unavailable", 
            "timestamp": datetime.utcnow().isoformat(),
        }

    import asyncio
    captured_flights: List[Dict] = []
    search_url = _build_search_url(
        origin, destination, departure_date, return_date,
        passenger_count, travel_class,
    )

    logger.info(f"[scraper] Starting live flight search: {origin} → {destination}")
    logger.info(f"[scraper] Search URL: {search_url}")

    for attempt in range(max_retries):
        try:
            async with async_playwright() as p:
                # Launch browser with optimized settings
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox", 
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                        "--disable-blink-features=AutomationControlled",
                        "--disable-web-security",
                        "--disable-features=VizDisplayCompositor",
                    ],
                )
                
                page = await browser.new_page()
                await _apply_stealth(page)

                response_count = 0
                async def on_response(response: Any) -> None:
                    nonlocal response_count
                    response_count += 1
                    
                    if not _is_flight_response(response.url):
                        return
                    if not (200 <= response.status < 300):
                        return
                    
                    try:
                        body = await response.text()
                        if len(body) > 100:  # Skip tiny responses
                            logger.debug(f"[scraper] Processing response {response_count} from {response.url[:100]}...")
                            parsed = _parse_google_response_body(body)
                            if parsed:
                                logger.info(f"[scraper] Found {len(parsed)} flights in response")
                                captured_flights.extend(parsed)
                    except Exception as exc:
                        logger.debug(f"[scraper] Failed to process response: {exc}")

                page.on("response", on_response)
                
                # Navigate and wait for content to load
                logger.info(f"[scraper] Attempt {attempt + 1}: Navigating to Google Flights...")
                await page.goto(search_url, wait_until="networkidle", timeout=45000)
                
                # Wait for flight data to load
                await asyncio.sleep(15)  # Increased wait time
                
                # Try to trigger more API calls by interacting with the page
                try:
                    # Scroll to load more results
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await asyncio.sleep(3)
                        
                except Exception as scroll_exc:
                    logger.debug(f"[scraper] Interaction failed (non-fatal): {scroll_exc}")

                await browser.close()
                logger.info(f"[scraper] Attempt {attempt + 1}: Captured {len(captured_flights)} total flights")

            if captured_flights:
                # Sort by price and remove duplicates
                unique_flights = {}
                for flight in captured_flights:
                    key = f"{flight['airline']}_{flight['flight_number']}_{flight['departure_time']}"
                    if key not in unique_flights or flight['price'] < unique_flights[key]['price']:
                        unique_flights[key] = flight
                
                final_flights = sorted(unique_flights.values(), key=lambda f: f.get("price") or 999999)
                
                logger.info(f"[scraper] ✅ SUCCESS: Returning {len(final_flights)} unique flights")
                return {
                    "success": True,
                    "provider": "network_interception_enhanced",
                    "origin": origin,
                    "destination": destination,
                    "departure_date": departure_date,
                    "return_date": return_date,
                    "flights": final_flights[:20],  # Limit to top 20
                    "total_results": len(final_flights),
                    "cached": False,
                    "timestamp": datetime.utcnow().isoformat(),
                }

            logger.warning(f"[scraper] Attempt {attempt + 1}: No flights captured (processed {response_count} responses)")

        except Exception as exc:
            logger.error(f"[scraper] Attempt {attempt + 1} failed: {exc}")
            if attempt == max_retries - 1:
                return {
                    "success": False,
                    "provider": "network_interception_enhanced",
                    "origin": origin,
                    "destination": destination,
                    "departure_date": departure_date,
                    "flights": [],
                    "total_results": 0,
                    "cached": False,
                    "error": f"Enhanced scraper failed after {max_retries} attempts: {str(exc)}",
                    "error_type": "scraper_error",
                    "timestamp": datetime.utcnow().isoformat(),
                }

    return {
        "success": False,
        "provider": "network_interception_enhanced",
        "origin": origin,
        "destination": destination,
        "departure_date": departure_date,
        "flights": [],
        "total_results": 0,
        "cached": False,
        "error": f"No flights captured after {max_retries} attempts. This may be due to Google Flights bot detection or API changes.",
        "error_type": "no_results",
        "timestamp": datetime.utcnow().isoformat(),
    }


# ── Fallback: Mock Data Generator (for development/demo) ──────────────────────

def _generate_mock_flights(
    origin: str,
    destination: str,
    departure_date: str,
    count: int = 8,
) -> List[Dict]:
    """
    Generate realistic mock flight data for testing/demo purposes.
    
    NOTE: This is a DEVELOPMENT fallback only. For production, integrate
    with a real flight API (Amadeus, Skyscanner, etc.).
    """
    import random
    from datetime import datetime, timedelta
    
    airlines = [
        {"code": "EK", "name": "Emirates", "base_price": 450},
        {"code": "MS", "name": "EgyptAir", "base_price": 380},
        {"code": "FZ", "name": "flydubai", "base_price": 320},
        {"code": "G9", "name": "Air Arabia", "base_price": 280},
        {"code": "LH", "name": "Lufthansa", "base_price": 520},
        {"code": "QR", "name": "Qatar Airways", "base_price": 480},
    ]
    
    flights = []
    base_time = datetime.strptime(departure_date, "%Y-%m-%d")
    
    for i in range(count):
        airline = random.choice(airlines)
        stops = random.choice([0, 0, 0, 1, 1])  # More direct flights
        
        # Random departure time
        hour = random.randint(6, 22)
        minute = random.choice([0, 15, 30, 45])
        dep_time = base_time.replace(hour=hour, minute=minute)
        
        # Duration based on stops
        if stops == 0:
            duration_minutes = random.randint(200, 260)  # ~3.5-4.5h for CAI-DXB
        else:
            duration_minutes = random.randint(360, 540)  # 6-9h with stop
        
        arr_time = dep_time + timedelta(minutes=duration_minutes)
        
        # Price variation
        price = airline["base_price"] + random.randint(-50, 100)
        if stops > 0:
            price -= random.randint(30, 80)  # Cheaper with stops
        
        flight = {
            "flight_id": f"{airline['code']}{random.randint(100, 999)}_{i}",
            "airline": airline["name"],
            "flight_number": f"{airline['code']}{random.randint(100, 999)}",
            "departure_time": dep_time.strftime("%H:%M"),
            "arrival_time": arr_time.strftime("%H:%M"),
            "duration": f"{duration_minutes // 60}h {duration_minutes % 60}m",
            "price": price,
            "price_currency": "USD",
            "stops": stops,
            "raw_text": f"Mock flight data for {origin} to {destination}",
        }
        
        flights.append(flight)
    
    # Sort by price
    flights.sort(key=lambda f: f["price"])
    
    return flights
