from typing import List, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from geoalchemy2.elements import WKTElement
from sqlalchemy import UUID
from shapely import Point
from app.models.tracking_model import TrackingPoint
from app.models.shipment_model import Shipment
from app.services.shipments_service import calculate_distance_km
from sqlalchemy import func
from shapely.geometry import Point
from geoalchemy2.shape import from_shape
from app.models.driver_model import Driver

def save_tracking_point(
    db: Session,
    driver_id: UUID,
    shipment_id: UUID,
    latitude: float,
    longitude: float,
    speed_kph: float | None = None
):
    try:
        point = from_shape(Point(longitude, latitude), srid=4326)

        tracking = TrackingPoint(
            driver_id=driver_id,
            shipment_id=shipment_id,
            location=point,
            speed_kph=speed_kph
        )

        db.add(tracking)
        db.commit()
        db.refresh(tracking)

        return tracking

    except Exception:
        db.rollback()
        raise Exception("Error saving tracking point")

def update_driver_current_location(
    db: Session,
    driver_id: UUID,
    latitude: float,
    longitude: float
):
    driver = db.query(Driver).filter(Driver.id == driver_id).first()

    if not driver:
        raise Exception("Driver not found")

    try:
        point = from_shape(Point(longitude, latitude), srid=4326)
        driver.location = point

        db.commit()
        db.refresh(driver)

        return driver

    except Exception:
        db.rollback()
        raise Exception("Error updating driver location")

def calculate_route_deviation(
    db: Session,
    shipment_id: UUID,
    latitude: float,
    longitude: float,
    threshold_meters: float = 100
):
    shipment = db.query(Shipment).filter(
        Shipment.id == shipment_id
    ).first()

    if not shipment or not shipment.route:
        raise Exception("Shipment route not found")

    point = from_shape(Point(longitude, latitude), srid=4326)

    distance = db.query(
        func.ST_Distance(shipment.route, point)
    ).scalar()

    distance_m = float(distance)

    return {
        "distance_from_route_meters": round(distance_m, 2),
        "is_deviated": distance_m > threshold_meters
    }

def track_driver(
    db: Session,
    driver_id: UUID,
    shipment_id: UUID,
    latitude: float,
    longitude: float,
    speed_kph: float | None = None
):
    tracking = save_tracking_point(
        db,
        driver_id,
        shipment_id,
        latitude,
        longitude,
        speed_kph
    )

    update_driver_current_location(
        db,
        driver_id,
        latitude,
        longitude
    )

    deviation = calculate_route_deviation(
        db,
        shipment_id,
        latitude,
        longitude
    )

    return {
        "tracking_id": tracking.id,
        "distance_from_route_meters": deviation["distance_from_route_meters"],
        "is_deviated": deviation["is_deviated"]
    }

def calculate_total_distance_traveled(
    db: Session,
    shipment_id: UUID
):
    result = db.query(
        func.ST_Length(
            func.ST_MakeLine(
                TrackingPoint.location
            )
        )
    ).filter(
        TrackingPoint.shipment_id == shipment_id
    ).scalar()

    return round(float(result or 0), 2)

def calculate_remaining_distance(
    db: Session,
    shipment_id: UUID,
    latitude: float,
    longitude: float
):
    shipment = db.query(Shipment).filter(
        Shipment.id == shipment_id
    ).first()

    if not shipment:
        raise Exception("Shipment not found")

    point = from_shape(Point(longitude, latitude), srid=4326)

    remaining = db.query(
        func.ST_Distance(
            shipment.destination,
            point
        )
    ).scalar()

    return round(float(remaining or 0), 2)

def calculate_eta(
    remaining_distance_meters: float,
    speed_kph: float
):
    if not speed_kph or speed_kph <= 0:
        return None

    distance_km = remaining_distance_meters / 1000
    hours = distance_km / speed_kph

    minutes = hours * 60

    return round(minutes, 2)

def find_nearest_drivers(
    db: Session,
    latitude: float,
    longitude: float,
    radius_meters: float = 5000,
    limit: int = 5
):
    point = from_shape(Point(longitude, latitude), srid=4326)

    drivers = db.query(
        Driver.id,
        func.ST_Distance(Driver.location, point).label("distance")
    ).filter(
        func.ST_DWithin(Driver.location, point, radius_meters)
    ).order_by("distance").limit(limit).all()

    return drivers



def calculate_average_speed(shipment_id: UUID, db: Session) -> dict:
    """
    Calculate average speed during delivery
    
    Args:
        shipment_id: ID of the shipment
        db: Database session
    
    Returns:
        Dictionary with speed metrics
    """
    tracking_points = db.query(TrackingPoint).filter(
        TrackingPoint.shipment_id == shipment_id
    ).order_by(TrackingPoint.recorded_at.asc()).all()
    
    if len(tracking_points) < 2:
        return {
            "average_speed_kmh": 0,
            "max_speed_kmh": 0,
            "message": "Insufficient tracking data"
        }
    
    speeds = []
    
    for i in range(1, len(tracking_points)):
        prev_point = tracking_points[i-1]
        curr_point = tracking_points[i]
        
        # Calculate distance between points
        distance = calculate_distance_km(
            prev_point.x, prev_point.y,
            curr_point.x, curr_point.y
        )
        
        # Calculate time difference in hours
        time_diff = (curr_point.recorded_at - prev_point.recorded_at).total_seconds() / 3600
        
        if time_diff > 0:
            speed = distance / time_diff
            speeds.append(speed)
    
    if not speeds:
        return {
            "average_speed_kmh": 0,
            "max_speed_kmh": 0,
            "message": "Could not calculate speed"
        }
    
    # Also include speeds from tracking points if available
    recorded_speeds = [p.speed_kmh for p in tracking_points if p.speed_kmh]
    
    return {
        "average_speed_kmh": round(sum(speeds) / len(speeds), 2) if speeds else 0,
        "max_speed_kmh": round(max(speeds), 2) if speeds else 0,
        "min_speed_kmh": round(min(speeds), 2) if speeds else 0,
        "calculated_from_points": len(speeds),
        "recorded_speeds_available": len(recorded_speeds)
    }

def detect_delivery_stops(shipment_id: UUID, db: Session, min_stop_minutes: int = 5) -> List[dict]:
    """
    Detect where the driver stopped during delivery
    Useful for identifying delays or multiple pickup/delivery points
    
    Args:
        shipment_id: ID of the shipment
        db: Database session
        min_stop_minutes: Minimum minutes to consider as a stop
    
    Returns:
        List of detected stops with details
    """
    tracking_points = db.query(TrackingPoint).filter(
        TrackingPoint.shipment_id == shipment_id
    ).order_by(TrackingPoint.recorded_at.asc()).all()
    
    if len(tracking_points) < 2:
        return []
    
    stops = []
    
    for i in range(1, len(tracking_points)):
        prev_point = tracking_points[i-1]
        curr_point = tracking_points[i]
        
        # Calculate distance moved
        distance = calculate_distance_km(
            prev_point.x, prev_point.y,
            curr_point.x, curr_point.y
        )
        
        # Calculate time difference
        time_diff_minutes = (curr_point.recorded_at - prev_point.recorded_at).total_seconds() / 60
        
        # If little movement over significant time = stop
        if distance < 0.1 and time_diff_minutes >= min_stop_minutes:  # Less than 100m movement
            stops.append({
                "location": {
                    "latitude": prev_point.x,
                    "longitude": prev_point.y
                },
                "start_time": prev_point.recorded_at.isoformat(),
                "end_time": curr_point.recorded_at.isoformat(),
                "duration_minutes": round(time_diff_minutes, 1),
                "notes": prev_point.notes or "Unspecified stop"
            })
    
    return stops

def calculate_estimated_delivery_time(
    current_location_lat: float,
    current_location_lng: float,
    destination_lat: float,
    destination_lng: float,
    current_speed_kmh: Optional[float] = None
) -> dict:
    
    Driver.location = from_shape(Point(current_location_lng, current_location_lat), srid=4326)
    Shipment.destination = from_shape(Point(destination_lng, destination_lat), srid=4326)
    """
    Calculate estimated time to reach destination from current location
    
    Args:
        current_location_lat: Current latitude
        current_location_lng: Current longitude
        destination_lat: Destination latitude
        destination_lng: Destination longitude
        current_speed_kmh: Current speed (optional)
    
    Returns:
        Dictionary with ETA information
    """
    # Calculate remaining distance
    remaining_distance = calculate_distance_km(
        current_location_lat, current_location_lng,
        destination_lat, destination_lng
    )
    
    # Use current speed if available, otherwise assume average urban speed
    speed = current_speed_kmh if current_speed_kmh and current_speed_kmh > 0 else 40
    
    # Calculate time in hours
    time_hours = remaining_distance / speed
    time_minutes = time_hours * 60
    
    # Calculate ETA
    eta = datetime.utcnow() + timedelta(minutes=time_minutes)
    
    return {
        "remaining_distance_km": round(remaining_distance, 2),
        "current_speed_kmh": round(speed, 2),
        "estimated_time_minutes": round(time_minutes, 1),
        "eta": eta.isoformat(),
        "eta_formatted": eta.strftime("%I:%M %p")
    }

def get_shipment_tracking_summary(shipment_id: UUID, db: Session) -> dict:
    """
    Get comprehensive tracking summary for a shipment
    
    Args:
        shipment_id: ID of the shipment
        db: Database session
    
    Returns:
        Dictionary with complete tracking summary
    """
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        return {"error": "Shipment not found"}
    
    tracking_points = db.query(TrackingPoint).filter(
        TrackingPoint.shipment_id == shipment_id
    ).order_by(TrackingPoint.recorded_at.asc()).all()
    
    summary = {
        "shipment_id": shipment_id,
        "tracking_number": shipment.tracking_number,
        "status": shipment.status.value,
        "origin": {
            "latitude": shipment.origin.x,
            "longitude": shipment.origin.y,
            "address": shipment.origin_address
        },
        "destination": {
            "latitude": shipment.destination.x,
            "longitude": shipment.destination.y,
            "address": shipment.destination_address
        },
        "estimated_distance_km": shipment.estimated_distance_km,
        "tracking_points_count": len(tracking_points)
    }
    
    if tracking_points:
        # Latest location
        latest_point = tracking_points[-1]
        summary["current_location"] = {
            "latitude": latest_point.x,
            "longitude": latest_point.y,
            "timestamp": latest_point.recorded_at.isoformat(),
            "speed_kmh": latest_point.speed_kmh
        }
        
        # Location accuracy
        accuracy = update_driver_current_location(latest_point, datetime.utcnow())
        summary["location_accuracy"] = accuracy
        
        # Route deviation
        deviation = calculate_route_deviation(shipment_id, db)
        summary["route_deviation"] = deviation
        
        # Average speed
        speed_info = calculate_average_speed(shipment_id, db)
        summary["speed_info"] = speed_info
        
        # Detected stops
        stops = detect_delivery_stops(shipment_id, db)
        summary["stops_detected"] = len(stops)
        
        # ETA if still in transit
        from app.models.shipment_model import ShipmentStatus
        if shipment.status in [ShipmentStatus.IN_TRANSIT, ShipmentStatus.ASSIGNED]:
            eta_info = calculate_estimated_delivery_time(
                latest_point.x,
                latest_point.y,
                shipment.destination.x,
                shipment.destination.y,
                latest_point.speed_kmh
            )
            summary["eta"] = eta_info
    else:
        summary["message"] = "No tracking data available yet"
    
    return summary

def validate_tracking_point_sequence(shipment_id: UUID, db: Session) -> dict:
    """
    Validate that tracking points are in logical sequence
    Detects anomalies like impossible speeds or backward movement
    
    Args:
        shipment_id: ID of the shipment
        db: Database session
    
    Returns:
        Dictionary with validation results
    """
    tracking_points = db.query(TrackingPoint).filter(
        TrackingPoint.shipment_id == shipment_id
    ).order_by(TrackingPoint.recorded_at.asc()).all()
    
    if len(tracking_points) < 2:
        return {
            "valid": True,
            "anomalies": [],
            "message": "Not enough data to validate"
        }
    
    anomalies = []
    
    for i in range(1, len(tracking_points)):
        prev_point = tracking_points[i-1]
        curr_point = tracking_points[i]
        
        # Check time sequence
        if curr_point.recorded_at <= prev_point.recorded_at:
            anomalies.append({
                "type": "time_sequence",
                "point_id": curr_point.id,
                "message": "Tracking point timestamp is not sequential"
            })
        
        # Calculate speed between points
        distance = calculate_distance_km(
            prev_point.x, prev_point.y,
            curr_point.x, curr_point.y
        )
        
        time_diff_hours = (curr_point.recorded_at - prev_point.recorded_at).total_seconds() / 3600
        
        if time_diff_hours > 0:
            speed = distance / time_diff_hours
            
            # Check for impossible speeds (>150 km/h in urban delivery)
            if speed > 150:
                anomalies.append({
                    "type": "impossible_speed",
                    "point_id": curr_point.id,
                    "speed_kmh": round(speed, 2),
                    "message": f"Impossible speed detected: {speed:.0f} km/h"
                })
    
    return {
        "valid": len(anomalies) == 0,
        "anomalies": anomalies,
        "total_points_checked": len(tracking_points),
        "message": "Validation complete" if len(anomalies) == 0 else f"Found {len(anomalies)} anomalies"
    }