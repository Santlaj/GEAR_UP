/**
 * Centralized API client for the mm inspector frontend.
 * All backend calls go through this module.
 *
 * Uses the Vite dev proxy (/api → http://127.0.0.1:8000)
 * so no hardcoded backend URL is needed.
 */

function getToken(): string | null {
  return localStorage.getItem('lmcs_token');
}

export function clearSession(): void {
  localStorage.removeItem('pramaan_auth_session');
  localStorage.removeItem('lmcs_token');
  localStorage.removeItem('lmcs_scope');
}

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

/**
 * Generic API fetch wrapper.
 * - Attaches Bearer token from localStorage
 * - Handles JSON and FormData bodies
 * - Parses FastAPI error responses
 * - Auto-clears session on 401
 */
export async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);

  const token = getToken();
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  // Don't set Content-Type for FormData — browser sets it with boundary
  if (init.body && !(init.body instanceof FormData)) {
    if (!headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json');
    }
  }

  const res = await fetch(`/api${path}`, { ...init, headers });

  if (!res.ok) {
    // Handle 401 without infinite page reload loops
    if (res.status === 401 && !path.includes('/auth/login')) {
      clearSession();
      throw new ApiError(401, 'Unauthorized or session expired.');
    }

    // Parse FastAPI error detail
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (body.detail) {
        detail = typeof body.detail === 'string'
          ? body.detail
          : JSON.stringify(body.detail);
      }
    } catch {
      // If JSON parsing fails, try text
      try {
        detail = await res.text();
      } catch {
        // Use statusText
      }
    }
    throw new ApiError(res.status, detail);
  }

  return res.json() as Promise<T>;
}
