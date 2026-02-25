from geoalchemy2 import Geography
from geoalchemy2.elements import WKTElement
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
import random
from datetime import datetime
from typing import Optional
import string
from decimal import Decimal, ROUND_HALF_UP

def generate_tracking_number() -> str:
    """
    Generate a unique tracking number
    Format: ANTU-YYYYMMDD-XXXXX
    Example: ANTU-20250210-A7K9M
    """
    date_part = datetime.now().strftime("%Y%m%d")
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    return f"ANTU-{date_part}-{random_part}"


def calculate_distance_km(
    db: Session,
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float
) -> Decimal:
    """
    Returns distance in kilometers between two coordinates
    without creating a shipment.
    """

    origin = WKTElement(f"POINT({origin_lng} {origin_lat})", srid=4326)
    destination = WKTElement(f"POINT({dest_lng} {dest_lat})", srid=4326)

    distance_meters = db.query(
             func.ST_Distance(origin, destination)
             ).scalar()
    
    if distance_meters is None:
        raise ValueError("Distance calculation failed")
    
    distance_km = Decimal(distance_meters) / Decimal("1000")
    estimated_distance_km = distance_km.quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )
    return estimated_distance_km


def calculate_delivery_cost(
    estimated_distance_km: Decimal,
    weight_kg: Decimal,
    vehicle_type: Optional[str] = None
) -> Decimal:
    """
    Calculate delivery cost based on distance, weight, and vehicle type
    
    Pricing Structure (in KSH):
    - Base fare: 200 KSH
    - 0-10 km: 50 KSH/km
    - 10-50 km: 40 KSH/km
    - 50+ km: 30 KSH/km
    - Weight surcharge: 20 KSH per 10kg above 20kg
    - Vehicle type multiplier:
        - Motorcycle: 1.0x (default)
        - Van: 1.3x
        - Truck: 1.5x
        - Pickup: 1.2x
    
    Args:
        distance_km: Distance in kilometers
        weight_kg: Package weight in kilograms
        vehicle_type: Type of vehicle (optional)
    
    Returns:
        Total cost in KSH (rounded to nearest whole number)
    """
    # Base fare
    base_fare = 200
    
    # Distance-based cost
    if estimated_distance_km <= 10:
        distance_cost = estimated_distance_km * 50
    elif estimated_distance_km <= 50:
        distance_cost = (10 * 50) + ((estimated_distance_km - 10) * 40)
    else:
        distance_cost = (10 * 50) + (40 * 40) + ((estimated_distance_km - 50) * 30)
    
    # Weight surcharge (for packages over 20kg)
    weight_surcharge = 0
    if weight_kg > 20:
        excess_weight = weight_kg - 20
        weight_surcharge = (excess_weight / 10) * 20
    
    # Calculate subtotal
    subtotal = base_fare + distance_cost + weight_surcharge
    
    # Apply vehicle type multiplier
    vehicle_multipliers = {
        "motorcycle": 1.0,
        "van": 1.3,
        "truck": 1.5,
        "pickup": 1.2
    }
    
    if vehicle_type:
        multiplier = vehicle_multipliers.get(vehicle_type.lower(), 1.0)
        subtotal *= multiplier
    
    return round(subtotal, 0)

def estimate_delivery_time(estimated_distance_km: Decimal) -> int:
    """
    Estimate delivery time in minutes based on distance
    Assumes average speed of 40 km/h in urban areas
    
    Args:
        distance_km: Distance in kilometers
    
    Returns:
        Estimated time in minutes
    """
    # Average speed in km/h (accounting for traffic, stops, etc.)
    average_speed = 40
    
    # Calculate time in hours, convert to minutes
    time_hours = estimated_distance_km / average_speed
    time_minutes = time_hours * 60
    
    # Add buffer time for pickup/delivery (15 minutes each)
    buffer_time = 30
    
    total_time = time_minutes + buffer_time
    
    return round(total_time, 0)

def validate_coordinates(latitude: float, longitude: float) -> bool:
    """
    Validate that coordinates are within valid ranges
    
    Args:
        latitude: Latitude as string
        longitude: Longitude as string
    
    Returns:
        True if valid, False otherwise
    """
    try:
        lat = float(latitude)
        lng = float(longitude)
        
        # Valid latitude: -90 to 90
        # Valid longitude: -180 to 180
        if -90 <= lat <= 90 and -180 <= lng <= 180:
            return True
        return False
    except (ValueError, TypeError):
        return False

# Example usage and testing
if __name__ == "__main__":
    # Test tracking number generation
    print("Tracking Number:", generate_tracking_number())
    
    # Test distance calculation (Nairobi CBD to JKIA)
    estimated_distance_km = calculate_distance_km("-1.286389", "36.817223", "-1.319167", "36.927778")
    print(f"Distance: {estimated_distance_km} km")
    
    # Test cost calculation
    cost = calculate_delivery_cost(estimated_distance_km, 15, "motorcycle")
    print(f"Cost: KSH {cost}")
    
    # Test time estimation
    time = estimate_delivery_time(estimated_distance_km)
    print(f"Estimated Time: {time} minutes")