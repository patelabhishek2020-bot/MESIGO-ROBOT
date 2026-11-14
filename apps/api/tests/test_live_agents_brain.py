"""Central Brain + agents inventory against a live API."""

from __future__ import annotations

import httpx
import pytest

pytestmark = [pytest.mark.live, pytest.mark.critical]


def test_brain_status(client: httpx.Client, auth_headers: dict[str, str]) -> None:
    res = client.get("/api/v1/brain/status", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert body.get("brain") == "online"
    agents = body.get("agents") or []
    assert len(agents) >= 10, f"expected ~12 agents, got {len(agents)}"
    routes = body.get("routes") or {}
    assert "list_leads" in routes
    assert "send_email" in routes


def test_brain_agents_list(client: httpx.Client, auth_headers: dict[str, str]) -> None:
    res = client.get("/api/v1/brain/agents", headers=auth_headers)
    assert res.status_code == 200
    agents = res.json().get("agents") or []
    ids = {a.get("agent_id") or a.get("id") for a in agents}
    # Accept either agent_id or id field from registry info
    if not any(ids):
        ids = {a.get("name") for a in agents}
    assert len(agents) >= 10


def test_agents_inventory(client: httpx.Client, auth_headers: dict[str, str]) -> None:
    res = client.get("/api/v1/agents", headers=auth_headers)
    assert res.status_code == 200
    agents = res.json().get("agents") or []
    assert len(agents) >= 10
    # detail for lead CRM
    first = agents[0]
    agent_id = first.get("agent_id") or first.get("id")
    assert agent_id
    detail = client.get(f"/api/v1/agents/{agent_id}", headers=auth_headers)
    assert detail.status_code == 200


def test_brain_route_list_leads(client: httpx.Client, auth_headers: dict[str, str]) -> None:
    res = client.post(
        "/api/v1/brain/route",
        headers=auth_headers,
        json={"intent": "list_leads", "payload": {}},
    )
    assert res.status_code == 200
    body = res.json()
    assert body.get("success") is True
    assert body.get("executed") is True
    assert body.get("requires_approval") in (False, None)


def test_agent_invoke_list_leads(client: httpx.Client, auth_headers: dict[str, str]) -> None:
    res = client.post(
        "/api/v1/agents/lead_crm/invoke",
        headers=auth_headers,
        json={"intent": "list_leads", "payload": {}},
    )
    assert res.status_code == 200
    body = res.json()
    assert body.get("success") is True
