import { apiFetch } from './client';

export interface InfractionRank {
  rank: number;
  clause: string;
  title: string;
  count: number;
  percentage: number;
}

export interface JurisdictionStat {
  district_id: string;
  name: string;
  audits: number;
  compliance_rate: number;
}

export interface DashboardStats {
  total_audits: number;
  compliance_rate: number;
  penal_dockets: number;
  total_fines_inr: number;
  infractions_ranking: InfractionRank[];
  jurisdiction_summary: JurisdictionStat[];
}

export async function fetchDashboardStats(): Promise<DashboardStats> {
  return apiFetch<DashboardStats>('/dashboard/stats');
}
