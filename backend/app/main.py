import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from app.core.config import settings
from app.api.v1.router import api_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("yuriwoori")

app = FastAPI(title="YuriWoori Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(OperationalError)
async def database_unavailable_handler(request: Request, exc: OperationalError):
    logger.error("Database connection error on %s %s: %s", request.method, request.url.path, exc.orig)
    return JSONResponse(
        status_code=503,
        content={"detail": "Database is unavailable. Check DATABASE_URL in .env and that PostgreSQL is running."},
    )


app.include_router(api_router, prefix="/v1")


@app.get("/")
def root():
    return {"message": "YuriWoori API is running"}
