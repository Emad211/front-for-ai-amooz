import type {
  Organization,
  OrgMembership,
  InvitationCode,
  Workspace,
  OrgDashboard,
  ValidateCodeResult,
  RedeemCodeResult,
  OrgRole,
} from '@/types';

const RAW_API_URL = (process.env.NEXT_PUBLIC_API_URL ?? '').replace(/\/$/, '');
const API_URL = RAW_API_URL.endsWith('/api') ? RAW_API_URL : `${RAW_API_URL}/api`;

function getAccessToken(): string {
  if (typeof window === 'undefined') {
    throw new Error('This action must run in the browser.');
  }
  const access = window.localStorage.getItem('ai_amooz_access');
  if (!access) {
    throw new Error('ابتدا وارد حساب کاربری شوید.');
  }
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

function extractErrorMessage(payload: unknown, fallback: string) {
  if (payload && typeof payload === 'object') {
    const obj = payload as Record<string, unknown>;
    if (obj.errors && typeof obj.errors === 'object') {
      const entries = Object.entries(obj.errors as Record<string, unknown>)
        .map(([field, messages]) => {
          if (Array.isArray(messages)) {
            const joined = messages.map((m) => String(m)).join(', ');
            return field === 'non_field_errors' ? joined : `${field}: ${joined}`;
          }
          return `${field}: ${String(messages)}`;
        })
        .filter(Boolean);
      if (entries.length) return entries.join(' | ');
    }
    if (typeof obj.detail === 'string' && obj.detail.trim()) return obj.detail;
    if (typeof obj.message === 'string' && obj.message.trim()) return obj.message;
  }
  if (typeof payload === 'string' && payload.trim()) return payload;
  return fallback;
}

async function requestJson<T>(path: string, options: RequestInit = {}): Promise<T> {
  if (!RAW_API_URL) {
    throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
  }

  const headers = new Headers(options.headers);
  if (!headers.has('Authorization')) {
    try {
      headers.set('Authorization', `Bearer ${getAccessToken()}`);
    } catch {
      // Allow unauthenticated requests (e.g., validate & redeem code)
    }
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

  const payload = await parseJson(response);
  if (!response.ok) {
    const message = extractErrorMessage(payload, 'درخواست ناموفق بود.');
    throw new Error(message);
  }
  return payload as T;
}

/**
 * Organization Service
 * Handles all data fetching for organizations, memberships, invitations, and workspaces.
 */
export const OrganizationService = {
  // ============================================================================
  // Platform Admin — Organization CRUD
  // ============================================================================

  getOrganizations: async (): Promise<Organization[]> => {
    return requestJson<Organization[]>('/organizations/');
  },

  getOrganization: async (orgId: number): Promise<Organization> => {
    return requestJson<Organization>(`/organizations/${orgId}/`);
  },

  createOrganization: async (data: {
    name: string;
    slug: string;
    student_capacity?: number;
    description?: string;
    phone?: string;
    address?: string;
  }): Promise<Organization> => {
    return requestJson<Organization>('/organizations/', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  updateOrganization: async (orgId: number, data: Partial<{
    name: string;
    slug: string;
    student_capacity: number;
    subscription_status: string;
    description: string;
    phone: string;
    address: string;
    owner: number | null;
  }>): Promise<Organization> => {
    return requestJson<Organization>(`/organizations/${orgId}/`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  },

  deleteOrganization: async (orgId: number): Promise<void> => {
    await requestJson(`/organizations/${orgId}/`, { method: 'DELETE' });
  },

  // ============================================================================
  // Org Admin — Member Management
  // ============================================================================

  getMembers: async (orgId: number, filters?: {
    role?: OrgRole;
    status?: string;
    search?: string;
  }): Promise<OrgMembership[]> => {
    const params = new URLSearchParams();
    if (filters?.role) params.set('role', filters.role);
    if (filters?.status) params.set('status', filters.status);
    if (filters?.search) params.set('search', filters.search);
    const qs = params.toString();
    return requestJson<OrgMembership[]>(
      `/organizations/${orgId}/members/${qs ? `?${qs}` : ''}`,
    );
  },

  updateMember: async (orgId: number, membershipId: number, data: {
    org_role?: OrgRole;
    status?: string;
    internal_id?: string;
  }): Promise<OrgMembership> => {
    return requestJson<OrgMembership>(
      `/organizations/${orgId}/members/${membershipId}/`,
      { method: 'PATCH', body: JSON.stringify(data) },
    );
  },

  removeMember: async (orgId: number, membershipId: number): Promise<void> => {
    await requestJson(`/organizations/${orgId}/members/${membershipId}/`, {
      method: 'DELETE',
    });
  },

  // ============================================================================
  // Org Admin — Invitation Codes
  // ============================================================================

  getInvitationCodes: async (orgId: number): Promise<InvitationCode[]> => {
    return requestJson<InvitationCode[]>(`/organizations/${orgId}/invitation-codes/`);
  },

  createInvitationCode: async (orgId: number, data: {
    target_role: OrgRole;
    label?: string;
    max_uses?: number;
    expires_at?: string | null;
    custom_code?: string;
  }): Promise<InvitationCode> => {
    return requestJson<InvitationCode>(
      `/organizations/${orgId}/invitation-codes/`,
      { method: 'POST', body: JSON.stringify(data) },
    );
  },

  updateInvitationCode: async (orgId: number, codeId: number, data: {
    is_active?: boolean;
    max_uses?: number;
    expires_at?: string | null;
  }): Promise<InvitationCode> => {
    return requestJson<InvitationCode>(
      `/organizations/${orgId}/invitation-codes/${codeId}/`,
      { method: 'PATCH', body: JSON.stringify(data) },
    );
  },

  deleteInvitationCode: async (orgId: number, codeId: number): Promise<void> => {
    await requestJson(`/organizations/${orgId}/invitation-codes/${codeId}/`, {
      method: 'DELETE',
    });
  },

  // ============================================================================
  // Org Dashboard
  // ============================================================================

  getDashboard: async (orgId: number): Promise<OrgDashboard> => {
    return requestJson<OrgDashboard>(`/organizations/${orgId}/dashboard/`);
  },

  // ============================================================================
  // Invitation Code Validation & Redemption (public)
  // ============================================================================

  validateCode: async (code: string): Promise<ValidateCodeResult> => {
    return requestJson<ValidateCodeResult>(
      `/organizations/validate-code/?code=${encodeURIComponent(code)}`,
    );
  },

  redeemCode: async (data: {
    code: string;
    username?: string;
    password?: string;
    first_name?: string;
    last_name?: string;
  }): Promise<RedeemCodeResult> => {
    return requestJson<RedeemCodeResult>('/organizations/redeem-code/', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  // ============================================================================
  // Workspace Switcher
  // ============================================================================

  getMyWorkspaces: async (): Promise<Workspace[]> => {
    return requestJson<Workspace[]>('/organizations/my-workspaces/');
  },
};
