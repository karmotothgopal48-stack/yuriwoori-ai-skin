const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  if (!res.ok) {
    throw new ApiError(`Request failed: ${res.status}`, res.status);
  }

  return res.json() as Promise<T>;
}

export const api = {
  get: <T>(path: string) => request<T>(path, { method: "GET" }),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
};

export interface HealthResponse {
  status: string;
  service: string;
}

export function getHealth() {
  return api.get<HealthResponse>("/v1/health");
}
export interface ScanCreateResponse {
  scan_id: string;
}

export interface FrameQualityResponse {
  frame_id: string;
  angle: string;
  blur_score: number;
  lighting_score: number;
  quality_score: number;
  passed: boolean;
}

export function createScan() {
  return api.post<ScanCreateResponse>("/v1/scans");
}

export function uploadFrame(scanId: string, angle: string, imageBase64: string) {
  return api.post<FrameQualityResponse>(`/v1/scans/${scanId}/frames`, {
    angle,
    image_base64: imageBase64,
  });
}export interface SkinProfileResponse {
  scan_id: string;
  skin_type: string | null;
  hydration: number | null;
  oiliness: number | null;
  texture: number | null;
  redness: number | null;
  pigmentation: number | null;
  blemish_index: number | null;
  pore_visibility: number | null;
  overall_score: number | null;
  model_version: string | null;
}

export function analyzeScan(scanId: string) {
  return api.post<SkinProfileResponse>(`/v1/scans/${scanId}/analyze`);
}export function getScanProfile(scanId: string) {
  return api.get<SkinProfileResponse>(`/v1/scans/${scanId}`);
}export interface PassportResponse {
  skin_type: string | null;
  top_concerns: string[];
  overall_score: number | null;
  last_scanned_at: string | null;
}

export function saveToPassport(scanId: string) {
  return api.post<PassportResponse>(`/v1/passport/save/${scanId}`);
}

export function getPassport() {
  return api.get<PassportResponse>("/v1/passport");
}export interface ProductResponse {
  id: string;
  name: string;
  price: number | null;
  currency: string;
  image_url: string | null;
  category: string | null;
  routine_step: string | null;
  description: string | null;
  product_url: string | null;
}

export function getProducts() {
  return api.get<ProductResponse[]>("/v1/products");
}export interface RecommendationResponse {
  product_id: string;
  name: string;
  price: number | null;
  image_url: string | null;
  match_reason: string;
  rank: number;
}

export function getRecommendations(scanId: string) {
  return api.get<RecommendationResponse[]>(`/v1/scans/${scanId}/recommendations`);
}export interface RoutineStepResponse {
  step_order: number;
  product_id: string;
  product_name: string;
  image_url: string | null;
  reason: string;
}

export interface RoutineResponse {
  AM: RoutineStepResponse[];
  PM: RoutineStepResponse[];
}

export function getRoutine(scanId: string) {
  return api.get<RoutineResponse>(`/v1/scans/${scanId}/routine`);
}
export interface CoachMessageResponse {
  conversation_id: string;
  reply: string;
  cited_product_ids: string[];
}

export function sendCoachMessage(message: string, conversationId?: string) {
  return api.post<CoachMessageResponse>("/v1/coach/message", {
    message,
    conversation_id: conversationId ?? null,
  });
}export interface CompatibilityFlagResponse {
  product_a_name: string;
  product_b_name: string;
  relationship_type: string;
  explanation: string;
}

export function checkCompatibility(scanId: string) {
  return api.get<CompatibilityFlagResponse[]>(`/v1/scans/${scanId}/compatibility`);
}export interface BenefitEntry {
  icon: string;
  title: string;
  description: string;
}

export interface ProductDetailResponse {
  id: string;
  name: string;
  price: number | null;
  currency: string;
  image_url: string | null;
  category: string | null;
  routine_step: string | null;
  description: string | null;
  product_url: string | null;
  concern_tags: string[];
  chips: string[];
  benefits: BenefitEntry[];
  ingredients: string[];
}

export function getProductDetail(productId: string) {
  return api.get<ProductDetailResponse>(`/v1/products/${productId}`);
}export interface SnapshotEntry {
  day_offset: number;
  hydration: number | null;
  oiliness: number | null;
  texture: number | null;
  redness: number | null;
  pigmentation: number | null;
  blemish_index: number | null;
}

export interface MeaningfulChange {
  metric: string;
  start: number;
  latest: number;
  delta: number;
  direction: string;
}

export interface ProgressResponse {
  snapshots: SnapshotEntry[];
  meaningful_changes: MeaningfulChange[];
}

export function getProgress(userId: string) {
  return api.get<ProgressResponse>(`/v1/progress/${userId}`);
}export interface AgentLineItem {
  name: string;
  step: string | null;
  price: number | null;
}

export interface ShoppingAgentResponse {
  cart_id: string;
  items: AgentLineItem[];
  total: number;
  budget: number;
  tags: string[];
}

export function buildAgentRoutine(message: string, scanId?: string) {
  return api.post<ShoppingAgentResponse>("/v1/shopping-agent/build", {
    message,
    scan_id: scanId ?? null,
  });
}