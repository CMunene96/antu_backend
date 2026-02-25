from typing import Optional, List, Tuple
from geoalchemy2 import WKTElement
from decimal import Decimal
from shapely import Point
from geoalchemy2.shape import from_shape
from sqlalchemy import UUID
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.models.driver_model import Driver, DriverStatus
from app.models.shipment_model import Shipment, ShipmentStatus
from app.models.user_model import User
from app.services.shipments_service import calculate_distance_km

def calculate_driver_efficiency_score(driver_id: UUID, db: Session) -> dict:
    """
    Calculate overall efficiency score for a driver
    Based on: completion rate, on-time delivery, distance covered
    
    Args:
        driver_id: ID of the driver
        db: Database session
    
    Returns:
        Dictionary with efficiency metrics and score
    """
    driver = db.query(Driver).filter(Driver.id == driver_id).first()
    if not driver:
        return {"score": 0, "status": "unknown"}
    
    # Get all shipments
    total_shipments = db.query(Shipment).filter(Shipment.driver_id == driver.id).count()
    
    if total_shipments == 0:
        return {
            "score": 0,
            "status": "no_data",
            "message": "No deliveries yet"
        }
    
    # Calculate completion rate
    completed = db.query(Shipment).filter(
        Shipment.driver_id == driver_id,
        Shipment.status == ShipmentStatus.DELIVERED
    ).count()
    
    cancelled = db.query(Shipment).filter(
        Shipment.driver_id == driver_id,
        Shipment.status == ShipmentStatus.CANCELLED
    ).count()
    
    completion_rate = (completed / total_shipments) * 100 if total_shipments > 0 else 0
    
    # Calculate distance efficiency
    total_distance = db.query(Shipment).filter(
        Shipment.driver_id == driver_id,
        Shipment.status == ShipmentStatus.DELIVERED
    ).with_entities(Shipment.estimated_distance_km).all()
    
    distance_covered = sum([d[0] or 0 for d in total_distance])
    
    # Efficiency score calculation (0-100)
    # 60% weight on completion rate, 40% on total deliveries
    efficiency_score = (completion_rate * 0.7) + min(40, (completed / 10) * 40)
    
    # Determine status
    if efficiency_score >= 80:
        status = "excellent"
        rating = 5
    elif efficiency_score >= 60:
        status = "good"
        rating = 4
    elif efficiency_score >= 40:
        status = "average"
        rating = 3
    elif efficiency_score >= 20:
        status = "needs_improvement"
        rating = 2
    else:
        status = "poor"
        rating = 1
    
    return {
        "score": round(efficiency_score, 2),
        "rating": rating,
        "status": status,
        "total_deliveries": total_shipments,
        "completed_deliveries": completed,
        "cancelled_deliveries": cancelled,
        "completion_rate": round(completion_rate, 2),
        "total_distance_km": round(distance_covered, 2),
        "average_distance_per_delivery": round(distance_covered / completed, 2) if completed > 0 else 0
    }

def get_driver_active_workload(driver_id: UUID, db: Session) -> dict:
    """
    Get current workload of a driver
    
    Args:
        driver_id: ID of the driver
        db: Database session
    
    Returns:
        Dictionary with current workload information
    """
    assigned = db.query(Shipment).filter(
        Shipment.driver_id == driver_id,
        Shipment.status == ShipmentStatus.ASSIGNED
    ).count()
    
    in_transit = db.query(Shipment).filter(
        Shipment.driver_id == driver_id,
        Shipment.status == ShipmentStatus.IN_TRANSIT
    ).count()
    
    total_active = assigned + in_transit
    
    # Get pending distance
    active_shipments = db.query(Shipment).filter(
        Shipment.driver_id == driver_id,
        Shipment.status.in_([ShipmentStatus.ASSIGNED, ShipmentStatus.IN_TRANSIT])
    ).all()
    
    pending_distance = sum([s.estimated_distance_km or 0 for s in active_shipments])
    
    # Determine workload status
    if total_active == 0:
        workload_status = "free"
    elif total_active <= 2:
        workload_status = "light"
    elif total_active <= 5:
        workload_status = "moderate"
    else:
        workload_status = "heavy"
    
    return {
        "assigned_shipments": assigned,
        "in_transit_shipments": in_transit,
        "total_active": total_active,
        "pending_distance_km": round(pending_distance, 2),
        "workload_status": workload_status,
        "can_accept_more": total_active < 5  # Max 5 active shipments
    }

def update_driver_location(db: Session, driver_id, current_latitude: float, current_longitude: float):
    driver = db.query(Driver).filter(Driver.id == driver_id).first()

    if not driver:
        raise Exception("Driver not found")

    try:
        # Create PostGIS geography point
        point = from_shape(Point(current_longitude, current_latitude), srid=4326)
        driver.location = point

        db.commit()
        db.refresh(driver)

        return driver

    except Exception:
        db.rollback()
        raise Exception("Error updating driver location")


def calculate_estimated_arrival_time(
    driver_id: UUID,
    current_lat: float,
    current_lng: float,
    destination_lat: float,
    destination_lng: float,
    db: Session
) -> Optional[dict]:
    """
    Calculate estimated time of arrival for a driver to a destination
    
    Args:
        driver_id: ID of the driver
        destination_lat: Destination latitude
        destination_lng: Destination longitude
        db: Database session
    
    Returns:
        Dictionary with ETA information or None
    """
    driver = db.query(Driver).filter(Driver.id == driver_id).first()
    if not driver or not driver.is_active:
        return None
    
    # Calculate distance from current location to destination
    distance = calculate_distance_km(
        origin= WKTElement(f"POINT({current_lng} {current_lat})", srid=4326),
        destination= WKTElement(f"POINT({destination_lng} {destination_lat})", srid=4326)
    )
    
    # Assume average speed of 40 km/h in urban areas
    average_speed_kmh = 40
    time_hours = distance / average_speed_kmh
    time_minutes = time_hours * 60
    
    # Calculate ETA
    eta = datetime.utcnow() + timedelta(minutes=time_minutes)
    
    return {
        "current_location": {
            "location": driver.location,
            "last_update": driver.last_location_update
        },
        "destination": {
            "latitude": destination_lat,
            "longitude": destination_lng
        },
        "distance_km": round(distance, 2),
        "estimated_time_minutes": round(time_minutes, 0),
        "eta": eta.isoformat(),
        "last_location_update": driver.last_location_update
    }

def check_driver_availability_for_shipment(
    driver_id: UUID,
    shipment_weight_kg: float,
    db: Session
) -> dict:
    """
    Check if a driver is available and suitable for a shipment
    
    Args:
        driver_id: ID of the driver
        shipment_weight_kg: Weight of the shipment
        db: Database session
    
    Returns:
        Dictionary with availability status and reason
    """
    from app.models.vehicle_model import Vehicle
    
    driver = db.query(Driver).filter(Driver.id == driver_id).first()
    if not driver:
        return {
            "available": False,
            "reason": "Driver not found"
        }
    
    if not driver.is_active:
        return {
            "available": False,
            "reason": "Driver is not active"
        }
    
    if driver.status == DriverStatus.OFF_DUTY:
        return {
            "available": False,
            "reason": "Driver is off duty"
        }
    
    # Check workload
    workload = get_driver_active_workload(driver_id, db)
    if not workload["can_accept_more"]:
        return {
            "available": False,
            "reason": f"Driver has maximum workload ({workload['total_active']} active shipments)"
        }
    
    # Check vehicle capacity if assigned
    if driver.vehicle_id:
        vehicle = db.query(Vehicle).filter(Vehicle.id == driver.vehicle_id).first()
        if vehicle and vehicle.capacity_kg < shipment_weight_kg:
            return {
                "available": False,
                "reason": f"Vehicle capacity ({vehicle.capacity_kg} kg) insufficient for shipment ({shipment_weight_kg} kg)"
            }
    else:
        return {
            "available": False,
            "reason": "Driver has no vehicle assigned"
        }
    
    return {
        "available": True,
        "reason": "Driver is available",
        "current_workload": workload["total_active"],
        "driver_status": driver.status
    }

def get_driver_daily_summary(driver_id: UUID, date: datetime, db: Session) -> dict:
    """
    Get summary of driver's activities for a specific day
    
    Args:
        driver_id: ID of the driver
        date: Date to get summary for
        db: Database session
    
    Returns:
        Dictionary with daily summary
    """
    start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)
    
    # Shipments picked up today
    picked_up = db.query(Shipment).filter(
        Shipment.driver_id == driver_id,
        Shipment.picked_up_at >= start_of_day,
        Shipment.picked_up_at < end_of_day
    ).count()
    
    # Shipments delivered today
    delivered = db.query(Shipment).filter(
        Shipment.driver_id == driver_id,
        Shipment.delivered_at >= start_of_day,
        Shipment.delivered_at < end_of_day
    ).count()
    
    # Distance covered today
    today_shipments = db.query(Shipment).filter(
        Shipment.driver_id == driver_id,
        Shipment.delivered_at >= start_of_day,
        Shipment.delivered_at < end_of_day
    ).all()
    
    distance_today = sum([s.estimated_distance_km or 0 for s in today_shipments])
    
    return {
        "date": start_of_day.date().isoformat(),
        "shipments_picked_up": picked_up,
        "shipments_delivered": delivered,
        "distance_covered_km": round(distance_today, 2),
        "deliveries_per_hour": round(delivered / 8, 2) if delivered > 0 else 0  # Assuming 8-hour workday
    }

def find_nearest_available_driver(
    origin_lat: float,
    origin_lng: float,
    shipment_weight_kg: Decimal,
    db: Session,
    max_distance_km: Decimal = 50
) -> Optional[Tuple[Driver, float]]:
    """
    Find the nearest available driver to a pickup location
    
    Args:
        origin_lat: Pickup latitude
        origin_lng: Pickup longitude
        shipment_weight_kg: Weight of shipment
        db: Database session
        max_distance_km: Maximum search radius
    
    Returns:
        Tuple of (Driver, distance) or None
    """
    # Get all available drivers with location data
    drivers = db.query(Driver).filter(
        Driver.is_active == True,
        Driver.status.in_([DriverStatus.AVAILABLE, DriverStatus.ON_DUTY]),
        Driver.location.isnot(None),
    ).all()
    
    nearest_driver = None
    nearest_distance = float('inf')
    
    for driver in drivers:
        # Check if driver can handle the shipment
        availability = check_driver_availability_for_shipment(
            driver.id,
            shipment_weight_kg,
            db
        )
        
        if not availability["available"]:
            continue
        
        # Calculate distance to pickup point
        distance = calculate_distance_km(
            driver.location.y if driver.location else 0,
            driver.location.x if driver.location else 0,
            origin_lat,
            origin_lng
        )
        
        if distance < nearest_distance and distance <= max_distance_km:
            nearest_distance = distance
            nearest_driver = driver
    
    if nearest_driver:
        return (nearest_driver, nearest_distance)
    
    return None

def get_driver_performance_trends(driver_id: UUID, days: int, db: Session) -> dict:
    """
    Get performance trends over specified number of days
    
    Args:
        driver_id: ID of the driver
        days: Number of days to analyze
        db: Database session
    
    Returns:
        Dictionary with trend analysis
    """
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Get shipments in period
    shipments = db.query(Shipment).filter(
        Shipment.driver_id == driver_id,
        Shipment.created_at >= start_date
    ).all()
    
    if not shipments:
        return {
            "period_days": days,
            "total_shipments": 0,
            "trend": "no_data"
        }
    
    # Calculate daily averages
    daily_deliveries = len([s for s in shipments if s.status == ShipmentStatus.DELIVERED]) / days
    
    # Split into first half and second half to detect trend
    mid_point = start_date + timedelta(days=days/2)
    first_half = [s for s in shipments if s.created_at < mid_point and s.status == ShipmentStatus.DELIVERED]
    second_half = [s for s in shipments if s.created_at >= mid_point and s.status == ShipmentStatus.DELIVERED]
    
    first_half_avg = len(first_half) / (days/2)
    second_half_avg = len(second_half) / (days/2)
    
    # Determine trend
    if second_half_avg > first_half_avg * 1.1:
        trend = "improving"
    elif second_half_avg < first_half_avg * 0.9:
        trend = "declining"
    else:
        trend = "stable"
    
    return {
        "period_days": days,
        "total_shipments": len(shipments),
        "delivered": len([s for s in shipments if s.status == ShipmentStatus.DELIVERED]),
        "daily_average": round(daily_deliveries, 2),
        "first_half_average": round(first_half_avg, 2),
        "second_half_average": round(second_half_avg, 2),
        "trend": trend,
        "performance_change_percent": round(((second_half_avg - first_half_avg) / first_half_avg * 100), 2) if first_half_avg > 0 else 0
    }