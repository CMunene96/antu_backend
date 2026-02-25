from sqlalchemy import Column, Integer, Numeric, String, Float, DateTime, Enum, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID
import enum
from app.database import Base
import uuid

class VehicleStatus(str, enum.Enum):
    AVAILABLE = "available"
    IN_USE = "in_use"
    MAINTENANCE = "maintenance"
    INACTIVE = "inactive"

class VehicleType(str, enum.Enum):
    MOTORCYCLE = "motorcycle"
    VAN = "van"
    TRUCK = "truck"
    PICKUP = "pickup"

class Vehicle(Base):
    __tablename__ = "vehicles"
    
    id =  Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plate_number = Column(String, unique=True, index=True, nullable=False)
    vehicle_type = Column(Enum(VehicleType), nullable=False)
    model = Column(String)
    fuel_rate_per_km = Column(Numeric(10, 2), nullable=False)  # Fuel consumption rate
    capacity_kg = Column(Numeric(10, 2), nullable=False)  # Maximum weight capacity
    status = Column(Enum(VehicleStatus), default=VehicleStatus.AVAILABLE)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    drivers = relationship("Driver", back_populates="vehicle")
