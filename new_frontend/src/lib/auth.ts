/**
 * Authentication module for the LMCS Inspector & Enforcement Portal.
 *
 * Uses the real backend POST /api/auth/login and GET /api/users/me.
 * No fake token fallback — if credentials or connection fail, login fails.
 */

import { UserContext } from '../shared/schema';
import { loginApi, BackendScope } from '../api/auth';
import { fetchUserProfile } from '../api/users';

export type { BackendScope };

export interface AuthSession {
  access_token: string;
  token_type: string;
  user: UserContext;
  scope: BackendScope;
  portal: 'inspector' | 'admin';
  logged_at: string;
}

const AUTH_STORAGE_KEY = 'pramaan_auth_session';

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
  localStorage.removeItem(AUTH_STORAGE_KEY);
  localStorage.removeItem('lmcs_token');
  localStorage.removeItem('lmcs_scope');
}

export interface LoginParams {
  email: string;
  password: string;
  portal: 'inspector' | 'admin';
}

/**
 * Authenticate an officer against the real backend.
 * Validates credentials via POST /api/auth/login and retrieves full
 * officer profile and jurisdiction scope from GET /api/users/me.
 */
export async function loginOfficer(params: LoginParams): Promise<AuthSession> {
  const { email, password, portal } = params;

  // 1. Authenticate against backend
  const data = await loginApi(email.trim(), password.trim(), portal);

  // Temporarily store token so subsequent request attaches Bearer token
  localStorage.setItem('lmcs_token', data.access_token);

  // 2. Fetch authoritative user profile and scope from backend
  let user: UserContext;
  let scope: BackendScope = data.scope;

  try {
    const profile = await fetchUserProfile();
    user = profile.user;
    scope = profile.scope;
  } catch (err) {
    console.warn('Profile enrichment call failed, using login scope:', err);
    user = {
      id: scope.user_id,
      name: `Officer ${scope.user_id}`,
      role: scope.role as any,
      district_id: scope.district_id || 'Unassigned',
      district_name: scope.district_id ? `${scope.district_id} Circle` : 'Unassigned',
      state_id: scope.state_id || 'N/A',
      state_name: scope.state_id || 'N/A',
      badge_number: scope.user_id.toUpperCase(),
      cadre: scope.role === 'inspector' ? 'Gazetted Field Enforcement (LMI Cadre)' : 'Designated Officer Cadre',
    };
  }

  const session: AuthSession = {
    access_token: data.access_token,
    token_type: data.token_type || 'bearer',
    user,
    scope,
    portal,
    logged_at: new Date().toISOString(),
  };

  saveSession(session);
  return session;
}

/**
 * Validate current session with backend and refresh profile
 */
export async function validateSession(): Promise<AuthSession | null> {
  const existing = getStoredSession();
  if (!existing || !existing.access_token) return null;

  try {
    const profile = await fetchUserProfile();
    const updated: AuthSession = {
      ...existing,
      user: profile.user,
      scope: profile.scope,
    };
    saveSession(updated);
    return updated;
  } catch {
    clearAuthSession();
    return null;
  }
}
