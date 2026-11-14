"""Agent 4 — Supplier & Rate."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.agents.base import AgentResult, BaseAgent
from app.agents.helpers import require_db
from app.models.operations import RateQuote, Supplier


class SupplierRateAgent(BaseAgent):
    agent_id = "supplier_rate"
    name = "Supplier & Rate"
    description = "Source suppliers and negotiate / track rates"
    status = "ready"
    capabilities = [
        "find_supplier",
        "create_supplier",
        "list_suppliers",
        "get_rate",
        "add_rate",
        "compare_rates",
    ]

    async def handle(self, intent: str, payload: dict[str, Any], context: dict[str, Any]) -> AgentResult:
        db = require_db(context)
        handlers = {
            "create_supplier": self._create_supplier,
            "find_supplier": self._list_suppliers,
            "list_suppliers": self._list_suppliers,
            "add_rate": self._add_rate,
            "get_rate": self._get_rates,
            "compare_rates": self._compare_rates,
        }
        fn = handlers.get(intent)
        if not fn:
            return self.unsupported(intent)
        return await fn(db, payload)

    async def _create_supplier(self, db, payload: dict[str, Any]) -> AgentResult:
        if not payload.get("name"):
            return AgentResult(success=False, message="name required")
        supplier = Supplier(
            id=uuid.uuid4(),
            name=payload["name"],
            country=payload.get("country"),
            email=payload.get("email"),
            phone=payload.get("phone"),
            products=payload.get("products") or [],
            rating=payload.get("rating"),
            notes=payload.get("notes"),
        )
        db.add(supplier)
        await db.flush()
        return AgentResult(
            success=True,
            message=f"Supplier created: {supplier.name}",
            data={"supplier_id": str(supplier.id)},
        )

    async def _list_suppliers(self, db, payload: dict[str, Any]) -> AgentResult:
        q = select(Supplier).order_by(Supplier.created_at.desc()).limit(int(payload.get("limit", 50)))
        if payload.get("country"):
            q = q.where(Supplier.country == payload["country"])
        if payload.get("query"):
            q = q.where(Supplier.name.ilike(f"%{payload['query']}%"))
        rows = (await db.execute(q)).scalars().all()
        return AgentResult(
            success=True,
            message=f"Found {len(rows)} suppliers",
            data={
                "suppliers": [
                    {
                        "id": str(r.id),
                        "name": r.name,
                        "country": r.country,
                        "rating": float(r.rating) if r.rating is not None else None,
                        "status": r.status,
                        "products": r.products,
                    }
                    for r in rows
                ]
            },
        )

    async def _add_rate(self, db, payload: dict[str, Any]) -> AgentResult:
        if not payload.get("product_name") or payload.get("unit_price") is None:
            return AgentResult(success=False, message="product_name and unit_price required")
        quote = RateQuote(
            id=uuid.uuid4(),
            supplier_id=uuid.UUID(str(payload["supplier_id"])) if payload.get("supplier_id") else None,
            product_name=payload["product_name"],
            unit_price=float(payload["unit_price"]),
            currency=payload.get("currency", "USD"),
            moq=payload.get("moq"),
            lead_time_days=payload.get("lead_time_days"),
            source=payload.get("source", "manual"),
            valid_until=datetime.fromisoformat(payload["valid_until"]) if payload.get("valid_until") else None,
        )
        db.add(quote)
        await db.flush()
        return AgentResult(
            success=True,
            message="Rate quote stored",
            data={"quote_id": str(quote.id), "unit_price": float(quote.unit_price), "currency": quote.currency},
        )

    async def _get_rates(self, db, payload: dict[str, Any]) -> AgentResult:
        q = select(RateQuote).order_by(RateQuote.created_at.desc()).limit(int(payload.get("limit", 50)))
        if payload.get("product_name"):
            q = q.where(RateQuote.product_name.ilike(f"%{payload['product_name']}%"))
        if payload.get("supplier_id"):
            q = q.where(RateQuote.supplier_id == uuid.UUID(str(payload["supplier_id"])))
        rows = (await db.execute(q)).scalars().all()
        return AgentResult(
            success=True,
            message=f"{len(rows)} rate quotes",
            data={
                "quotes": [
                    {
                        "id": str(r.id),
                        "supplier_id": str(r.supplier_id) if r.supplier_id else None,
                        "product_name": r.product_name,
                        "unit_price": float(r.unit_price),
                        "currency": r.currency,
                        "moq": float(r.moq) if r.moq is not None else None,
                        "lead_time_days": r.lead_time_days,
                    }
                    for r in rows
                ]
            },
        )

    async def _compare_rates(self, db, payload: dict[str, Any]) -> AgentResult:
        product = payload.get("product_name")
        if not product:
            return AgentResult(success=False, message="product_name required")
        q = (
            select(RateQuote)
            .where(RateQuote.product_name.ilike(f"%{product}%"))
            .order_by(RateQuote.unit_price.asc())
            .limit(20)
        )
        rows = (await db.execute(q)).scalars().all()
        ranked = [
            {
                "id": str(r.id),
                "supplier_id": str(r.supplier_id) if r.supplier_id else None,
                "unit_price": float(r.unit_price),
                "currency": r.currency,
                "lead_time_days": r.lead_time_days,
            }
            for r in rows
        ]
        return AgentResult(
            success=True,
            message=f"Compared {len(ranked)} quotes (lowest first)",
            data={"product_name": product, "ranked": ranked, "best": ranked[0] if ranked else None},
        )
