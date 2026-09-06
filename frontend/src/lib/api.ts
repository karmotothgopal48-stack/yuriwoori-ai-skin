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
}