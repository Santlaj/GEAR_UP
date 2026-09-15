import { apiFetch } from './client';
import { UserContext } from '../shared/schema';
import { BackendScope } from './auth';

export interface UserProfileResponse {
  user: UserContext;
  scope: BackendScope;
}

export async function fetchUserProfile(): Promise<UserProfileResponse> {
  return apiFetch<UserProfileResponse>('/users/me');
}
