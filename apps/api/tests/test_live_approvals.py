"""Approval queue: side-effect → OTP → decide."""

from __future__ import annotations

import httpx
import pytest

from tests.conftest import assert_no_secret_leak

pytestmark = [pytest.mark.live, pytest.mark.critical]


def test_approvals_pending_list(client: httpx.Client, auth_headers: dict[str, str]) -> None:
    res = client.get("/api/v1/approvals/pending", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert "approvals" in body
    assert isinstance(body["approvals"], list)


def test_approval_flow_side_effect_otp_decide(
    client: httpx.Client, auth_headers: dict[str, str]
) -> None:
    """
    Queue a gated side-effect (send_email), capture OTP (dry-run), decide approve.
    """
    # 1) Side-effect intent should queue for owner approval
    route = client.post(
        "/api/v1/brain/route",
        headers=auth_headers,
        json={
            "intent": "send_email",
            "payload": {
                "to": "ops-test@example.com",
                "subject": "Mesigo live test (safe)",
                "body": "Automated approval-flow test — no real send expected when dry-run.",
                "otp_channel": "email",
                "otp_dry_run": True,
            },
        },
    )
    assert route.status_code == 200, route.text[:300]
    queued = route.json()
    assert_no_secret_leak(queued)
    assert queued.get("requires_approval") is True, f"expected approval gate: {queued}"
    assert queued.get("executed") is False
    pending = queued.get("pending_approval") or {}
    approval_id = pending.get("approval_id")
    assert approval_id, f"missing approval_id: {queued}"

    otp = pending.get("otp") or {}
    assert otp.get("success") is True, f"OTP create failed: {otp}"
    challenge_id = otp.get("challenge_id")
    assert challenge_id
    # dry-run returns dev_code; provider path may not — then request a fresh OTP
    code = otp.get("dev_code")
    if not code:
        req = client.post(
            "/api/v1/approvals/otp/request",
            headers=auth_headers,
            json={"channel": "email", "purpose": "approval"},
        )
        assert req.status_code == 200
        otp2 = req.json()
        code = otp2.get("dev_code")
        if otp2.get("challenge_id"):
            # Standalone OTP is not linked to approval; without linked code we cannot decide.
            # Prefer the original challenge when possible.
            pass
    assert code, (
        "No OTP code available for decide (expected dry-run dev_code on VPS without Twilio/SMTP send). "
        f"otp_keys={sorted(otp.keys())}"
    )

    # 2) Pending list includes the new approval
    listing = client.get(
        "/api/v1/approvals/pending",
        headers=auth_headers,
        params={"status": "pending"},
    )
    assert listing.status_code == 200
    ids = {a.get("id") for a in listing.json().get("approvals") or []}
    assert approval_id in ids

    # 3) Decide with OTP (reject to avoid executing a real send even with force)
    decide = client.post(
        f"/api/v1/approvals/{approval_id}/decide",
        headers=auth_headers,
        json={"approve": False, "otp_code": code, "note": "live test reject", "execute": False},
    )
    assert decide.status_code == 200, decide.text[:400]
    body = decide.json()
    assert_no_secret_leak(body)
    decision = body.get("decision") or body
    assert decision.get("success") is True, decision
    assert decision.get("status") == "rejected"

    # 4) No longer in pending
    listing2 = client.get(
        "/api/v1/approvals/pending",
        headers=auth_headers,
        params={"status": "pending"},
    )
    ids2 = {a.get("id") for a in listing2.json().get("approvals") or []}
    assert approval_id not in ids2


def test_otp_request_endpoint(client: httpx.Client, auth_headers: dict[str, str]) -> None:
    res = client.post(
        "/api/v1/approvals/otp/request",
        headers=auth_headers,
        json={"channel": "email", "purpose": "approval"},
    )
    assert res.status_code == 200
    body = res.json()
    assert_no_secret_leak(body)
    assert body.get("success") is True
    assert body.get("challenge_id")
    assert body.get("destination_masked")
    # code only when dry-run
    if body.get("dev_code"):
        assert len(str(body["dev_code"])) == 6
