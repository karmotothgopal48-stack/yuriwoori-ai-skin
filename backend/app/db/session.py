import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.core.config import settings

logger = logging.getLogger(__name__)

# Placeholder used only so the app can boot (and /v1/health, /docs work) when
# DATABASE_URL is not configured yet. Any route that touches the DB will fail
# with a connection error until a real DATABASE_URL is set in .env.
_UNCONFIGURED_URL = "postgresql://postgres@localhost:5432/yuriwoori_db"

if not settings.database_url:
    logger.warning("DATABASE_URL is not set - database-backed endpoints will fail until it is configured in .env")

engine = create_engine(settings.database_url or _UNCONFIGURED_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
