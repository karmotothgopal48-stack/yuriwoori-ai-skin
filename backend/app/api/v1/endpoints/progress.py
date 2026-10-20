import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import current_user
from app.db.session import get_db
from app.db.models import ProgressSnapshot, User
from app.schemas import ProgressResponse
from app.services.progress import build_progress_series

router = APIRouter()


@router.get("/{user_id}", response_model=ProgressResponse)
def get_progress(user_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    # Signed-up users can only read their own progress (pre-signup guest snapshots are not exposed).
    if user_id != user.id:
        raise HTTPException(status_code=403, detail="You can only view your own progress.")
    snapshots = db.query(ProgressSnapshot).filter(ProgressSnapshot.user_id == user_id).all()
    result = build_progress_series(snapshots)
    return ProgressResponse(**result)
