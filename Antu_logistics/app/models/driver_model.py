from geoalchemy2 import Geography
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Enum, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID
import enum
from app.database import Base
import uuid

class DriverStatus(str, enum.Enum):
    AVAILABLE = "available"
    ON_DUTY = "on_duty"
    OFF_DUTY = "off_duty"

class Driver(Base):
    __tablename__ = "drivers"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=True)
    license_number = Column(String, unique=True, nullable=False)
    status = Column(Enum(DriverStatus), default=DriverStatus.OFF_DUTY)
    location=Column(Geography(geometry_type="POINT", srid=4326), nullable=True)
    last_location_update = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="driver_profile")
    vehicle = relationship("Vehicle", back_populates="drivers")
    shipments = relationship("Shipment", back_populates="driver")
