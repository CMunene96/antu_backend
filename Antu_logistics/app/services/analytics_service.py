from typing import Dict, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import UUID, func, and_
from app.models.shipment_model import Shipment, ShipmentStatus
from app.models.driver_model import Driver, DriverStatus
from app.models.vehicle_model import Vehicle, VehicleStatus
from app.models.user_model import User, UserRole

def calculate_revenue_forecast(db: Session, days_ahead: int = 30) -> dict:
    """
    Forecast revenue for the next period based on historical data
    
    Args:
        db: Database session
        days_ahead: Number of days to forecast
    
    Returns:
        Dictionary with forecast data
    """
    # Get historical data from last 30 days
    past_30_days = datetime.utcnow() - timedelta(days=30)
    
    historical_shipments = db.query(Shipment).filter(
        Shipment.created_at >= past_30_days,
        Shipment.status == ShipmentStatus.DELIVERED
    ).all()
    
    if not historical_shipments:
        return {
            "forecast_days": days_ahead,
            "forecasted_revenue": 0,
            "confidence": "low",
            "message": "Insufficient historical data"
        }
    
    # Calculate average daily revenue
    total_revenue = sum([s.actual_cost or s.estimated_cost or 0 for s in historical_shipments])
    avg_daily_revenue = total_revenue / 30
    
    # Calculate growth trend
    first_15_days = [s for s in historical_shipments if s.created_at < past_30_days + timedelta(days=15)]
    last_15_days = [s for s in historical_shipments if s.created_at >= past_30_days + timedelta(days=15)]
    
    first_half_revenue = sum([s.actual_cost or s.estimated_cost or 0 for s in first_15_days])
    second_half_revenue = sum([s.actual_cost or s.estimated_cost or 0 for s in last_15_days])
    
    growth_rate = ((second_half_revenue - first_half_revenue) / first_half_revenue) if first_half_revenue > 0 else 0
    
    # Apply growth rate to forecast
    forecasted_revenue = avg_daily_revenue * days_ahead * (1 + growth_rate)
    
    # Determine confidence
    if len(historical_shipments) > 50:
        confidence = "high"
    elif len(historical_shipments) > 20:
        confidence = "medium"
    else:
        confidence = "low"
    
    return {
        "forecast_days": days_ahead,
        "forecasted_revenue": round(forecasted_revenue, 2),
        "avg_daily_revenue": round(avg_daily_revenue, 2),
        "growth_rate_percent": round(growth_rate * 100, 2),
        "confidence": confidence,
        "based_on_shipments": len(historical_shipments)
    }

def analyze_peak_hours(db: Session) -> dict:
    """
    Analyze peak hours for shipment creation and delivery
    
    Args:
        db: Database session
    
    Returns:
        Dictionary with peak hour analysis
    """
    # Get all shipments
    shipments = db.query(Shipment).all()
    
    if not shipments:
        return {"message": "No data available"}
    
    # Count shipments by hour of day
    creation_hours = {}
    delivery_hours = {}
    
    for shipment in shipments:
        # Creation hour
        hour = shipment.created_at.hour
        creation_hours[hour] = creation_hours.get(hour, 0) + 1
        
        # Delivery hour
        if shipment.delivered_at:
            delivery_hour = shipment.delivered_at.hour
            delivery_hours[delivery_hour] = delivery_hours.get(delivery_hour, 0) + 1
    
    # Find peak hours
    peak_creation_hour = max(creation_hours, key=creation_hours.get) if creation_hours else 0
    peak_delivery_hour = max(delivery_hours, key=delivery_hours.get) if delivery_hours else 0
    
    return {
        "peak_creation_hour": f"{peak_creation_hour:02d}:00",
        "peak_creation_count": creation_hours.get(peak_creation_hour, 0),
        "peak_delivery_hour": f"{peak_delivery_hour:02d}:00",
        "peak_delivery_count": delivery_hours.get(peak_delivery_hour, 0),
        "hourly_creation_distribution": {f"{k:02d}:00": v for k, v in sorted(creation_hours.items())},
        "hourly_delivery_distribution": {f"{k:02d}:00": v for k, v in sorted(delivery_hours.items())}
    }

def calculate_customer_lifetime_value(shipper_id: UUID, db: Session) -> dict:
    """
    Calculate the lifetime value of a customer
    
    Args:
        customer_id: ID of the customer
        db: Database session
    
    Returns:
        Dictionary with CLV metrics
    """
    customer = db.query(User).filter(User.id == shipper_id).first()
    if not customer or customer.role != UserRole.CUSTOMER:
        return {"error": "Shipper not found"}
    
    # Get all shipments
    shipments = db.query(Shipment).filter(Shipment.shipper_id== shipper_id).all()
    
    if not shipments:
        return {
            "customer_id": shipper_id,
            "lifetime_value": 0,
            "total_shipments": 0,
            "message": "No shipment history"
        }
    
    # Calculate metrics
    total_spent = sum([s.actual_cost or s.estimated_cost or 0 for s in shipments])
    total_shipments = len(shipments)
    avg_order_value = total_spent / total_shipments
    
    # Calculate frequency (days between orders)
    if total_shipments > 1:
        first_order = min([s.created_at for s in shipments])
        last_order = max([s.created_at for s in shipments])
        days_active = (last_order - first_order).days
        order_frequency_days = days_active / (total_shipments - 1) if total_shipments > 1 else 0
    else:
        order_frequency_days = 0
        days_active = 0
    
    # Predict future value (simple model)
    # Assume customer will continue for another year
    if order_frequency_days > 0:
        estimated_future_orders = 365 / order_frequency_days
        predicted_ltv = total_spent + (estimated_future_orders * avg_order_value)
    else:
        predicted_ltv = total_spent
    
    # Customer segment
    if total_spent > 50000:
        segment = "premium"
    elif total_spent > 20000:
        segment = "regular"
    elif total_spent > 5000:
        segment = "occasional"
    else:
        segment = "new"
    
    return {
        "customer_id": shipper_id,
        "customer_name": customer.full_name,
        "lifetime_value": round(total_spent, 2),
        "predicted_ltv_next_year": round(predicted_ltv, 2),
        "total_shipments": total_shipments,
        "average_order_value": round(avg_order_value, 2),
        "order_frequency_days": round(order_frequency_days, 1),
        "customer_since": shipments[0].created_at.date().isoformat() if shipments else None,
        "days_active": days_active,
        "customer_segment": segment
    }

def analyze_delivery_performance(db: Session) -> dict:
    """
    Analyze overall delivery performance metrics
    
    Args:
        db: Database session
    
    Returns:
        Dictionary with performance analysis
    """
    # Get all delivered shipments
    delivered_shipments = db.query(Shipment).filter(
        Shipment.status == ShipmentStatus.DELIVERED,
        Shipment.picked_up_at.isnot(None),
        Shipment.delivered_at.isnot(None)
    ).all()
    
    if not delivered_shipments:
        return {"message": "No delivery data available"}
    
    delivery_times = []
    
    for shipment in delivered_shipments:
        if shipment.picked_up_at and shipment.delivered_at:
            delivery_time = (shipment.delivered_at - shipment.picked_up_at).total_seconds() / 3600  # hours
            delivery_times.append(delivery_time)
    
    if not delivery_times:
        return {"message": "No valid delivery time data"}
    
    avg_delivery_time = sum(delivery_times) / len(delivery_times)
    min_delivery_time = min(delivery_times)
    max_delivery_time = max(delivery_times)
    
    # Calculate on-time delivery rate (assuming 24 hours is target)
    on_time_deliveries = sum(1 for t in delivery_times if t <= 24)
    on_time_rate = (on_time_deliveries / len(delivery_times)) * 100
    
    # Performance rating
    if on_time_rate >= 90:
        rating = "excellent"
    elif on_time_rate >= 75:
        rating = "good"
    elif on_time_rate >= 60:
        rating = "average"
    else:
        rating = "needs_improvement"
    
    return {
        "total_deliveries": len(delivered_shipments),
        "average_delivery_time_hours": round(avg_delivery_time, 2),
        "fastest_delivery_hours": round(min_delivery_time, 2),
        "slowest_delivery_hours": round(max_delivery_time, 2),
        "on_time_deliveries": on_time_deliveries,
        "on_time_rate_percent": round(on_time_rate, 2),
        "performance_rating": rating
    }

def get_geographic_insights(db: Session) -> dict:
    """
    Analyze geographic patterns in deliveries
    
    Args:
        db: Database session
    
    Returns:
        Dictionary with geographic insights
    """
    from collections import defaultdict
    
    shipments = db.query(Shipment).filter(
        Shipment.status == ShipmentStatus.DELIVERED
    ).all()
    
    if not shipments:
        return {"message": "No delivery data available"}
    
    # This is simplified - in production you'd use geocoding to get actual areas
    # For now, we'll analyze based on coordinates
    
    total_distance = sum([s.estimated_distance_km or 0 for s in shipments])
    avg_distance = total_distance / len(shipments)
    
    # Categorize by distance
    short_range = sum(1 for s in shipments if (s.estimated_distance_km or 0) < 5)
    medium_range = sum(1 for s in shipments if 5 <= (s.estimated_distance_km or 0) < 20)
    long_range = sum(1 for s in shipments if (s.estimated_distance_km or 0) >= 20)
    
    return {
        "total_deliveries": len(shipments),
        "total_distance_covered_km": round(total_distance, 2),
        "average_delivery_distance_km": round(avg_distance, 2),
        "distance_distribution": {
            "short_range_0_5km": short_range,
            "medium_range_5_20km": medium_range,
            "long_range_20plus_km": long_range
        },
        "distribution_percentages": {
            "short_range_percent": round(short_range / len(shipments) * 100, 2),
            "medium_range_percent": round(medium_range / len(shipments) * 100, 2),
            "long_range_percent": round(long_range / len(shipments) * 100, 2)
        }
    }

def calculate_fleet_efficiency(db: Session) -> dict:
    """
    Calculate overall fleet efficiency metrics
    
    Args:
        db: Database session
    
    Returns:
        Dictionary with fleet efficiency metrics
    """
    total_vehicles = db.query(Vehicle).filter(Vehicle.is_active == True).count()
    available_vehicles = db.query(Vehicle).filter(
        Vehicle.is_active == True,
        Vehicle.status == VehicleStatus.AVAILABLE
    ).count()
    
    total_drivers = db.query(Driver).filter(Driver.is_active == True).count()
    active_drivers = db.query(Driver).filter(
        Driver.is_active == True,
        Driver.status.in_([DriverStatus.AVAILABLE, DriverStatus.ON_DUTY])
    ).count()
    
    # Calculate utilization rates
    vehicle_utilization = ((total_vehicles - available_vehicles) / total_vehicles * 100) if total_vehicles > 0 else 0
    driver_utilization = (active_drivers / total_drivers * 100) if total_drivers > 0 else 0
    
    # Get active shipments
    active_shipments = db.query(Shipment).filter(
        Shipment.status.in_([ShipmentStatus.ASSIGNED, ShipmentStatus.IN_TRANSIT])
    ).count()
    
    # Calculate capacity
    total_capacity = db.query(func.sum(Vehicle.capacity_kg)).filter(
        Vehicle.is_active == True
    ).scalar() or 0
    
    # Efficiency rating
    overall_efficiency = (vehicle_utilization + driver_utilization) / 2
    
    if overall_efficiency >= 80:
        rating = "excellent"
    elif overall_efficiency >= 60:
        rating = "good"
    elif overall_efficiency >= 40:
        rating = "average"
    else:
        rating = "underutilized"
    
    return {
        "total_vehicles": total_vehicles,
        "available_vehicles": available_vehicles,
        "vehicle_utilization_percent": round(vehicle_utilization, 2),
        "total_drivers": total_drivers,
        "active_drivers": active_drivers,
        "driver_utilization_percent": round(driver_utilization, 2),
        "active_shipments": active_shipments,
        "total_fleet_capacity_kg": float(total_capacity),
        "overall_efficiency_percent": round(overall_efficiency, 2),
        "efficiency_rating": rating,
        "shipments_per_driver": round(active_shipments / active_drivers, 2) if active_drivers > 0 else 0
    }

def generate_executive_summary(db: Session) -> dict:
    """
    Generate a comprehensive executive summary
    
    Args:
        db: Database session
    
    Returns:
        Dictionary with executive summary
    """
    # Get current date info
    today = datetime.utcnow().date()
    this_month_start = today.replace(day=1)
    last_month_start = (this_month_start - timedelta(days=1)).replace(day=1)
    
    # This month's metrics
    this_month_shipments = db.query(Shipment).filter(
        Shipment.created_at >= datetime.combine(this_month_start, datetime.min.time())
    ).count()
    
    this_month_revenue = db.query(func.sum(Shipment.actual_cost)).filter(
        Shipment.created_at >= datetime.combine(this_month_start, datetime.min.time()),
        Shipment.status == ShipmentStatus.DELIVERED
    ).scalar() or 0
    
    # Last month's metrics for comparison
    last_month_shipments = db.query(Shipment).filter(
        and_(
            Shipment.created_at >= datetime.combine(last_month_start, datetime.min.time()),
            Shipment.created_at < datetime.combine(this_month_start, datetime.min.time())
        )
    ).count()
    
    last_month_revenue = db.query(func.sum(Shipment.actual_cost)).filter(
        and_(
            Shipment.created_at >= datetime.combine(last_month_start, datetime.min.time()),
            Shipment.created_at < datetime.combine(this_month_start, datetime.min.time())
        ),
        Shipment.status == ShipmentStatus.DELIVERED
    ).scalar() or 0
    
    # Calculate growth
    shipment_growth = ((this_month_shipments - last_month_shipments) / last_month_shipments * 100) if last_month_shipments > 0 else 0
    revenue_growth = ((this_month_revenue - last_month_revenue) / last_month_revenue * 100) if last_month_revenue > 0 else 0
    
    # Get other metrics
    delivery_performance = analyze_delivery_performance(db)
    fleet_efficiency = calculate_fleet_efficiency(db)
    
    return {
        "report_date": today.isoformat(),
        "period": "monthly",
        "this_month": {
            "shipments": this_month_shipments,
            "revenue": round(float(this_month_revenue), 2)
        },
        "last_month": {
            "shipments": last_month_shipments,
            "revenue": round(float(last_month_revenue), 2)
        },
        "growth": {
            "shipments_percent": round(shipment_growth, 2),
            "revenue_percent": round(revenue_growth, 2)
        },
        "performance": {
            "on_time_rate": delivery_performance.get("on_time_rate_percent", 0),
            "avg_delivery_time_hours": delivery_performance.get("average_delivery_time_hours", 0)
        },
        "fleet": {
            "utilization_percent": fleet_efficiency.get("overall_efficiency_percent", 0),
            "active_shipments": fleet_efficiency.get("active_shipments", 0)
        }
    }

def identify_business_opportunities(db: Session) -> List[dict]:
    """
    Identify business growth opportunities based on data
    
    Args:
        db: Database session
    
    Returns:
        List of identified opportunities
    """
    opportunities = []
    
    # Check underutilized fleet
    fleet_efficiency = calculate_fleet_efficiency(db)
    if fleet_efficiency.get("vehicle_utilization_percent", 100) < 50:
        opportunities.append({
            "type": "underutilized_fleet",
            "priority": "high",
            "description": f"Vehicle utilization is only {fleet_efficiency['vehicle_utilization_percent']:.0f}%. Consider marketing campaigns or new service routes.",
            "potential_impact": "Increase revenue by 30-50% with better utilization"
        })
    
    # Check for repeat customers
    customers_with_multiple_orders = db.query(
        Shipment.customer_id,
        func.count(Shipment.id)
    ).group_by(Shipment.customer_id).having(func.count(Shipment.id) > 5).count()
    
    total_customers = db.query(User).filter(User.role == UserRole.CUSTOMER).count()
    
    repeat_rate = (customers_with_multiple_orders / total_customers * 100) if total_customers > 0 else 0
    
    if repeat_rate < 30:
        opportunities.append({
            "type": "low_repeat_rate",
            "priority": "medium",
            "description": f"Only {repeat_rate:.0f}% of customers have 5+ orders. Consider loyalty programs.",
            "potential_impact": "Increase customer retention and lifetime value"
        })
    
    # Check geographic coverage
    geo_insights = get_geographic_insights(db)
    if geo_insights.get("distribution_percentages", {}).get("long_range_percent", 0) < 20:
        opportunities.append({
            "type": "expand_coverage",
            "priority": "medium",
            "description": "Most deliveries are short-range. Consider expanding to suburban/inter-city routes.",
            "potential_impact": "Access new markets and premium pricing for long-distance"
        })
    
    return opportunities