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

type WizardData = {
  status: WizardStatus;
  company: Record<string, string | null> | null;
  products: unknown[];
  markets: unknown[];
  emails: Record<string, string>;
  messaging: Record<string, string>;
  social: Record<string, string>;
  banking_logistics: Record<string, string>;
  llm: Record<string, string>;
  approval_matrix: { rules: unknown[] };
  doc_categories: { categories: unknown[] };
  staff_roles: { roles: unknown[] };
  owner_phones: { phones: string; primary_phone: string };
  voice_biometric: { enrollment_phrase: string; label: string };
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

const SECRET_FIELD_HINT =
  "Masked value means a secret is already saved. Edit to overwrite; leave as-is to keep.";

function cleanFormValues(data: Record<string, string>): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(data || {})) {
    if (k.includes("__")) continue;
    if (v === undefined || v === null) continue;
    out[k] = String(v);
  }
  return out;
}

export default function WizardPage() {
  const router = useRouter();
  const [status, setStatus] = useState<WizardStatus | null>(null);
  const [data, setData] = useState<WizardData | null>(null);
  const [step, setStep] = useState("company");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [hydrateKey, setHydrateKey] = useState(0);

  async function loadAll() {
    const payload = await apiFetch<WizardData>("/api/v1/wizard/data");
    setData(payload);
    setStatus(payload.status);
    setStep(payload.status?.current_step || "company");
    setHydrateKey((k) => k + 1);
  }

  useEffect(() => {
    if (!getToken()) {
      router.replace("/");
      return;
    }
    loadAll().catch((err) => setError(err.message));
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
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  async function reopen() {
    setBusy(true);
    setError("");
    try {
      await apiFetch("/api/v1/wizard/reopen", { method: "POST", body: "{}" });
      await loadAll();
      setMessage("Wizard reopened — saved fields loaded (secrets masked).");
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
      await loadAll();
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Complete failed");
    } finally {
      setBusy(false);
    }
  }

  const llmDefaults = cleanFormValues({
    provider: "openai",
    model: "gpt-4o",
    ...(data?.llm || {}),
  });
  const emailDefaults = cleanFormValues({
    smtp_port: "587",
    ...(data?.emails || {}),
  });

  return (
    <Shell>
      <div className="stack">
        <div className="panel">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <div>
              <div className="brand-mark">MASTER SETUP</div>
              <h1 style={{ margin: "0.2rem 0" }}>Setup Wizard</h1>
              <p className="muted" style={{ margin: 0 }}>
                First-launch and reopenable. Saved values load into each step; API keys show masked.
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
          {!data ? <p className="muted">Loading saved wizard data…</p> : null}

          {data && step === "company" && (
            <StepForm
              key={`company-${hydrateKey}`}
              busy={busy}
              fields={[
                ["legal_name", "Legal name", true],
                ["trade_name", "Trade name"],
                ["country", "Country"],
                ["email", "Email"],
                ["phone", "Phone"],
                ["address", "Address"],
              ]}
              defaults={cleanFormValues((data.company as Record<string, string>) || {})}
              onSubmit={(form) => run("/api/v1/wizard/company", form)}
            />
          )}
          {data && step === "products" && (
            <SimpleJsonForm
              key={`products-${hydrateKey}`}
              busy={busy}
              hint='Example: [{"name":"Widget A","hs_code":"8471","is_import":true,"is_export":true}]'
              defaultValue={JSON.stringify(
                data.products?.length
                  ? data.products
                  : [{ name: "Primary Product", sku: "SKU-001", is_import: true, is_export: true }],
                null,
                2
              )}
              onSubmit={(products) => run("/api/v1/wizard/products", { products })}
            />
          )}
          {data && step === "markets" && (
            <SimpleJsonForm
              key={`markets-${hydrateKey}`}
              busy={busy}
              hint='Example: [{"name":"India","country_code":"IN","currency":"INR","direction":"both"}]'
              defaultValue={JSON.stringify(
                data.markets?.length
                  ? data.markets
                  : [{ name: "Home market", country_code: "IN", currency: "INR", direction: "both" }],
                null,
                2
              )}
              onSubmit={(markets) => run("/api/v1/wizard/markets", { markets })}
            />
          )}
          {data && step === "emails" && (
            <>
              <p className="muted mono">{SECRET_FIELD_HINT}</p>
              <StepForm
                key={`emails-${hydrateKey}`}
                busy={busy}
                secretFields={["smtp_password"]}
                fields={[
                  ["smtp_host", "SMTP host", true],
                  ["smtp_port", "SMTP port", true],
                  ["smtp_user", "SMTP user", true],
                  ["smtp_password", "SMTP password", !emailDefaults.smtp_password],
                  ["from_email", "From email", true],
                  ["from_name", "From name"],
                ]}
                defaults={emailDefaults}
                onSubmit={(form) =>
                  run("/api/v1/wizard/emails", {
                    ...form,
                    smtp_port: Number(form.smtp_port || 587),
                    use_tls: true,
                  })
                }
              />
            </>
          )}
          {data && step === "messaging" && (
            <>
              <p className="muted mono">{SECRET_FIELD_HINT}</p>
              <StepForm
                key={`messaging-${hydrateKey}`}
                busy={busy}
                secretFields={[
                  "twilio_auth_token",
                  "whatsapp_business_token",
                  "wechat_app_secret",
                ]}
                fields={[
                  ["twilio_account_sid", "Twilio Account SID"],
                  ["twilio_auth_token", "Twilio Auth Token"],
                  ["twilio_whatsapp_from", "WhatsApp from"],
                  ["whatsapp_business_token", "WhatsApp Business token"],
                  ["wechat_app_id", "WeChat App ID"],
                  ["wechat_app_secret", "WeChat App Secret"],
                ]}
                defaults={cleanFormValues(data.messaging || {})}
                onSubmit={(form) => run("/api/v1/wizard/messaging", form)}
              />
            </>
          )}
          {data && step === "social" && (
            <>
              <p className="muted mono">{SECRET_FIELD_HINT}</p>
              <StepForm
                key={`social-${hydrateKey}`}
                busy={busy}
                secretFields={[
                  "twitter_api_key",
                  "twitter_api_secret",
                  "linkedin_access_token",
                  "facebook_page_token",
                  "instagram_access_token",
                ]}
                fields={[
                  ["twitter_api_key", "X/Twitter API key"],
                  ["twitter_api_secret", "X/Twitter API secret"],
                  ["linkedin_access_token", "LinkedIn token"],
                  ["facebook_page_token", "Facebook page token"],
                  ["instagram_access_token", "Instagram token"],
                ]}
                defaults={cleanFormValues(data.social || {})}
                onSubmit={(form) => run("/api/v1/wizard/social", form)}
              />
            </>
          )}
          {data && step === "banking_logistics" && (
            <>
              <p className="muted mono">{SECRET_FIELD_HINT}</p>
              <StepForm
                key={`banking-${hydrateKey}`}
                busy={busy}
                secretFields={["primary_bank_account", "logistics_api_key"]}
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
                defaults={cleanFormValues(data.banking_logistics || {})}
                onSubmit={(form) => run("/api/v1/wizard/banking-logistics", form)}
              />
            </>
          )}
          {data && step === "llm" && (
            <>
              <p className="muted mono">{SECRET_FIELD_HINT}</p>
              <StepForm
                key={`llm-${hydrateKey}`}
                busy={busy}
                secretFields={["api_key"]}
                fields={[
                  ["provider", "Provider", true],
                  ["api_key", "API key", !llmDefaults.api_key],
                  ["model", "Model", true],
                  ["base_url", "Base URL"],
                ]}
                defaults={llmDefaults}
                onSubmit={(form) => run("/api/v1/wizard/llm", form)}
              />
            </>
          )}
          {data && step === "approval_matrix" && (
            <SimpleJsonForm
              key={`approval-${hydrateKey}`}
              busy={busy}
              hint="Array of approval rules (mode: auto|approval|deny)"
              defaultValue={JSON.stringify(
                data.approval_matrix?.rules?.length
                  ? data.approval_matrix.rules
                  : [
                      {
                        action_key: "send_email",
                        display_name: "Send outbound email",
                        agent_id: "communication",
                        mode: "approval",
                        requires_owner: true,
                      },
                    ],
                null,
                2
              )}
              onSubmit={(rules) => run("/api/v1/wizard/approval-matrix", { rules })}
            />
          )}
          {data && step === "doc_categories" && (
            <SimpleJsonForm
              key={`docs-${hydrateKey}`}
              busy={busy}
              hint='[{"name":"Contracts","slug":"contracts","description":"Sales contracts"}]'
              defaultValue={JSON.stringify(
                data.doc_categories?.categories?.length
                  ? data.doc_categories.categories
                  : [{ name: "Contracts", slug: "contracts", description: "Sales & purchase contracts" }],
                null,
                2
              )}
              onSubmit={(categories) => run("/api/v1/wizard/doc-categories", { categories })}
            />
          )}
          {data && step === "staff_roles" && (
            <SimpleJsonForm
              key={`roles-${hydrateKey}`}
              busy={busy}
              hint='[{"name":"ops_lead","description":"Ops lead","permissions":{"crm":true}}]'
              defaultValue={JSON.stringify(
                data.staff_roles?.roles?.length
                  ? data.staff_roles.roles
                  : [{ name: "ops_lead", description: "Operations lead", permissions: { crm: true, docs: true } }],
                null,
                2
              )}
              onSubmit={(roles) => run("/api/v1/wizard/staff-roles", { roles })}
            />
          )}
          {data && step === "owner_phones" && (
            <StepForm
              key={`phones-${hydrateKey}`}
              busy={busy}
              fields={[
                ["phones", "Owner phones (comma-separated)", true],
                ["primary_phone", "Primary phone"],
              ]}
              defaults={{
                phones: data.owner_phones?.phones || "",
                primary_phone: data.owner_phones?.primary_phone || "",
              }}
              onSubmit={(form) =>
                run("/api/v1/wizard/owner-phones", {
                  phones: String(form.phones || "")
                    .split(",")
                    .map((p) => p.trim())
                    .filter(Boolean),
                  primary_phone: form.primary_phone || null,
                })
              }
            />
          )}
          {data && step === "voice_biometric" && (
            <VoiceStep
              key={`voice-${hydrateKey}`}
              busy={busy}
              initialPhrase={
                data.voice_biometric?.enrollment_phrase ||
                "Mesigo AI authorize my voice for business operations"
              }
              onMeta={(phrase) => run("/api/v1/wizard/voice-biometric", phrase)}
            />
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
  secretFields = [],
}: {
  fields: [string, string, boolean?][];
  onSubmit: (data: Record<string, string>) => void;
  busy: boolean;
  defaults?: Record<string, string>;
  secretFields?: string[];
}) {
  const [values, setValues] = useState<Record<string, string>>(defaults);
  useEffect(() => {
    setValues(defaults);
  }, [defaults]);

  function handle(e: FormEvent) {
    e.preventDefault();
    onSubmit(values);
  }
  return (
    <form className="stack" onSubmit={handle}>
      {fields.map(([key, label, required]) => {
        const isSecret = secretFields.includes(key);
        const masked = isSecret && (values[key] || "").includes("…");
        return (
          <div className="field" key={key}>
            <label htmlFor={key}>
              {label}
              {masked ? " (saved · masked)" : ""}
            </label>
            <input
              id={key}
              required={!!required}
              value={values[key] || ""}
              autoComplete={isSecret ? "off" : undefined}
              onChange={(e) => setValues((v) => ({ ...v, [key]: e.target.value }))}
              onFocus={() => {
                // If focusing a masked secret, clear so owner can paste a new key
                if (isSecret && (values[key] || "").includes("…")) {
                  setValues((v) => ({ ...v, [key]: "" }));
                }
              }}
            />
          </div>
        );
      })}
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
  useEffect(() => {
    setText(defaultValue);
  }, [defaultValue]);
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
  initialPhrase,
}: {
  busy: boolean;
  onMeta: (body: { enrollment_phrase: string; label: string }) => void;
  initialPhrase: string;
}) {
  const [phrase, setPhrase] = useState(initialPhrase);
  const [file, setFile] = useState<File | null>(null);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    setPhrase(initialPhrase);
  }, [initialPhrase]);

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
      const body = await res.json();
      if (!res.ok) throw new Error(body?.error?.message || "Upload failed");
      setMsg(body.message || "Voice enrolled");
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
