"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Shell } from "@/components/Shell";
import { apiFetch, getToken } from "@/lib/api";

type Approval = {
  id: string;
  action_key: string;
  agent_id: string;
  intent: string;
  status: string;
  created_at?: string;
};

export default function ApprovalsPage() {
  const router = useRouter();
  const [items, setItems] = useState<Approval[]>([]);
  const [otp, setOtp] = useState<Record<string, string>>({});
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [monitor, setMonitor] = useState("");

  async function refresh() {
    const data = await apiFetch<{ approvals: Approval[] }>("/api/v1/approvals/pending");
    setItems(data.approvals);
  }

  useEffect(() => {
    if (!getToken()) {
      router.replace("/");
      return;
    }
    refresh().catch((err) => setError(err.message));
  }, [router]);

  async function decide(id: string, approve: boolean) {
    setError("");
    setMessage("");
    try {
      const data = await apiFetch(`/api/v1/approvals/${id}/decide`, {
        method: "POST",
        body: JSON.stringify({ approve, otp_code: otp[id] || null, execute: true }),
      });
      setMessage(JSON.stringify(data, null, 2));
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Decide failed");
    }
  }

  async function runMonitor() {
    try {
      const data = await apiFetch("/api/v1/monitor/check", { method: "POST", body: "{}" });
      setMonitor(JSON.stringify(data, null, 2));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Monitor failed");
    }
  }

  return (
    <Shell>
      <div className="stack">
        <div className="panel">
          <div className="brand-mark">OWNER CONTROL</div>
          <h1 style={{ margin: "0.2rem 0" }}>Approvals + OTP</h1>
          <p className="muted">Side-effect intents queue here; confirm with OTP-to-owner flow.</p>
          {error ? <p className="error">{error}</p> : null}
          <div className="agent-list" style={{ marginTop: "1rem" }}>
            {items.length === 0 ? <p className="muted">No pending approvals.</p> : null}
            {items.map((item) => (
              <div className="agent-item" key={item.id} style={{ flexDirection: "column", alignItems: "stretch" }}>
                <div className="row" style={{ justifyContent: "space-between" }}>
                  <div>
                    <strong>{item.intent}</strong>
                    <div className="muted mono">
                      {item.agent_id} · {item.action_key}
                    </div>
                  </div>
                  <span className="badge warn">{item.status}</span>
                </div>
                <div className="row" style={{ marginTop: "0.65rem" }}>
                  <input
                    placeholder="OTP code"
                    value={otp[item.id] || ""}
                    onChange={(e) => setOtp((v) => ({ ...v, [item.id]: e.target.value }))}
                    style={{ flex: 1, minWidth: 120 }}
                  />
                  <button className="btn primary" type="button" onClick={() => decide(item.id, true)}>
                    Approve + execute
                  </button>
                  <button className="btn" type="button" onClick={() => decide(item.id, false)}>
                    Reject
                  </button>
                </div>
              </div>
            ))}
          </div>
          {message ? (
            <pre className="mono" style={{ marginTop: "1rem", whiteSpace: "pre-wrap" }}>
              {message}
            </pre>
          ) : null}
        </div>

        <div className="panel">
          <h2>API subscription monitor</h2>
          <p className="muted">Self-checks wizard credentials for LLM, Twilio, SMTP, social, logistics.</p>
          <button className="btn" type="button" onClick={runMonitor}>
            Run checks
          </button>
          {monitor ? (
            <pre className="mono" style={{ marginTop: "1rem", whiteSpace: "pre-wrap" }}>
              {monitor}
            </pre>
          ) : null}
        </div>
      </div>
    </Shell>
  );
}
