/**
 * Impersonation session service — «ورود مستقیم مدیر» (risman step 4).
 *
 * The client half of the borrowed-session protocol:
 *
 * - `startImpersonation()` mints the 30-minute imp token pair on the backend,
 *   then performs the LOCAL identity swap: the manager's access token and
 *   cached profile are parked in a sessionStorage snapshot, the imp access
 *   takes their place, and a minimal stub profile (id + role of the target)
 *   drives every route guard to the target's own panel.
 * - `stopImpersonation()` asks the backend to close the ImpersonationLog row
 *   and restores the parked manager identity.
 *
 * sessionStorage (not localStorage) on purpose: the borrowed session dies with
 * the tab, so a closed laptop cannot outlive the manager's attention — the same
 * rationale as the backend's 30-minute clamp (`IMP_LIFETIME`).
 *
 * The manager's HttpOnly refresh cookie is never touched, which is exactly what
 * lets the stop call — routed through the same-origin `/api` proxy, where the
 * cookie rides along — authenticate as the manager with zero token handling in
 * JS. During the borrowed session `auth-service` refuses to refresh (see its
 * guard on `isImpersonating()`): minting a fresh MANAGER token from that cookie
 * would silently unmask the impersonation.
 *
 * Deliberately dependency-free (no auth-service import): `auth-service` imports
 * this module's `isImpersonating()`, so a cycle would break the auth layer.
 */

const IMP_SESSION_KEY = 'ai_amooz_imp_session';
const ACCESS_KEY = 'ai_amooz_access';
const USER_KEY = 'ai_amooz_user';
const ROLE_KEY = 'userRole';

/** Must mirror the backend's `IMP_LIFETIME` (organizations/views_impersonation.py). */
export const IMP_LIFETIME_MS = 30 * 60 * 1000;

/** The parked manager identity + the borrowed pair, kept for one tab session. */
export type ImpersonationSession = {
  orgId: number;
  /** The manager's access token, parked for the ride back. */
  managerAccess: string;
  /** The manager's cached profile JSON, restored verbatim on exit. */
  managerUserJson: string;
  impRefresh: string;
  targetId: number;
  targetRole: string;
  targetName: string;
  /** Epoch ms when the swap happened — drives the banner countdown. */
  startedAt: number;
};

function isClient(): boolean {
  return typeof window !== 'undefined';
}

export function getImpersonationSession(): ImpersonationSession | null {
  if (!isClient()) return null;
  const raw = window.sessionStorage.getItem(IMP_SESSION_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as ImpersonationSession;
    if (
      typeof parsed.orgId === 'number' &&
      typeof parsed.managerAccess === 'string' && parsed.managerAccess &&
      typeof parsed.managerUserJson === 'string' &&
      typeof parsed.impRefresh === 'string' && parsed.impRefresh &&
      typeof parsed.targetId === 'number' &&
      typeof parsed.startedAt === 'number'
    ) {
      return parsed;
    }
    return null;
  } catch {
    return null;
  }
}

export function isImpersonating(): boolean {
  return getImpersonationSession() !== null;
}

export function isImpersonationExpired(session: ImpersonationSession): boolean {
  return session.startedAt + IMP_LIFETIME_MS <= Date.now();
}

/** Where the borrowed identity lands: their own panel, nothing else. */
export function targetLandingFor(role: string): string {
  return role === 'ADVISOR' ? '/advisor' : '/home';
}

const RAW_API_URL = (process.env.NEXT_PUBLIC_API_URL ?? '').replace(/\/$/, '');
const API_URL = RAW_API_URL.endsWith('/api') ? RAW_API_URL : `${RAW_API_URL}/api`;

async function extractDetail(response: Response, fallback: string): Promise<string> {
  try {
    const payload: unknown = await response.json();
    if (payload && typeof payload === 'object') {
      const detail = (payload as Record<string, unknown>).detail;
      if (typeof detail === 'string' && detail.trim()) return detail;
    }
  } catch {
    // Non-JSON body — fall through to the generic message.
  }
  return fallback;
}

/**
 * Mint the borrowed pair and swap identities in-place. Throws with the
 * backend's pinned Persian message (400 self/non-member-role, 404 org or
 * member not found) so the caller can toast it verbatim.
 */
export async function startImpersonation(args: StartImpersonationArgs): Promise<ImpersonationSession> {
  if (!isClient()) throw new Error('این عملیات فقط در مرورگر ممکن است.');
  const managerAccess = window.localStorage.getItem(ACCESS_KEY);
  if (!managerAccess) throw new Error('ابتدا وارد حساب کاربری شوید.');

  let response: Response;
  try {
    response = await fetch(
      `${API_URL}/organizations/${args.orgId}/impersonate/${args.targetUserId}/`,
      {
        method: 'POST',
        headers: { Authorization: `Bearer ${managerAccess}` },
      },
    );
  } catch {
    throw new Error('ارتباط با سرور برقرار نشد.');
  }

  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(await extractDetail(response, 'شروع ورود مستقیم ناموفق بود.'));
  }
  const body = (payload ?? {}) as Record<string, unknown>;
  const access = typeof body.access === 'string' ? body.access : '';
  const refresh = typeof body.refresh === 'string' ? body.refresh : '';
  const user = (body.user ?? {}) as Record<string, unknown>;
  const targetId = typeof user.id === 'number' ? user.id : args.targetUserId;
  const targetRole = typeof user.role === 'string' ? user.role : args.targetRole;
  if (!access || !refresh) {
    throw new Error('پاسخ سرور ناقص بود؛ ورود مستقیم انجام نشد.');
  }

  const session: ImpersonationSession = {
    orgId: args.orgId,
    managerAccess,
    managerUserJson: window.localStorage.getItem(USER_KEY) ?? '',
    impRefresh: refresh,
    targetId,
    targetRole,
    targetName: args.targetName,
    startedAt: Date.now(),
  };

  // The swap: park the manager, wear the target.
  window.localStorage.setItem(ACCESS_KEY, access);
  window.localStorage.setItem(
    USER_KEY,
    JSON.stringify({
      id: targetId,
      username: args.targetName,
      role: targetRole,
      // Never let the onboarding gate bounce a borrowed session.
      is_profile_completed: true,
    }),
  );
  window.localStorage.setItem(ROLE_KEY, targetRole);
  window.sessionStorage.setItem(IMP_SESSION_KEY, JSON.stringify(session));
  window.dispatchEvent(new Event('user-profile-updated'));
  return session;
}

/**
 * Close the backend log row (best effort — an expired session closes itself
 * server-side by the 30-minute clamp) and restore the parked manager identity.
 */
export async function stopImpersonation(): Promise<void> {
  if (!isClient()) return;
  const session = getImpersonationSession();
  if (!session) return;

  try {
    // Same-origin proxy: the manager's own HttpOnly refresh cookie (never
    // swapped during impersonation) is the credential the stop view accepts.
    await fetch(`/api/organizations/${session.orgId}/impersonate/stop/`, {
      method: 'POST',
      credentials: 'include',
    });
  } catch {
    // Network hiccups must not trap the manager inside the borrowed session.
  }

  // Restore the manager wholesale.
  window.localStorage.setItem(ACCESS_KEY, session.managerAccess);
  if (session.managerUserJson) {
    window.localStorage.setItem(USER_KEY, session.managerUserJson);
    try {
      const restored = JSON.parse(session.managerUserJson) as { role?: string };
      if (restored?.role) window.localStorage.setItem(ROLE_KEY, restored.role);
    } catch {
      // Corrupt snapshot — the profile fetch on next load repairs the role.
    }
  }
  window.sessionStorage.removeItem(IMP_SESSION_KEY);
  window.dispatchEvent(new Event('user-profile-updated'));
}

export type StartImpersonationArgs = {
  orgId: number;
  /** The TARGET's user id (an advisor or student of the org). */
  targetUserId: number;
  targetName: string;
  targetRole: string;
};