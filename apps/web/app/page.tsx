"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, getToken, setToken } from "@/lib/api";

type LoginResponse = {
  access_token: string;
  must_change_password: boolean;
  setup_required: boolean;
};

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("owner");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (getToken()) router.replace("/dashboard");
  }, [router]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const data = await apiFetch<LoginResponse>("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });
      setToken(data.access_token);
      if (data.setup_required) router.push("/wizard");
      else router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-wrap">
      <div className="panel login-card stack">
        <div className="brand">
          <span className="brand-mark">MESIGO AI</span>
          <h1 className="brand-name" style={{ margin: 0 }}>
            Command Access
          </h1>
          <p className="muted" style={{ margin: "0.35rem 0 0" }}>
            Scientific operations console for autonomous import-export control.
          </p>
        </div>
        <form className="stack" onSubmit={onSubmit}>
          <div className="field">
            <label htmlFor="username">Username</label>
            <input
              id="username"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          {error ? <p className="error">{error}</p> : null}
          <button className="btn primary" type="submit" disabled={loading}>
            {loading ? "Authenticating…" : "Enter system"}
          </button>
        </form>
        <p className="muted mono">Auth: password + voice biometric hooks</p>
      </div>
    </div>
  );
}
