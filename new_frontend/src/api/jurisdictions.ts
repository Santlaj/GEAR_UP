import { apiFetch } from './client';

export interface JurisdictionCircle {
  district_id: string;
  name: string;
  state_id: string;
  state_name: string;
}

export async function fetchJurisdictions(): Promise<JurisdictionCircle[]> {
  return apiFetch<JurisdictionCircle[]>('/jurisdictions');
}
