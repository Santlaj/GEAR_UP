/**
 * Centralized API client for the new_frontend inspector frontend.
 * All backend calls go through this module.
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

/**
 * Resolves static asset paths to displayable URLs.
 *
 * ── Production (Render / Supabase) ──
 * The old flow constructed URLs like `/captures/insp-pb-xxx/image.jpg`
 * which only worked on localhost where the /captures directory existed.
 * On Render, these return 404 because the filesystem is ephemeral.
 *
 * ── New flow ──
 * - If the path is already an absolute URL (http/https/data:), return as-is.
 *   This handles Supabase signed URLs returned by the images API.
 * - For relative paths (scans/xxx.jpg, captures/xxx/yyy.jpg), return null.
 *   The caller should use fetchScanImages() or getScanEvidenceImageUrl()
 *   which route through the backend API → Supabase.
 */
export function resolveAssetUrl(path: string | null | undefined): string | null {
  if (!path) return null;
  // Already an absolute URL (Supabase signed URL, data: URI, etc.)
  if (path.startsWith('http://') || path.startsWith('https://') || path.startsWith('data:')) {
    return path;
  }
  // Relative path like "scans/xxx.jpg" or "captures/insp-pb-xxx/img.jpg"
  // These MUST NOT be turned into direct file URLs — they don't exist on Render.
  // Return null so the caller falls back to the backend API evidence endpoint.
  return null;
}

export function getScanEvidenceImageUrl(scanId: string): string {
  return `${API_BASE}/scans/${encodeURIComponent(scanId)}/evidence-image`;
}

function getToken(): string | null {
  return localStorage.getItem('lmcs_token');
}

export function clearSession(): void {
  try {
    localStorage.removeItem('pramaan_auth_session');
    localStorage.removeItem('lmcs_token');
    localStorage.removeItem('lmcs_scope');
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    sessionStorage.clear();
  } catch (e) {
    console.error('Failed to clear session', e);
  }
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
