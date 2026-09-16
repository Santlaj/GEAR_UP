import { fetchMe } from './auth';
import { UserContext } from '../shared/schema';
import { BackendScope } from './auth';

export interface UserProfileResponse {
  user: UserContext;
  scope: BackendScope;
}

/**
 * Fetches the current user profile.
 * Delegates to GET /api/auth/me (the unified auth endpoint).
 * The old /api/users/me endpoint is not used on production (Render).
 */
export async function fetchUserProfile(): Promise<UserProfileResponse> {
  const res = await fetchMe();
  return { user: res.user, scope: res.scope };
}
