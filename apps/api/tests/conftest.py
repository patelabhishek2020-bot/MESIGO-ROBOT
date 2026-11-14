"""Live / integration fixtures for Mesigo API.

Credentials come from env only (MESIGO_OWNER_USERNAME / MESIGO_OWNER_PASSWORD).
Never log or assert on secret values.
"""

from __future__ import annotations

import os
from typing import Any, Iterator

import httpx
import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--api-base",
        action="store",
        default=None,
        help="Mesigo API base URL (overrides MESIGO_API_BASE)",
    )


@pytest.fixture(scope="session")
def api_base(pytestconfig: pytest.Config) -> str:
    base = (
        pytestconfig.getoption("--api-base")
        or os.environ.get("MESIGO_API_BASE")
        or "http://127.0.0.1:8000"
    )
    return base.rstrip("/")


@pytest.fixture(scope="session")
def owner_creds() -> dict[str, str]:
    user = os.environ.get("MESIGO_OWNER_USERNAME", "").strip()
    password = os.environ.get("MESIGO_OWNER_PASSWORD", "").strip()
    if not user or not password:
        pytest.skip(
            "Set MESIGO_OWNER_USERNAME and MESIGO_OWNER_PASSWORD "
            "(e.g. from VPS /opt/mesigo/.env via SSH — never commit them)"
        )
    return {"username": user, "password": password}


@pytest.fixture(scope="session")
def client(api_base: str) -> Iterator[httpx.Client]:
    with httpx.Client(base_url=api_base, timeout=60.0) as c:
        yield c


@pytest.fixture(scope="session")
def owner_token(client: httpx.Client, owner_creds: dict[str, str]) -> str:
    res = client.post("/api/v1/auth/login", json=owner_creds)
    assert res.status_code == 200, f"login failed: {res.status_code} {res.text[:200]}"
    data = res.json()
    token = data.get("access_token")
    assert token, "login response missing access_token"
    return token


@pytest.fixture(scope="session")
def auth_headers(owner_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {owner_token}"}


def assert_no_secret_leak(payload: Any) -> None:
    """Fail if a response body looks like it echoed a full/partial API key."""
    import re

    blob = str(payload)
    for match in re.finditer(r"sk-[^\s\"',}\\]+", blob):
        token = match.group(0)
        # Intentional wizard mask uses an ellipsis (…); everything else is a leak.
        if "…" in token or "..." in token:
            continue
        if len(token) > 8:
            raise AssertionError("Possible API key leaked in response payload")
