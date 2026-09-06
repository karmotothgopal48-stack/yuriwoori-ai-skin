class SkinProfileResponse(BaseModel):
    scan_id: uuid.UUID
    skin_type: str | None
    hydration: float | None
    oiliness: float | None
    texture: float | None
    redness: float | None
    pigmentation: float | None
    blemish_index: float | None
    pore_visibility: float | None
    overall_score: float | None
    model_version: str | None
    from datetime import datetime


class PassportResponse(BaseModel):
    skin_type: str | None
    top_concerns: list[str]
    overall_score: float | None
    last_scanned_at: datetime | None