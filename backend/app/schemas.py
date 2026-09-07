import uuid
from datetime import datetime

from pydantic import BaseModel


class ScanCreateResponse(BaseModel):
    scan_id: uuid.UUID


class FrameUploadRequest(BaseModel):
    angle: str
    image_base64: str


class FrameQualityResponse(BaseModel):
    frame_id: uuid.UUID
    angle: str
    blur_score: float
    lighting_score: float
    quality_score: float
    passed: bool


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

class RecommendationResponse(BaseModel):
    product_id: uuid.UUID
    name: str
    price: float | None
    image_url: str | None
    match_reason: str
    rank: intclass RoutineStepResponse(BaseModel):
    step_order: int
    product_id: uuid.UUID
    product_name: str
    image_url: str | None
    reason: str


class RoutineResponse(BaseModel):
    AM: list[RoutineStepResponse]
    PM: list[RoutineStepResponse]
    class CoachMessageRequest(BaseModel):
    conversation_id: uuid.UUID | None = None
    message: str


class CoachMessageResponse(BaseModel):
    conversation_id: uuid.UUID
    reply: str
    cited_product_ids: list[str]
    class CompatibilityFlagResponse(BaseModel):
    product_a_name: str
    product_b_name: str
    relationship_type: str
    explanation: str