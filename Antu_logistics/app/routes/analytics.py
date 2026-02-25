from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.database import get_db
from app.core.deps import get_current_user  # adjust if your dependency path differs
from app.models.user_model import User, UserRole

from app.services.analytics_service import (
    calculate_revenue_forecast,
    analyze_peak_hours,
    calculate_customer_lifetime_value,
    analyze_delivery_performance,
    get_geographic_insights,
    calculate_fleet_efficiency,
    generate_executive_summary,
    identify_business_opportunities
)

router = APIRouter(
    prefix="/analytics",
    tags=["Analytics"]
)


# ----------------------------------------
# Role Protection Helper
# ----------------------------------------

def require_admin_or_manager(current_user: User = Depends(get_current_user)):
    if current_user.role not in [UserRole.ADMIN, UserRole.LOGISTICS_MANAGER]:
        raise HTTPException(status_code=403, detail="Not authorized")
    return current_user


# ----------------------------------------
# Revenue Forecast
# ----------------------------------------

@router.get("/revenue-forecast")
def revenue_forecast(
    days_ahead: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_manager)
):
    return calculate_revenue_forecast(db, days_ahead)


# ----------------------------------------
# Peak Hours Analysis
# ----------------------------------------

@router.get("/peak-hours")
def peak_hours(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_manager)
):
    return analyze_peak_hours(db)


# ----------------------------------------
# Customer Lifetime Value
# ----------------------------------------

@router.get("/customer/{shipper_id}/lifetime-value")
def customer_lifetime_value(
    shipper_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_manager)
):
    return calculate_customer_lifetime_value(shipper_id, db)


# ----------------------------------------
# Delivery Performance
# ----------------------------------------

@router.get("/delivery-performance")
def delivery_performance(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_manager)
):
    return analyze_delivery_performance(db)


# ----------------------------------------
# Geographic Insights
# ----------------------------------------

@router.get("/geographic-insights")
def geographic_insights(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_manager)
):
    return get_geographic_insights(db)


# ----------------------------------------
# Fleet Efficiency
# ----------------------------------------

@router.get("/fleet-efficiency")
def fleet_efficiency(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_manager)
):
    return calculate_fleet_efficiency(db)


# ----------------------------------------
# Executive Summary
# ----------------------------------------

@router.get("/executive-summary")
def executive_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_manager)
):
    return generate_executive_summary(db)


# ----------------------------------------
# Business Opportunities
# ----------------------------------------

@router.get("/business-opportunities")
def business_opportunities(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_manager)
):
    return identify_business_opportunities(db)
