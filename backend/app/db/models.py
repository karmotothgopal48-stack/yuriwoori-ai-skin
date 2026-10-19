from pgvector.sqlalchemy import Vector
import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, Float, Integer, DateTime, ForeignKey, ARRAY, Enum, Index, event, inspect, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
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
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    marketing_opt_in: Mapped[bool] = mapped_column(Boolean, default=False)
    # When the user accepted the privacy notice at signup, and which version of it
    consented_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    consent_version: Mapped[str | None] = mapped_column(String, nullable=True)
    # WhatsApp number in international format (+<country><number>), entered at signup
    whatsapp: Mapped[str | None] = mapped_column(String, nullable=True)
    # When the user proved the email / WhatsApp number is theirs with a one-time code (results are only sent then)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    whatsapp_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # When the user agreed to have their skin-analysis report sent to that email / WhatsApp number
    report_consent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ContactVerification(Base):
    """A one-time code sent to the user's own email or WhatsApp number (only its HMAC is stored)."""
    __tablename__ = "contact_verifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    channel: Mapped[str] = mapped_column(String)  # "email" | "whatsapp"
    destination: Mapped[str] = mapped_column(String)
    code_hash: Mapped[str] = mapped_column(String)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Report(Base):
    """A customer's skin-analysis report: the record that it was made (for which scan and customer), its secret
    link (token stored only as a SHA-256 hash; expires, can be revoked) and its deliveries. The report itself is
    generated in memory from the saved analysis whenever it is sent or opened (services/reports.content_for) and
    is never stored: content is NULL for every report made since then. Reports made before keep their stored
    content exactly as it is (preserved by the owner's decision); it is never read, changed or cleared by the app.
    Both rules are enforced below, on every insert and update."""
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scans.id"), unique=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    content: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True), nullable=True)  # older reports only; never read or written
    token_hash: Mapped[str] = mapped_column(String, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_viewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class StoredReportContent(ValueError):
    """Raised when code tries to store new report content, or to change a stored report's content."""


@event.listens_for(Report, "before_insert")
def _new_reports_store_no_content(mapper, connection, report):
    if report.content is not None:
        raise StoredReportContent("Report content is generated in memory and is never stored.")


@event.listens_for(Report, "before_update")
def _stored_report_content_never_changes(mapper, connection, report):
    if inspect(report).attrs.content.history.has_changes():
        raise StoredReportContent("A report's stored content is preserved as it is and is never changed.")


class ResultDelivery(Base):
    """Sending a report on one channel; retries update this row (one per report and channel), so a
    customer never gets duplicates. Status:
      pending   - waiting to be sent (e.g. the channel isn't configured or the contact isn't confirmed yet)
      sending   - handed to the provider right now
      accepted  - WhatsApp's Cloud API accepted it; WhatsApp hasn't confirmed sending yet (webhook)
      sent      - the provider confirmed: SMTP server accepted the email / WhatsApp webhook reported "sent"
      delivered - WhatsApp webhook reported delivered (or read)
      failed    - the provider refused or failed; safe to retry"""
    __tablename__ = "result_deliveries"
    __table_args__ = (
        Index("uq_result_deliveries_report_channel", "report_id", "channel", unique=True,
              postgresql_where=text("report_id IS NOT NULL")),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    scan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scans.id"), index=True)
    report_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("reports.id"), nullable=True)
    channel: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    provider_message_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # The customer's email / WhatsApp number when the report was made (by their own session). The report is only
    # ever sent there: if the account's contact changes later, this report is not sent to the new contact.
    destination: Mapped[str | None] = mapped_column(String, nullable=True)
    # A report PDF uploaded to WhatsApp's media store for this message: kept only until it is deleted there.
    provider_media_id: Mapped[str | None] = mapped_column(String, nullable=True)


class CustomerSheetSync(Base):
    """Copying one customer's row to the team's follow-up spreadsheet (app/services/customer_sheet.py). PostgreSQL
    is the source of truth: a change bumps wanted_version, and the row counts as written only once the write of that
    version was read back from the spreadsheet (synced_version). Status:
      pending - waiting to be written (new, changed, or Excel sync not enabled yet)
      syncing - claimed by a worker right now (a stale claim is taken over after a few minutes)
      synced  - Graph confirmed the latest version
      failed  - the spreadsheet service refused or was unreachable; retried after next_attempt_at
      not_eligible - the customer no longer qualifies (not written)
    last_error holds only a short error code, never personal data or Graph's response text."""
    __tablename__ = "customer_sheet_sync"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    status: Mapped[str] = mapped_column(String, default="pending", index=True)
    wanted_version: Mapped[int] = mapped_column(Integer, default=1)
    claimed_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    synced_version: Mapped[int] = mapped_column(Integer, default=0)
    attempts: Mapped[int] = mapped_column(Integer, default=0)  # consecutive failures
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(String, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


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
    client_ip: Mapped[str | None] = mapped_column(String, nullable=True)  # server-side request IP at scan start

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
    shopify_variant_id: Mapped[str | None] = mapped_column(String, nullable=True)
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
    chips: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default="{}"
    )
    benefits_raw: Mapped[str | None] = mapped_column(String, nullable=True)


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

    # ORM link only (no schema change); used by reports and by GET /scans/{id}/recommendations
    product: Mapped["Product"] = relationship()


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

class ProgressSnapshot(Base):
    __tablename__ = "progress_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    scan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scans.id"))
    day_offset: Mapped[int] = mapped_column(Integer)
    hydration: Mapped[float | None] = mapped_column(Float, nullable=True)
    oiliness: Mapped[float | None] = mapped_column(Float, nullable=True)
    texture: Mapped[float | None] = mapped_column(Float, nullable=True)
    redness: Mapped[float | None] = mapped_column(Float, nullable=True)
    pigmentation: Mapped[float | None] = mapped_column(Float, nullable=True)
    blemish_index: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
class Cart(Base):
    __tablename__ = "carts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    shopify_cart_id: Mapped[str | None] = mapped_column(String, nullable=True)  # populated in Step 19
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    items: Mapped[list["CartItem"]] = relationship(back_populates="cart")


class CartItem(Base):
    __tablename__ = "cart_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cart_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("carts.id"))
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"))
    quantity: Mapped[int] = mapped_column(Integer, default=1)

    cart: Mapped["Cart"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship()


class EngagementEventType(str, enum.Enum):
    recommendations_shown = "recommendations_shown"  # one row per product on the Products screen the user saw
    product_clicked = "product_clicked"  # user opened a product's official yuriwoori.com page


class EngagementEvent(Base):
    """What a signed-up user did after an analysis. Purchases are NOT recorded here:
    there is no order integration, so a click is never treated as a purchase."""

    __tablename__ = "engagement_events"
    # "Shown" is recorded once per scan and product, even if two requests race (database-enforced).
    __table_args__ = (
        Index("uq_engagement_shown_once", "scan_id", "product_handle", unique=True,
              postgresql_where=text("event_type = 'recommendations_shown'")),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type: Mapped[EngagementEventType] = mapped_column(Enum(EngagementEventType), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    scan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scans.id"), index=True)
    product_handle: Mapped[str] = mapped_column(String)  # official catalogue handle, validated server-side
    product_url: Mapped[str] = mapped_column(String)  # official URL from the catalogue, not from the browser
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    client_ip: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
