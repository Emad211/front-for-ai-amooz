import { ApiRequestError, getStoredTokens, type RegisterResponse } from "./auth-service";

const RAW_API = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/$/, "");
// Same-origin Next /api proxy so the teacher-completion refresh cookie is
// first-party (and admin calls avoid cross-origin CORS).
const API_URL = "/api";

export type AccessRequestKind = "teacher" | "organization";
export type AccessRequestStatus = "pending" | "contacted" | "approved" | "rejected";

export type TeacherAccessRequestPayload = {
  kind: "teacher";
  full_name: string;
  phone: string;
  email?: string;
  expertise?: string;
  note?: string;
};

export type OrgAccessRequestPayload = {
  kind: "organization";
  full_name: string;
  phone: string;
  email?: string;
  org_name: string;
  city?: string;
  expected_students?: number;
  website?: string;
  note?: string;
};

export type AccessRequestPayload = TeacherAccessRequestPayload | OrgAccessRequestPayload;

export type CompleteTeacherPayload = {
  token: string;
  username: string;
  password: string;
  first_name?: string;
  last_name?: string;
};

export type AccessRequestAdmin = {
  id: number;
  kind: AccessRequestKind;
  kind_display: string;
  full_name: string;
  phone: string;
  email: string;
  expertise: string;
  org_name: string;
  city: string;
  expected_students: number | null;
  website: string;
  note: string;
  status: AccessRequestStatus;
  status_display: string;
  admin_note: string;
  reject_reason: string;
  reviewed_by_name: string | null;
  reviewed_at: string | null;
  registration_token: string;
  created_user: number | null;
  created_organization: number | null;
  created_at: string;
  updated_at: string;
};

export type Paginated<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

async function parseJson(res: Response) {
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  { auth = false }: { auth?: boolean } = {}
): Promise<T> {
  if (!RAW_API) {
    throw new Error("NEXT_PUBLIC_API_URL تنظیم نشده است.");
  }

  const headers = new Headers(options.headers);
  if (!headers.has("Content-Type") && options.body) {
    headers.set("Content-Type", "application/json");
  }
  if (auth) {
    const tokens = getStoredTokens();
    if (tokens?.access && !headers.has("Authorization")) {
      headers.set("Authorization", `Bearer ${tokens.access}`);
    }
  }

  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { ...options, headers, credentials: "include" });
  } catch {
    throw new Error("ارتباط با سرور برقرار نشد.");
  }

  const payload = await parseJson(res);
  if (!res.ok) {
    // Throw ApiRequestError so forms can use normalizeApiError() for field-level errors.
    throw new ApiRequestError("درخواست ناموفق بود.", res.status, payload);
  }
  return payload as T;
}

// ── Public intake + completion ───────────────────────────────────────────────

export async function submitAccessRequest(
  payload: AccessRequestPayload
): Promise<{ id: number; detail: string }> {
  return request("/waitlist/requests/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function completeTeacherRegistration(
  payload: CompleteTeacherPayload
): Promise<RegisterResponse> {
  return request("/waitlist/complete/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// ── Admin review ─────────────────────────────────────────────────────────────

export async function listAccessRequests(params?: {
  kind?: AccessRequestKind;
  status?: AccessRequestStatus;
}): Promise<Paginated<AccessRequestAdmin>> {
  const qs = new URLSearchParams();
  if (params?.kind) qs.set("kind", params.kind);
  if (params?.status) qs.set("status", params.status);
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return request(`/waitlist/admin/requests/${suffix}`, { method: "GET" }, { auth: true });
}

export async function approveAccessRequest(id: number): Promise<AccessRequestAdmin> {
  return request(`/waitlist/admin/requests/${id}/approve/`, { method: "POST" }, { auth: true });
}

export async function rejectAccessRequest(id: number, reason = ""): Promise<AccessRequestAdmin> {
  return request(
    `/waitlist/admin/requests/${id}/reject/`,
    { method: "POST", body: JSON.stringify({ reason }) },
    { auth: true }
  );
}
