import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import ProgressSnapshot
from app.schemas import ProgressResponse
from app.api.v1.endpoints.passport import GUEST_USER_ID
from app.services.progress import build_progress_series

router = APIRouter()


@router.get("/{user_id}", response_model=ProgressResponse)
def get_progress(user_id: uuid.UUID, db: Session = Depends(get_db)):
    query = db.query(ProgressSnapshot)
    if user_id == GUEST_USER_ID:
        # Pre-auth scans are stored with a null user_id; the guest id represents them.
        query = query.filter(ProgressSnapshot.user_id.is_(None))
    else:
        query = query.filter(ProgressSnapshot.user_id == user_id)
    snapshots = query.all()
    result = build_progress_series(snapshots)
    return ProgressResponse(**result)