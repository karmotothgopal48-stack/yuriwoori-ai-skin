from fastapi import APIRouter
from app.api.v1.endpoints import health, scans, passport, products

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(scans.router, prefix="/scans", tags=["scans"])
api_router.include_router(passport.router, prefix="/passport", tags=["passport"])
api_router.include_router(products.router, prefix="/products", tags=["products"])