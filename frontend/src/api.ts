import { accessToken } from "./auth";
import type { AllocationResources, AllocationResponse, CustomResourceInput, DashboardResponse, DisasterRequest, RequestStatus } from "./types";

const BASE_URL = (import.meta.env.VITE_API_URL ?? "http://localhost:8001").replace(/\/$/, "");
type ErrorBody = { detail?: unknown; message?: unknown; error?: unknown };

async function call<T>(path: string, init: RequestInit = {}, authenticated = false): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  if (authenticated) headers.set("Authorization", `Bearer ${await accessToken()}`);
  const response = await fetch(`${BASE_URL}${path}`, { ...init, headers });
  const body = await response.json().catch(() => ({})) as ErrorBody;
  if (!response.ok) throw new Error(extractErrorMessage(body, response.status));
  return body as T;
}

function extractErrorMessage(body: ErrorBody, status: number): string {
  for (const value of [body.detail, body.message, body.error]) {
    if (typeof value === "string" && value.trim()) return value;
  }
  return `HTTP ${status}`;
}

export interface CreateRequestPayload { city: string; district: string; address: string; latitude?: number; longitude?: number; message: string; }
export interface CreateRequestResponse { requestId: string; status: RequestStatus; analysisStatus: string; message: string; createdAt: string; }

export function createRequest(payload: CreateRequestPayload): Promise<CreateRequestResponse> {
  return call("/v1/requests", { method: "POST", headers: { "Idempotency-Key": crypto.randomUUID() }, body: JSON.stringify(payload) });
}
export function getRequest(id: string): Promise<DisasterRequest> { return call(`/v1/requests/${encodeURIComponent(id)}`); }
export function getDashboard(): Promise<DashboardResponse> { return call("/v1/admin/dashboard", {}, true); }
export function updateRequestStatus(id: string, status: RequestStatus): Promise<DisasterRequest> {
  return call(`/v1/admin/requests/${encodeURIComponent(id)}/status`, { method: "PATCH", body: JSON.stringify({ status }) }, true);
}
export async function allocateResources(resources: AllocationResources, customResources: CustomResourceInput[] = []): Promise<AllocationResponse> {
  const response = await call<unknown>("/v1/admin/allocations", { method: "POST", body: JSON.stringify({ resources, customResources }) }, true);
  if (!isAllocationResponse(response)) {
    throw new Error("Kaynak dağıtımı hesaplanamadı. API yanıtı beklenen dağıtım sonucunu içermiyor.");
  }
  return response;
}

function isAllocationResponse(value: unknown): value is AllocationResponse {
  if (!isRecord(value)) return false;
  const response = value as Partial<AllocationResponse>;
  return Array.isArray(response.allocations)
    && isRecord(response.unallocated)
    && isRecord(response.inputResources)
    && typeof response.explanation === "string"
    && typeof response.rulesVersion === "string";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object";
}
