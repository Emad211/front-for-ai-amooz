type TokenResponse = {
  access: string;
  refresh: string;
};

export class ApiRequestError extends Error {
  status: number;
  payload: unknown;

  constructor(message: string, status: number, payload: unknown) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.payload = payload;
  }
}

export type FieldErrors = Record<string, string[]>;

export type NormalizedApiError = {
  status?: number;
  message: string;
  fieldErrors: FieldErrors;
  raw?: unknown;
};

export type AuthMeResponse = {
  id: number;
  username: string;
  first_name?: string;
  last_name?: string;
  email: string;
  phone?: string | null;
  avatar?: string | null;
  role: string;
  is_profile_completed: boolean;
  // Platform-admin flags (sent by MeSerializer). Optional: may be absent on
  // stale cached profiles. Used by the admin login + admin route guard.
  is_staff?: boolean;
  is_superuser?: boolean;
  // TEACHER only: may use a personal (freelancer) workspace. False = org-only.
  // May be absent on stale cached profiles from before this field shipped.
  is_freelancer?: boolean;
};

export type LoginPayload = {
  username: string;
  password: string;
  role?: string;
};

export type RegisterPayload = {
  username: string;
  password: string;
  email?: string;
  role?: string;
  first_name?: string;
  last_name?: string;
  phone?: string;
};

export type RegisterResponse = {
  user: AuthMeResponse;
  tokens: TokenResponse;
};

export type InviteLoginPayload = {
  code: string;
  phone: string;
};

const RAW_API = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, "");

if (!RAW_API) {
  console.warn("NEXT_PUBLIC_API_URL is not set");
}

// Auth requests go through the SAME-ORIGIN Next.js /api proxy (see next.config.ts)
// so the HttpOnly refresh cookie is first-party (SameSite=Lax) and cross-site/CORS
// is avoided. (Data services still call the backend directly with a Bearer token.)
const API_URL = "/api";

const STORAGE_KEYS = {
  access: "ai_amooz_access",
  refresh: "ai_amooz_refresh",
  user: "ai_amooz_user",
};

function isClient() {
  return typeof window !== "undefined";
}

function isPlainObject(v: unknown): v is Record<string, unknown> {
  return !!v && typeof v === "object" && !Array.isArray(v);
}

function toStringArray(v: unknown): string[] {
  if (!v) return [];
  if (Array.isArray(v)) return v.map((x) => String(x)).filter(Boolean);
  if (typeof v === "string") return [v];
  return [String(v)];
}

/**
 * ترجمه پیام‌های رایج Django/DRF به فارسی.
 * (هرچی بیشتر با بک‌اندت برخورد کنی، می‌تونی map رو کامل‌تر کنی.)
 */
export function translateBackendMessage(msg: string): string {
  const m = String(msg ?? "").trim();
  if (!m) return m;

  const directMap: Record<string, string> = {
    'This field is required.': "این فیلد اجباری است.",
    "Enter a valid email address.": "لطفاً یک ایمیل معتبر وارد کنید.",
    'Method "GET" not allowed.': "این درخواست پشتیبانی نمی‌شود.",
    "Authentication credentials were not provided.": "ابتدا وارد حساب کاربری شوید.",
    "Invalid token.": "توکن نامعتبر است.",
    "Token is invalid or expired": "توکن نامعتبر است یا منقضی شده است.",
    "No active account found with the given credentials": "نام کاربری یا رمز عبور اشتباه است.",
    "Unable to log in with provided credentials.": "نام کاربری یا رمز عبور اشتباه است.",
    "Validation error.": "لطفاً اطلاعات را بررسی کنید.",
    "A user with that username already exists.": "این نام کاربری قبلاً ثبت شده است.",
  };

  if (directMap[m]) return directMap[m];

  // Ensure this field has at least X characters.
  const minLen = m.match(/Ensure this field has at least (\d+) characters\./i);
  if (minLen?.[1]) return `این فیلد باید حداقل ${minLen[1]} کاراکتر باشد.`;

  // Ensure this field has no more than X characters.
  const maxLen = m.match(/Ensure this field has no more than (\d+) characters\./i);
  if (maxLen?.[1]) return `این فیلد نمی‌تواند بیشتر از ${maxLen[1]} کاراکتر باشد.`;

  // This field may not be blank.
  if (/may not be blank/i.test(m)) return "این فیلد نمی‌تواند خالی باشد.";

  return m; // fallback همان انگلیسی/پیام اصلی
}

/**
 * تلاش می‌کند fieldErrors را از شکل‌های مختلف DRF بیرون بکشد:
 * - { detail, errors: {field: [..]} }
 * - { field: [..] }  (ساختار استاندارد Serializer errors)
 * - { non_field_errors: [..] }
 */
function extractFieldErrors(payload: unknown): FieldErrors {
  const out: FieldErrors = {};

  if (!isPlainObject(payload)) return out;

  const candidate =
    isPlainObject(payload.errors) ? (payload.errors as Record<string, unknown>) : (payload as Record<string, unknown>);

  if (!isPlainObject(candidate)) return out;

  for (const [key, val] of Object.entries(candidate)) {
    if (key === "detail" || key === "errors" || key === "message") continue;

    const arr = toStringArray(val)
      .map((s) => translateBackendMessage(s))
      .filter(Boolean);

    if (arr.length) out[key] = arr;
  }

  return out;
}

function pickBestMessage(payload: unknown, fieldErrors: FieldErrors): string {
  // اگر fieldErrors داریم، بهترین پیام: اولین پیامِ اولین فیلد
  const firstField = Object.keys(fieldErrors)[0];
  if (firstField) {
    const firstMsg = fieldErrors[firstField]?.[0];
    if (firstMsg) return firstMsg;
  }

  if (isPlainObject(payload) && typeof payload.detail === "string") {
    return translateBackendMessage(payload.detail);
  }

  if (typeof payload === "string") return translateBackendMessage(payload);

  return "خطا در ارتباط با سرور";
}

/**
 * این تابع را در UI صدا بزن تا:
 * - هم پیام کلی داشته باشی
 * - هم خطاهای فیلدی (برای setError)
 */
export function normalizeApiError(err: unknown): NormalizedApiError {
  if (err instanceof ApiRequestError) {
    const fieldErrors = extractFieldErrors(err.payload);
    const message = pickBestMessage(err.payload, fieldErrors);

    return {
      status: err.status,
      message,
      fieldErrors,
      raw: err.payload,
    };
  }

  if (err instanceof Error) {
    return {
      message: translateBackendMessage(err.message),
      fieldErrors: {},
      raw: err,
    };
  }

  return {
    message: "خطای ناشناخته رخ داد",
    fieldErrors: {},
    raw: err,
  };
}

async function parseJson(res: Response) {
  const text = await res.text();
  if (!text) return null;

  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

// پیام Error را از normalizeApiError بگیر تا دیگر "Validation error." گیر نکنیم
function extractError(payload: unknown): string {
  const fieldErrors = extractFieldErrors(payload);
  const message = pickBestMessage(payload, fieldErrors);

  // اگر detail دقیقاً "Validation error." بود ولی fieldErrors داریم،
  // pickBestMessage اول fieldErrors را انتخاب می‌کند و اینجا پیام دقیق نمایش می‌دهیم.
  return message;
}

async function baseRequest<T>(path: string, options: RequestInit = {}, retry = true): Promise<T> {
  const headers = new Headers(options.headers);

  // اگر FormData بود Content-Type را دست نزن (مرورگر boundary را ست می‌کند)
  const bodyIsFormData = typeof FormData !== "undefined" && options.body instanceof FormData;

  if (!headers.has("Content-Type") && !bodyIsFormData) {
    headers.set("Content-Type", "application/json");
  }

  const tokens = getStoredTokens();

  if (tokens?.access && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${tokens.access}`);
  }

  const url = `${API_URL}${path}`;

  let res: Response;

  try {
    // credentials:include so the HttpOnly refresh cookie flows on auth calls.
    res = await fetch(url, { ...options, headers, credentials: "include" });
  } catch {
    throw new Error("ارتباط با سرور برقرار نشد");
  }

  // Refresh flow
  if (res.status === 401 && retry) {
    try {
      const newAccess = await refreshAccessToken();
      headers.set("Authorization", `Bearer ${newAccess}`);
      return baseRequest(path, { ...options, headers }, false);
    } catch {
      clearAuthStorage();
      throw new Error("جلسه شما منقضی شده است");
    }
  }

  // 204 No Content
  if (res.status === 204) return null as T;

  const payload = await parseJson(res);

  if (!res.ok) {
    throw new ApiRequestError(extractError(payload), res.status, payload);
  }

  return payload as T;
}

export function getStoredTokens(): TokenResponse | null {
  if (!isClient()) return null;

  // The refresh token now lives in an HttpOnly cookie, not localStorage — so
  // the access token alone determines whether we have a usable session here.
  const access = localStorage.getItem(STORAGE_KEYS.access);
  if (!access) return null;

  const refresh = localStorage.getItem(STORAGE_KEYS.refresh) || "";
  return { access, refresh };
}

export function persistTokens(tokens: TokenResponse) {
  if (!isClient()) return;
  localStorage.setItem(STORAGE_KEYS.access, tokens.access);
  // Never persist the refresh token in JS-readable storage — it is delivered as
  // an HttpOnly cookie by the backend. Remove any legacy value.
  localStorage.removeItem(STORAGE_KEYS.refresh);
}

export function persistUser(user: AuthMeResponse) {
  if (!isClient()) return;

  localStorage.setItem(STORAGE_KEYS.user, JSON.stringify(user));
  localStorage.setItem("userRole", user.role);

  window.dispatchEvent(new Event("user-profile-updated"));
}

export function getStoredUser(): AuthMeResponse | null {
  if (!isClient()) return null;

  const value = localStorage.getItem(STORAGE_KEYS.user);
  if (!value) return null;

  try {
    return JSON.parse(value);
  } catch {
    return null;
  }
}

export function clearAuthStorage() {
  if (!isClient()) return;

  localStorage.removeItem(STORAGE_KEYS.access);
  localStorage.removeItem(STORAGE_KEYS.refresh);
  localStorage.removeItem(STORAGE_KEYS.user);
  localStorage.removeItem("userRole");
}

export async function login(payload: LoginPayload): Promise<TokenResponse> {
  return baseRequest("/token/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function register(payload: RegisterPayload): Promise<RegisterResponse> {
  return baseRequest("/auth/register/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function inviteLogin(payload: InviteLoginPayload): Promise<RegisterResponse> {
  return baseRequest("/auth/invite-login/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function requestPasswordReset(identifier: string): Promise<{ detail: string }> {
  return baseRequest("/auth/password-reset/request/", {
    method: "POST",
    body: JSON.stringify({ identifier }),
  });
}

export type PasswordResetConfirmPayload = {
  identifier: string;
  code: string;
  new_password: string;
};

export async function confirmPasswordReset(
  payload: PasswordResetConfirmPayload
): Promise<{ detail: string; access?: string; refresh?: string }> {
  return baseRequest("/auth/password-reset/confirm/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function fetchMe(): Promise<AuthMeResponse> {
  return baseRequest("/accounts/me/", { method: "GET" });
}

export type CompleteOnboardingPayload = {
  username: string;
  password: string;
  email: string;
  phone: string;
  first_name: string;
  last_name?: string;
  // role-specific (optional)
  grade?: string;
  major?: string;
  expertise?: string;
};

/**
 * Forced post-login onboarding: the code-logged-in user sets the credentials
 * they'll log in with from now on (+ email/phone/profile). Returns the fresh
 * user (with is_profile_completed=true) — persist it before routing away.
 */
export async function completeOnboarding(
  payload: CompleteOnboardingPayload
): Promise<AuthMeResponse> {
  return baseRequest("/accounts/complete-onboarding/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function logout(): Promise<void> {
  // The backend reads the refresh from the HttpOnly cookie, blacklists it, and
  // clears the cookie. Only call it when we have a local session.
  const access = isClient() ? localStorage.getItem(STORAGE_KEYS.access) : null;
  if (access) {
    try {
      await baseRequest("/auth/logout/", { method: "POST", body: JSON.stringify({}) });
    } catch {
      // Clear locally regardless of the network result.
    }
  }
  clearAuthStorage();
}

export async function refreshAccessToken(): Promise<string> {
  // The refresh token travels in the HttpOnly cookie (sent via credentials:include
  // on this same-origin /api request); the backend rotates it and re-sets the
  // cookie. We never see or store the refresh token in JS.
  const res = await fetch(`${API_URL}/token/refresh/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({}),
  });

  const payload = await parseJson(res);

  if (!res.ok || !isPlainObject(payload) || typeof payload.access !== "string") {
    clearAuthStorage();
    throw new Error("جلسه منقضی شده");
  }

  // Persist only the new access token — the rotated refresh stays in the cookie.
  if (isClient()) {
    localStorage.setItem(STORAGE_KEYS.access, payload.access);
  }

  return payload.access;
}
