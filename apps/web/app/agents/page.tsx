"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Shell } from "@/components/Shell";
import { apiFetch, getToken } from "@/lib/api";

type Agent = {
  agent_id: string;
  name: string;
  description: string;
  status: string;
  capabilities?: string[];
};

export default function AgentsPage() {
  const router = useRouter();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selected, setSelected] = useState<string>("lead_crm");
  const [intent, setIntent] = useState("list_leads");
  const [payload, setPayload] = useState("{}");
  const [result, setResult] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!getToken()) {
      router.replace("/");
      return;
    }
    apiFetch<{ agents: Agent[] }>("/api/v1/agents")
      .then((data) => {
        setAgents(data.agents);
        if (data.agents[0]) {
          setSelected(data.agents[0].agent_id);
          setIntent(data.agents[0].capabilities?.[0] || "list_leads");
        }
      })
      .catch((err) => setError(err.message));
  }, [router]);

  async function invoke(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const parsed = JSON.parse(payload || "{}");
      const data = await apiFetch(`/api/v1/agents/${selected}/invoke`, {
        method: "POST",
        body: JSON.stringify({ intent, payload: parsed }),
      });
      setResult(JSON.stringify(data, null, 2));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invoke failed");
    }
  }

  const current = agents.find((a) => a.agent_id === selected);

  return (
    <Shell>
      <div className="stack">
        <div className="panel">
          <div className="brand-mark">MODULES</div>
          <h1 style={{ margin: "0.2rem 0" }}>Agents 2–12</h1>
          <p className="muted">Real modules wired through the Central Brain (approval gating included).</p>
          {error ? <p className="error">{error}</p> : null}
          <div className="agent-list">
            {agents.map((a, idx) => (
              <button
                key={a.agent_id}
                type="button"
                className="agent-item"
                style={{ cursor: "pointer", textAlign: "left", width: "100%", background: selected === a.agent_id ? "rgba(61,214,198,0.08)" : undefined }}
                onClick={() => {
                  setSelected(a.agent_id);
                  setIntent(a.capabilities?.[0] || "");
                }}
              >
                <div>
                  <strong>
                    {idx + 2} · {a.name}
                  </strong>
                  <div className="muted">{a.description}</div>
                </div>
                <span className={`badge ${a.status === "ready" ? "ok" : "stub"}`}>{a.status}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="panel">
          <h2>Invoke {current?.name || selected}</h2>
          <p className="muted mono">{(current?.capabilities || []).join(" · ")}</p>
          <form className="stack" onSubmit={invoke}>
            <div className="field">
              <label>Intent</label>
              <input value={intent} onChange={(e) => setIntent(e.target.value)} />
            </div>
            <div className="field">
              <label>Payload JSON</label>
              <textarea rows={6} value={payload} onChange={(e) => setPayload(e.target.value)} />
            </div>
            <button className="btn primary" type="submit">
              Route via Brain
            </button>
          </form>
          {result ? (
            <pre className="mono" style={{ marginTop: "1rem", whiteSpace: "pre-wrap" }}>
              {result}
            </pre>
          ) : null}
        </div>
      </div>
    </Shell>
  );
}
