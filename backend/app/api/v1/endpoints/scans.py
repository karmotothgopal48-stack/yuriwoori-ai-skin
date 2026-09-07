from app.db.models import ProgressSnapshot
from app.services.ingredient_compatibility import check_routine_compatibility
from app.schemas import CompatibilityFlagResponse
from app.db.models import Routine, RoutineStep, TimeOfDay
from app.services.routine_builder import build_routine
from app.schemas import RoutineResponse, RoutineStepResponse

from app.db.models import Recommendation
from app.services.recommendation import build_recommendations
from app.schemas import RecommendationResponse

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
                first_snapshot = (
        db.query(ProgressSnapshot)
        .filter(ProgressSnapshot.user_id == scan.user_id)
        .order_by(ProgressSnapshot.created_at)
        .first()
    )
    day_offset = (profile.created_at - first_snapshot.created_at).days if first_snapshot else 0

    db.add(
        ProgressSnapshot(
            user_id=scan.user_id,
            scan_id=scan_id,
            day_offset=day_offset,
            hydration=profile.hydration,
            oiliness=profile.oiliness,
            texture=profile.texture,
            redness=profile.redness,
            pigmentation=profile.pigmentation,
            blemish_index=profile.blemish_index,
        )
    )

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
@router.get("/{scan_id}/recommendations", response_model=list[RecommendationResponse])
def get_recommendations(scan_id: uuid.UUID, db: Session = Depends(get_db)):
    profile = db.query(SkinProfile).filter(SkinProfile.scan_id == scan_id).first()
    if not profile:
        raise HTTPException(status_code=400, detail="Scan has no analyzed profile yet")

    existing = db.query(Recommendation).filter(Recommendation.skin_profile_id == profile.id).all()
    if existing:
        return [
            RecommendationResponse(
                product_id=r.product_id,
                name=r.product.name,
                price=r.product.price,
                image_url=r.product.image_url,
                match_reason=r.match_reason,
                rank=r.rank,
            )
            for r in sorted(existing, key=lambda r: r.rank)
        ]

    results = build_recommendations(db, profile)
    response = []
    for rank, item in enumerate(results, start=1):
        rec = Recommendation(
            user_id=profile.user_id,
            skin_profile_id=profile.id,
            product_id=item["product"].id,
            rank=rank,
            match_reason=item["match_reason"],
        )
        db.add(rec)
        response.append(
            RecommendationResponse(
                product_id=item["product"].id,
                name=item["product"].name,
                price=item["product"].price,
                image_url=item["product"].image_url,
                match_reason=item["match_reason"],
                rank=rank,
            )
        )
    db.commit()
    return response
@router.get("/{scan_id}/routine", response_model=RoutineResponse)
def get_routine(scan_id: uuid.UUID, db: Session = Depends(get_db)):
    profile = db.query(SkinProfile).filter(SkinProfile.scan_id == scan_id).first()
    if not profile:
        raise HTTPException(status_code=400, detail="Scan has no analyzed profile yet")

    existing_routine = db.query(Routine).filter(Routine.skin_profile_id == profile.id).first()
    if existing_routine:
        am_steps = [s for s in existing_routine.steps if s.time_of_day == TimeOfDay.AM]
        pm_steps = [s for s in existing_routine.steps if s.time_of_day == TimeOfDay.PM]

        def to_response(steps):
            return [
                RoutineStepResponse(
                    step_order=s.step_order,
                    product_id=s.product_id,
                    product_name=s.product.name,
                    image_url=s.product.image_url,
                    reason=s.reason,
                )
                for s in sorted(steps, key=lambda s: s.step_order)
            ]

        return RoutineResponse(AM=to_response(am_steps), PM=to_response(pm_steps))

    built = build_routine(db, profile)
    routine = Routine(user_id=profile.user_id, skin_profile_id=profile.id)
    db.add(routine)
    db.flush()

    def persist(period: str, picks: list[dict]):
        for pick in picks:
            db.add(
                RoutineStep(
                    routine_id=routine.id,
                    time_of_day=TimeOfDay[period],
                    step_order=pick["step_order"],
                    product_id=pick["product"].id,
                    reason=pick["reason"],
                    concern_addressed=pick["step"],
                )
            )

    persist("AM", built["AM"])
    persist("PM", built["PM"])
    db.commit()

    def to_response_new(picks):
        return [
            RoutineStepResponse(
                step_order=p["step_order"],
                product_id=p["product"].id,
                product_name=p["product"].name,
                image_url=p["product"].image_url,
                reason=p["reason"],
            )
            for p in picks
        ]

    return RoutineResponse(AM=to_response_new(built["AM"]), PM=to_response_new(built["PM"]))
@router.get("/{scan_id}/compatibility", response_model=list[CompatibilityFlagResponse])
def check_compatibility(scan_id: uuid.UUID, db: Session = Depends(get_db)):
    profile = db.query(SkinProfile).filter(SkinProfile.scan_id == scan_id).first()
    if not profile:
        raise HTTPException(status_code=400, detail="Scan has no analyzed profile yet")

    routine = db.query(Routine).filter(Routine.skin_profile_id == profile.id).first()
    if not routine:
        raise HTTPException(status_code=400, detail="No routine built yet for this scan")

    product_ids = list({s.product_id for s in routine.steps})
    flags = check_routine_compatibility(db, product_ids)

    result = []
    for f in flags:
        product_a = db.get(Product, f["product_id_a"])
        product_b = db.get(Product, f["product_id_b"])
        result.append(
            CompatibilityFlagResponse(
                product_a_name=product_a.name,
                product_b_name=product_b.name,
                relationship_type=f["relationship_type"],
                explanation=f["explanation"],
            )
        )
    return result
