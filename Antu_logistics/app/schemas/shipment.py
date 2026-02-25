from __future__ import annotations
from decimal import Decimal
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field

from app.models.shipment_model import ShipmentStatus
from app.schemas.tracking import TrackingPointRead


class ShipmentBase(BaseModel):
    tracking_number: str
    shipper_id: UUID
    driver_id: Optional[UUID] = None
    origin_latitude: float = Field(..., ge=-90, le=90, description="Origin latitude")
    origin_longitude: float = Field(..., ge=-180, le=180, description="Origin longitude")
    destination_latitude: float = Field(..., ge=-90, le=90, description="Destination latitude")
    destination_longitude: float = Field(..., ge=-180, le=180, description="Destination longitude")
    package_description: Optional[str] = None
    weight_kg: Decimal = Field(..., gt=0)
    volume_m3: Optional[Decimal] = None
    status: Optional[str] = None
    estimated_distance_km: Optional[Decimal] = None
    estimated_cost: Optional[Decimal] = None
    actual_cost: Optional[Decimal] = None
    recipient_name: str
    recipient_phone: str


class ShipmentCreate(ShipmentBase):
    pass

class ShipmentUpdate(BaseModel):
    status: Optional[ShipmentStatus] = None
    driver_id: Optional[UUID] = None
    estimated_distance_km: Optional[Decimal] = None
    actual_cost: Optional[Decimal] = None

class ShipmentRead(ShipmentBase):
    id: UUID
    created_at: datetime
    assigned_at: Optional[datetime] = None
    picked_up_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    tracking_points: List[TrackingPointRead] = []
    tracking_number: str
    shipper_id: Optional[UUID] = None
    driver_id: Optional[UUID] = None
    status: ShipmentStatus
    estimated_distance_km: Optional[Decimal] = None
    estimated_cost: Optional[Decimal] = None
    actual_cost: Optional[Decimal] = None

    model_config = {"from_attributes": True}
