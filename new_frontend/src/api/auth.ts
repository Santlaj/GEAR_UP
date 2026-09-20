/**
 * Auth API functions — calls the backend auth endpoints.
 */

import { apiFetch } from './client';
import { UserContext } from '../shared/schema';

export interface BackendScope {
  role: string;
  user_id: string;
  district_id: string | null;
  state_id: string | null;
  scope_expires_at: string | null;
  auditor_level?: string | null;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  scope: BackendScope;
  session_id?: string | null;
  portal?: string;
  user?: any;
}

export interface AuthMeResponse {
  user: UserContext;
  scope: BackendScope;
  session_id?: string | null;
  role?: string;
  user_id?: string;
}

/**
 * POST /api/auth/login
 */
export async function loginApi(
  email: string,
  password: string,
  portal: 'inspector' | 'admin' | 'auto' = 'auto',
  captchaToken?: string | null,
): Promise<LoginResponse> {
  return apiFetch<LoginResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({
      email,
      password,
      portal,
      captcha_token: captchaToken || undefined,
    }),
  });
}

/**
 * POST /api/auth/logout — revokes session on the server
 */
export async function logoutApi(): Promise<{ success: boolean; message: string }> {
  try {
    return await apiFetch<{ success: boolean; message: string }>('/auth/logout', {
      method: 'POST',
    });
  } catch {
    return { success: true, message: 'Local session cleared' };
  }
}

/**
 * GET /api/auth/me — returns authoritative user profile, session identity, and jurisdiction scope
 */
export async function fetchMe(): Promise<AuthMeResponse> {
  return apiFetch<AuthMeResponse>('/auth/me');
}
