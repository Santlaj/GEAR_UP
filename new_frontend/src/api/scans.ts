/**
 * Scans API functions — calls the existing backend scan endpoints.
 */

import { apiFetch, API_BASE } from './client';
import { ScanRecord } from '../shared/schema';

/**
 * POST /api/scans — submit a new scan with image(s).
 * Expects FormData with: gps_lat, gps_lng, source, images[], geometry_json, source_url?
 */
export async function submitScan(formData: FormData): Promise<ScanRecord> {
  return apiFetch<ScanRecord>('/scans', {
    method: 'POST',
    body: formData,
  });
}

/**
 * GET /api/scans — list scans scoped to the authenticated user's jurisdiction.
 */
export async function fetchScans(): Promise<ScanRecord[]> {
  return apiFetch<ScanRecord[]>('/scans');
}

/**
 * GET /api/scans/{scanId}/versions — list all versions of a scan.
 */
export async function fetchScanVersions(scanId: string): Promise<ScanRecord[]> {
  return apiFetch<ScanRecord[]>(`/scans/${encodeURIComponent(scanId)}/versions`);
}

/**
 * POST /api/scans/{scanId}/re-evaluate — re-evaluate a scan through the backend ComplianceEngine.
 */
export async function reevaluateScan(scanId: string): Promise<ScanRecord> {
  return apiFetch<ScanRecord>(`/scans/${encodeURIComponent(scanId)}/re-evaluate`, {
    method: 'POST',
  });
}

/**
 * POST /api/scans/{scanId}/declarations/{fieldName}/confirm-missing
 */
export async function confirmFieldMissing(
  scanId: string,
  fieldName: string,
  reason: string,
): Promise<ScanRecord> {
  return apiFetch<ScanRecord>(
    `/scans/${encodeURIComponent(scanId)}/declarations/${encodeURIComponent(fieldName)}/confirm-missing`,
    {
      method: 'POST',
      body: JSON.stringify({ reason }),
    },
  );
}

/**
 * Returns the direct URL to download the authentic WeasyPrint PDF report
 */
export function getScanPdfUrl(scanId: string): string {
  return `${API_BASE}/scans/${encodeURIComponent(scanId)}/report.pdf`;
}

/**
 * Returns the direct URL to download the authentic DOCX report
 */
export function getScanDocxUrl(scanId: string): string {
  return `${API_BASE}/scans/${encodeURIComponent(scanId)}/report.docx`;
}

/**
 * Returns the direct URL to view the authentic print-ready Gazette HTML report
 */
export function getScanHtmlUrl(scanId: string): string {
  return `${API_BASE}/scans/${encodeURIComponent(scanId)}/report.html`;
}

/**
 * Triggers a download of the PDF report by fetching as blob.
 * Avoids browser navigation drops and handles errors gracefully.
 */
export async function downloadScanPdf(scanId: string, filename: string): Promise<void> {
  const token = localStorage.getItem('lmcs_token');
  const url = getScanPdfUrl(scanId);
  const res = await fetch(url, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) {
    throw new Error(`Failed to download PDF report (HTTP ${res.status})`);
  }
  const blob = await res.blob();
  const objectUrl = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = objectUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(objectUrl);
  document.body.removeChild(a);
}

/**
 * Triggers a download of the DOCX report by fetching as blob.
 */
export async function downloadScanDocx(scanId: string, filename: string): Promise<void> {
  const token = localStorage.getItem('lmcs_token');
  const url = getScanDocxUrl(scanId);
  const res = await fetch(url, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) {
    throw new Error(`Failed to download DOCX report (HTTP ${res.status})`);
  }
  const blob = await res.blob();
  const objectUrl = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = objectUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(objectUrl);
  document.body.removeChild(a);
}

export interface ScanVerificationResult {
  valid: boolean;
  scan_id: string;
  report_no: string;
  report_version: number;
  report_hash: string;
  previous_report_hash: string | null;
  date_scanned: string;
  qr_payload: string;
  statutory_act: string;
  chain_verified: boolean;
}

/**
 * GET /api/scans/{scanId}/verify — verify cryptographic integrity from the server
 */
export async function verifyScanApi(scanId: string): Promise<ScanVerificationResult> {
  return apiFetch<ScanVerificationResult>(`/scans/${encodeURIComponent(scanId)}/verify`);
}

export interface IssueNoticePayload {
  recipient: string;
  fine_amount: number;
  reason: string;
}

export interface IssueNoticeResponse {
  success: boolean;
  notice_ref: string;
  scan_id: string;
  report_no: string;
  recipient: string;
  fine_amount: number;
  reason: string;
  statutory_clause: string;
  issued_at: string;
  status: string;
}

/**
 * POST /api/scans/{scanId}/notice — issue official compounding notice
 */
export async function issueNoticeApi(
  scanId: string,
  payload: IssueNoticePayload,
): Promise<IssueNoticeResponse> {
  return apiFetch<IssueNoticeResponse>(`/scans/${encodeURIComponent(scanId)}/notice`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

