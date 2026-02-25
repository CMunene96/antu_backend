from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from decimal import Decimal
from typing import Optional

from app.database import get_db
from app.core.deps import get_current_user
from app.models.user_model import User, UserRole
from app.models.vehicle_model import VehicleType

from app.services.vehicle_service import (
    get_vehicle_utilization_rate,
    get_optimal_vehicle_for_shipment,
    calculate_vehicle_maintenance_score,
    get_vehicle_cost_efficiency,
    check_vehicle_availability,
    get_vehicle_characteristics
)

router = APIRouter(
    prefix="/vehicle-analytics",
    tags=["Vehicle Analytics"]
)


# ----------------------------------------
# Role Protection
# ----------------------------------------

def require_staff(current_user: User = Depends(get_current_user)):
    if current_user.role not in [
        UserRole.ADMIN,
        UserRole.LOGISTICS_MANAGER,
    ]:
        raise HTTPException(status_code=403, detail="Not authorized")
    return current_user


# ----------------------------------------
# Vehicle Utilization
# ----------------------------------------

@router.get("/{vehicle_id}/utilization")
def vehicle_utilization(
    vehicle_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff)
):
    rate = get_vehicle_utilization_rate(vehicle_id, db)

    return {
        "vehicle_id": vehicle_id,
        "utilization_percent": round(rate, 2)
    }


# ----------------------------------------
# Optimal Vehicle Recommendation
# ----------------------------------------

@router.get("/recommend")
def recommend_vehicle(
    weight_kg: Decimal,
    distance_km: Decimal,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff)
):
    vehicle = get_optimal_vehicle_for_shipment(
        weight_kg,
        distance_km,
        db
    )

    if not vehicle:
        return {"message": "No suitable vehicle available"}

    return {
        "vehicle_id": vehicle.id,
        "vehicle_type": vehicle.vehicle_type,
        "capacity_kg": float(vehicle.capacity_kg),
        "reason": "Best match based on weight and distance"
    }


# ----------------------------------------
# Maintenance Score
# ----------------------------------------

@router.get("/{vehicle_id}/maintenance")
def maintenance_score(
    vehicle_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff)
):
    return calculate_vehicle_maintenance_score(vehicle_id, db)


# ----------------------------------------
# Cost Efficiency
# ----------------------------------------

@router.get("/{vehicle_id}/cost-efficiency")
def cost_efficiency(
    vehicle_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff)
):
    return get_vehicle_cost_efficiency(vehicle_id, db)


# ----------------------------------------
# Availability Check
# ----------------------------------------

@router.get("/{vehicle_id}/availability")
def availability(
    vehicle_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff)
):
    return check_vehicle_availability(vehicle_id, db)


# ----------------------------------------
# Vehicle Type Characteristics
# ----------------------------------------

@router.get("/characteristics/{vehicle_type}")
def characteristics(
    vehicle_type: VehicleType,
    current_user: User = Depends(require_staff)
):
    return get_vehicle_characteristics(vehicle_type)
