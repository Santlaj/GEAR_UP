import type { JurisdictionScope, OverallVerdict, ScanRecord } from "../../../shared/schema";

const PORTAL_HOST = "localhost:5174";

export function getToken() {
  return localStorage.getItem("lmcs_admin_token");
}
export function getScope(): JurisdictionScope | null {
  const raw = localStorage.getItem("lmcs_admin_scope");
  return raw ? (JSON.parse(raw) as JurisdictionScope) : null;
}
export function setSession(token: string, scope: JurisdictionScope) {
  localStorage.setItem("lmcs_admin_token", token);
  localStorage.setItem("lmcs_admin_scope", JSON.stringify(scope));
}
export function clearSession() {
  localStorage.removeItem("lmcs_admin_token");
  localStorage.removeItem("lmcs_admin_scope");
}

async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("X-Portal-Host", PORTAL_HOST);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(`/api${path}`, { ...init, headers });
  if (!res.ok) throw new Error(await res.text());
  return res.json() as Promise<T>;
}

export async function login(email: string, password: string) {
  return api<{ access_token: string; scope: JurisdictionScope }>("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, portal: "admin" }),
  });
}

export async function listScans(foreignDistrict = "D-SHOULD-IGNORE") {
  // Foreign district must be overridden server-side.
  return api<ScanRecord[]>(`/scans?district_id=${encodeURIComponent(foreignDistrict)}`);
}

export async function overrideScan(scanId: string, new_verdict: OverallVerdict, reason: string) {
  return api<ScanRecord>(`/scans/${scanId}/override`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ new_verdict, reason, district_id: "D-FOREIGN" }),
  });
}
