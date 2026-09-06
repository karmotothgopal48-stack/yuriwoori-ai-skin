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
    from datetime import datetime


class PassportResponse(BaseModel):
    skin_type: str | None
    top_concerns: list[str]
    overall_score: float | None
    last_scanned_at: datetime | None
    class ProductResponse(BaseModel):
    id: uuid.UUID
    name: str
    price: float | None
    currency: str
    image_url: str | None
    category: str | None
    routine_step: str | None
    description: str | None
    product_url: str | None

    class Config:
        from_attributes = True