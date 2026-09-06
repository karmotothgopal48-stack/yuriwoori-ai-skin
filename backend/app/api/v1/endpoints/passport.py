import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Scan, SkinProfile, SkinPassport
from app.schemas import PassportResponse

router = APIRouter()


@router.post("/save/{scan_id}", response_model=PassportResponse)
def save_to_passport(scan_id: uuid.UUID, db: Session = Depends(get_db)):
    scan = db.get(Scan, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    profile = db.query(SkinProfile).filter(SkinProfile.scan_id == scan_id).first()
    if not profile:
        raise HTTPException(status_code=400, detail="Scan has no analyzed profile yet")

    concerns = []
    if (profile.redness or 0) > 40:
        concerns.append("redness")
    if (profile.pigmentation or 0) > 40:
        concerns.append("pigmentation")
    if (profile.blemish_index or 0) > 40:
        concerns.append("blemishes")
    if (profile.pore_visibility or 0) > 40:
        concerns.append("pore visibility")
    if not concerns:
        concerns = ["balanced skin"]

    # scan.user_id is null pre-auth (Step 20) — using a fixed dev placeholder for now
    passport = db.get(SkinPassport, scan.user_id) if scan.user_id else None
    if not passport:
        passport = SkinPassport(user_id=scan.user_id or uuid.UUID(int=0))
        db.add(passport)

    passport.latest_scan_id = scan_id
    passport.skin_type = profile.skin_type
    passport.top_concerns = concerns[:3]
    passport.overall_score = profile.overall_score
    passport.last_scanned_at = profile.created_at

    db.commit()
    db.refresh(passport)

    return PassportResponse(
        skin_type=passport.skin_type,
        top_concerns=passport.top_concerns,
        overall_score=passport.overall_score,
        last_scanned_at=passport.last_scanned_at,
    )


@router.get("", response_model=PassportResponse)
def get_passport(db: Session = Depends(get_db)):
    # Dev placeholder until Step 20 real auth ties this to the logged-in user_id
    passport = db.get(SkinPassport, uuid.UUID(int=0))
    if not passport:
        raise HTTPException(status_code=404, detail="No passport yet — scan and save first")

    return PassportResponse(
        skin_type=passport.skin_type,
        top_concerns=passport.top_concerns,
        overall_score=passport.overall_score,
        last_scanned_at=passport.last_scanned_at,
    )
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Scan, SkinProfile, SkinPassport
from app.schemas import PassportResponse

router = APIRouter()


@router.post("/save/{scan_id}", response_model=PassportResponse)
def save_to_passport(scan_id: uuid.UUID, db: Session = Depends(get_db)):
    scan = db.get(Scan, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    profile = db.query(SkinProfile).filter(SkinProfile.scan_id == scan_id).first()
    if not profile:
        raise HTTPException(status_code=400, detail="Scan has no analyzed profile yet")

    concerns = []
    if (profile.redness or 0) > 40:
        concerns.append("redness")
    if (profile.pigmentation or 0) > 40:
        concerns.append("pigmentation")
    if (profile.blemish_index or 0) > 40:
        concerns.append("blemishes")
    if (profile.pore_visibility or 0) > 40:
        concerns.append("pore visibility")
    if not concerns:
        concerns = ["balanced skin"]

    # scan.user_id is null pre-auth (Step 20) — using a fixed dev placeholder for now
    passport = db.get(SkinPassport, scan.user_id) if scan.user_id else None
    if not passport:
        passport = SkinPassport(user_id=scan.user_id or uuid.UUID(int=0))
        db.add(passport)

    passport.latest_scan_id = scan_id
    passport.skin_type = profile.skin_type
    passport.top_concerns = concerns[:3]
    passport.overall_score = profile.overall_score
    passport.last_scanned_at = profile.created_at

    db.commit()
    db.refresh(passport)

    return PassportResponse(
        skin_type=passport.skin_type,
        top_concerns=passport.top_concerns,
        overall_score=passport.overall_score,
        last_scanned_at=passport.last_scanned_at,
    )


@router.get("", response_model=PassportResponse)
def get_passport(db: Session = Depends(get_db)):
    # Dev placeholder until Step 20 real auth ties this to the logged-in user_id
    passport = db.get(SkinPassport, uuid.UUID(int=0))
    if not passport:
        raise HTTPException(status_code=404, detail="No passport yet — scan and save first")

    return PassportResponse(
        skin_type=passport.skin_type,
        top_concerns=passport.top_concerns,
        overall_score=passport.overall_score,
        last_scanned_at=passport.last_scanned_at,
    )