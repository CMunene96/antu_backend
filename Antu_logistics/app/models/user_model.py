from sqlalchemy import Column, Integer, String, DateTime, Enum, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import enum
import uuid
from app.database import Base

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    LOGISTICS_MANAGER = "manager"
    DRIVER = "driver"
    CUSTOMER = "shipper"

class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    driver_profile = relationship("Driver", back_populates="user", uselist=False)
    shipments_as_customer = relationship("Shipment", back_populates="customer", foreign_keys="Shipper_id")