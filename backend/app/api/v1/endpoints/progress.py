import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import ProgressSnapshot
from app.schemas import ProgressResponse
from app.services.progress import build_progress_series

router = APIRouter()


@router.get("/{user_id}", response_model=ProgressResponse)
def get_progress(user_id: uuid.UUID, db: Session = Depends(get_db)):
    snapshots = db.query(ProgressSnapshot).filter(ProgressSnapshot.user_id == user_id).all()
    result = build_progress_series(snapshots)
    return ProgressResponse(**result)