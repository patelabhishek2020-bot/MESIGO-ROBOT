"""Offline unit checks for secret redaction helpers."""

from __future__ import annotations

from app.services.llm import redact_secrets


def test_redact_secrets_strips_openai_style_keys() -> None:
    raw = (
        'Incorrect API key provided: sk-NEWOVERWRITEKEY1234567890. '
        'You can find your API key at https://platform.openai.com/account/api-keys.'
    )
    out = redact_secrets(raw)
    assert "sk-NEWOVERWRITE" not in out
    assert "7890" not in out or "[REDACTED]" in out
    assert "sk-" not in out or "[REDACTED]" in out


def test_redact_secrets_strips_partial_masked_provider_echo() -> None:
    raw = "Incorrect API key provided: sk-NEWOV****************7890."
    out = redact_secrets(raw)
    assert "sk-NEWOV" not in out
    assert "[REDACTED]" in out
