import React, { useState } from "react";
import { Navigate, Route, Routes, useNavigate } from "react-router-dom";
import {
  getScope,
  getToken,
  login,
  setSession,
} from "./services/scansApi";
import { DistrictAdminDashboard } from "./pages/DistrictAdminDashboard";

function LoginPage() {
  const nav = useNavigate();
  const [email, setEmail] = useState("district@lmcs.gov.in");
  const [password, setPassword] = useState("district-demo");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const res = await login(email, password);
      if (res.scope.role === "inspector") {
        throw new Error("Inspectors must use the mobile Inspector Capture portal.");
      }
      setSession(res.access_token, res.scope);
      nav("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="login">
      <div style={{ marginBottom: "var(--space-4)" }}>
        <p className="brand-eyebrow">Legal Metrology Division</p>
        <h1 className="brand" style={{ fontSize: "var(--text-xl)" }}>
          LMCS Supervisory Portal
        </h1>
        <p className="sub">
          District Officers, State Administrators &amp; Statutory Auditors
        </p>
      </div>

      <form onSubmit={onSubmit} style={{ display: "grid", gap: "var(--space-3)" }}>
        <label style={{ display: "grid", gap: "var(--space-1)", fontWeight: 600 }}>
          Official Email
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="username"
          />
        </label>
        <label style={{ display: "grid", gap: "var(--space-1)", fontWeight: 600 }}>
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete="current-password"
          />
        </label>
        {error && <div className="state-error">{error}</div>}
        <button type="submit" className="btn btn-primary" disabled={submitting}>
          {submitting ? "Authenticating…" : "Sign In to Administrative Portal"}
        </button>
      </form>
    </div>
  );
}

function Private({ children }: { children: React.ReactNode }) {
  if (!getToken() || !getScope() || getScope()?.role === "inspector") {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <Private>
            <DistrictAdminDashboard />
          </Private>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
