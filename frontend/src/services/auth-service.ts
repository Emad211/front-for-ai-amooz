type TokenResponse = {
  access: string;
  refresh: string;
};

export type AuthMeResponse = {
  id: number;
  username: string;
  email: string;
  role: string;
  is_profile_completed: boolean;
};

export type LoginPayload = {
  username: string;
  password: string;
};

export type RegisterPayload = LoginPayload & {
  email?: string;
  role?: string;
};

export type RegisterResponse = {
  user: AuthMeResponse;
  tokens: TokenResponse;
};

const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? '').replace(/\/$/, '');

if (!API_URL) {
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

async function request<T>(path: string, options: RequestInit = {}) {
  const headers = new Headers(options.headers);
  if (!headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
  });

  const payload = await parseJson(response);

  if (!response.ok) {
    const message =
      (payload && typeof payload === 'object' && 'detail' in payload && payload.detail) ||
      (payload && typeof payload === 'object' && 'message' in payload && payload.message) ||
      (Array.isArray(payload) && payload.join(', ')) ||
      response.statusText;

    throw new Error(typeof message === 'string' ? message : 'خطا در ارتباط با سرور');
  }

  return payload as T;
}

export async function login(payload: LoginPayload): Promise<TokenResponse> {
  return request<TokenResponse>('/token/', {
    method: 'POST',
    body: JSON.stringify({ username: payload.username, password: payload.password }),
  });
}

export async function register(payload: RegisterPayload): Promise<RegisterResponse> {
  return request<RegisterResponse>('/auth/register/', {
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
  window.localStorage.setItem('userRole', user.role.toLowerCase());
}

export function clearAuthStorage() {
  if (!isClient()) return;
  window.localStorage.removeItem(STORAGE_KEYS.access);
  window.localStorage.removeItem(STORAGE_KEYS.refresh);
  window.localStorage.removeItem(STORAGE_KEYS.user);
  window.localStorage.removeItem('userRole');
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
