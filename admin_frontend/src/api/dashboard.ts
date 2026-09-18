/**
 * Dashboard API service for PRAMAAN Admin Frontend.
 */

import { apiFetch } from './client';

export interface InfractionRankingItem {
  rank: number;
  clause: string;
  title: string;
  count: number;
  percentage: number;
}

export interface JurisdictionSummaryItem {
  district_id: string;
  name: string;
  audits: number;
  compliance_rate: number;
}

export interface DashboardStatsResponse {
  total_audits: number;
  compliance_rate: number;
  penal_dockets: number;
  total_fines_inr: number;
  infractions_ranking: InfractionRankingItem[];
  jurisdiction_summary: JurisdictionSummaryItem[];
}

export interface MapPointResponse {
  scan_id: string;
  lat: number;
  lng: number;
  verdict: 'COMPLIANT' | 'NON_COMPLIANT' | 'NEEDS_REVIEW' | string;
  review_status: 'pending' | 'approved' | 'rejected' | 'needs_review' | string;
  product_name: string;
  date_scanned: string | null;
  inspector_id: string;
  district_id: string;
  report_no: string;
}

let statsCache: { time: number; data: DashboardStatsResponse } | null = null;

export async function fetchDashboardStats(): Promise<DashboardStatsResponse> {
  if (statsCache && Date.now() - statsCache.time < 15000) {
    return statsCache.data;
  }
  const data = await apiFetch<DashboardStatsResponse>('/dashboard/stats');
  statsCache = { time: Date.now(), data };
  return data;
}

export function invalidateDashboardStatsCache(): void {
  statsCache = null;
}
