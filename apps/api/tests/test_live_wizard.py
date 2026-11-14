"""Setup Wizard hydrate + LLM encrypted settings (no secret printing)."""

from __future__ import annotations

import httpx
import pytest

from tests.conftest import assert_no_secret_leak

pytestmark = [pytest.mark.live, pytest.mark.critical]


def test_wizard_status(client: httpx.Client, auth_headers: dict[str, str]) -> None:
    res = client.get("/api/v1/wizard/status", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert "completed" in body
    assert isinstance(body.get("steps"), list)
    assert "llm" in body["steps"]
    assert "company" in body["steps"]


def test_wizard_data_hydrates_and_masks_secrets(
    client: httpx.Client, auth_headers: dict[str, str]
) -> None:
    res = client.get("/api/v1/wizard/data", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert_no_secret_leak(data)

    assert data.get("status") is not None
    company = data.get("company")
    assert company is not None, "expected saved company on VPS"
    assert company.get("legal_name"), "company.legal_name empty"
    assert isinstance(data.get("products"), list)
    assert isinstance(data.get("markets"), list)

    llm = data.get("llm") or {}
    api_key = str(llm.get("api_key") or "")
    assert api_key, "LLM api_key missing from hydrate (expected masked value)"
    assert "…" in api_key or "..." in api_key or api_key.startswith("••••"), (
        f"LLM api_key not masked (len={len(api_key)})"
    )
    # Never assert on plaintext length beyond mask shape
    assert llm.get("api_key__has_value") in (True, "true", 1) or llm.get("api_key__masked") in (
        True,
        "true",
        1,
    )
    assert llm.get("provider"), "llm.provider missing"
    assert llm.get("model"), "llm.model missing"

    emails = data.get("emails") or {}
    smtp_pw = str(emails.get("smtp_password") or "")
    if smtp_pw:
        assert "…" in smtp_pw or "..." in smtp_pw or smtp_pw.startswith("••••")


def test_wizard_reopen_keeps_hydration(
    client: httpx.Client, auth_headers: dict[str, str]
) -> None:
    before = client.get("/api/v1/wizard/data", headers=auth_headers).json()
    reopen = client.post("/api/v1/wizard/reopen", headers=auth_headers, json={})
    assert reopen.status_code == 200
    assert reopen.json().get("success") is True

    after = client.get("/api/v1/wizard/data", headers=auth_headers).json()
    assert (after.get("company") or {}).get("legal_name") == (before.get("company") or {}).get(
        "legal_name"
    )
    before_key = (before.get("llm") or {}).get("api_key")
    after_key = (after.get("llm") or {}).get("api_key")
    assert before_key and after_key
    assert "…" in str(after_key) or "..." in str(after_key)
    assert_no_secret_leak(after)


def test_settings_meta_masks_secrets(
    client: httpx.Client, auth_headers: dict[str, str]
) -> None:
    res = client.get("/api/v1/wizard/settings-meta", headers=auth_headers, params={"category": "llm"})
    assert res.status_code == 200
    settings = res.json().get("settings") or []
    assert settings, "expected llm encrypted settings rows"
    for row in settings:
        if row.get("is_secret") and row.get("has_value"):
            val = str(row.get("value") or "")
            assert "…" in val or "..." in val or val.startswith("••••")
    assert_no_secret_leak(res.json())
