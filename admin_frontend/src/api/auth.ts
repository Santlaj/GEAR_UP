/**
 * Authentication and session service for PRAMAAN Admin Frontend.
 */

import { apiFetch, setToken, clearSession } from './client';

export interface UserScope {
  role: 'district_officer' | 'state_admin' | 'national_admin' | 'auditor' | 'inspector' | string;
  user_id: string;
  district_id: string | null;
  state_id: string | null;
  scope_expires_at?: string | null;
  auditor_level?: string | null;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  scope: UserScope;
  session_id?: string | null;
  portal?: string;
}

export interface StoredUser {
  email: string;
  name: string;
  badge: string;
  role: string;
  district: string;
  state: string;
}

export function getStoredScope(): UserScope | null {
  try {
    const raw = localStorage.getItem('lmcs_scope');
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function setStoredScope(scope: UserScope): void {
  try {
    localStorage.setItem('lmcs_scope', JSON.stringify(scope));
  } catch {}
}

export async function loginAdmin(
  email: string,
  password: string,
  portal: string = 'auto',
): Promise<LoginResponse> {
  const data = await apiFetch<LoginResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({
      email: email.trim(),
      password: password.trim(),
      portal,
    }),
  });

  if (data && data.access_token) {
    setToken(data.access_token);
    if (data.scope) {
      setStoredScope(data.scope);
    }
    if ((data as any).user) {
      try {
        localStorage.setItem('pramaan_admin_user', JSON.stringify((data as any).user));
      } catch {}
    }
  }
  return data;
}

export async function fetchCurrentScope(): Promise<UserScope | null> {
  const token = getToken();
  if (!token) return null;
  try {
    return await apiFetch<UserScope>('/auth/me');
  } catch {
    return null;
  }
}

export function logoutAdmin(): void {
  const token = getToken();
  if (token) {
    apiFetch('/auth/logout', { method: 'POST' }).catch(() => {
      // Best-effort remote revocation
    });
  }
  clearSession();
}
