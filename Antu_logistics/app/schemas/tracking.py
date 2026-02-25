from __future__ import annotations
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field


class TrackingPointBase(BaseModel):
    shipment_id: UUID
    latitude: float = Field(..., ge=-90, le=90, description="Latitude of the location")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude of the location")
    speed_kmh: Optional[float] = None
    recorded_at: Optional[datetime] = None
    notes: Optional[str] = None


class TrackingPointCreate(TrackingPointBase):
    shipment_id: UUID
    latitude: float = Field(..., ge=-90, le=90, description="Latitude of the location")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude of the location")


class TrackingPointRead(TrackingPointBase):
    id: UUID
    shipment_id: UUID
    time: datetime

    model_config = {"from_attributes": True}
