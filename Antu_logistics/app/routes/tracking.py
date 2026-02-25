from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Optional

from app.database import get_db
from app.core.deps import get_current_user
from app.models.user_model import User, UserRole

from app.services.tracking_service import (
    track_driver,
    calculate_total_distance_traveled,
    calculate_remaining_distance,
    calculate_eta,
    find_nearest_drivers,
    calculate_average_speed,
    detect_delivery_stops,
    calculate_estimated_delivery_time,
    get_shipment_tracking_summary,
    validate_tracking_point_sequence,
)

router = APIRouter(
    prefix="/tracking",
    tags=["Tracking"]
)


# ----------------------------------------
# Role Protection
# ----------------------------------------

def require_staff(current_user: User = Depends(get_current_user)):
    if current_user.role not in [
        UserRole.ADMIN,
        UserRole.LOGISTICS_MANAGER,
        UserRole.DRIVER
    ]:
        raise HTTPException(status_code=403, detail="Not authorized")
    return current_user


# ----------------------------------------
# Track Driver (Main Endpoint)
# ----------------------------------------

@router.post("/update")
def update_tracking(
    driver_id: UUID,
    shipment_id: UUID,
    latitude: float,
    longitude: float,
    speed_kph: Optional[float] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff)
):
    return track_driver(
        db,
        driver_id,
        shipment_id,
        latitude,
        longitude,
        speed_kph
    )


# ----------------------------------------
# Total Distance Traveled
# ----------------------------------------

@router.get("/shipment/{shipment_id}/total-distance")
def total_distance(
    shipment_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff)
):
    return {
        "shipment_id": shipment_id,
        "total_distance_meters": calculate_total_distance_traveled(db, shipment_id)
    }


# ----------------------------------------
# Remaining Distance
# ----------------------------------------

@router.get("/shipment/{shipment_id}/remaining-distance")
def remaining_distance(
    shipment_id: UUID,
    latitude: float,
    longitude: float,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff)
):
    return {
        "shipment_id": shipment_id,
        "remaining_distance_meters": calculate_remaining_distance(
            db,
            shipment_id,
            latitude,
            longitude
        )
    }


# ----------------------------------------
# ETA Calculation (Manual)
# ----------------------------------------

@router.get("/eta")
def eta(
    remaining_distance_meters: float,
    speed_kph: float,
    current_user: User = Depends(require_staff)
):
    minutes = calculate_eta(remaining_distance_meters, speed_kph)

    return {
        "remaining_distance_meters": remaining_distance_meters,
        "speed_kph": speed_kph,
        "eta_minutes": minutes
    }


# ----------------------------------------
# Nearest Drivers
# ----------------------------------------

@router.get("/nearest-drivers")
def nearest_drivers(
    latitude: float,
    longitude: float,
    radius_meters: float = Query(5000, ge=100),
    limit: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff)
):
    drivers = find_nearest_drivers(
        db,
        latitude,
        longitude,
        radius_meters,
        limit
    )

    return [
        {
            "driver_id": d.id,
            "distance_meters": round(float(d.distance), 2)
        }
        for d in drivers
    ]


# ----------------------------------------
# Average Speed
# ----------------------------------------

@router.get("/shipment/{shipment_id}/average-speed")
def average_speed(
    shipment_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff)
):
    return calculate_average_speed(shipment_id, db)


# ----------------------------------------
# Detect Stops
# ----------------------------------------

@router.get("/shipment/{shipment_id}/stops")
def stops(
    shipment_id: UUID,
    min_stop_minutes: int = Query(5, ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff)
):
    return detect_delivery_stops(
        shipment_id,
        db,
        min_stop_minutes
    )


# ----------------------------------------
# Estimated Delivery Time (Direct GPS)
# ----------------------------------------

@router.get("/estimate-delivery-time")
def estimate_delivery_time(
    current_lat: float,
    current_lng: float,
    destination_lat: float,
    destination_lng: float,
    speed_kmh: Optional[float] = None,
    current_user: User = Depends(require_staff)
):
    return calculate_estimated_delivery_time(
        current_lat,
        current_lng,
        destination_lat,
        destination_lng,
        speed_kmh
    )


# ----------------------------------------
# Shipment Tracking Summary
# ----------------------------------------

@router.get("/shipment/{shipment_id}/summary")
def tracking_summary(
    shipment_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff)
):
    return get_shipment_tracking_summary(shipment_id, db)


# ----------------------------------------
# Validate Tracking Sequence
# ----------------------------------------

@router.get("/shipment/{shipment_id}/validate")
def validate_sequence(
    shipment_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff)
):
    return validate_tracking_point_sequence(shipment_id, db)
