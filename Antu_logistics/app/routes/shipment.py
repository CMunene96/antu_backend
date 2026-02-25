from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from uuid import UUID

from app.database import get_db
from app.models.user_model import User, UserRole
from app.models.shipment_model import Shipment, ShipmentStatus
from app.models.driver_model import Driver
from app.schemas.shipment import ShipmentCreate, ShipmentUpdate, ShipmentRead as ShipmentResponse
from app.core.deps import get_current_user, require_role
from app.services.shipments_service import (
    generate_tracking_number,
    calculate_distance_km,
    calculate_delivery_cost,
    validate_coordinates
)

router = APIRouter(prefix="/shipments", tags=["Shipments"])

@router.post("/", response_model=ShipmentResponse, status_code=status.HTTP_201_CREATED)
def create_shipment(
    shipment_data: ShipmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new shipment
    - Customers can create shipments for themselves
    - Admins can create shipments for any customer
    """
    # Validate coordinates
    if not validate_coordinates(shipment_data.origin):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid origin coordinates"
        )
    
    if not validate_coordinates(shipment_data.destination):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid destination coordinates"
        )
    
    # Calculate distance
    distance = calculate_distance_km(
        shipment_data.origin,
        shipment_data.destination  
    )
    
    # Calculate estimated cost
    estimated_cost = calculate_delivery_cost(
        distance,
        shipment_data.weight_kg
    )
    
    # Create shipment
    new_shipment = Shipment(
        tracking_number=generate_tracking_number(),
        customer_id=current_user.id,

        origin_address=shipment_data.origin,
        destination_address=shipment_data.destination,
        package_description=shipment_data.package_description,
        weight_kg=shipment_data.weight_kg,
        volume_m3=shipment_data.volume_m3,
        recipient_name=shipment_data.recipient_name,
        recipient_phone=shipment_data.recipient_phone,
        estimated_distance_km=distance,
        estimated_cost=estimated_cost,
        status=ShipmentStatus.CREATED
    )
    
    db.add(new_shipment)
    db.commit()
    db.refresh(new_shipment)
    
    return new_shipment

@router.get("/", response_model=List[ShipmentResponse])
def list_shipments(
    status_filter: Optional[ShipmentStatus] = Query(None, description="Filter by status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List shipments
    - Customers see only their shipments
    - Drivers see only assigned shipments
    - Admins see all shipments
    """
    query = db.query(Shipment)
    
    # Apply role-based filtering
    if current_user.role == UserRole.CUSTOMER:
        query = query.filter(Shipment.shipper_id == current_user.id)
    elif current_user.role == UserRole.DRIVER:
        # Get driver profile
        driver = db.query(Driver).filter(Driver.user_id == current_user.id).first()
        if driver:
            query = query.filter(Shipment.driver_id == driver.id)
        else:
            return []  # Driver has no profile yet
    
    # Apply status filter if provided
    if status_filter:
        query = query.filter(Shipment.status == status_filter)
    
    # Apply pagination
    shipments = query.order_by(Shipment.created_at.desc()).offset(skip).limit(limit).all()
    
    return shipments

@router.get("/tracking/{tracking_number}", response_model=ShipmentResponse)
def track_shipment_by_number(
    tracking_number: str,
    db: Session = Depends(get_db)
):
    """
    Track a shipment by tracking number (public endpoint - no auth required for now)
    In production, you might want to add a verification code
    """
    shipment = db.query(Shipment).filter(
        Shipment.tracking_number == tracking_number
    ).first()
    
    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shipment not found"
        )
    
    return shipment

@router.get("/{shipment_id}", response_model=ShipmentResponse)
def get_shipment(
    shipment_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific shipment by ID"""
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    
    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shipment not found"
        )
    
    # Check permissions
    if current_user.role == UserRole.CUSTOMER and shipment.shipper_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this shipment"
        )
    
    if current_user.role == UserRole.DRIVER:
        driver = db.query(Driver).filter(Driver.user_id == current_user.id).first()
        if not driver or shipment.driver_id != driver.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view this shipment"
            )
    
    return shipment

@router.put("/{shipment_id}", response_model=ShipmentResponse)
def update_shipment(
    shipment_id: UUID,
    update_data: ShipmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.DRIVER]))
):
    """
    Update a shipment
    - Admins can update any field
    - Drivers can only update status
    """
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    
    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shipment not found"
        )
    
    # If driver, verify they're assigned to this shipment
    if current_user.role == UserRole.DRIVER:
        driver = db.query(Driver).filter(Driver.user_id == current_user.id).first()
        if not driver or shipment.driver_id != driver.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this shipment"
            )
    
    # Update fields
    if update_data.status is not None:
        shipment.status = update_data.status
        
        # Update timestamps based on status
        if update_data.status == ShipmentStatus.IN_TRANSIT and not shipment.picked_up_at:
            shipment.picked_up_at = datetime.utcnow()
        elif update_data.status == ShipmentStatus.DELIVERED and not shipment.delivered_at:
            shipment.delivered_at = datetime.utcnow()
    
    if update_data.driver_id is not None and current_user.role == UserRole.ADMIN:
        # Verify driver exists
        driver = db.query(Driver).filter(Driver.id == update_data.driver_id).first()
        if not driver:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Driver not found"
            )
        shipment.driver_id = update_data.driver_id
        shipment.assigned_at = datetime.utcnow()
        shipment.status = ShipmentStatus.ASSIGNED
    
    if update_data.actual_cost is not None and current_user.role == UserRole.ADMIN:
        shipment.actual_cost = update_data.actual_cost
    
    db.commit()
    db.refresh(shipment)
    
    return shipment

@router.delete("/{shipment_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_shipment(
    shipment_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.LOGISTICS_MANAGER, UserRole.CUSTOMER]))
):
    """
    Cancel a shipment
    - Customers can cancel their own pending shipments
    - Admins can cancel any shipment
    """
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    
    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shipment not found"
        )
    
    # Check permissions
    if current_user.role == UserRole.CUSTOMER:
        if shipment.shipper_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to cancel this shipment"
            )
        if shipment.status not in [ShipmentStatus.CREATED, ShipmentStatus.ASSIGNED]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Can only cancel pending or assigned shipments"
            )
    
    shipment.status = ShipmentStatus.CANCELLED
    db.commit()
    
    return None

@router.post("/{shipment_id}/assign", response_model=ShipmentResponse)
def assign_driver_to_shipment(
    shipment_id: UUID,
    driver_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN]))
):
    """
    Assign a driver to a shipment (Admin only)
    """
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shipment not found"
        )
    
    driver = db.query(Driver).filter(Driver.id == driver_id).first()
    if not driver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver not found"
        )
    
    if not driver.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Driver is not active"
        )
    
    shipment.driver_id = driver_id
    shipment.assigned_at = datetime.utcnow()
    shipment.status = ShipmentStatus.ASSIGNED
    
    db.commit()
    db.refresh(shipment)
    
    return shipment