"""Agent 7 — Compliance & Government Rules."""

import uuid
from typing import Any

from sqlalchemy import select

from app.agents.base import AgentResult, BaseAgent
from app.agents.helpers import require_db
from app.models.operations import ComplianceCheck, ComplianceRule

SEED_RULES = [
    ("SANCTIONS-SCREEN", "Counterparty sanctions screening", "global", "sanctions", "high"),
    ("HS-CLASSIFY", "HS code classification review", "customs", "customs", "medium"),
    ("IE-LICENSE", "Import/export license check", "home", "license", "high"),
    ("DUAL-USE", "Dual-use goods assessment", "global", "compliance", "high"),
]


class ComplianceAgent(BaseAgent):
    agent_id = "compliance"
    name = "Compliance & Government Rules"
    description = "Licenses, customs, regulatory rules"
    status = "ready"
    capabilities = [
        "check_compliance",
        "list_rules",
        "add_rule",
        "seed_rules",
        "list_checks",
        "file_compliance",
    ]

    async def handle(self, intent: str, payload: dict[str, Any], context: dict[str, Any]) -> AgentResult:
        db = require_db(context)
        if intent == "seed_rules":
            return await self._seed(db)
        if intent == "add_rule":
            return await self._add_rule(db, payload)
        if intent == "list_rules":
            return await self._list_rules(db)
        if intent in ("check_compliance", "file_compliance"):
            return await self._check(db, payload)
        if intent == "list_checks":
            return await self._list_checks(db, payload)
        return self.unsupported(intent)

    async def _seed(self, db) -> AgentResult:
        created = 0
        for code, title, jurisdiction, category, severity in SEED_RULES:
            existing = (await db.execute(select(ComplianceRule).where(ComplianceRule.code == code))).scalar_one_or_none()
            if existing:
                continue
            db.add(
                ComplianceRule(
                    id=uuid.uuid4(),
                    code=code,
                    title=title,
                    jurisdiction=jurisdiction,
                    category=category,
                    severity=severity,
                    summary=title,
                )
            )
            created += 1
        await db.flush()
        return AgentResult(success=True, message=f"Seeded {created} compliance rules", data={"created": created})

    async def _add_rule(self, db, payload: dict[str, Any]) -> AgentResult:
        if not payload.get("code") or not payload.get("title"):
            return AgentResult(success=False, message="code and title required")
        rule = ComplianceRule(
            id=uuid.uuid4(),
            code=payload["code"],
            title=payload["title"],
            jurisdiction=payload.get("jurisdiction"),
            category=payload.get("category"),
            summary=payload.get("summary"),
            severity=payload.get("severity", "medium"),
        )
        db.add(rule)
        await db.flush()
        return AgentResult(success=True, message="Rule added", data={"rule_id": str(rule.id), "code": rule.code})

    async def _list_rules(self, db) -> AgentResult:
        rows = (await db.execute(select(ComplianceRule).where(ComplianceRule.is_active.is_(True)))).scalars().all()
        return AgentResult(
            success=True,
            message=f"{len(rows)} active rules",
            data={
                "rules": [
                    {
                        "id": str(r.id),
                        "code": r.code,
                        "title": r.title,
                        "category": r.category,
                        "severity": r.severity,
                    }
                    for r in rows
                ]
            },
        )

    async def _check(self, db, payload: dict[str, Any]) -> AgentResult:
        subject_type = payload.get("subject_type", "shipment")
        subject_ref = payload.get("subject_ref") or payload.get("reference") or "unknown"
        # Ensure baseline rules exist
        count = len((await db.execute(select(ComplianceRule))).scalars().all())
        if count == 0:
            await self._seed(db)

        rules = (await db.execute(select(ComplianceRule).where(ComplianceRule.is_active.is_(True)))).scalars().all()
        findings = []
        result = "pass"
        country = (payload.get("country") or "").upper()
        sanctioned_hint = country in {"KP", "IR", "SY", "CU"}  # illustrative
        for rule in rules:
            finding = {"rule": rule.code, "title": rule.title, "status": "pass"}
            if rule.category == "sanctions" and sanctioned_hint:
                finding["status"] = "fail"
                finding["detail"] = f"Jurisdiction {country} requires enhanced sanctions review"
                result = "fail"
            elif rule.category == "license" and payload.get("requires_license"):
                finding["status"] = "review"
                finding["detail"] = "License documentation must be attached"
                if result == "pass":
                    result = "review"
            findings.append(finding)

        check = ComplianceCheck(
            id=uuid.uuid4(),
            subject_type=subject_type,
            subject_ref=str(subject_ref),
            result=result,
            findings=findings,
        )
        db.add(check)
        await db.flush()
        return AgentResult(
            success=True,
            message=f"Compliance check {result}",
            data={"check_id": str(check.id), "result": result, "findings": findings},
            requires_approval=(result != "pass"),
            action_key="file_compliance",
        )

    async def _list_checks(self, db, payload: dict[str, Any]) -> AgentResult:
        q = select(ComplianceCheck).order_by(ComplianceCheck.created_at.desc()).limit(int(payload.get("limit", 50)))
        rows = (await db.execute(q)).scalars().all()
        return AgentResult(
            success=True,
            message=f"{len(rows)} checks",
            data={
                "checks": [
                    {
                        "id": str(r.id),
                        "subject_type": r.subject_type,
                        "subject_ref": r.subject_ref,
                        "result": r.result,
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                    }
                    for r in rows
                ]
            },
        )
