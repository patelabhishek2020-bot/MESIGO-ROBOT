"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Shell } from "@/components/Shell";
import { apiFetch, getToken } from "@/lib/api";

export default function ConsolePage() {
  const router = useRouter();
  const [text, setText] = useState("list leads");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [log, setLog] = useState<string[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!getToken()) router.replace("/");
  }, [router]);

  async function send(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const data = await apiFetch<{
        session_id: string;
        reply: string;
        intent?: string;
        result?: unknown;
      }>("/api/v1/interface/text", {
        method: "POST",
        body: JSON.stringify({ text, session_id: sessionId }),
      });
      setSessionId(data.session_id);
      setLog((prev) => [
        ...prev,
        `You: ${text}`,
        `Mesigo${data.intent ? ` [${data.intent}]` : ""}: ${data.reply}`,
      ]);
      setText("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    }
  }

  async function sendVoiceTranscript() {
    setError("");
    try {
      const data = await apiFetch<{ session_id: string; reply: string; intent?: string }>(
        "/api/v1/interface/voice/transcript",
        {
          method: "POST",
          body: JSON.stringify({ transcript: text || "list staff", session_id: sessionId }),
        }
      );
      setSessionId(data.session_id);
      setLog((prev) => [
        ...prev,
        `Voice STT: ${text || "list staff"}`,
        `Mesigo${data.intent ? ` [${data.intent}]` : ""}: ${data.reply}`,
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    }
  }

  return (
    <Shell>
      <div className="panel stack">
        <div className="brand-mark">INTERFACE</div>
        <h1 style={{ margin: 0 }}>Voice + Text Console</h1>
        <p className="muted">
          Exact commands still work (`list leads`, `intent:finance_summary`). Other messages use
          the Setup Wizard LLM for natural replies. Voice path accepts STT transcripts (Whisper hook).
        </p>
        {sessionId ? <span className="badge">session {sessionId.slice(0, 8)}</span> : null}
        <div
          className="mono"
          style={{
            minHeight: 220,
            border: "1px solid var(--line)",
            borderRadius: 8,
            padding: "0.85rem",
            background: "rgba(0,0,0,.25)",
            whiteSpace: "pre-wrap",
          }}
        >
          {log.length
            ? log.join("\n")
            : "Try: Hello · How many leads today? · System status · list leads · finance summary"}
        </div>
        <form className="stack" onSubmit={send}>
          <div className="field">
            <label>Command</label>
            <input value={text} onChange={(e) => setText(e.target.value)} placeholder="list leads" />
          </div>
          {error ? <p className="error">{error}</p> : null}
          <div className="row">
            <button className="btn primary" type="submit">
              Send text
            </button>
            <button className="btn" type="button" onClick={sendVoiceTranscript}>
              Send as voice transcript
            </button>
          </div>
        </form>
      </div>
    </Shell>
  );
}
