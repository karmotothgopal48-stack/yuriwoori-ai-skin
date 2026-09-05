from fastapi import APIRouter
from app.api.v1.endpoints import health

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])

# Future steps will add more, e.g.:
# from app.api.v1.endpoints import scans
# api_router.include_router(scans.router, prefix="/scans", tags=["scans"])