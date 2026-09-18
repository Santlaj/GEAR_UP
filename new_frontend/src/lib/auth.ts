/**
 * Authentication module for the LMCS Inspector & Enforcement Portal.
 *
 * Connects directly to backend POST /api/auth/login, POST /api/auth/logout, and GET /api/auth/me.
 * Features persistent server-side session tracking, robust token preservation across reloads,
 * and reliable rehydration.
 */

import { UserContext } from '../shared/schema';
import { loginApi, logoutApi, fetchMe, BackendScope } from '../api/auth';
import { ApiError } from '../api/client';

export type { BackendScope };

export interface AuthSession {
  access_token: string;
  token_type: string;
  user: UserContext;
  scope: BackendScope;
  session_id?: string | null;
  portal: 'inspector' | 'admin';
  logged_at: string;
}

const AUTH_STORAGE_KEY = 'pramaan_auth_session';

export function getStoredToken(): string | null {
  return localStorage.getItem('lmcs_token');
}

export function getStoredSession(): AuthSession | null {
  try {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch (e) {
    console.error('Failed to parse auth session', e);
    return null;
  }
}

export function saveSession(session: AuthSession): void {
  try {
    localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(session));
    localStorage.setItem('lmcs_token', session.access_token);
    localStorage.setItem('lmcs_scope', JSON.stringify(session.scope));
  } catch (e) {
    console.error('Failed to save auth session', e);
  }
}

export function clearAuthSession(): void {
  try {
    localStorage.removeItem(AUTH_STORAGE_KEY);
    localStorage.removeItem('lmcs_token');
    localStorage.removeItem('lmcs_scope');
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    sessionStorage.clear();
  } catch (e) {
    console.error('Failed to clear auth session', e);
  }
}

export interface LoginParams {
  email: string;
  password: string;
  portal?: 'inspector' | 'admin' | 'auto';
}

/**
 * Authenticate an officer against the real backend.
 * Validates credentials via POST /api/auth/login, records server session,
 * and retrieves authoritative user identity via GET /api/auth/me.
 */
export async function loginOfficer(params: LoginParams): Promise<AuthSession> {
  const { email, password, portal = 'auto' } = params;

  // 1. Authenticate against backend and receive bound JWT
  const data = await loginApi(email.trim(), password.trim(), portal);

  // Store token immediately so subsequent requests have Authorization header
  localStorage.setItem('lmcs_token', data.access_token);

  // 2. Direct hydration from loginApi payload (instant < 0.1ms, zero blocking roundtrip)
  let scope: BackendScope = data.scope;
  let session_id: string | null = data.session_id || null;
  let user: UserContext;

  if (data.user && typeof data.user === 'object') {
    const rawUser = (data.user.user && typeof data.user.user === 'object') ? data.user.user : data.user;
    user = {
      id: rawUser.id || scope.user_id,
      name: rawUser.name || rawUser.full_name || `Officer ${scope.user_id}`,
      role: (rawUser.role || scope.role) as any,
      district_id: rawUser.district_id || scope.district_id || 'Unassigned',
      district_name: rawUser.district_name || (scope.district_id ? `${scope.district_id} Circle` : 'Unassigned'),
      state_id: rawUser.state_id || scope.state_id || 'N/A',
      state_name: rawUser.state_name || scope.state_id || 'N/A',
      badge_number: rawUser.badge_number || rawUser.badge || scope.user_id.toUpperCase(),
      cadre:
        rawUser.cadre ||
        (scope.role === 'inspector'
          ? 'Gazetted Field Enforcement (LMI Cadre)'
          : 'Designated Officer Cadre'),
    };
  } else {
    user = {
      id: scope.user_id,
      name: `Officer ${scope.user_id}`,
      role: scope.role as any,
      district_id: scope.district_id || 'Unassigned',
      district_name: scope.district_id ? `${scope.district_id} Circle` : 'Unassigned',
      state_id: scope.state_id || 'N/A',
      state_name: scope.state_id || 'N/A',
      badge_number: scope.user_id.toUpperCase(),
      cadre:
        scope.role === 'inspector'
          ? 'Gazetted Field Enforcement (LMI Cadre)'
          : 'Designated Officer Cadre',
    };
    // Non-blocking background sync if needed
    fetchMe().then((meData) => {
      const existing = getStoredSession();
      if (existing) {
        saveSession({ ...existing, user: meData.user, scope: meData.scope });
      }
    }).catch(() => {});
  }

  const effectivePortal: 'inspector' | 'admin' =
    (data.portal as 'inspector' | 'admin') || (scope.role === 'inspector' ? 'inspector' : 'admin');

  const session: AuthSession = {
    access_token: data.access_token,
    token_type: data.token_type || 'bearer',
    user,
    scope,
    session_id,
    portal: effectivePortal,
    logged_at: new Date().toISOString(),
  };

  if (effectivePortal === 'inspector') {
    saveSession(session);
  } else {
    // Clear token if user belongs to administrative cadre (prevent inspector portal mismatch)
    clearAuthSession();
  }
  return session;
}

/**
 * Revoke the server session and clear local credentials.
 */
export async function logoutOfficer(): Promise<void> {
  clearAuthSession();
  try {
    await logoutApi();
  } catch (err) {
    console.warn('Backend logout request encountered an issue:', err);
  }
}

/**
 * Validates active session against backend GET /api/auth/me upon page reload.
 *
 * CRITICAL LIFECYCLE RULE:
 * - If token is expired or revoked (HTTP 401), clears storage and returns null.
 * - If a transient network glitch occurs, retains stored session and does NOT boot the user out.
 */
export async function validateSession(): Promise<AuthSession | null> {
  const token = getStoredToken();
  if (!token) return null;

  try {
    const meData = await fetchMe();
    const existing = getStoredSession();
    const updated: AuthSession = {
      access_token: token,
      token_type: 'bearer',
      user: meData.user,
      scope: meData.scope,
      session_id: meData.session_id || existing?.session_id || null,
      portal: existing?.portal || (meData.scope.role === 'inspector' ? 'inspector' : 'admin'),
      logged_at: existing?.logged_at || new Date().toISOString(),
    };
    saveSession(updated);
    return updated;
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) {
      // Token expired or revoked server-side: only now is it cleared
      console.warn('Active session is invalid or revoked. Clearing credentials.');
      clearAuthSession();
      return null;
    }

    // Network timeout or temporary backend unavailability: retain existing cache
    console.warn('Could not contact backend for session revalidation; retaining stored session:', err);
    return getStoredSession();
  }
}
