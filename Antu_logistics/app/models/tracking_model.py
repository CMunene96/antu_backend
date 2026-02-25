from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID
from geoalchemy2 import Geography
from app.database import Base
import uuid

class TrackingPoint(Base):
    __tablename__ = "tracking_points"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shipment_id = Column(UUID(as_uuid=True), ForeignKey("shipments.id"), nullable=False)
    location = Column(Geography(geometry_type='POINT', srid=4326), nullable=False)  # GPS coordinates
    speed_kmh = Column(Float, nullable=True)  # Speed at this point
    recorded_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    notes = Column(String, nullable=True)  # e.g., "Delayed due to traffic"
    
    # Relationships
    shipment = relationship("Shipment", back_populates="tracking_points")
