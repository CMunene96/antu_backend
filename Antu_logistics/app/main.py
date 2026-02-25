from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.database import engine, Base
from app.routes import auth , analytics , tracking , vehicle , shipment , driver

Base.metadata.create_all(bind=engine)

# Initialize FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="A logistics management system for real-time shipment tracking",
    version="1.0.0"
)

# CORS middleware - configure for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change this in production to specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(analytics.router)
app.include_router(tracking.router)
app.include_router(vehicle.router)
app.include_router(shipment.router)
app.include_router(driver.router)

@app.get("/")
def root():
    """Root endpoint"""
    return {
        "message": "Welcome to Antu Logistics System API",
        "version": "1.0.0",
        "docs": "/docs"
    }

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}