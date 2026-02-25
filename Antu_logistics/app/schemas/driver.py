from __future__ import annotations
from typing import Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field

from app.models.driver_model import DriverStatus


class DriverBase(BaseModel):
    user_id: UUID
    vehicle_id: Optional[UUID] = None
    license_number: str
    last_location_update: Optional[datetime] = None


class DriverCreate(DriverBase):
    user_id: UUID
    license_number: str

class DriverUpdate(BaseModel):
    vehicle_id: Optional[UUID] = None
    status: Optional[DriverStatus] = None
    is_active: Optional[bool] = None

class LocationUpdate(BaseModel):
    lat: float = Field(..., description="Latitude of the driver's current location")
    lng: float = Field(..., description="Longitude of the driver's current location")
    recorded_at: Optional[datetime] = None


class DriverRead(DriverBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_location_update: Optional[datetime] = None
    current_latitude: Optional[float] = None
    current_longitude: Optional[float] = None
    is_active: bool
    status: DriverStatus


    model_config = {"from_attributes": True}
