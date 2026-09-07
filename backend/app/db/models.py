from pgvector.sqlalchemy import Vector
import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, Float, Integer, DateTime, ForeignKey, ARRAY, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.db.session import Base


class ScanStatus(str, enum.Enum):
    pending = "pending"
    quality_failed = "quality_failed"
    analyzed = "analyzed"
    error = "error"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    marketing_opt_in: Mapped[bool] = mapped_column(Boolean, default=False)


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    device_fingerprint: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    device_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("devices.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    status: Mapped[ScanStatus] = mapped_column(Enum(ScanStatus), default=ScanStatus.pending)
    angles_captured: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)

    frames: Mapped[list["ScanFrame"]] = relationship(back_populates="scan")


class ScanFrame(Base):
    __tablename__ = "scan_frames"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scans.id"))
    angle: Mapped[str] = mapped_column(String)
    storage_key: Mapped[str] = mapped_column(String)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    blur_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    lighting_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    face_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    scan: Mapped["Scan"] = relationship(back_populates="frames")


class SkinProfile(Base):
    __tablename__ = "skin_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scans.id"))
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    skin_type: Mapped[str | None] = mapped_column(String, nullable=True)
    hydration: Mapped[float | None] = mapped_column(Float, nullable=True)
    oiliness: Mapped[float | None] = mapped_column(Float, nullable=True)
    texture: Mapped[float | None] = mapped_column(Float, nullable=True)
    redness: Mapped[float | None] = mapped_column(Float, nullable=True)
    pigmentation: Mapped[float | None] = mapped_column(Float, nullable=True)
    blemish_index: Mapped[float | None] = mapped_column(Float, nullable=True)
    pore_visibility: Mapped[float | None] = mapped_column(Float, nullable=True)
    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_version: Mapped[str | None] = mapped_column(String, nullable=True)


class SkinPassport(Base):
    __tablename__ = "skin_passports"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    latest_scan_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("scans.id"), nullable=True)
    skin_type: Mapped[str | None] = mapped_column(String, nullable=True)
    top_concerns: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_scanned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
class Product(Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    shopify_product_id: Mapped[str] = mapped_column(
        String, unique=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String, default="INR")
    image_url: Mapped[str | None] = mapped_column(String, nullable=True)
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    routine_step: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    product_url: Mapped[str | None] = mapped_column(String, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    concern_tags: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default="{}"
    )


class Ingredient(Base):
    __tablename__ = "ingredients"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    inci_name: Mapped[str | None] = mapped_column(String, nullable=True)
    function: Mapped[str | None] = mapped_column(String, nullable=True)
    concern_tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)


class ProductIngredient(Base):
    __tablename__ = "product_ingredients"

    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"), primary_key=True)
    ingredient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ingredients.id"), primary_key=True)
    concentration_note: Mapped[str | None] = mapped_column(String, nullable=True)


class IngredientInteractionType(str, enum.Enum):
    synergistic = "synergistic"
    caution = "caution"
    avoid_same_routine = "avoid_same_routine"


class IngredientInteraction(Base):
    __tablename__ = "ingredient_interactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ingredient_a_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ingredients.id"))
    ingredient_b_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ingredients.id"))
    relationship_type: Mapped[IngredientInteractionType] = mapped_column(Enum(IngredientInteractionType))
    explanation: Mapped[str | None] = mapped_column(String, nullable=True)


class TimeOfDay(str, enum.Enum):
    AM = "AM"
    PM = "PM"


class Routine(Base):
    __tablename__ = "routines"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    skin_profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("skin_profiles.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    steps: Mapped[list["RoutineStep"]] = relationship(back_populates="routine")


class RoutineStep(Base):
    __tablename__ = "routine_steps"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    routine_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("routines.id"))
    time_of_day: Mapped[TimeOfDay] = mapped_column(Enum(TimeOfDay))
    step_order: Mapped[int] = mapped_column(Integer)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"))
    reason: Mapped[str] = mapped_column(String)
    concern_addressed: Mapped[str | None] = mapped_column(String, nullable=True)

    routine: Mapped["Routine"] = relationship(back_populates="steps")
    product: Mapped["Product"] = relationship()


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    skin_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("skin_profiles.id")
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id")
    )
    rank: Mapped[int] = mapped_column(Integer)
    match_reason: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )


class ProductEmbedding(Base):
    __tablename__ = "product_embeddings"

    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"), primary_key=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(384))
    source_text: Mapped[str] = mapped_column(String)


class IngredientEmbedding(Base):
    __tablename__ = "ingredient_embeddings"

    ingredient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ingredients.id"), primary_key=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(384))
    source_text: Mapped[str] = mapped_column(String)


class CoachConversation(Base):
    __tablename__ = "coach_conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    messages: Mapped[list["CoachMessage"]] = relationship(back_populates="conversation")


class CoachRole(str, enum.Enum):
    user = "user"
    assistant = "assistant"


class CoachMessage(Base):
    __tablename__ = "coach_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("coach_conversations.id"))
    role: Mapped[CoachRole] = mapped_column(Enum(CoachRole))
    content: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    cited_product_ids: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)

    conversation: Mapped["CoachConversation"] = relationship(back_populates="messages")
