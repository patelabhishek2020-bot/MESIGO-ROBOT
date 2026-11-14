"""LLM client — reads provider/keys from Setup Wizard encrypted settings."""

from __future__ import annotations

import json
import re
from typing import Any, Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.services.settings_store import get_setting

logger = get_logger("llm")

# Provider error bodies often echo partial API keys — never return those to clients.
_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}", re.I),
    re.compile(r"sk-[A-Za-z0-9_\*]{6,}", re.I),
    re.compile(r"key-[A-Za-z0-9_\-]{8,}", re.I),
    re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", re.I),
]


def redact_secrets(text: str) -> str:
    """Strip API-key-like tokens from provider/error text before returning to clients."""
    if not text:
        return ""
    out = str(text)
    for pat in _SECRET_PATTERNS:
        out = pat.sub("[REDACTED]", out)
    # Collapse OpenAI-style "Incorrect API key provided: …" leftovers
    out = re.sub(
        r"(Incorrect API key provided:)[^\".\n]+",
        r"\1 [REDACTED]",
        out,
        flags=re.I,
    )
    return out


async def get_llm_config(db: AsyncSession) -> dict[str, Optional[str]]:
    provider = (await get_setting(db, "llm", "provider") or "openai").strip().lower()
    api_key = await get_setting(db, "llm", "api_key")
    model = await get_setting(db, "llm", "model") or "gpt-4o-mini"
    base_url = await get_setting(db, "llm", "base_url")
    return {
        "provider": provider,
        "api_key": api_key,
        "model": model,
        "base_url": (base_url or "").rstrip("/") or None,
    }


def llm_configured(cfg: dict[str, Optional[str]]) -> bool:
    return bool(cfg.get("api_key"))


def _chat_endpoint(cfg: dict[str, Optional[str]]) -> str:
    base = cfg.get("base_url")
    provider = cfg.get("provider") or "openai"
    if base:
        if base.endswith("/chat/completions"):
            return base
        if base.endswith("/v1"):
            return f"{base}/chat/completions"
        return f"{base}/v1/chat/completions"
    if provider in ("openai", "azure", "custom", "groq", "together"):
        # Azure typically needs base_url from wizard; default OpenAI-compatible public API
        return "https://api.openai.com/v1/chat/completions"
    if provider == "anthropic":
        # Prefer OpenAI-compatible proxy via base_url; without it we use messages API below
        return "anthropic"
    return "https://api.openai.com/v1/chat/completions"


async def chat_completion(
    db: AsyncSession,
    *,
    messages: list[dict[str, str]],
    temperature: float = 0.4,
    max_tokens: int = 800,
    response_json: bool = False,
) -> dict[str, Any]:
    """
    Call the configured LLM. Returns {success, content, raw?, error?}.
    Never logs the API key.
    """
    cfg = await get_llm_config(db)
    if not llm_configured(cfg):
        return {
            "success": False,
            "error": "missing_llm_key",
            "content": (
                "No LLM API key is configured yet. Open Setup Wizard → LLM keys, "
                "save your provider key, then try again. Exact commands like "
                "`list leads` still work without an LLM."
            ),
        }

    provider = cfg["provider"] or "openai"
    endpoint = _chat_endpoint(cfg)

    try:
        if provider == "anthropic" and endpoint == "anthropic":
            return await _anthropic_messages(cfg, messages, temperature, max_tokens)
        return await _openai_compatible(
            cfg, endpoint, messages, temperature, max_tokens, response_json=response_json
        )
    except httpx.HTTPError as exc:
        logger.warning("llm_http_error", error=str(exc), provider=provider)
        return {"success": False, "error": "http_error", "content": f"LLM request failed: {exc}"}
    except Exception as exc:  # noqa: BLE001
        logger.exception("llm_unexpected", error=str(exc))
        return {"success": False, "error": "unexpected", "content": f"LLM error: {exc}"}


async def _openai_compatible(
    cfg: dict[str, Optional[str]],
    endpoint: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
    *,
    response_json: bool,
) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type": "application/json",
    }
    body: dict[str, Any] = {
        "model": cfg["model"],
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_json:
        body["response_format"] = {"type": "json_object"}

    async with httpx.AsyncClient(timeout=60.0) as client:
        res = await client.post(endpoint, headers=headers, json=body)
        if res.status_code >= 400:
            # Never echo provider bodies (they often include partial API keys).
            logger.warning("llm_bad_status", status=res.status_code, provider=cfg.get("provider"))
            hint = "Invalid API key" if res.status_code in (401, 403) else "Check Wizard LLM settings"
            return {
                "success": False,
                "error": f"status_{res.status_code}",
                "content": redact_secrets(
                    f"LLM provider returned {res.status_code}. {hint}."
                ),
            }
        data = res.json()
        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        return {"success": True, "content": redact_secrets((content or "").strip()), "raw": data}


async def _anthropic_messages(
    cfg: dict[str, Optional[str]],
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
) -> dict[str, Any]:
    system = ""
    converted = []
    for m in messages:
        if m["role"] == "system":
            system = (system + "\n" + m["content"]).strip()
        else:
            converted.append({"role": m["role"], "content": m["content"]})
    headers = {
        "x-api-key": cfg["api_key"] or "",
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    body = {
        "model": cfg["model"],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": converted,
    }
    if system:
        body["system"] = system
    async with httpx.AsyncClient(timeout=60.0) as client:
        res = await client.post("https://api.anthropic.com/v1/messages", headers=headers, json=body)
        if res.status_code >= 400:
            hint = "Invalid API key" if res.status_code in (401, 403) else "Check Wizard LLM settings"
            return {
                "success": False,
                "error": f"status_{res.status_code}",
                "content": redact_secrets(f"Anthropic returned {res.status_code}. {hint}."),
            }
        data = res.json()
        parts = data.get("content") or []
        text = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
        return {"success": True, "content": text.strip(), "raw": data}


def _extract_json(text: str) -> Optional[dict[str, Any]]:
    text = (text or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return None
    return None


async def interpret_natural_language(
    db: AsyncSession,
    *,
    text: str,
    available_intents: list[str],
    transcript: list[dict[str, Any]],
    username: Optional[str] = None,
) -> dict[str, Any]:
    """
    Ask the LLM whether to chat or map to an intent.
    Returns:
      {mode: "chat"|"intent"|"error", reply?, intent?, payload?, llm?}
    """
    recent = transcript[-8:] if transcript else []
    history_lines = []
    for turn in recent:
        role = turn.get("role", "user")
        t = turn.get("text") or turn.get("reply") or ""
        history_lines.append(f"{role}: {t}")

    system = (
        "You are Mesigo AI, the owner's Import-Export Business Operating System assistant. "
        "Be concise, professional, and helpful. "
        "Decide how to handle the latest user message.\n"
        "Respond ONLY with a JSON object of one of these shapes:\n"
        '1) {"mode":"chat","reply":"<natural language reply>"}\n'
        '2) {"mode":"intent","intent":"<intent_name>","payload":{...},"reply_hint":"<optional short note>"}\n'
        "Use mode=intent only when the user clearly wants an operational action that matches an available intent. "
        "For greetings, status questions you can answer yourself, explanations, or ambiguous chat, use mode=chat. "
        "If they ask how many leads / list something operational, prefer mode=intent with the right list_* intent. "
        "Never invent intents outside the provided list. Never include API keys or secrets."
    )
    user_blob = {
        "username": username,
        "available_intents": available_intents,
        "recent_transcript": history_lines,
        "message": text,
    }
    result = await chat_completion(
        db,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user_blob)},
        ],
        temperature=0.2,
        max_tokens=600,
        response_json=True,
    )
    if not result.get("success"):
        return {
            "mode": "error",
            "reply": result.get("content") or "LLM unavailable",
            "llm": {"error": result.get("error"), "configured": llm_configured(await get_llm_config(db))},
        }

    parsed = _extract_json(result["content"])
    if not parsed or parsed.get("mode") not in ("chat", "intent"):
        # Treat free text as chat reply
        return {
            "mode": "chat",
            "reply": result["content"] or "I'm here. How can I help with your import-export operations?",
            "llm": {"provider": (await get_llm_config(db)).get("provider")},
        }

    if parsed["mode"] == "chat":
        return {
            "mode": "chat",
            "reply": parsed.get("reply") or result["content"],
            "llm": {"provider": (await get_llm_config(db)).get("provider")},
        }

    intent = str(parsed.get("intent") or "").strip()
    if intent not in available_intents:
        return {
            "mode": "chat",
            "reply": parsed.get("reply_hint")
            or parsed.get("reply")
            or (
                f"I understood you want '{intent}', but that isn't a registered operation. "
                "Try a listed command or rephrase."
            ),
            "llm": {"provider": (await get_llm_config(db)).get("provider"), "rejected_intent": intent},
        }
    payload = parsed.get("payload") if isinstance(parsed.get("payload"), dict) else {}
    return {
        "mode": "intent",
        "intent": intent,
        "payload": payload,
        "reply_hint": parsed.get("reply_hint"),
        "llm": {"provider": (await get_llm_config(db)).get("provider")},
    }


async def phrase_agent_result(
    db: AsyncSession,
    *,
    user_text: str,
    intent: str,
    routed: dict[str, Any],
) -> Optional[str]:
    """Optional natural phrasing of a structured agent result."""
    cfg = await get_llm_config(db)
    if not llm_configured(cfg):
        return None
    summary = {
        "user_text": user_text,
        "intent": intent,
        "success": routed.get("success"),
        "message": routed.get("message"),
        "requires_approval": routed.get("requires_approval"),
        "executed": routed.get("executed"),
        "data": routed.get("data"),
        "pending_approval": routed.get("pending_approval"),
    }
    result = await chat_completion(
        db,
        messages=[
            {
                "role": "system",
                "content": (
                    "Rewrite the Mesigo agent result as a short natural reply for the business owner. "
                    "Stay factual. Mention if owner approval/OTP is required. No JSON, no secrets."
                ),
            },
            {"role": "user", "content": json.dumps(summary, default=str)[:6000]},
        ],
        temperature=0.3,
        max_tokens=400,
    )
    if result.get("success") and result.get("content"):
        return result["content"]
    return None
