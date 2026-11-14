"""Auth endpoint smoke tests against a live API."""

from __future__ import annotations

import httpx
import pytest

pytestmark = [pytest.mark.live, pytest.mark.critical]


def test_health(client: httpx.Client) -> None:
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body.get("status") == "ok"
    assert "mesigo" in str(body.get("service", "")).lower()


def test_ready(client: httpx.Client) -> None:
    res = client.get("/ready")
    assert res.status_code == 200
    body = res.json()
    assert body.get("status") == "ready"
    assert body.get("database") == "ok"


def test_login_rejects_bad_password(client: httpx.Client, owner_creds: dict[str, str]) -> None:
    res = client.post(
        "/api/v1/auth/login",
        json={"username": owner_creds["username"], "password": "definitely-wrong-password"},
    )
    assert res.status_code in (401, 403)


def test_login_and_me(client: httpx.Client, auth_headers: dict[str, str]) -> None:
    res = client.get("/api/v1/auth/me", headers=auth_headers)
    assert res.status_code == 200
    me = res.json()
    assert me.get("is_owner") is True
    assert me.get("username")
    assert me.get("id")


def test_me_requires_auth(client: httpx.Client) -> None:
    res = client.get("/api/v1/auth/me")
    assert res.status_code in (401, 403)
