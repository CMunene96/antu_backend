from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime
from decimal import Decimal
from typing import Optional

from app.database import get_db
from app.core.deps import get_current_user
from app.models.user_model import User, UserRole

from app.services.driver_service import (
    calculate_driver_efficiency_score,
    get_driver_active_workload,
    update_driver_location,
    calculate_estimated_arrival_time,
    check_driver_availability_for_shipment,
    get_driver_daily_summary,
    find_nearest_available_driver,
    get_driver_performance_trends
)

router = APIRouter(
    prefix="/driver-analytics",
    tags=["Driver Analytics"]
)


# ----------------------------------------
# Role Protection
# ----------------------------------------

def require_staff(current_user: User = Depends(get_current_user)):
    if current_user.role not in [UserRole.ADMIN, UserRole.MANAGER]:
        raise HTTPException(status_code=403, detail="Not authorized")
    return current_user


# ----------------------------------------
# Driver Efficiency Score
# ----------------------------------------

@router.get("/{driver_id}/efficiency")
def driver_efficiency(
    driver_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff)
):
    return calculate_driver_efficiency_score(driver_id, db)


# ----------------------------------------
# Active Workload
# ----------------------------------------

@router.get("/{driver_id}/workload")
def driver_workload(
    driver_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff)
):
    return get_driver_active_workload(driver_id, db)


# ----------------------------------------
# Update Driver Location
# ----------------------------------------

@router.post("/{driver_id}/location")
def update_location(
    driver_id: UUID,
    latitude: float,
    longitude: float,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff)
):
    driver = update_driver_location(db, driver_id, latitude, longitude)

    return {
        "driver_id": driver.id,
        "message": "Location updated successfully"
    }


# ----------------------------------------
# ETA Calculation
# ----------------------------------------

@router.get("/{driver_id}/eta")
def driver_eta(
    driver_id: UUID,
    current_lat: float,
    current_lng: float,
    destination_lat: float,
    destination_lng: float,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff)
):
    eta = calculate_estimated_arrival_time(
        driver_id,
        current_lat,
        current_lng,
        destination_lat,
        destination_lng,
        db
    )

    if not eta:
        raise HTTPException(status_code=404, detail="Driver not available")

    return eta


# ----------------------------------------
# Driver Availability Check
# ----------------------------------------

@router.get("/{driver_id}/availability")
def driver_availability(
    driver_id: UUID,
    shipment_weight_kg: float,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff)
):
    return check_driver_availability_for_shipment(
        driver_id,
        shipment_weight_kg,
        db
    )


# ----------------------------------------
# Daily Summary
# ----------------------------------------

@router.get("/{driver_id}/daily-summary")
def driver_daily_summary(
    driver_id: UUID,
    date: datetime,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff)
):
    return get_driver_daily_summary(driver_id, date, db)


# ----------------------------------------
# Find Nearest Available Driver
# ----------------------------------------

@router.get("/nearest-driver")
def nearest_driver(
    origin_lat: float,
    origin_lng: float,
    shipment_weight_kg: Decimal,
    max_distance_km: Decimal = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff)
):
    result = find_nearest_available_driver(
        origin_lat,
        origin_lng,
        shipment_weight_kg,
        db,
        max_distance_km
    )

    if not result:
        return {"message": "No suitable driver found within range"}

    driver, distance = result

    return {
        "driver_id": driver.id,
        "distance_km": round(distance, 2),
        "driver_status": driver.status
    }


# ----------------------------------------
# Performance Trends
# ----------------------------------------

@router.get("/{driver_id}/performance-trends")
def performance_trends(
    driver_id: UUID,
    days: int = Query(30, ge=7, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff)
):
    return get_driver_performance_trends(driver_id, days, db)
