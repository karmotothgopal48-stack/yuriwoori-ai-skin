import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from app.core.config import settings
from app.api.v1.router import api_router
from app.api.v1.endpoints import health
from app.services.live_catalogue import LiveCatalogueUnavailable

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("yuriwoori")

app = FastAPI(title="YuriWoori Backend", version="0.1.0")


# Starlette answers unhandled exceptions from its outermost layer, outside CORSMiddleware, so those 500s
# had no CORS headers: the browser hid them and the frontend reported "Can't reach the YuriWoori server".
# Registered before CORSMiddleware so CORS wraps it and every error reaches the browser as JSON.
@app.middleware("http")
async def unhandled_error_as_json(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "The server hit an unexpected error. Please try again."})


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_error_without_input(request: Request, exc: RequestValidationError):
    # FastAPI's default 422 repeats the rejected input, which for a scan upload can be the photo itself.
    # Only where and why: never the submitted value (NO SELFIE STORAGE / no personal data in responses).
    errors = [{k: v for k, v in e.items() if k in ("loc", "msg", "type")} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": errors})


@app.exception_handler(OperationalError)
async def database_unavailable_handler(request: Request, exc: OperationalError):
    logger.error("Database connection error on %s %s: %s", request.method, request.url.path, exc.orig)
    return JSONResponse(
        status_code=503,
        content={"detail": "Database is unavailable. Check DATABASE_URL in .env and that PostgreSQL is running."},
    )


@app.exception_handler(LiveCatalogueUnavailable)
async def catalogue_unavailable_handler(request: Request, exc: LiveCatalogueUnavailable):
    # products come only from the live store: without it there is nothing honest to show (no stale/CSV fallback)
    return JSONResponse(status_code=503, content={"detail": str(exc)})


app.include_router(api_router, prefix="/v1")

# Liveness check at the root too (load balancers, scripts); same handler as /v1/health.
app.add_api_route("/health", health.health_check, methods=["GET"], tags=["health"])


@app.get("/")
def root():
    return {"message": "YuriWoori API is running"}
