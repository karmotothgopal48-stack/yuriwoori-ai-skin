from fastapi import APIRouter
from app.api.v1.endpoints import health, scans, passport, products, coach, progress, shopping_agent, shopify, catalogue, users, events, admin, delivery, reports

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(scans.router, prefix="/scans", tags=["scans"])
api_router.include_router(events.router, prefix="/events", tags=["engagement"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(passport.router, prefix="/passport", tags=["passport"])
api_router.include_router(products.router, prefix="/products", tags=["products"])
api_router.include_router(coach.router, prefix="/coach", tags=["coach"])
api_router.include_router(progress.router, prefix="/progress", tags=["progress"])
api_router.include_router(shopping_agent.router, prefix="/shopping-agent", tags=["shopping-agent"])
api_router.include_router(shopify.router, prefix="/shopify", tags=["shopify"])
api_router.include_router(catalogue.router, prefix="/catalogue", tags=["catalogue"])
api_router.include_router(delivery.router, prefix="/delivery", tags=["delivery"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
