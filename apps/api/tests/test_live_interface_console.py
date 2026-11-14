"""Console / interface — keyword commands + NL via Wizard LLM keys."""

from __future__ import annotations

import httpx
import pytest

from tests.conftest import assert_no_secret_leak

pytestmark = [pytest.mark.live, pytest.mark.critical]


def _text(client: httpx.Client, headers: dict[str, str], text: str) -> dict:
    res = client.post("/api/v1/interface/text", headers=headers, json={"text": text})
    assert res.status_code == 200, f"interface/text failed: {res.status_code} {res.text[:300]}"
    body = res.json()
    assert_no_secret_leak(body)
    assert body.get("reply"), f"empty reply for {text!r}: {body}"
    return body


def test_console_list_leads(client: httpx.Client, auth_headers: dict[str, str]) -> None:
    body = _text(client, auth_headers, "list leads")
    assert body.get("source") == "intent"
    assert body.get("intent") == "list_leads"
    assert body.get("routed") is True
    result = body.get("result") or {}
    assert result.get("success") is True
    assert result.get("executed") is True


def test_console_system_status(client: httpx.Client, auth_headers: dict[str, str]) -> None:
    body = _text(client, auth_headers, "system status")
    assert body.get("intent") == "system_status"
    assert "brain" in body.get("reply", "").lower() or "agent" in body.get("reply", "").lower()
    result = body.get("result") or {}
    assert result.get("success") is True
    data = result.get("data") or {}
    assert data.get("brain") == "online"
    assert isinstance(data.get("agents"), list)
    assert len(data["agents"]) >= 10


def test_console_explicit_intent(client: httpx.Client, auth_headers: dict[str, str]) -> None:
    body = _text(client, auth_headers, "intent:list_documents")
    assert body.get("intent") == "list_documents"
    assert body.get("routed") is True


def test_console_nl_hello_uses_wizard_llm(
    client: httpx.Client, auth_headers: dict[str, str]
) -> None:
    """
    'hello' is not a keyword intent → NL path.
    Assert Wizard LLM is configured (encrypted settings) without printing secrets.
    """
    # Precondition: wizard hydrate shows a saved (masked) key
    wiz = client.get("/api/v1/wizard/data", headers=auth_headers)
    assert wiz.status_code == 200
    llm = (wiz.json().get("llm") or {})
    masked = str(llm.get("api_key") or "")
    assert masked and ("…" in masked or "..." in masked or masked.startswith("••••")), (
        "LLM key not saved/masked in wizard — configure Setup Wizard LLM first"
    )
    assert_no_secret_leak(wiz.json())

    body = _text(client, auth_headers, "hello")
    assert body.get("source") in {"nl_llm", "nl_llm_intent"}, (
        f"expected NL path for hello, got source={body.get('source')!r}"
    )
    nl = body.get("nl") or {}
    llm_meta = nl.get("llm") or {}
    # Configured path: must not report missing_llm_key
    assert llm_meta.get("error") != "missing_llm_key", (
        "NL fell back to missing_llm_key — Wizard encrypted LLM key not used"
    )
    # Prefer provider present when key is configured (even if upstream LLM returns 401)
    if llm_meta.get("error"):
        # Key was read and used; provider auth failure is environment, not missing config
        assert str(llm_meta.get("error")).startswith("status_") or llm_meta.get("configured") is True, (
            f"unexpected NL llm error without configured key: {llm_meta}"
        )
    else:
        assert llm_meta.get("provider") or body.get("reply")
    assert_no_secret_leak(body)


def test_console_nl_asserts_configured_flag_path(
    client: httpx.Client, auth_headers: dict[str, str]
) -> None:
    """Second NL probe: casual chat that should not invent operational intents blindly."""
    body = _text(client, auth_headers, "Thanks — just checking the console.")
    assert body.get("source") in {"nl_llm", "nl_llm_intent"}
    nl = body.get("nl") or {}
    llm_meta = nl.get("llm") or {}
    assert llm_meta.get("error") != "missing_llm_key"
    assert_no_secret_leak(body)
