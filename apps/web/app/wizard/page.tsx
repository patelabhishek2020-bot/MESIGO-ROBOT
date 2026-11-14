"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Shell } from "@/components/Shell";
import { apiFetch, getToken } from "@/lib/api";

type WizardStatus = {
  completed: boolean;
  current_step: string;
  completed_steps: string[];
  steps: string[];
};

const STEP_LABELS: Record<string, string> = {
  company: "Company",
  products: "Products",
  markets: "Markets",
  emails: "Emails",
  messaging: "WhatsApp / Twilio / WeChat",
  social: "Social",
  banking_logistics: "Banking / Logistics / CHA",
  llm: "LLM keys",
  approval_matrix: "Approval matrix",
  doc_categories: "Doc categories",
  staff_roles: "Staff roles",
  owner_phones: "Owner phones",
  voice_biometric: "Voice biometric",
};

export default function WizardPage() {
  const router = useRouter();
  const [status, setStatus] = useState<WizardStatus | null>(null);
  const [step, setStep] = useState("company");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function refresh() {
    const data = await apiFetch<WizardStatus>("/api/v1/wizard/status");
    setStatus(data);
    setStep(data.current_step || "company");
  }

  useEffect(() => {
    if (!getToken()) {
      router.replace("/");
      return;
    }
    refresh().catch((err) => setError(err.message));
  }, [router]);

  const chips = useMemo(() => status?.steps || Object.keys(STEP_LABELS), [status]);

  async function run(path: string, body: unknown) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const res = await apiFetch<{ wizard?: WizardStatus; message?: string }>(path, {
        method: "POST",
        body: JSON.stringify(body),
      });
      setMessage(res.message || "Saved (encrypted where secret).");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  async function reopen() {
    setBusy(true);
    try {
      await apiFetch("/api/v1/wizard/reopen", { method: "POST", body: "{}" });
      await refresh();
      setMessage("Wizard reopened. Existing encrypted settings retained.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reopen failed");
    } finally {
      setBusy(false);
    }
  }

  async function complete() {
    setBusy(true);
    try {
      const res = await apiFetch<{ message: string }>("/api/v1/wizard/complete", {
        method: "POST",
        body: "{}",
      });
      setMessage(res.message);
      await refresh();
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Complete failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Shell>
      <div className="stack">
        <div className="panel">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <div>
              <div className="brand-mark">MASTER SETUP</div>
              <h1 style={{ margin: "0.2rem 0" }}>Setup Wizard</h1>
              <p className="muted" style={{ margin: 0 }}>
                First-launch and reopenable. All credentials encrypt in-system — no owner .env
                editing.
              </p>
            </div>
            <div className="row">
              <button className="btn ghost" type="button" onClick={reopen} disabled={busy}>
                Reopen
              </button>
              <button className="btn primary" type="button" onClick={complete} disabled={busy}>
                Complete setup
              </button>
            </div>
          </div>
          <div className="steps">
            {chips.map((s) => {
              const done = status?.completed_steps?.includes(s);
              const current = step === s;
              return (
                <button
                  key={s}
                  type="button"
                  className={`step-chip ${done ? "done" : ""} ${current ? "current" : ""}`}
                  onClick={() => setStep(s)}
                >
                  {STEP_LABELS[s] || s}
                </button>
              );
            })}
          </div>
          {error ? <p className="error">{error}</p> : null}
          {message ? <p className="success">{message}</p> : null}
        </div>

        <div className="panel">
          <h2>{STEP_LABELS[step] || step}</h2>
          {step === "company" && (
            <StepForm
              busy={busy}
              fields={[
                ["legal_name", "Legal name", true],
                ["trade_name", "Trade name"],
                ["country", "Country"],
                ["email", "Email"],
                ["phone", "Phone"],
                ["address", "Address"],
              ]}
              onSubmit={(data) => run("/api/v1/wizard/company", data)}
            />
          )}
          {step === "products" && (
            <SimpleJsonForm
              busy={busy}
              hint='Example: [{"name":"Widget A","hs_code":"8471","is_import":true,"is_export":true}]'
              defaultValue='[{"name":"Primary Product","sku":"SKU-001","is_import":true,"is_export":true}]'
              onSubmit={(products) => run("/api/v1/wizard/products", { products })}
            />
          )}
          {step === "markets" && (
            <SimpleJsonForm
              busy={busy}
              hint='Example: [{"name":"India","country_code":"IN","currency":"INR","direction":"both"}]'
              defaultValue='[{"name":"Home market","country_code":"IN","currency":"INR","direction":"both"}]'
              onSubmit={(markets) => run("/api/v1/wizard/markets", { markets })}
            />
          )}
          {step === "emails" && (
            <StepForm
              busy={busy}
              fields={[
                ["smtp_host", "SMTP host", true],
                ["smtp_port", "SMTP port", true],
                ["smtp_user", "SMTP user", true],
                ["smtp_password", "SMTP password", true],
                ["from_email", "From email", true],
                ["from_name", "From name"],
              ]}
              defaults={{ smtp_port: "587" }}
              onSubmit={(data) =>
                run("/api/v1/wizard/emails", {
                  ...data,
                  smtp_port: Number(data.smtp_port || 587),
                  use_tls: true,
                })
              }
            />
          )}
          {step === "messaging" && (
            <StepForm
              busy={busy}
              fields={[
                ["twilio_account_sid", "Twilio Account SID"],
                ["twilio_auth_token", "Twilio Auth Token"],
                ["twilio_whatsapp_from", "WhatsApp from"],
                ["whatsapp_business_token", "WhatsApp Business token"],
                ["wechat_app_id", "WeChat App ID"],
                ["wechat_app_secret", "WeChat App Secret"],
              ]}
              onSubmit={(data) => run("/api/v1/wizard/messaging", data)}
            />
          )}
          {step === "social" && (
            <StepForm
              busy={busy}
              fields={[
                ["twitter_api_key", "X/Twitter API key"],
                ["twitter_api_secret", "X/Twitter API secret"],
                ["linkedin_access_token", "LinkedIn token"],
                ["facebook_page_token", "Facebook page token"],
                ["instagram_access_token", "Instagram token"],
              ]}
              onSubmit={(data) => run("/api/v1/wizard/social", data)}
            />
          )}
          {step === "banking_logistics" && (
            <StepForm
              busy={busy}
              fields={[
                ["primary_bank_name", "Bank name"],
                ["primary_bank_account", "Bank account"],
                ["swift_code", "SWIFT"],
                ["logistics_partner", "Logistics partner"],
                ["logistics_api_key", "Logistics API key"],
                ["cha_name", "CHA name"],
                ["cha_license", "CHA license"],
                ["cha_contact", "CHA contact"],
              ]}
              onSubmit={(data) => run("/api/v1/wizard/banking-logistics", data)}
            />
          )}
          {step === "llm" && (
            <StepForm
              busy={busy}
              fields={[
                ["provider", "Provider", true],
                ["api_key", "API key", true],
                ["model", "Model", true],
                ["base_url", "Base URL"],
              ]}
              defaults={{ provider: "openai", model: "gpt-4o" }}
              onSubmit={(data) => run("/api/v1/wizard/llm", data)}
            />
          )}
          {step === "approval_matrix" && (
            <SimpleJsonForm
              busy={busy}
              hint="Array of approval rules (mode: auto|approval|deny)"
              defaultValue={`[{"action_key":"send_email","display_name":"Send outbound email","agent_id":"communication","mode":"approval","requires_owner":true},{"action_key":"pay_invoice","display_name":"Pay invoice","agent_id":"finance","mode":"approval","amount_limit":1000,"currency":"USD","requires_owner":true}]`}
              onSubmit={(rules) => run("/api/v1/wizard/approval-matrix", { rules })}
            />
          )}
          {step === "doc_categories" && (
            <SimpleJsonForm
              busy={busy}
              hint='[{"name":"Contracts","slug":"contracts","description":"Sales contracts"}]'
              defaultValue='[{"name":"Contracts","slug":"contracts","description":"Sales & purchase contracts"}]'
              onSubmit={(categories) => run("/api/v1/wizard/doc-categories", { categories })}
            />
          )}
          {step === "staff_roles" && (
            <SimpleJsonForm
              busy={busy}
              hint='[{"name":"ops_lead","description":"Ops lead","permissions":{"crm":true}}]'
              defaultValue='[{"name":"ops_lead","description":"Operations lead","permissions":{"crm":true,"docs":true}}]'
              onSubmit={(roles) => run("/api/v1/wizard/staff-roles", { roles })}
            />
          )}
          {step === "owner_phones" && (
            <StepForm
              busy={busy}
              fields={[
                ["phones", "Owner phones (comma-separated)", true],
                ["primary_phone", "Primary phone"],
              ]}
              onSubmit={(data) =>
                run("/api/v1/wizard/owner-phones", {
                  phones: String(data.phones || "")
                    .split(",")
                    .map((p) => p.trim())
                    .filter(Boolean),
                  primary_phone: data.primary_phone || null,
                })
              }
            />
          )}
          {step === "voice_biometric" && (
            <VoiceStep busy={busy} onMeta={(phrase) => run("/api/v1/wizard/voice-biometric", phrase)} />
          )}
        </div>
      </div>
    </Shell>
  );
}

function StepForm({
  fields,
  onSubmit,
  busy,
  defaults = {},
}: {
  fields: [string, string, boolean?][];
  onSubmit: (data: Record<string, string>) => void;
  busy: boolean;
  defaults?: Record<string, string>;
}) {
  const [values, setValues] = useState<Record<string, string>>(defaults);
  function handle(e: FormEvent) {
    e.preventDefault();
    onSubmit(values);
  }
  return (
    <form className="stack" onSubmit={handle}>
      {fields.map(([key, label, required]) => (
        <div className="field" key={key}>
          <label htmlFor={key}>{label}</label>
          <input
            id={key}
            required={!!required}
            value={values[key] || ""}
            onChange={(e) => setValues((v) => ({ ...v, [key]: e.target.value }))}
          />
        </div>
      ))}
      <button className="btn primary" type="submit" disabled={busy}>
        Save step
      </button>
    </form>
  );
}

function SimpleJsonForm({
  defaultValue,
  hint,
  onSubmit,
  busy,
}: {
  defaultValue: string;
  hint: string;
  onSubmit: (parsed: unknown) => void;
  busy: boolean;
}) {
  const [text, setText] = useState(defaultValue);
  const [localError, setLocalError] = useState("");
  function handle(e: FormEvent) {
    e.preventDefault();
    try {
      const parsed = JSON.parse(text);
      setLocalError("");
      onSubmit(parsed);
    } catch {
      setLocalError("Invalid JSON");
    }
  }
  return (
    <form className="stack" onSubmit={handle}>
      <p className="muted mono">{hint}</p>
      <div className="field">
        <label>JSON payload</label>
        <textarea rows={10} value={text} onChange={(e) => setText(e.target.value)} />
      </div>
      {localError ? <p className="error">{localError}</p> : null}
      <button className="btn primary" type="submit" disabled={busy}>
        Save step
      </button>
    </form>
  );
}

function VoiceStep({
  busy,
  onMeta,
}: {
  busy: boolean;
  onMeta: (body: { enrollment_phrase: string; label: string }) => void;
}) {
  const [phrase, setPhrase] = useState("Mesigo AI authorize my voice for business operations");
  const [file, setFile] = useState<File | null>(null);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  async function upload() {
    if (!file) {
      setErr("Choose an audio sample first");
      return;
    }
    setErr("");
    const fd = new FormData();
    fd.append("file", file);
    try {
      await onMeta({ enrollment_phrase: phrase, label: "primary" });
      const token = getToken();
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/auth/voice/enroll?label=primary&enrollment_phrase=${encodeURIComponent(phrase)}`,
        {
          method: "POST",
          headers: token ? { Authorization: `Bearer ${token}` } : undefined,
          body: fd,
        }
      );
      const data = await res.json();
      if (!res.ok) throw new Error(data?.error?.message || "Upload failed");
      setMsg(data.message || "Voice enrolled");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Upload failed");
    }
  }

  return (
    <div className="stack">
      <p className="muted">
        Enrollment hooks store voice samples and reserve embedding refs for speaker recognition.
      </p>
      <div className="field">
        <label>Enrollment phrase</label>
        <input value={phrase} onChange={(e) => setPhrase(e.target.value)} />
      </div>
      <div className="field">
        <label>Voice sample (wav/mp3/webm)</label>
        <input type="file" accept="audio/*" onChange={(e) => setFile(e.target.files?.[0] || null)} />
      </div>
      {err ? <p className="error">{err}</p> : null}
      {msg ? <p className="success">{msg}</p> : null}
      <div className="row">
        <button
          className="btn"
          type="button"
          disabled={busy}
          onClick={() => onMeta({ enrollment_phrase: phrase, label: "primary" })}
        >
          Mark phrase step
        </button>
        <button className="btn primary" type="button" disabled={busy} onClick={upload}>
          Upload & enroll
        </button>
      </div>
    </div>
  );
}
