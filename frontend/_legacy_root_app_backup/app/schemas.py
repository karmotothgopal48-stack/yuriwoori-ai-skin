from pydantic import BaseModel
import uuid


class ScanCreateResponse(BaseModel):
    scan_id: uuid.UUID


class FrameUploadRequest(BaseModel):
    angle: str  # "front" | "left" | "right"
    image_base64: str


class FrameQualityResponse(BaseModel):
    frame_id: uuid.UUID
    angle: str
    blur_score: float
    lighting_score: float
    quality_score: float
    passed: bool