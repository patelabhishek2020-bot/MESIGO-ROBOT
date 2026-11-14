"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Shell } from "@/components/Shell";
import { apiFetch, getToken } from "@/lib/api";

type User = {
  username: string;
  full_name?: string;
  is_owner: boolean;
  must_change_password: boolean;
  roles: string[];
};

type WizardStatus = {
  completed: boolean;
  current_step: string;
  completed_steps: string[];
};

type BrainStatus = {
  brain: string;
  agents: { agent_id: string; name: string; status: string }[];
};

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [wizard, setWizard] = useState<WizardStatus | null>(null);
  const [brain, setBrain] = useState<BrainStatus | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!getToken()) {
      router.replace("/");
      return;
    }
    (async () => {
      try {
        const [me, wiz, br] = await Promise.all([
          apiFetch<User>("/api/v1/auth/me"),
          apiFetch<WizardStatus>("/api/v1/wizard/status"),
          apiFetch<BrainStatus>("/api/v1/brain/status"),
        ]);
        setUser(me);
        setWizard(wiz);
        setBrain(br);
        if (!wiz.completed) router.replace("/wizard");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load");
      }
    })();
  }, [router]);

  return (
    <Shell>
      <div className="stack">
        <div className="panel">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <div>
              <div className="brand-mark">OPERATIONS</div>
              <h1 style={{ margin: "0.2rem 0" }}>System Overview</h1>
              <p className="muted" style={{ margin: 0 }}>
                Welcome{user ? `, ${user.full_name || user.username}` : ""}. Owner retains full
                approval control.
              </p>
            </div>
            <span className={`badge ${wizard?.completed ? "ok" : "warn"}`}>
              setup {wizard?.completed ? "complete" : "required"}
            </span>
          </div>
          {error ? <p className="error">{error}</p> : null}
          <div className="stat-grid">
            <div className="stat">
              <div className="label">Brain</div>
              <div className="value">{brain?.brain || "—"}</div>
            </div>
            <div className="stat">
              <div className="label">Agents registered</div>
              <div className="value">{brain?.agents?.length ?? "—"}</div>
            </div>
            <div className="stat">
              <div className="label">Wizard step</div>
              <div className="value" style={{ fontSize: "1.05rem" }}>
                {wizard?.current_step || "—"}
              </div>
            </div>
            <div className="stat">
              <div className="label">Role</div>
              <div className="value" style={{ fontSize: "1.05rem" }}>
                {user?.is_owner ? "owner" : user?.roles?.[0] || "—"}
              </div>
            </div>
          </div>
        </div>

        <div className="panel">
          <h2>Agent registry</h2>
          <p className="muted">Agents 2–12 are foundation stubs. Central Brain is online.</p>
          <div className="agent-list">
            <div className="agent-item">
              <div>
                <strong>1 · Central AI Brain</strong>
                <div className="muted mono">orchestrator</div>
              </div>
              <span className="badge ok">ready</span>
            </div>
            {(brain?.agents || []).map((agent, idx) => (
              <div className="agent-item" key={agent.agent_id}>
                <div>
                  <strong>
                    {idx + 2} · {agent.name}
                  </strong>
                  <div className="muted mono">{agent.agent_id}</div>
                </div>
                <span className="badge stub">{agent.status}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </Shell>
  );
}
