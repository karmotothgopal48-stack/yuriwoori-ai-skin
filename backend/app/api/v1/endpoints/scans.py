from app.db.models import ProgressSnapshot
from app.services.ingredient_compatibility import check_routine_compatibility
from app.schemas import CompatibilityFlagResponse
from app.services.routine_builder import build_maintenance_routine, build_routine
from app.schemas import RoutineResponse, RoutineStepResponse

from app.services.benchmark import BENCHMARK_VERSION, benchmark_for
from app.services.product_detail import parse_benefits
from app.services.engagement import snapshot_recommendations
from app.services.live_catalogue import get_catalogue
from app.services.product_records import ensure_product_rows, latest_routine, save_routine_if_changed
from app.services.recommendation import active_concerns, build_recommendations, profile_metrics
from app.schemas import RecommendationResponse

import base64
import binascii
import uuid
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.security import client_ip, current_user
from app.db.session import get_db
from app.db.models import Scan, ScanFrame, SkinProfile, ScanStatus, Product, User
from app.schemas import (
    AnalyzeRequest,
    ScanCreateResponse,
    FrameUploadRequest,
    FrameQualityResponse,
    SkinProfileResponse,
)
from app.services import customer_sheet, delivery
from app.services.cv_quality import analyze_frame
from app.services.skin_analysis import analyze_skin_profile, body_part_of, missing_measurements, AnalysisUnavailableError

router = APIRouter()

# scan_frames.storage_key for frames recorded since photos stopped being stored (the column is required).
PHOTO_NOT_STORED = "not-stored"


def _decode_photo(image_base64: str) -> bytes:
    """The photo's bytes, in memory only (400 if it isn't valid base64)."""
    try:
        return base64.b64decode(image_base64.split(",", 1)[-1])
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=400, detail="image_base64 is not valid base64")


def _profile_response(profile: SkinProfile, body_part: str) -> SkinProfileResponse:
    benchmark = benchmark_for(body_part)
    return SkinProfileResponse(
        benchmark=benchmark,
        benchmark_version=BENCHMARK_VERSION if benchmark else None,
        scan_id=profile.scan_id,
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


def _own_scan(db: Session, scan_id: uuid.UUID, user: User) -> Scan:
    """The scan, only if it belongs to the signed-in user (404 / 403 otherwise)."""
    scan = db.get(Scan, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    if scan.user_id != user.id:
        raise HTTPException(status_code=403, detail="This scan belongs to another user.")
    return scan


@router.post("", response_model=ScanCreateResponse)
def create_scan(request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    # Signup is required: every analysis is linked to a user, with the server-side request IP.
    scan = Scan(status=ScanStatus.pending, angles_captured=[], user_id=user.id, client_ip=client_ip(request))
    db.add(scan)
    db.commit()
    db.refresh(scan)
    return ScanCreateResponse(scan_id=scan.id)


@router.post("/{scan_id}/frames", response_model=FrameQualityResponse)
def upload_frame(scan_id: uuid.UUID, payload: FrameUploadRequest, user: User = Depends(current_user), db: Session = Depends(get_db)):
    scan = _own_scan(db, scan_id, user)

    result = analyze_frame(payload.image_base64)

    _decode_photo(payload.image_base64)  # 400 if it isn't valid base64

    # The photo itself is NOT stored (no disk, database or S3): only its quality scores are recorded.
    # The analyze request sends the photo again and it is processed in memory there.
    frame = ScanFrame(
        scan_id=scan_id,
        angle=payload.angle,
        storage_key=PHOTO_NOT_STORED,
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
def analyze_scan(scan_id: uuid.UUID, background: BackgroundTasks, payload: AnalyzeRequest | None = None,
                 user: User = Depends(current_user), db: Session = Depends(get_db)):
    scan = _own_scan(db, scan_id, user)

    if len(scan.angles_captured) < 1:
        raise HTTPException(status_code=400, detail="No passed frames to analyze yet")

    # The capture screen identifies the body part and uploads it as the frame angle ("hand", or
    # "front" for a face); the matching detector then verifies it, so a photo without that body
    # part is rejected with 422 instead of being measured.
    body_part = body_part_of(scan.angles_captured)

    # Analyzing the same scan twice must not create duplicate profiles/snapshots.
    existing_profile = db.query(SkinProfile).filter(SkinProfile.scan_id == scan_id).first()
    if existing_profile:
        return _profile_response(existing_profile, body_part)

    # Photos are never stored, so the photo comes with this request. It must be one that passed this
    # scan's quality check (same angle, same check), and it is analysed in memory, then discarded.
    if payload is None:
        raise HTTPException(status_code=400, detail="Please send the photo with the analysis request (photos are not stored).")
    if payload.angle not in scan.angles_captured or (body_part == "hand" and payload.angle != "hand"):
        raise HTTPException(status_code=400, detail="This photo didn't pass the quality check for this scan.")
    if not analyze_frame(payload.image_base64)["passed"]:
        raise HTTPException(status_code=400, detail="This photo didn't pass the quality check for this scan.")
    try:
        metrics = analyze_skin_profile([_decode_photo(payload.image_base64)], body_part)
    except AnalysisUnavailableError as exc:
        raise HTTPException(status_code=503, detail=f"Skin analysis engine is unavailable: {exc}")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

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
        model_version="heuristic-cv-v0-hand" if body_part == "hand" else "heuristic-cv-v0",
    )
    db.add(profile)
    db.flush()  # populates profile.created_at, needed for day_offset below
    scan.status = ScanStatus.analyzed
    first_snapshot = (
        db.query(ProgressSnapshot)
        .filter(ProgressSnapshot.user_id == scan.user_id)
        .order_by(ProgressSnapshot.created_at)
        .first()
    )
    day_offset = (profile.created_at - first_snapshot.created_at).days if first_snapshot else 0

    # Progress follows the face over time. A hand is a different skin area, so a hand scan is not
    # added to that series (comparing it with face scans would report false "changes").
    if body_part == "face":
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

    customer_sheet.mark_changed(db, user)  # the workbook's Analysis Status (no measurements are exported)
    db.commit()
    db.refresh(profile)
    background.add_task(customer_sheet.run_in_background)
    # the report is made and sent from here (to the verified contact only), even if the browser closes now
    background.add_task(delivery.report_after_analysis, scan.id, user.id)

    return _profile_response(profile, body_part)


@router.get("/{scan_id}", response_model=SkinProfileResponse)
def get_scan_profile(scan_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    scan = _own_scan(db, scan_id, user)

    profile = db.query(SkinProfile).filter(SkinProfile.scan_id == scan_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Scan not analyzed yet")

    return _profile_response(profile, body_part_of(scan.angles_captured))

@router.get("/{scan_id}/recommendations", response_model=list[RecommendationResponse])
def get_recommendations(scan_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Ranked products for this scan, chosen from the live store catalogue on every request."""
    scan = _own_scan(db, scan_id, user)
    profile = db.query(SkinProfile).filter(SkinProfile.scan_id == scan_id).first()
    if not profile:
        raise HTTPException(status_code=400, detail="Scan has no analyzed profile yet")

    results = build_recommendations(profile, get_catalogue().products, body_part=body_part_of(scan.angles_captured))
    rows = ensure_product_rows(db, [item["product"] for item in results])
    snapshot_recommendations(db, profile, results)  # first-served ranking, kept for the admin report (commits)
    return [
        RecommendationResponse(
            product_id=rows[item["product"].handle].id,
            name=item["product"].name,
            price=item["product"].price,
            image_url=item["product"].image_url,
            match_reason=item["match_reason"],
            rank=rank,
        )
        for rank, item in enumerate(results, start=1)
    ]


def _routine_response(built: dict, rows: dict, catalogue) -> RoutineResponse:
    """A routine of live products: names, images, prices and availability are the store's current ones."""
    def steps(picks):
        return [
            RoutineStepResponse(
                step_order=p["step_order"],
                product_id=rows[p["product"].handle].id,
                product_name=p["product"].name,
                image_url=p["product"].image_url,
                reason=p["reason"],
                handle=p["product"].handle,
                routine_step=p["product"].routine_step,
                product_url=p["product"].product_url,
                price=p["product"].price,
                available=p["product"].available,
                variant_id=p["product"].variant_id,
                how_to_use=p["product"].how_to_use,
                key_benefit=p["product"].key_benefit,
                benefits=parse_benefits(p["product"].benefits_raw),
                ingredients=list(p["product"].ingredients),
            )
            for p in picks
        ]

    return RoutineResponse(AM=steps(built["AM"]), PM=steps(built["PM"]),
                           catalogue_fetched_at=catalogue.fetched_at, catalogue_stale=catalogue.stale)


@router.get("/{scan_id}/routine", response_model=RoutineResponse)
def get_routine(scan_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """The scan's AM/PM routine, rebuilt from the live store catalogue on every request. The result is saved
    (a new version only when it changed), but a saved routine never replaces the live one."""
    scan = _own_scan(db, scan_id, user)
    profile = db.query(SkinProfile).filter(SkinProfile.scan_id == scan_id).first()
    if not profile:
        raise HTTPException(status_code=400, detail="Scan has no analyzed profile yet")

    catalogue = get_catalogue()
    built = build_routine(profile, catalogue.products, body_part_of(scan.angles_captured))
    rows = ensure_product_rows(db, [p["product"] for period in ("AM", "PM") for p in built[period]])
    save_routine_if_changed(db, profile, built, rows)
    db.commit()
    return _routine_response(built, rows, catalogue)


@router.get("/{scan_id}/maintenance-routine", response_model=RoutineResponse)
def get_maintenance_routine(scan_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """A simple care routine for a scan whose analysis found no concern (analysis_status "balanced").
    Refused for a scan with concerns (it has its personalized routine) or an incomplete analysis.
    Built from the live catalogue on request and not saved, so the stored routine of every scan stays the targeted one."""
    scan = _own_scan(db, scan_id, user)
    profile = db.query(SkinProfile).filter(SkinProfile.scan_id == scan_id).first()
    if not profile:
        raise HTTPException(status_code=400, detail="Scan has no analyzed profile yet")
    body_part = body_part_of(scan.angles_captured)
    missing = missing_measurements(profile, body_part)
    if missing:
        raise HTTPException(status_code=422, detail=f"This analysis is incomplete (missing: {', '.join(missing)}). Please scan again.")
    if active_concerns(profile_metrics(profile)):
        raise HTTPException(status_code=409, detail="This scan has skin concerns; its personalized routine applies, not a maintenance routine.")

    catalogue = get_catalogue()
    built = build_maintenance_routine(catalogue.products, body_part)
    rows = ensure_product_rows(db, [p["product"] for period in ("AM", "PM") for p in built[period]])
    db.commit()
    return _routine_response(built, rows, catalogue)


@router.get("/{scan_id}/compatibility", response_model=list[CompatibilityFlagResponse])
def check_compatibility(scan_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _own_scan(db, scan_id, user)
    profile = db.query(SkinProfile).filter(SkinProfile.scan_id == scan_id).first()
    if not profile:
        raise HTTPException(status_code=400, detail="Scan has no analyzed profile yet")

    routine = latest_routine(db, profile.id)  # the version last built from the live catalogue
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
