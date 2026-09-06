import os
import base64
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Scan, ScanFrame, SkinProfile, ScanStatus
from app.schemas import (
    ScanCreateResponse,
    FrameUploadRequest,
    FrameQualityResponse,
    SkinProfileResponse,
)
from app.services.cv_quality import analyze_frame
from app.services.skin_analysis import analyze_skin_profile

router = APIRouter()
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "uploads")


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

    scan_folder = os.path.join(UPLOAD_DIR, str(scan_id))
    os.makedirs(scan_folder, exist_ok=True)
    file_path = os.path.join(scan_folder, f"{payload.angle}.jpg")

    raw_b64 = payload.image_base64.split(",", 1)[-1]
    with open(file_path, "wb") as f:
        f.write(base64.b64decode(raw_b64))

    frame = ScanFrame(
        scan_id=scan_id,
        angle=payload.angle,
        storage_key=file_path,
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


@router.post("/{scan_id}/analyze", response_model=SkinProfileResponse)
def analyze_scan(scan_id: uuid.UUID, db: Session = Depends(get_db)):
    scan = db.get(Scan, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    if len(scan.angles_captured) < 1:
        raise HTTPException(status_code=400, detail="No passed frames to analyze yet")

    frame_paths = [
        os.path.join(UPLOAD_DIR, str(scan_id), f"{angle}.jpg") for angle in scan.angles_captured
    ]
    frame_paths = [p for p in frame_paths if os.path.exists(p)]

    metrics = analyze_skin_profile(frame_paths)

    profile = SkinProfile(
        scan_id=scan_id,
        user_id=scan.user_id,
        skin_type=metrics["skin_type"],
        hydration=metrics["hydration"],
        oiliness=metrics["oiliness"],
        texture=metrics["texture"],
        redness=metrics["redness"],
        pigmentation=metrics["pigmentation"],
        blemish_index=metrics["blemish_index"],
        pore_visibility=metrics["pore_visibility"],
        overall_score=metrics["overall_score"],
        model_version="heuristic-cv-v0",
    )
    db.add(profile)
    scan.status = ScanStatus.analyzed
    db.commit()
    db.refresh(profile)

    return SkinProfileResponse(
        scan_id=scan_id,
        skin_type=profile.skin_type,
        hydration=profile.hydration,
        oiliness=profile.oiliness,
        texture=profile.texture,
        redness=profile.redness,
        pigmentation=profile.pigmentation,
        blemish_index=profile.blemish_index,
        pore_visibility=profile.pore_visibility,
        overall_score=profile.overall_score,
        model_version=profile.model_version,
    )


@router.get("/{scan_id}", response_model=SkinProfileResponse)
def get_scan_profile(scan_id: uuid.UUID, db: Session = Depends(get_db)):
    scan = db.get(Scan, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    profile = db.query(SkinProfile).filter(SkinProfile.scan_id == scan_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Scan not analyzed yet")

    return SkinProfileResponse(
        scan_id=scan_id,
        skin_type=profile.skin_type,
        hydration=profile.hydration,
        oiliness=profile.oiliness,
        texture=profile.texture,
        redness=profile.redness,
        pigmentation=profile.pigmentation,
        blemish_index=profile.blemish_index,
        pore_visibility=profile.pore_visibility,
        overall_score=profile.overall_score,
        model_version=profile.model_version,
    )