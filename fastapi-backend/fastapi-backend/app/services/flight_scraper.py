"""
Lightweight Flight Scraper — fast-flights Integration
=====================================================
Replaces the heavy Playwright scraper with a fast, lightweight solution.

Uses the fast-flights library for quick flight data retrieval without
browser overhead or complex setup requirements.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

USE_MOCK_FLIGHT_DATA = os.getenv("USE_MOCK_FLIGHT_DATA", "false").lower() == "true"


def get_live_flights(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: Optional[str] = None,
    passenger_count: int = 1,
    travel_class: str = "economy",
) -> Dict[str, Any]:
    """
    Get live flight data using fast-flights library.
    
    Returns structured flight data in the same format as the old scraper
    for compatibility with existing code.
    """
    
    # Mock mode check
    if USE_MOCK_FLIGHT_DATA:
        logger.info(f"[mock] Returning mock flight data for {origin} → {destination}")
        return _generate_mock_flights(origin, destination, departure_date, passenger_count, travel_class)
    
    try:
        from fast_flights import FlightData, Passenger, FlightSearch
        
        logger.info(f"[fast-flights] Searching flights: {origin} → {destination} on {departure_date}")
        
        # Create flight search configuration
        flight_data = [
            FlightData(
                date=departure_date,
                from_airport=origin,
                to_airport=destination
            )
        ]
        
        # Add return flight if specified
        if return_date:
            flight_data.append(
                FlightData(
                    date=return_date,
                    from_airport=destination,
                    to_airport=origin
                )
            )
        
        # Configure passengers
        passengers = Passenger(adults=passenger_count)
        
        # Map travel class
        seat_map = {
            "economy": "economy",
            "premium_economy": "premium_economy", 
            "business": "business",
            "first": "first"
        }
        seat = seat_map.get(travel_class, "economy")
        
        # Execute search
        search = FlightSearch(
            flight_data=flight_data,
            passengers=passengers,
            seat=seat
        )
        
        flights = search.flights
        
        if not flights:
            logger.warning(f"[fast-flights] No flights found for {origin} → {destination}")
            return {
                "success": False,
                "provider": "fast_flights",
                "origin": origin,
                "destination": destination,
                "departure_date": departure_date,
                "return_date": return_date,
                "flights": [],
                "total_results": 0,
                "cached": False,
                "error": "No flights found for the specified route and date",
                "error_type": "no_results",
                "timestamp": datetime.utcnow().isoformat(),
            }
        
        # Convert flights to our standard format
        formatted_flights = []
        for i, flight in enumerate(flights[:20]):  # Limit to 20 results
            formatted_flight = _format_flight_data(flight, i + 1)
            if formatted_flight:
                formatted_flights.append(formatted_flight)
        
        logger.info(f"[fast-flights] ✅ SUCCESS: Found {len(formatted_flights)} flights")
        
        return {
            "success": True,
            "provider": "fast_flights",
            "origin": origin,
            "destination": destination,
            "departure_date": departure_date,
            "return_date": return_date,
            "flights": formatted_flights,
            "total_results": len(formatted_flights),
            "cached": False,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
    except ImportError:
        logger.error("[fast-flights] fast-flights library not installed")
        return {
            "success": False,
            "provider": "fast_flights",
            "origin": origin,
            "destination": destination,
            "departure_date": departure_date,
            "flights": [],
            "total_results": 0,
            "cached": False,
            "error": "fast-flights library not installed. Run: pip install fast-flights",
            "error_type": "library_missing",
            "timestamp": datetime.utcnow().isoformat(),
        }
        
    except Exception as e:
        logger.error(f"[fast-flights] Error fetching flights: {e}")
        return {
            "success": False,
            "provider": "fast_flights", 
            "origin": origin,
            "destination": destination,
            "departure_date": departure_date,
            "flights": [],
            "total_results": 0,
            "cached": False,
            "error": f"Flight search failed: {str(e)}",
            "error_type": "search_error",
            "timestamp": datetime.utcnow().isoformat(),
        }


def _format_flight_data(flight: Any, index: int) -> Optional[Dict[str, Any]]:
    """
    Convert fast-flights flight object to our standard format.
    """
    try:
        # Extract basic flight information
        flight_id = getattr(flight, 'id', None) or f"ff_{index}"
        airline = getattr(flight, 'airline', None) or getattr(flight, 'carrier', 'Unknown')
        flight_number = getattr(flight, 'flight_number', None) or getattr(flight, 'number', '')
        
        # Extract timing information
        departure_time = getattr(flight, 'departure_time', None) or getattr(flight, 'depart', '')
        arrival_time = getattr(flight, 'arrival_time', None) or getattr(flight, 'arrive', '')
        duration = getattr(flight, 'duration', None) or getattr(flight, 'flight_time', '')
        
        # Extract price information
        price = getattr(flight, 'price', 0)
        if hasattr(flight, 'cost'):
            price = getattr(flight, 'cost', 0)
        elif hasattr(flight, 'fare'):
            price = getattr(flight, 'fare', 0)
        
        # Try to extract numeric price from string if needed
        if isinstance(price, str):
            import re
            price_match = re.search(r'(\d+\.?\d*)', price.replace(',', ''))
            price = float(price_match.group(1)) if price_match else 0
        
        currency = getattr(flight, 'currency', 'USD')
        
        # Extract stops information
        stops = getattr(flight, 'stops', 0)
        if hasattr(flight, 'connections'):
            stops = len(getattr(flight, 'connections', []))
        
        formatted_flight = {
            "flight_id": str(flight_id),
            "airline": str(airline)[:50],
            "flight_number": str(flight_number)[:20], 
            "departure_time": str(departure_time),
            "arrival_time": str(arrival_time),
            "duration": str(duration),
            "price": int(float(price)) if price > 0 else 0,
            "price_currency": str(currency),
            "stops": int(stops),
            "raw_text": str(flight)[:200],
        }
        
        return formatted_flight
        
    except Exception as exc:
        logger.debug(f"Failed to format flight data: {exc}")
        return None


def _generate_mock_flights(
    origin: str,
    destination: str,
    departure_date: str,
    passenger_count: int = 1,
    travel_class: str = "economy"
) -> Dict[str, Any]:
    """
    Generate realistic mock flight data for testing.
    """
    import random
    
    # Base prices by class
    base_prices = {
        "economy": 350,
        "premium_economy": 700,
        "business": 1400,
        "first": 2800
    }
    
    base_price = base_prices.get(travel_class, 350)
    
    airlines = [
        {"name": "Emirates", "code": "EK", "multiplier": 1.2},
        {"name": "EgyptAir", "code": "MS", "multiplier": 1.0},
        {"name": "Qatar Airways", "code": "QR", "multiplier": 1.15},
        {"name": "flydubai", "code": "FZ", "multiplier": 0.85},
        {"name": "Air Arabia", "code": "G9", "multiplier": 0.75},
        {"name": "Etihad Airways", "code": "EY", "multiplier": 1.1},
    ]
    
    mock_flights = []
    
    for i, airline in enumerate(airlines):
        # Generate flight details
        flight_num = random.randint(100, 999)
        price = int(base_price * airline["multiplier"] * random.uniform(0.8, 1.3))
        stops = random.choice([0, 0, 0, 1])  # Mostly direct flights
        
        # Generate realistic times
        dep_hour = random.randint(6, 22)
        dep_min = random.choice([0, 15, 30, 45])
        
        if stops == 0:
            duration = f"{random.randint(3, 5)}h {random.randint(0, 59)}m"
            arr_hour = (dep_hour + random.randint(3, 5)) % 24
        else:
            duration = f"{random.randint(6, 9)}h {random.randint(0, 59)}m"
            arr_hour = (dep_hour + random.randint(6, 9)) % 24
            price = int(price * 0.9)  # Cheaper with stops
        
        arr_min = random.choice([0, 15, 30, 45])
        
        flight = {
            "flight_id": f"ff_{airline['code']}{flight_num}",
            "airline": airline["name"],
            "flight_number": f"{airline['code']} {flight_num}",
            "departure_time": f"{dep_hour:02d}:{dep_min:02d}",
            "arrival_time": f"{arr_hour:02d}:{arr_min:02d}",
            "duration": duration,
            "price": price,
            "price_currency": "USD",
            "stops": stops,
            "raw_text": f"Mock flight {airline['name']} {origin}→{destination}",
        }
        
        mock_flights.append(flight)
    
    # Sort by price
    mock_flights.sort(key=lambda f: f["price"])
    
    return {
        "success": True,
        "provider": "mock_data_fast",
        "origin": origin,
        "destination": destination, 
        "departure_date": departure_date,
        "return_date": None,
        "flights": mock_flights,
        "total_results": len(mock_flights),
        "cached": False,
        "timestamp": datetime.utcnow().isoformat(),
    }