type TokenResponse = {
  access: string;
  refresh: string;
};

export class ApiRequestError extends Error {
  status: number;
  payload: unknown;

  constructor(message: string, status: number, payload: unknown) {
    super(message);
    this.name = 'ApiRequestError';
    this.status = status;
    this.payload = payload;
  }
}

export type AuthMeResponse = {
  id: number;
  username: string;
  first_name?: string;
  last_name?: string;
  email: string;
  phone?: string | null;
  avatar?: string | null;
  role: string;
  is_staff?: boolean;
  is_superuser?: boolean;
  is_profile_completed: boolean;
};

export type LoginPayload = {
  username: string;
  password: string;
  role?: string;
};

export type RegisterPayload = LoginPayload & {
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

const RAW_API_URL = (process.env.NEXT_PUBLIC_API_URL ?? '').replace(/\/$/, '');

// We want all requests to target the Django API root: `${BACKEND}/api`.
// Allow either:
// - NEXT_PUBLIC_API_URL="https://example.com"  -> https://example.com/api
// - NEXT_PUBLIC_API_URL="https://example.com/api" -> https://example.com/api
const API_URL = RAW_API_URL.endsWith('/api') ? RAW_API_URL : `${RAW_API_URL}/api`;

if (!RAW_API_URL) {
  console.warn('NEXT_PUBLIC_API_URL is not defined. Auth requests may fail.');
}

const STORAGE_KEYS = {
  access: 'ai_amooz_access',
  refresh: 'ai_amooz_refresh',
  user: 'ai_amooz_user',
};

async function parseJson(response: Response) {
  const text = await response.text();
  if (!text) return null;

  try {
    return JSON.parse(text);
  } catch (error) {
    return text;
  }
}

function stringifyErrorPayload(payload: unknown): string | null {
  if (!payload) return null;
  if (typeof payload === 'string') return payload;

  if (Array.isArray(payload)) {
    const parts = payload
      .map((item) => (typeof item === 'string' ? item : JSON.stringify(item)))
      .filter(Boolean);
    return parts.length ? parts.join(', ') : null;
  }

  if (typeof payload === 'object') {
    const obj = payload as Record<string, unknown>;

    // 1. Handle our unified validation error structure: {"detail": "...", "errors": {...}}
    if (obj.errors && typeof obj.errors === 'object') {
      const errorEntries = Object.entries(obj.errors as Record<string, string[]>)
        .map(([field, messages]) => {
          const msg = Array.isArray(messages) ? messages.join(', ') : String(messages);
          // Map common field names to Persian for better UX if needed, 
          // but for now just show the message.
          return field === 'non_field_errors' ? msg : `${field}: ${msg}`;
        })
        .filter(Boolean);
      
      if (errorEntries.length > 0) return errorEntries.join(' | ');
    }

    // 2. Fallback to detail or message
    if (typeof obj.detail === 'string' && obj.detail.trim()) return obj.detail;
    if (typeof obj.message === 'string' && obj.message.trim()) return obj.message;

    // 3. Generic object iteration
    const entries = Object.entries(obj)
      .filter(([key]) => key !== 'detail' && key !== 'errors') // skip already handled
      .map(([key, value]) => {
        if (typeof value === 'string') return `${key}: ${value}`;
        if (Array.isArray(value)) {
          const joined = value
            .map((v) => (typeof v === 'string' ? v : JSON.stringify(v)))
            .filter(Boolean)
            .join(', ');
          return joined ? `${key}: ${joined}` : null;
        }
        if (value && typeof value === 'object') return `${key}: ${JSON.stringify(value)}`;
        return null;
      })
      .filter((x): x is string => Boolean(x));

    return entries.length ? entries.join(' | ') : null;
  }

  return null;
}

async function request<T>(path: string, options: RequestInit = {}) {
  const headers = new Headers(options.headers);
  if (!headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const url = `${API_URL}${path}`;

  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      headers,
    });
  } catch (error) {
    const hint = RAW_API_URL
      ? `آدرس فعلی API: ${RAW_API_URL}`
      : 'NEXT_PUBLIC_API_URL تنظیم نشده است.';

    throw new Error(
      `ارتباط با سرور برقرار نشد. (${hint})` +
        ' معمولاً یکی از این‌هاست: بک‌اند اجرا نیست، آدرس/پورت اشتباه است، یا مرورگر به خاطر CORS/Mixed Content درخواست را بلاک کرده.'
    );
  }

  const payload = await parseJson(response);

  if (!response.ok) {
    const message = stringifyErrorPayload(payload) || response.statusText || 'خطا در ارتباط با سرور';
    throw new ApiRequestError(message, response.status, payload);
  }

  return payload as T;
}

export async function login(payload: LoginPayload): Promise<TokenResponse> {
  const body: Record<string, string> = {
    username: payload.username,
    password: payload.password,
  };
  if (payload.role) {
    body.role = payload.role;
  }
  return request<TokenResponse>('/token/', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function register(payload: RegisterPayload): Promise<RegisterResponse> {
  return request<RegisterResponse>('/auth/register/', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function inviteLogin(payload: InviteLoginPayload): Promise<RegisterResponse> {
  return request<RegisterResponse>('/auth/invite-login/', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function fetchMe(accessToken: string): Promise<AuthMeResponse> {
  return request<AuthMeResponse>('/accounts/me/', {
    method: 'GET',
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });
}

export async function logout(refreshToken: string, accessToken?: string): Promise<void> {
  await request('/auth/logout/', {
    method: 'POST',
    body: JSON.stringify({ refresh: refreshToken }),
    headers: accessToken
      ? {
          Authorization: `Bearer ${accessToken}`,
        }
      : undefined,
  });
}

function isClient() {
  return typeof window !== 'undefined';
}

export function persistTokens(tokens: TokenResponse) {
  if (!isClient()) return;
  window.localStorage.setItem(STORAGE_KEYS.access, tokens.access);
  window.localStorage.setItem(STORAGE_KEYS.refresh, tokens.refresh);
}

export function persistUser(user: AuthMeResponse) {
  if (!isClient()) return;
  window.localStorage.setItem(STORAGE_KEYS.user, JSON.stringify(user));
  window.localStorage.setItem('userRole', (user.role || '').toLowerCase());
  
  // Notify other components that user data has changed
  window.dispatchEvent(new Event('user-profile-updated'));
}

export function clearAuthStorage() {
  if (!isClient()) return;
  window.localStorage.removeItem(STORAGE_KEYS.access);
  window.localStorage.removeItem(STORAGE_KEYS.refresh);
  window.localStorage.removeItem(STORAGE_KEYS.user);
  window.localStorage.removeItem('userRole');
  window.localStorage.removeItem('ai_amooz_active_workspace');
}

export function getStoredTokens(): TokenResponse | null {
  if (!isClient()) return null;
  const access = window.localStorage.getItem(STORAGE_KEYS.access);
  const refresh = window.localStorage.getItem(STORAGE_KEYS.refresh);
  return access && refresh ? { access, refresh } : null;
}

export function getStoredUser(): AuthMeResponse | null {
  if (!isClient()) return null;
  const value = window.localStorage.getItem(STORAGE_KEYS.user);
  if (!value) return null;

  try {
    return JSON.parse(value) as AuthMeResponse;
  } catch (error) {
    console.warn('Failed to parse stored user', error);
    return null;
  }
}

/**
 * Attempt to refresh the access token using the stored refresh token.
 * On success, persists the new access token and returns it.
 * On failure, clears auth storage and redirects to /login.
 */
export async function refreshAccessToken(): Promise<string> {
  const tokens = getStoredTokens();
  const refresh = (tokens?.refresh || '').trim();
  if (!refresh) {
    clearAuthStorage();
    if (isClient() && !window.location.pathname.startsWith('/login')) {
      window.location.href = '/login';
    }
    throw new Error('جلسه شما منقضی شده است. لطفاً دوباره وارد شوید.');
  }

  const url = `${API_URL}/token/refresh/`;
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh }),
  });

  const payload = await parseJson(response);
  if (!response.ok) {
    clearAuthStorage();
    if (isClient() && !window.location.pathname.startsWith('/login')) {
      window.location.href = '/login';
    }
    throw new Error('جلسه شما منقضی شده است. لطفاً دوباره وارد شوید.');
  }

  const newAccess = (payload as Record<string, unknown>)?.access;
  if (typeof newAccess !== 'string' || !newAccess.trim()) {
    clearAuthStorage();
    if (isClient() && !window.location.pathname.startsWith('/login')) {
      window.location.href = '/login';
    }
    throw new Error('توکن جدید معتبر نیست. لطفاً دوباره وارد شوید.');
  }

  persistTokens({ access: newAccess, refresh });
  return newAccess;
}
