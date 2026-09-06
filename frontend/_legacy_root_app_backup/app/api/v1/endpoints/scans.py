import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Scan, ScanFrame, ScanStatus
from app.schemas import ScanCreateResponse, FrameUploadRequest, FrameQualityResponse
from app.services.cv_quality import analyze_frame

router = APIRouter()


@router.post("", response_model=ScanCreateResponse)
def create_scan(db: Session = Depends(get_db)):
    scan = Scan(status=ScanStatus.pending, angles_captured=[])
    db.add(scan)
    db.commit()
    db.refresh(scan)
    return ScanCreateResponse(scan_id=scan.id)


@router.post("/{scan_id}/frames", response_model=FrameQualityResponse)
def upload_frame(scan_id: uuid.UUID, payload: FrameUploadRequest, db: Session = Depends(get_db)):
    scan = db.get(Scan, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    result = analyze_frame(payload.image_base64)

    frame = ScanFrame(
        scan_id=scan_id,
        angle=payload.angle,
        storage_key=f"local/{scan_id}/{payload.angle}.jpg",  # real object storage arrives in a later step
        quality_score=result["quality_score"],
        blur_score=result["blur_score"],
        lighting_score=result["lighting_score"],
        face_confidence=1.0,
    )
    db.add(frame)

    if result["passed"] and payload.angle not in scan.angles_captured:
        scan.angles_captured = [*scan.angles_captured, payload.angle]

    db.commit()
    db.refresh(frame)

    return FrameQualityResponse(
        frame_id=frame.id,
        angle=frame.angle,
        blur_score=result["blur_score"],
        lighting_score=result["lighting_score"],
        quality_score=result["quality_score"],
        passed=result["passed"],
    )