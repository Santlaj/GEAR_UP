/**
 * Auth API functions — calls the existing backend auth endpoints.
 */

import { apiFetch } from './client';

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
}

/**
 * POST /api/auth/login
 */
export async function loginApi(
  email: string,
  password: string,
  portal: 'inspector' | 'admin',
): Promise<LoginResponse> {
  return apiFetch<LoginResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password, portal }),
  });
}

/**
 * GET /api/auth/me — returns the server-derived jurisdiction scope
 */
export async function fetchMe(): Promise<BackendScope> {
  return apiFetch<BackendScope>('/auth/me');
}
