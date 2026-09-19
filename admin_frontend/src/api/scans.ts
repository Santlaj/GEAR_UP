/**
 * Scans & Reports API service for PRAMAAN Admin Frontend.
 */

import { apiFetch, API_BASE, getToken } from './client';

export interface BackendDeclaration {
  field_name: string;
  display_name: string;
  detected_value: string | null;
  status: 'compliant' | 'non_compliant' | 'missing' | 'ambiguous' | string;
  confidence: number;
  infraction_rule?: string | null;
  rule_citation?: string | null;
  rejection_reason?: string | null;
  statutory_basis?: string | null;
}

export interface BackendScanRecord {
  scan_id: string;
  report_no: string;
  report_version: number;
  inspector_id: string;
  district_id: string;
  state_id: string;
  date_scanned: string;
  overall_verdict: 'COMPLIANT' | 'NON_COMPLIANT' | 'NEEDS_REVIEW' | string;
  review_status: 'pending' | 'approved' | 'rejected' | 'needs_review' | string;
  product: {
    name: string;
    category?: string;
    manufacturer?: string;
    net_quantity?: string;
    mrp?: string;
    barcode?: string;
    batch_no?: string;
  };
  declarations: BackendDeclaration[];
  non_compliant_fields: string[];
  missing_fields: string[];
  infractions_count: number;
  total_fine_inr: number;
  images: Array<{
    url: string;
    filename?: string;
    panel?: string;
  }>;
  gps?: {
    lat: number;
    lng: number;
    accuracy?: number;
  } | null;
  notice_status?: string | null;
  hash_chain?: {
    current_hash: string;
    previous_hash: string | null;
  };
}

export interface ReviewResponse {
  scan_id: string;
  review_status: string;
  overall_verdict: string;
}

export interface FetchScansOptions {
  reviewStatus?: string;
  districtId?: string;
  stateId?: string;
  inspectorId?: string;
}

const scanCache = new Map<string, { time: number; data: BackendScanRecord[] }>();

export function invalidateFrontendScanCache(): void {
  scanCache.clear();
}

export async function fetchScans(
  optionsOrReviewStatus?: string | FetchScansOptions
): Promise<BackendScanRecord[]> {
  const params = new URLSearchParams();
  if (typeof optionsOrReviewStatus === 'string') {
    if (optionsOrReviewStatus) {
      params.set('review_status', optionsOrReviewStatus);
    }
  } else if (optionsOrReviewStatus) {
    if (optionsOrReviewStatus.reviewStatus) params.set('review_status', optionsOrReviewStatus.reviewStatus);
    if (optionsOrReviewStatus.districtId) params.set('district_id', optionsOrReviewStatus.districtId);
    if (optionsOrReviewStatus.stateId) params.set('state_id', optionsOrReviewStatus.stateId);
    if (optionsOrReviewStatus.inspectorId) params.set('inspector_id', optionsOrReviewStatus.inspectorId);
  }
  const query = params.toString() ? `?${params.toString()}` : '';
  const cacheKey = `/scans${query}`;
  const hit = scanCache.get(cacheKey);
  if (hit && Date.now() - hit.time < 15000) {
    return hit.data;
  }
  const data = await apiFetch<BackendScanRecord[]>(`/scans${query}`);
  scanCache.set(cacheKey, { time: Date.now(), data });
  return data;
}

export function getReportPdfUrl(scanId: string): string {
  return `${API_BASE}/scans/${encodeURIComponent(scanId)}/report.pdf`;
}

export function getReportDocxUrl(scanId: string): string {
  return `${API_BASE}/scans/${encodeURIComponent(scanId)}/report.docx`;
}

/**
 * Downloads official WeasyPrint PDF report via authenticated fetch and Blob URL.
 * Strictly requires the authoritative backend scan_id.
 * Automatically injects Authorization: Bearer header and revokes object URL after download.
 */
export async function downloadReportPdf(scanId: string, filename?: string): Promise<void> {
  if (!scanId || !scanId.trim()) {
    throw new Error('Download aborted: Valid backend scan_id is missing from this record.');
  }
  const token = getToken();
  const url = getReportPdfUrl(scanId);
  const res = await fetch(url, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) {
    throw new Error(`Failed to download official PDF report (HTTP ${res.status}: ${res.statusText || 'Access Denied or Not Found'})`);
  }
  const blob = await res.blob();
  const objectUrl = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = objectUrl;
  a.download = filename || `${scanId.replace(/[\/\\?%*:|"<>]/g, '_')}_Official_Gazette.pdf`;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(objectUrl);
  document.body.removeChild(a);
}

/**
 * Downloads official DOCX report via authenticated fetch and Blob URL.
 * Strictly requires the authoritative backend scan_id.
 * Automatically injects Authorization: Bearer header and revokes object URL after download.
 */
export async function downloadReportDocx(scanId: string, filename?: string): Promise<void> {
  if (!scanId || !scanId.trim()) {
    throw new Error('Download aborted: Valid backend scan_id is missing from this record.');
  }
  const token = getToken();
  const url = getReportDocxUrl(scanId);
  const res = await fetch(url, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) {
    throw new Error(`Failed to download official DOCX report (HTTP ${res.status}: ${res.statusText || 'Access Denied or Not Found'})`);
  }
  const blob = await res.blob();
  const objectUrl = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = objectUrl;
  a.download = filename || `${scanId.replace(/[\/\\?%*:|"<>]/g, '_')}_Official_Report.docx`;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(objectUrl);
  document.body.removeChild(a);
}
