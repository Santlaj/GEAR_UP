/**
 * Centralized API client for the PRAMAAN Admin Portal.
 * Handles JWT token injection, base URL resolution, and standardized error parsing.
 */

const metaEnv = (import.meta as any).env;

function resolveApiBase(): string {
  const raw = metaEnv && metaEnv.VITE_API_BASE_URL ? String(metaEnv.VITE_API_BASE_URL).trim().replace(/\/+$/, '') : '';
  if (!raw) return '/api';
  if (!raw.endsWith('/api') && !raw.endsWith('/api/v1')) {
    return `${raw}/api`;
  }
  return raw;
}

export const API_BASE = resolveApiBase();

export function getBackendOrigin(): string {
  if (API_BASE.startsWith('http://') || API_BASE.startsWith('https://')) {
    try {
      return new URL(API_BASE).origin;
    } catch {
      return '';
    }
  }
  return '';
}

export function resolveAssetUrl(path: string | null | undefined): string | null {
  if (!path) return null;
  if (path.startsWith('http://') || path.startsWith('https://') || path.startsWith('data:')) {
    return path;
  }
  const clean = path.startsWith('/') ? path.slice(1) : path;
  const origin = getBackendOrigin();
  return origin ? `${origin}/${clean}` : `/${clean}`;
}

export function getToken(): string | null {
  return localStorage.getItem('pramaan_admin_token') || localStorage.getItem('lmcs_token');
}

export function setToken(token: string): void {
  localStorage.setItem('pramaan_admin_token', token);
  localStorage.setItem('lmcs_token', token);
}

export function clearSession(): void {
  localStorage.removeItem('pramaan_admin_token');
  localStorage.removeItem('pramaan_admin_user');
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
 * - Attaches Bearer token
 * - Attaches X-Portal-Type: admin header
 * - Auto-parses FastAPI error responses
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
  headers.set('X-Portal-Type', 'admin');

  if (init.body && !(init.body instanceof FormData)) {
    if (!headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json');
    }
  }

  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  const url = `${API_BASE}${cleanPath}`;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 20000);
  let res: Response;
  try {
    res = await fetch(url, { ...init, headers, signal: init.signal || controller.signal });
  } catch (err: any) {
    clearTimeout(timeoutId);
    if (err.name === 'AbortError') {
      throw new ApiError(408, 'Request timed out. Please try again.');
    }
    throw err;
  } finally {
    clearTimeout(timeoutId);
  }

  if (!res.ok) {
    if (res.status === 401 && !path.includes('/auth/login')) {
      clearSession();
      throw new ApiError(401, 'Unauthorized or session expired.');
    }

    let detail = res.statusText;
    try {
      const body = await res.json();
      if (body.detail) {
        detail = typeof body.detail === 'string'
          ? body.detail
          : JSON.stringify(body.detail);
      }
    } catch {
      try {
        detail = await res.text();
      } catch {
        // use default statusText
      }
    }
    throw new ApiError(res.status, detail);
  }

  return res.json() as Promise<T>;
}
