from sqlalchemy import Column, Integer, String, Numeric, ForeignKey, DateTime, Enum, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from geoalchemy2 import Geography
import enum
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base
import uuid
from datetime import datetime, timezone

class ShipmentStatus(str, enum.Enum):
    CREATED = "created"
    ASSIGNED = "assigned"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    DELAYED = "delayed"
    CANCELLED = "cancelled"

class Shipment(Base):
    __tablename__ = "shipments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tracking_number = Column(String, unique=True, index=True, nullable=False)
    shipper_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=True)
    
    # Origin details
    origin = Column(Geography(geometry_type="POINT", srid=4326), nullable=False)
    
    # Destination details
    destination = Column(Geography(geometry_type="POINT", srid=4326), nullable=False)
    
    # Shipment details
    package_description = Column(Text)
    weight_kg = Column(Numeric(10, 2), nullable=False)
    volume_m3 = Column(Numeric(10, 2), nullable=True)
    status = Column(Enum(ShipmentStatus), default=ShipmentStatus.CREATED)
    
    # Cost and distance
    estimated_distance_km = Column(Numeric(10, 2), nullable=True)
    estimated_cost = Column(Numeric(10, 2), nullable=True)
    actual_cost = Column(Numeric(10, 2), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    assigned_at = Column(DateTime, nullable=True)
    picked_up_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Recipient details
    recipient_name = Column(String, nullable=False)
    recipient_phone = Column(String, nullable=False)
    
    # Relationships
    customer = relationship("User", back_populates="shipments_as_customer", foreign_keys=[shipper_id])
    driver = relationship("Driver", back_populates="shipments")
    tracking_points = relationship("TrackingPoint", back_populates="shipment", cascade="all, delete-orphan")
