/**
 * Authentication and session service for PRAMAAN Admin Frontend.
 */

import { apiFetch, setToken, clearSession, getToken } from './client';

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
  id?: string;
  email?: string;
  name?: string;
  full_name?: string;
  badge?: string;
  badge_number?: string;
  role?: string;
  district?: string;
  district_id?: string;
  district_name?: string;
  state?: string;
  state_id?: string;
  state_name?: string;
  cadre?: string;
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

export function getStoredUser(): StoredUser | null {
  try {
    const raw = localStorage.getItem('pramaan_admin_user');
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function setStoredUser(user: StoredUser): void {
  try {
    localStorage.setItem('pramaan_admin_user', JSON.stringify(user));
  } catch {}
}

export function formatOfficerName(
  user?: StoredUser | null,
  scope?: UserScope | null
): string {
  const rawName = user?.full_name || user?.name;
  if (rawName && rawName.trim()) {
    const trimmed = rawName.trim();
    if (/^(sh\.|shri|smt\.|smt|dr\.|dr|mr\.|mr|ms\.)/i.test(trimmed)) {
      return trimmed;
    }
    return `Sh. ${trimmed}`;
  }

  const email = user?.email;
  if (email && email.includes('@')) {
    const localPart = email.split('@')[0].replace(/[._0-9]+/g, ' ').trim();
    if (localPart) {
      const capitalized = localPart
        .split(' ')
        .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
        .join(' ');
      return `Sh. ${capitalized}`;
    }
  }

  const role = user?.role || scope?.role;
  if (role) {
    if (role === 'national_admin') return 'Sh. National Controller';
    if (role === 'state_admin') return 'Sh. State Controller';
    if (role === 'district_officer') return 'Sh. District Controller';
  }

  return 'Authorized Officer';
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
      setStoredUser((data as any).user);
    }
  }
  return data;
}

export async function fetchCurrentScope(): Promise<UserScope | null> {
  const token = getToken();
  if (!token) return null;
  try {
    const data = await apiFetch<any>('/auth/me');
    if (data && data.user) {
      setStoredUser(data.user);
    }
    if (data && data.scope) {
      setStoredScope(data.scope);
      return data.scope;
    }
    return data as UserScope;
  } catch {
    return null;
  }
}

export async function fetchCurrentUser(): Promise<StoredUser | null> {
  const token = getToken();
  const stored = getStoredUser();
  if (!token) return stored;
  try {
    const data = await apiFetch<any>('/auth/me');
    if (data && data.user) {
      setStoredUser(data.user);
      return data.user;
    }
    return stored;
  } catch {
    return stored;
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
