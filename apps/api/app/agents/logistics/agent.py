"""Agent 5 — Logistics & Documentation."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select

from app.agents.base import AgentResult, BaseAgent
from app.agents.helpers import require_db
from app.models.operations import Shipment

DEFAULT_DOCS = [
    "commercial_invoice",
    "packing_list",
    "bill_of_lading",
    "certificate_of_origin",
    "customs_declaration",
]


class LogisticsAgent(BaseAgent):
    agent_id = "logistics"
    name = "Logistics & Documentation"
    description = "Shipments, B/L, packing, CHA coordination"
    status = "ready"
    capabilities = [
        "book_shipment",
        "create_shipment",
        "update_shipment",
        "list_shipments",
        "prepare_docs",
        "shipment_status",
    ]

    async def handle(self, intent: str, payload: dict[str, Any], context: dict[str, Any]) -> AgentResult:
        db = require_db(context)
        if intent in ("book_shipment", "create_shipment"):
            return await self._create(db, payload)
        if intent == "update_shipment" or intent == "shipment_status":
            return await self._update(db, payload)
        if intent == "list_shipments":
            return await self._list(db, payload)
        if intent == "prepare_docs":
            return await self._prepare_docs(db, payload)
        return self.unsupported(intent)

    async def _create(self, db, payload: dict[str, Any]) -> AgentResult:
        ref = payload.get("reference") or f"SHP-{uuid.uuid4().hex[:8].upper()}"
        shipment = Shipment(
            id=uuid.uuid4(),
            reference=ref,
            direction=payload.get("direction", "export"),
            origin=payload.get("origin"),
            destination=payload.get("destination"),
            mode=payload.get("mode", "sea"),
            carrier=payload.get("carrier"),
            status=payload.get("status", "booked" if payload.get("book") else "draft"),
            etd=datetime.fromisoformat(payload["etd"]) if payload.get("etd") else None,
            eta=datetime.fromisoformat(payload["eta"]) if payload.get("eta") else None,
            docs_checklist=[{"doc": d, "ready": False} for d in DEFAULT_DOCS],
            metadata_json=payload.get("metadata") or {},
        )
        db.add(shipment)
        await db.flush()
        return AgentResult(
            success=True,
            message=f"Shipment {shipment.reference} created ({shipment.status})",
            data={"shipment_id": str(shipment.id), "reference": shipment.reference, "status": shipment.status},
            requires_approval=True,
            action_key="book_shipment",
        )

    async def _update(self, db, payload: dict[str, Any]) -> AgentResult:
        shipment = await self._get(db, payload)
        if isinstance(shipment, AgentResult):
            return shipment
        for field in ("status", "carrier", "origin", "destination", "mode"):
            if field in payload:
                setattr(shipment, field, payload[field])
        await db.flush()
        return AgentResult(
            success=True,
            message=f"Shipment {shipment.reference} → {shipment.status}",
            data={"shipment_id": str(shipment.id), "status": shipment.status, "reference": shipment.reference},
        )

    async def _list(self, db, payload: dict[str, Any]) -> AgentResult:
        q = select(Shipment).order_by(Shipment.created_at.desc()).limit(int(payload.get("limit", 50)))
        if payload.get("status"):
            q = q.where(Shipment.status == payload["status"])
        rows = (await db.execute(q)).scalars().all()
        return AgentResult(
            success=True,
            message=f"{len(rows)} shipments",
            data={
                "shipments": [
                    {
                        "id": str(r.id),
                        "reference": r.reference,
                        "direction": r.direction,
                        "origin": r.origin,
                        "destination": r.destination,
                        "mode": r.mode,
                        "status": r.status,
                    }
                    for r in rows
                ]
            },
        )

    async def _prepare_docs(self, db, payload: dict[str, Any]) -> AgentResult:
        shipment = await self._get(db, payload)
        if isinstance(shipment, AgentResult):
            return shipment
        checklist = list(shipment.docs_checklist or [])
        mark = set(payload.get("ready_docs") or [d["doc"] for d in checklist])
        for item in checklist:
            if item.get("doc") in mark:
                item["ready"] = True
        shipment.docs_checklist = checklist
        ready = sum(1 for i in checklist if i.get("ready"))
        await db.flush()
        return AgentResult(
            success=True,
            message=f"Docs prepared {ready}/{len(checklist)} for {shipment.reference}",
            data={"shipment_id": str(shipment.id), "docs_checklist": checklist},
        )

    async def _get(self, db, payload: dict[str, Any]):
        if payload.get("shipment_id"):
            row = (
                await db.execute(select(Shipment).where(Shipment.id == uuid.UUID(str(payload["shipment_id"]))))
            ).scalar_one_or_none()
        elif payload.get("reference"):
            row = (
                await db.execute(select(Shipment).where(Shipment.reference == payload["reference"]))
            ).scalar_one_or_none()
        else:
            return AgentResult(success=False, message="shipment_id or reference required")
        if not row:
            return AgentResult(success=False, message="Shipment not found")
        return row
