"""Agent 6 — Finance & Accounting."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select

from app.agents.base import AgentResult, BaseAgent
from app.agents.helpers import require_db
from app.models.operations import Invoice


class FinanceAgent(BaseAgent):
    agent_id = "finance"
    name = "Finance & Accounting"
    description = "Invoices, payments, FX, books"
    status = "ready"
    capabilities = [
        "create_invoice",
        "list_invoices",
        "pay_invoice",
        "mark_paid",
        "finance_summary",
    ]

    async def handle(self, intent: str, payload: dict[str, Any], context: dict[str, Any]) -> AgentResult:
        db = require_db(context)
        if intent == "create_invoice":
            return await self._create(db, payload)
        if intent == "list_invoices":
            return await self._list(db, payload)
        if intent in ("pay_invoice", "mark_paid"):
            return await self._pay(db, payload)
        if intent == "finance_summary":
            return await self._summary(db)
        return self.unsupported(intent)

    async def _create(self, db, payload: dict[str, Any]) -> AgentResult:
        if payload.get("amount") is None or not payload.get("counterparty"):
            return AgentResult(success=False, message="counterparty and amount required")
        number = payload.get("number") or f"INV-{uuid.uuid4().hex[:8].upper()}"
        inv = Invoice(
            id=uuid.uuid4(),
            number=number,
            direction=payload.get("direction", "receivable"),
            counterparty=payload["counterparty"],
            amount=float(payload["amount"]),
            currency=payload.get("currency", "USD"),
            status=payload.get("status", "draft"),
            due_date=datetime.fromisoformat(payload["due_date"]) if payload.get("due_date") else None,
            line_items=payload.get("line_items") or [],
        )
        db.add(inv)
        await db.flush()
        return AgentResult(
            success=True,
            message=f"Invoice {inv.number} created",
            data={"invoice_id": str(inv.id), "number": inv.number, "amount": float(inv.amount)},
        )

    async def _list(self, db, payload: dict[str, Any]) -> AgentResult:
        q = select(Invoice).order_by(Invoice.created_at.desc()).limit(int(payload.get("limit", 50)))
        if payload.get("status"):
            q = q.where(Invoice.status == payload["status"])
        rows = (await db.execute(q)).scalars().all()
        return AgentResult(
            success=True,
            message=f"{len(rows)} invoices",
            data={
                "invoices": [
                    {
                        "id": str(r.id),
                        "number": r.number,
                        "direction": r.direction,
                        "counterparty": r.counterparty,
                        "amount": float(r.amount),
                        "currency": r.currency,
                        "status": r.status,
                    }
                    for r in rows
                ]
            },
        )

    async def _pay(self, db, payload: dict[str, Any]) -> AgentResult:
        inv = None
        if payload.get("invoice_id"):
            inv = (
                await db.execute(select(Invoice).where(Invoice.id == uuid.UUID(str(payload["invoice_id"]))))
            ).scalar_one_or_none()
        elif payload.get("number"):
            inv = (await db.execute(select(Invoice).where(Invoice.number == payload["number"]))).scalar_one_or_none()
        if not inv:
            return AgentResult(success=False, message="Invoice not found")
        inv.status = "paid"
        inv.paid_at = datetime.now(timezone.utc)
        await db.flush()
        return AgentResult(
            success=True,
            message=f"Invoice {inv.number} marked paid",
            data={"invoice_id": str(inv.id), "amount": float(inv.amount), "currency": inv.currency},
            requires_approval=True,
            action_key="pay_invoice",
        )

    async def _summary(self, db) -> AgentResult:
        total = await db.scalar(select(func.coalesce(func.sum(Invoice.amount), 0)))
        paid = await db.scalar(
            select(func.coalesce(func.sum(Invoice.amount), 0)).where(Invoice.status == "paid")
        )
        open_amt = await db.scalar(
            select(func.coalesce(func.sum(Invoice.amount), 0)).where(Invoice.status.in_(["draft", "sent", "overdue"]))
        )
        return AgentResult(
            success=True,
            message="Finance summary",
            data={
                "total_amount": float(total or 0),
                "paid_amount": float(paid or 0),
                "open_amount": float(open_amt or 0),
            },
        )
