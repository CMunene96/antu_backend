from __future__ import annotations
from decimal import Decimal
from typing import Optional
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.vehicle_model import VehicleStatus


class VehicleBase(BaseModel):
    plate_number: str
    vehicle_type: str
    model: Optional[str] = None
    fuel_rate_per_km: Decimal = Field(..., gt=0)  
    capacity_kg: Decimal = Field(..., gt=0)
    status: Optional[str] = None
    is_active: bool = True


class VehicleCreate(VehicleBase):
    pass

class VehicleUpdate(BaseModel):
    model: Optional[str] = None
    capacity_kg: Optional[Decimal] = Field(None, gt=0)
    status: Optional[VehicleStatus] = None
    is_active: Optional[bool] = None


class VehicleRead(VehicleBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    status: VehicleStatus
    is_active: bool

    model_config = {"from_attributes": True}
