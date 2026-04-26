type TokenResponse = {
  access: string
  refresh: string
}

export class ApiRequestError extends Error {
  status: number
  payload: unknown

  constructor(message: string, status: number, payload: unknown) {
    super(message)
    this.name = "ApiRequestError"
    this.status = status
    this.payload = payload
  }
}

export type AuthMeResponse = {
  id: number
  username: string
  first_name?: string
  last_name?: string
  email: string
  phone?: string | null
  avatar?: string | null
  role: string
  is_profile_completed: boolean
}

export type LoginPayload = {
  username: string
  password: string
  role?: string
}

export type RegisterPayload = {
  username: string
  password: string
  email?: string
  role?: string
  first_name?: string
  last_name?: string
  phone?: string
}

export type RegisterResponse = {
  user: AuthMeResponse
  tokens: TokenResponse
}

export type InviteLoginPayload = {
  code: string
  phone: string
}

const RAW_API = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, "")

if (!RAW_API) {
  console.warn("NEXT_PUBLIC_API_URL is not set")
}

const API_URL = RAW_API.endsWith("/api") ? RAW_API : `${RAW_API}/api`

const STORAGE_KEYS = {
  access: "ai_amooz_access",
  refresh: "ai_amooz_refresh",
  user: "ai_amooz_user",
}

function isClient() {
  return typeof window !== "undefined"
}

async function parseJson(res: Response) {
  const text = await res.text()
  if (!text) return null

  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}

function extractError(payload: any): string {
  if (!payload) return "خطا در ارتباط با سرور"

  if (typeof payload === "string") return payload

  if (payload.detail) return payload.detail

  if (payload.errors) {
    return Object.entries(payload.errors)
      .map(([k, v]) => `${k}: ${(v as string[]).join(", ")}`)
      .join(" | ")
  }

  return JSON.stringify(payload)
}

async function baseRequest<T>(
  path: string,
  options: RequestInit = {},
  retry = true
): Promise<T> {
  const headers = new Headers(options.headers)

  if (!headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json")
  }

  const tokens = getStoredTokens()

  if (tokens?.access && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${tokens.access}`)
  }

  const url = `${API_URL}${path}`

  let res: Response

  try {
    res = await fetch(url, {
      ...options,
      headers,
    })
  } catch {
    throw new Error("ارتباط با سرور برقرار نشد")
  }

  if (res.status === 401 && retry) {
    try {
      const newAccess = await refreshAccessToken()
      headers.set("Authorization", `Bearer ${newAccess}`)

      return baseRequest(path, { ...options, headers }, false)
    } catch {
      clearAuthStorage()
      throw new Error("جلسه شما منقضی شده است")
    }
  }

  const payload = await parseJson(res)

  if (!res.ok) {
    throw new ApiRequestError(
      extractError(payload),
      res.status,
      payload
    )
  }

  return payload as T
}

export function getStoredTokens(): TokenResponse | null {
  if (!isClient()) return null

  const access = localStorage.getItem(STORAGE_KEYS.access)
  const refresh = localStorage.getItem(STORAGE_KEYS.refresh)

  if (!access || !refresh) return null

  return { access, refresh }
}

export function persistTokens(tokens: TokenResponse) {
  if (!isClient()) return

  localStorage.setItem(STORAGE_KEYS.access, tokens.access)
  localStorage.setItem(STORAGE_KEYS.refresh, tokens.refresh)
}

export function persistUser(user: AuthMeResponse) {
  if (!isClient()) return

  localStorage.setItem(STORAGE_KEYS.user, JSON.stringify(user))
  localStorage.setItem("userRole", user.role)

  window.dispatchEvent(new Event("user-profile-updated"))
}

export function getStoredUser(): AuthMeResponse | null {
  if (!isClient()) return null

  const value = localStorage.getItem(STORAGE_KEYS.user)

  if (!value) return null

  try {
    return JSON.parse(value)
  } catch {
    return null
  }
}

export function clearAuthStorage() {
  if (!isClient()) return

  localStorage.removeItem(STORAGE_KEYS.access)
  localStorage.removeItem(STORAGE_KEYS.refresh)
  localStorage.removeItem(STORAGE_KEYS.user)
  localStorage.removeItem("userRole")
}

export async function login(
  payload: LoginPayload
): Promise<TokenResponse> {
  return baseRequest("/token/", {
    method: "POST",
    body: JSON.stringify(payload),
  })
}

export async function register(
  payload: RegisterPayload
): Promise<RegisterResponse> {
  return baseRequest("/auth/register/", {
    method: "POST",
    body: JSON.stringify(payload),
  })
}

export async function inviteLogin(
  payload: InviteLoginPayload
): Promise<RegisterResponse> {
  return baseRequest("/auth/invite-login/", {
    method: "POST",
    body: JSON.stringify(payload),
  })
}

export async function fetchMe(): Promise<AuthMeResponse> {
  return baseRequest("/accounts/me/", {
    method: "GET",
  })
}

export async function logout(): Promise<void> {
  const tokens = getStoredTokens()

  if (!tokens) return

  await baseRequest("/auth/logout/", {
    method: "POST",
    body: JSON.stringify({ refresh: tokens.refresh }),
  })

  clearAuthStorage()
}

export async function refreshAccessToken(): Promise<string> {
  const tokens = getStoredTokens()

  if (!tokens?.refresh) {
    clearAuthStorage()
    throw new Error("جلسه منقضی شده")
  }

  const res = await fetch(`${API_URL}/token/refresh/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      refresh: tokens.refresh,
    }),
  })

  const payload = await parseJson(res)

  if (!res.ok || !payload?.access) {
    clearAuthStorage()
    throw new Error("جلسه منقضی شده")
  }

  persistTokens({
    access: payload.access,
    refresh: tokens.refresh,
  })

  return payload.access
}
