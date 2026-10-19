import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ScanCreateResponse(BaseModel):
    scan_id: uuid.UUID


class FrameUploadRequest(BaseModel):
    # only a safe character set is accepted
    angle: str = Field(pattern=r"^[A-Za-z0-9_-]{1,32}$")
    # ~14 MB of base64 text (~10 MB image)
    image_base64: str = Field(min_length=1, max_length=14_000_000)


class AnalyzeRequest(FrameUploadRequest):
    """POST /scans/{id}/analyze: the same photo again. Photos are never stored, so the analysis needs it in
    the request; it is processed in memory and discarded."""


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
    # Typical / Benchmark value per metric: fixed internal YuriWoori benchmarks for comparison only
    # (app/services/benchmark.py), not medical or population norms. Empty when none is configured (hand).
    benchmark: dict[str, float] = {}
    benchmark_version: str | None = None


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
    # live store fields
    handle: str | None = None
    available: bool | None = None
    variant_id: int | None = None

    model_config = ConfigDict(from_attributes=True)

class RecommendationResponse(BaseModel):
    product_id: uuid.UUID
    name: str
    price: float | None
    image_url: str | None
    match_reason: str
    rank: int

class BenefitEntry(BaseModel):
    icon: str
    title: str
    description: str


class RoutineStepResponse(BaseModel):
    step_order: int
    product_id: uuid.UUID
    product_name: str
    image_url: str | None
    reason: str
    # current details from the live store (app/services/live_catalogue.py)
    handle: str | None = None
    routine_step: str | None = None
    product_url: str | None = None
    price: float | None = None
    available: bool | None = None
    variant_id: int | None = None
    how_to_use: str | None = None
    # the brand's product copy (Shopify metafields), when the store has it
    key_benefit: str | None = None
    benefits: list[BenefitEntry] = []
    ingredients: list[str] = []


class RoutineResponse(BaseModel):
    AM: list[RoutineStepResponse]
    PM: list[RoutineStepResponse]
    catalogue_fetched_at: str | None = None  # when the live store data behind this routine was read
    catalogue_stale: bool = False  # true when the store couldn't be reached and its last copy was used


class CoachMessageRequest(BaseModel):
    conversation_id: uuid.UUID | None = None
    message: str = Field(min_length=1, max_length=2000)


class CoachMessageResponse(BaseModel):
    conversation_id: uuid.UUID
    reply: str
    cited_product_ids: list[str]


class CompatibilityFlagResponse(BaseModel):
    product_a_name: str
    product_b_name: str
    relationship_type: str
    explanation: str


class ProductDetailResponse(BaseModel):
    id: uuid.UUID
    name: str
    price: float | None
    currency: str
    image_url: str | None
    category: str | None
    routine_step: str | None
    description: str | None
    product_url: str | None
    concern_tags: list[str]
    chips: list[str]
    benefits: list[BenefitEntry]
    ingredients: list[str]


class SnapshotEntry(BaseModel):
    day_offset: int
    hydration: float | None
    oiliness: float | None
    texture: float | None
    redness: float | None
    pigmentation: float | None
    blemish_index: float | None


class MeaningfulChange(BaseModel):
    metric: str
    start: float
    latest: float
    delta: float
    direction: str


class ProgressResponse(BaseModel):
    snapshots: list[SnapshotEntry]
    meaningful_changes: list[MeaningfulChange]


class ShoppingAgentRequest(BaseModel):
    message: str
    scan_id: uuid.UUID | None = None


class AgentLineItem(BaseModel):
    name: str
    step: str | None
    price: float | None


class ShoppingAgentResponse(BaseModel):
    cart_id: uuid.UUID
    items: list[AgentLineItem]
    total: float
    budget: float
    tags: list[str]


class CheckoutResponse(BaseModel):
    checkout_url: str
    unresolved_products: list[str]


class CartLineIn(BaseModel):
    variant_id: int = Field(gt=0)  # Shopify variant ID (numeric), as /catalogue/live returns it
    quantity: int = Field(ge=1, le=20)


class CartQuoteRequest(BaseModel):
    lines: list[CartLineIn] = Field(min_length=1, max_length=50)


class CartDiscount(BaseModel):
    title: str  # Shopify's own name for the discount (automatic discount title or code)
    amount: float
    # automatic: applied by Shopify with no code (its title may look like a code); code: a coupon code on the cart
    kind: str = "automatic"


class DiscountSlab(BaseModel):
    min_subtotal: float
    amount: float
    title: str


class DiscountSlabs(BaseModel):
    """The store's discount slabs, only when Shopify's pricing of this cart matched them (verified)."""
    verified: bool
    table: list[DiscountSlab] = []
    current: DiscountSlab | None = None
    next: DiscountSlab | None = None
    add_for_next: float | None = None  # subtotal still needed to reach the next slab


class CartQuoteLine(BaseModel):
    variant_id: int | None
    handle: str | None
    title: str | None
    quantity: int | None
    unit_price: float | None
    compare_at_price: float | None
    subtotal: float | None
    total: float | None


class CartQuoteResponse(BaseModel):
    """A cart priced by Shopify (Storefront API). Totals are before shipping; checkout shows the final amount."""
    cart_id: str | None
    checkout_url: str
    currency: str
    subtotal: float | None
    discounts: list[CartDiscount]
    total: float | None
    total_quantity: int | None
    slabs: DiscountSlabs | None = None
    lines: list[CartQuoteLine]
    warnings: list[str] = []

class CatalogueProductResponse(BaseModel):
    handle: str
    name: str
    price: float | None
    currency: str = "INR"
    image_url: str | None
    category: str
    routine_step: str
    description: str | None
    product_url: str
    concern_tags: list[str]
    chips: list[str]
    ingredients: list[str]
    key_benefit: str | None = None
    how_to_use: str | None = None
    benefits: list[BenefitEntry] = []
    # live store fields
    product_id: int | None = None
    variant_id: int | None = None
    available: bool | None = None
    compare_at_price: float | None = None


class CatalogueRecommendation(CatalogueProductResponse):
    rank: int
    score: int
    matched_concerns: list[str]
    match_reason: str


class CatalogueRecommendationsResponse(BaseModel):
    scan_id: uuid.UUID | None
    # the analysis verdict, stated explicitly: "balanced" = every measurement was present and none
    # crossed its level; "concerns" = at least one did (listed in active_concerns)
    analysis_status: Literal["balanced", "concerns"]
    # concern tag -> plain-language phrase, for every concern the analysis flagged
    active_concerns: dict[str, str]
    recommendations: list[CatalogueRecommendation]
    catalogue_fetched_at: str | None = None
    catalogue_stale: bool = False


class LiveVariant(BaseModel):
    id: int
    title: str | None
    price: float | None
    compare_at_price: float | None
    available: bool


class LiveUsage(BaseModel):
    """How often to use a product, quoted from official YuriWoori text (never inferred)."""
    frequency: str | None  # morning_and_night | morning | daily | weekly | as_needed, or None when not stated
    quote: str | None  # the official sentence the frequency came from
    source: str | None  # "how_to_use" (product usage copy) or "description" (live product page)
    wear_time: str | None  # e.g. "15–20 minutes" for masks and patches, when stated


class LiveProduct(BaseModel):
    """Current details of one product from the official YuriWoori store (public Shopify feed)."""
    product_id: int
    handle: str
    title: str
    image_url: str | None
    url: str
    variant_id: int | None  # the variant added to the cart (first available one)
    price: float | None
    compare_at_price: float | None  # original price, only when it is higher than the current price
    discount_percent: int | None
    available: bool
    variants: list[LiveVariant]
    usage: LiveUsage | None = None


class LiveCatalogueResponse(BaseModel):
    store_url: str
    fetched_at: str | None
    stale: bool = False  # true when the store couldn't be reached and its last copy (from fetched_at) was used
    products: list[LiveProduct]


# ---------- users, engagement tracking, admin reports ----------

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class SignupRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    whatsapp: str = Field(min_length=6, max_length=25)  # normalised to +<country><number> (services/contact.py)
    email: str = Field(max_length=254, pattern=EMAIL_PATTERN)
    consent: bool  # must be true: the user accepted the privacy notice
    report_consent: bool = False  # separately: send my report to this email and WhatsApp number
    # the 6-digit sign-in code emailed when this email already has an account (asked for by code_required)
    code: str | None = Field(default=None, pattern=r"^\d{6}$")


class UserPublic(BaseModel):
    id: uuid.UUID
    name: str | None
    email: str
    whatsapp: str | None = None
    email_verified: bool = False
    whatsapp_verified: bool = False
    report_consent: bool = False


class SignupResponse(BaseModel):
    token: str | None = None
    user: UserPublic | None = None
    # the email already has an account: a sign-in code was emailed to sent_to (masked); send the form again with it
    code_required: bool = False
    sent_to: str | None = None


class DeliveryChannelRequest(BaseModel):
    channel: Literal["email", "whatsapp"]


class DeliveryConfirmRequest(DeliveryChannelRequest):
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class DeliveryChannelStatus(BaseModel):
    available: bool  # the channel is configured on the server
    verified: bool  # the user confirmed this contact with a one-time code
    destination: str | None  # masked, e.g. "p•••@example.com" / "+91•••••••210"


class DeliveryStatusResponse(BaseModel):
    email: DeliveryChannelStatus
    whatsapp: DeliveryChannelStatus
    report_consent: bool = False  # the user agreed to have their report sent


class DeliveryInfo(BaseModel):
    """One channel's delivery of a report (result_deliveries)."""
    channel: str
    # pending | sending | accepted (WhatsApp took it; not yet confirmed sent) | sent | delivered | failed
    status: str
    configured: bool
    verified: bool
    destination: str | None  # masked
    reason: str | None  # why it is pending/failed: not_configured | no_contact | no_consent | not_verified (None = provider error)
    attempts: int
    sent_at: datetime | None
    updated_at: datetime | None
    can_retry: bool


class ReportCreateRequest(BaseModel):
    scan_id: uuid.UUID


class ReportStatusResponse(BaseModel):
    report_id: uuid.UUID
    scan_id: uuid.UUID
    created_at: datetime
    expires_at: datetime
    revoked: bool
    report_consent: bool
    deliveries: list[DeliveryInfo]


class ReportViewResponse(BaseModel):
    content: dict  # the saved report (services/reports.py build_content)
    expires_at: datetime


class EngagementEventRequest(BaseModel):
    event_type: Literal["recommendations_shown", "product_clicked"]
    scan_id: uuid.UUID
    product_handle: str | None = Field(default=None, max_length=200)  # required for product_clicked


class EngagementEventResponse(BaseModel):
    recorded: int


class AdminLoginRequest(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=200)


class AdminLoginResponse(BaseModel):
    token: str
    expires_in: int
