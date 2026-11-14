"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Shell } from "@/components/Shell";
import { apiFetch, getToken } from "@/lib/api";

type Agent = { agent_id: string; name: string; description: string; status: string };

export default function BrainPage() {
  const router = useRouter();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [intent, setIntent] = useState("find_leads");
  const [result, setResult] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!getToken()) {
      router.replace("/");
      return;
    }
    apiFetch<{ agents: Agent[] }>("/api/v1/brain/agents")
      .then((data) => setAgents(data.agents))
      .catch((err) => setError(err.message));
  }, [router]);

  async function routeIntent(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const data = await apiFetch("/api/v1/brain/route", {
        method: "POST",
        body: JSON.stringify({ intent, payload: {} }),
      });
      setResult(JSON.stringify(data, null, 2));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Route failed");
    }
  }

  return (
    <Shell>
      <div className="stack">
        <div className="panel">
          <div className="brand-mark">ORCHESTRATOR</div>
          <h1 style={{ margin: "0.2rem 0" }}>Central AI Brain</h1>
          <p className="muted">Routes intents to agents and enforces the approval matrix.</p>
          <form className="stack" onSubmit={routeIntent} style={{ marginTop: "1rem" }}>
            <div className="field">
              <label htmlFor="intent">Intent</label>
              <input id="intent" value={intent} onChange={(e) => setIntent(e.target.value)} />
            </div>
            <button className="btn primary" type="submit">
              Route intent
            </button>
          </form>
          {error ? <p className="error">{error}</p> : null}
          {result ? (
            <pre className="mono" style={{ marginTop: "1rem", whiteSpace: "pre-wrap" }}>
              {result}
            </pre>
          ) : null}
        </div>
        <div className="panel">
          <h2>Registered agents</h2>
          <div className="agent-list">
            {agents.map((a) => (
              <div className="agent-item" key={a.agent_id}>
                <div>
                  <strong>{a.name}</strong>
                  <div className="muted">{a.description}</div>
                </div>
                <span className={`badge ${a.status === "ready" ? "ok" : "stub"}`}>{a.status}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </Shell>
  );
}
