from typing import Optional, List
from sqlalchemy import UUID
from decimal import Decimal
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.vehicle_model import Vehicle, VehicleStatus, VehicleType
from app.models.driver_model import Driver
from app.models.shipment_model import Shipment

def get_vehicle_utilization_rate(vehicle_id: UUID, db: Session) -> float:
    """
    Calculate vehicle utilization rate
    Returns percentage of time vehicle has been in use
    
    Args:
        vehicle_id: ID of the vehicle
        db: Database session
    
    Returns:
        Utilization rate as percentage (0-100)
    """
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not vehicle:
        return 0.0
    
    # Get total deliveries for drivers who used this vehicle
    total_deliveries = db.query(Shipment).join(
        Driver, Shipment.driver_id == Driver.id
    ).filter(Driver.vehicle_id == vehicle_id).count()
    
    # Simple calculation: if vehicle has deliveries, it's being utilized
    # More complex: track hours used vs hours available
    if total_deliveries == 0:
        return 0.0
    
    # Basic utilization: number of deliveries relative to vehicle age
    # This is simplified - in production, track actual hours
    return min(100.0, (total_deliveries / 30) * 100)  # 30 deliveries = 100% utilized

def get_optimal_vehicle_for_shipment(
    weight_kg: Decimal,
    distance_km: Decimal,
    db: Session
) -> Optional[Vehicle]:
    """
    Recommend the best vehicle for a shipment based on weight and distance
    
    Args:
        weight_kg: Package weight
        distance_km: Delivery distance
        db: Database session
    
    Returns:
        Recommended vehicle or None
    """
    # Get available vehicles that can handle the weight
    suitable_vehicles = db.query(Vehicle).filter(
        Vehicle.status == VehicleStatus.AVAILABLE,
        Vehicle.is_active == True,
        Vehicle.capacity_kg >= weight_kg
    ).all()
    
    if not suitable_vehicles:
        return None
    
    # Selection logic based on distance and weight
    if distance_km < 5 and weight_kg < 10:
        # Short distance, light package - prefer motorcycle
        for vehicle in suitable_vehicles:
            if vehicle.vehicle_type == VehicleType.MOTORCYCLE:
                return vehicle
    
    elif distance_km < 20 and weight_kg < 500:
        # Medium distance, medium weight - prefer van or pickup
        for vehicle in suitable_vehicles:
            if vehicle.vehicle_type in [VehicleType.VAN, VehicleType.PICKUP]:
                return vehicle
    
    else:
        # Long distance or heavy weight - prefer truck
        for vehicle in suitable_vehicles:
            if vehicle.vehicle_type == VehicleType.TRUCK:
                return vehicle
    
    # If no perfect match, return the first suitable vehicle
    return suitable_vehicles[0]

def calculate_vehicle_maintenance_score(vehicle_id: UUID, db: Session) -> dict:
    """
    Calculate when a vehicle might need maintenance based on usage
    
    Args:
        vehicle_id: ID of the vehicle
        db: Database session
    
    Returns:
        Dictionary with maintenance score and recommendation
    """
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not vehicle:
        return {"score": 0, "status": "unknown", "recommendation": "Vehicle not found"}
    
    # Get total distance covered by this vehicle
    total_distance = db.query(Shipment).join(
        Driver, Shipment.driver_id == Driver.id
    ).filter(
        Driver.vehicle_id == vehicle_id
    ).with_entities(Shipment.estimated_distance_km).all()
    
    total_km = sum([d[0] or 0 for d in total_distance])
    
    # Maintenance thresholds (in km)
    MAINTENANCE_INTERVALS = {
        VehicleType.MOTORCYCLE: 3000,
        VehicleType.VAN: 5000,
        VehicleType.TRUCK: 8000,
        VehicleType.PICKUP: 6000
    }
    
    interval = MAINTENANCE_INTERVALS.get(vehicle.vehicle_type, 5000)
    
    # Calculate score (0-100, where 100 means maintenance is due)
    score = min(100, (total_km / interval) * 100)
    
    if score >= 90:
        status = "urgent"
        recommendation = f"Maintenance urgently needed! {total_km:.0f} km covered."
    elif score >= 70:
        status = "soon"
        recommendation = f"Schedule maintenance soon. {total_km:.0f} km covered."
    elif score >= 50:
        status = "watch"
        recommendation = f"Monitor vehicle. {total_km:.0f} km covered."
    else:
        status = "good"
        recommendation = f"Vehicle in good condition. {total_km:.0f} km covered."
    
    return {
        "score": round(score, 2),
        "status": status,
        "total_distance_km": round(total_km, 2),
        "next_maintenance_km": interval,
        "recommendation": recommendation
    }

def get_vehicle_cost_efficiency(vehicle_id: UUID, db: Session) -> dict:
    """
    Calculate cost efficiency metrics for a vehicle
    
    Args:
        vehicle_id: ID of the vehicle
        db: Database session
    
    Returns:
        Dictionary with cost efficiency metrics
    """
    from sqlalchemy import func
    
    # Get all completed deliveries for this vehicle
    deliveries = db.query(Shipment).join(
        Driver, Shipment.driver_id == Driver.id
    ).filter(
        Driver.vehicle_id == vehicle_id,
        Shipment.delivered_at.isnot(None)
    ).all()
    
    if not deliveries:
        return {
            "total_deliveries": 0,
            "total_revenue": 0,
            "total_distance": 0,
            "revenue_per_km": 0,
            "revenue_per_delivery": 0
        }
    
    total_revenue = sum([d.actual_cost or d.estimated_cost or 0 for d in deliveries])
    total_distance = sum([d.estimated_distance_km or 0 for d in deliveries])
    total_deliveries = len(deliveries)
    
    return {
        "total_deliveries": total_deliveries,
        "total_revenue": round(total_revenue, 2),
        "total_distance_km": round(total_distance, 2),
        "revenue_per_km": round(total_revenue / total_distance, 2) if total_distance > 0 else 0,
        "revenue_per_delivery": round(total_revenue / total_deliveries, 2) if total_deliveries > 0 else 0,
        "average_distance_per_delivery": round(total_distance / total_deliveries, 2) if total_deliveries > 0 else 0
    }

def check_vehicle_availability(vehicle_id: UUID, db: Session) -> dict:
    """
    Check if a vehicle is available for assignment
    
    Args:
        vehicle_id: ID of the vehicle
        db: Database session
    
    Returns:
        Dictionary with availability status and details
    """
    from app.models.shipment_model import ShipmentStatus
    
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not vehicle:
        return {
            "available": False,
            "reason": "Vehicle not found"
        }
    
    if not vehicle.is_active:
        return {
            "available": False,
            "reason": "Vehicle is inactive"
        }
    
    if vehicle.status != VehicleStatus.AVAILABLE:
        return {
            "available": False,
            "reason": f"Vehicle status is {vehicle.status}",
            "current_status": vehicle.status
        }
    
    # Check if vehicle has a driver currently on active delivery
    driver = db.query(Driver).filter(Driver.vehicle_id == vehicle_id).first()
    if driver:
        active_shipments = db.query(Shipment).filter(
            Shipment.driver_id == driver.id,
            Shipment.status.in_([ShipmentStatus.IN_TRANSIT, ShipmentStatus.ASSIGNED])
        ).count()
        
        if active_shipments > 0:
            return {
                "available": False,
                "reason": f"Vehicle's driver has {active_shipments} active shipment(s)",
                "active_shipments": active_shipments
            }
    
    return {
        "available": True,
        "reason": "Vehicle is available for assignment"
    }

# Vehicle type comparison helpers
VEHICLE_CHARACTERISTICS = {
    VehicleType.MOTORCYCLE: {
        "speed": "fast",
        "cost": "low",
        "capacity": "very_low",
        "fuel_efficiency": "excellent",
        "best_for": "Small packages, short distances, city delivery"
    },
    VehicleType.PICKUP: {
        "speed": "medium",
        "cost": "medium",
        "capacity": "medium",
        "fuel_efficiency": "good",
        "best_for": "Medium packages, versatile use"
    },
    VehicleType.VAN: {
        "speed": "medium",
        "cost": "medium",
        "capacity": "high",
        "fuel_efficiency": "fair",
        "best_for": "Multiple packages, urban delivery"
    },
    VehicleType.TRUCK: {
        "speed": "slow",
        "cost": "high",
        "capacity": "very_high",
        "fuel_efficiency": "poor",
        "best_for": "Heavy/bulk items, long distance"
    }
}

def get_vehicle_characteristics(vehicle_type: VehicleType) -> dict:
    """
    Get characteristics and best use cases for a vehicle type
    
    Args:
        vehicle_type: Type of vehicle
    
    Returns:
        Dictionary with vehicle characteristics
    """
    return VEHICLE_CHARACTERISTICS.get(vehicle_type, {})