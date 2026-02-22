/**
 * Service for admin user management API calls.
 * Endpoints: GET/PATCH/DELETE /api/admin/users/
 */

export type AdminUser = {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  fullName: string;
  role: string;
  phone: string | null;
  isActive: boolean;
  isStaff: boolean;
  isSuperuser: boolean;
  dateJoined: string;
  lastLogin: string | null;
  avatar: string | null;
};

export type UserUpdatePayload = {
  role?: string;
  is_active?: boolean;
  is_staff?: boolean;
  first_name?: string;
  last_name?: string;
  email?: string;
  phone?: string;
};

const RAW_API_URL = (process.env.NEXT_PUBLIC_API_URL ?? '').replace(/\/$/, '');
const API_URL = RAW_API_URL.endsWith('/api') ? RAW_API_URL : `${RAW_API_URL}/api`;

function getAccessToken(): string {
  if (typeof window === 'undefined') {
    throw new Error('This action must run in the browser.');
  }
  const access = window.localStorage.getItem('ai_amooz_access');
  if (!access) throw new Error('ابتدا وارد حساب کاربری شوید.');
  return access;
}

async function parseJson(response: Response) {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

function extractError(payload: unknown, fallback: string): string {
  if (payload && typeof payload === 'object') {
    const obj = payload as Record<string, unknown>;
    if (typeof obj.detail === 'string' && obj.detail.trim()) return obj.detail;
    if (typeof obj.message === 'string' && obj.message.trim()) return obj.message;
  }
  if (typeof payload === 'string' && payload.trim()) return payload;
  return fallback;
}

async function requestJson<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (!headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${getAccessToken()}`);
  }
  if (!headers.has('Content-Type') && options.body) {
    headers.set('Content-Type', 'application/json');
  }

  const url = `${API_URL}${path}`;
  let response: Response;
  try {
    response = await fetch(url, { ...options, headers });
  } catch {
    throw new Error('ارتباط با سرور برقرار نشد.');
  }

  if (response.status === 204) return null as T;

  const payload = await parseJson(response);
  if (!response.ok) {
    throw new Error(extractError(payload, 'درخواست ناموفق بود.'));
  }
  return payload as T;
}

export const UserService = {
  /** List all users with optional search, role, and is_active filters. */
  getUsers: async (params?: {
    search?: string;
    role?: string;
    is_active?: string;
  }): Promise<AdminUser[]> => {
    const searchParams = new URLSearchParams();
    if (params?.search) searchParams.set('search', params.search);
    if (params?.role) searchParams.set('role', params.role);
    if (params?.is_active) searchParams.set('is_active', params.is_active);
    const qs = searchParams.toString();
    return requestJson<AdminUser[]>(`/admin/users/${qs ? `?${qs}` : ''}`);
  },

  /** Get a single user by ID. */
  getUser: async (userId: number): Promise<AdminUser> => {
    return requestJson<AdminUser>(`/admin/users/${userId}/`);
  },

  /** Update user fields. */
  updateUser: async (userId: number, data: UserUpdatePayload): Promise<AdminUser> => {
    return requestJson<AdminUser>(`/admin/users/${userId}/`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  },

  /** Delete a user. */
  deleteUser: async (userId: number): Promise<void> => {
    await requestJson<void>(`/admin/users/${userId}/`, {
      method: 'DELETE',
    });
  },
};
