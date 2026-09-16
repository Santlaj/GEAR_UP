import { apiFetch } from './client';

export interface ScanImageItem {
  id: string;
  role: 'front' | 'back' | 'side' | 'evidence' | string;
  original_filename?: string;
  mime_type?: string;
  file_size?: number;
  url: string | null;
  expires_in: number;
  storage_provider: string;
  created_at?: string;
}

export interface ScanImagesResponse {
  scan_id: string;
  report_no: string;
  images: ScanImageItem[];
}

export async function fetchScanImages(scanId: string): Promise<ScanImageItem[]> {
  try {
    const res = await apiFetch<ScanImagesResponse>(`/scans/${encodeURIComponent(scanId)}/images`);
    return res.images || [];
  } catch (err) {
    console.warn(`Failed to fetch images for scan ${scanId}:`, err);
    return [];
  }
}
