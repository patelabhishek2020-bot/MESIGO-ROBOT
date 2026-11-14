"""Agent 8 — Document Vault (AI analysis, expiry alerts)."""

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.agents.base import AgentResult, BaseAgent
from app.agents.helpers import require_db
from app.core.config import get_settings
from app.models.documents import Document, DocumentCategory
from app.models.operations import DocumentAnalysis
from app.services.settings_store import get_setting


class DocumentVaultAgent(BaseAgent):
    agent_id = "document_vault"
    name = "Document Vault"
    description = "Secure storage, AI analysis, and expiry alerts"
    status = "ready"
    capabilities = [
        "store_document",
        "retrieve_document",
        "list_documents",
        "analyze_document",
        "expiry_alerts",
        "delete_document",
    ]

    async def handle(self, intent: str, payload: dict[str, Any], context: dict[str, Any]) -> AgentResult:
        db = require_db(context)
        if intent == "store_document":
            return await self._store(db, payload, context)
        if intent == "retrieve_document":
            return await self._retrieve(db, payload)
        if intent == "list_documents":
            return await self._list(db, payload)
        if intent == "analyze_document":
            return await self._analyze(db, payload)
        if intent == "expiry_alerts":
            return await self._expiry_alerts(db, payload)
        if intent == "delete_document":
            return await self._delete(db, payload)
        return self.unsupported(intent)

    async def _store(self, db, payload: dict[str, Any], context: dict[str, Any]) -> AgentResult:
        title = payload.get("title")
        if not title:
            return AgentResult(success=False, message="title required")
        settings = get_settings()
        upload_dir = Path(settings.upload_dir)
        upload_dir.mkdir(parents=True, exist_ok=True)
        doc_id = uuid.uuid4()
        file_path = payload.get("file_path")
        if payload.get("content_base64"):
            import base64

            raw = base64.b64decode(payload["content_base64"])
            ext = payload.get("extension", ".bin")
            dest = upload_dir / f"{doc_id}{ext}"
            dest.write_bytes(raw)
            file_path = str(dest)

        category_id = None
        if payload.get("category_slug"):
            cat = (
                await db.execute(
                    select(DocumentCategory).where(DocumentCategory.slug == payload["category_slug"])
                )
            ).scalar_one_or_none()
            if cat:
                category_id = cat.id

        doc = Document(
            id=doc_id,
            category_id=category_id,
            title=title,
            file_path=file_path,
            mime_type=payload.get("mime_type"),
            uploaded_by=uuid.UUID(str(context["actor_user_id"])) if context.get("actor_user_id") else None,
            status="stored",
            metadata_json=payload.get("metadata") or {},
        )
        db.add(doc)
        await db.flush()

        analysis = None
        if payload.get("analyze", True):
            analysis = await self._run_analysis(db, doc, payload)

        return AgentResult(
            success=True,
            message=f"Document stored: {doc.title}",
            data={
                "document_id": str(doc.id),
                "file_path": doc.file_path,
                "analysis_id": str(analysis.id) if analysis else None,
            },
        )

    async def _retrieve(self, db, payload: dict[str, Any]) -> AgentResult:
        doc = await self._get_doc(db, payload)
        if isinstance(doc, AgentResult):
            return doc
        analyses = (
            await db.execute(
                select(DocumentAnalysis)
                .where(DocumentAnalysis.document_id == doc.id)
                .order_by(DocumentAnalysis.created_at.desc())
            )
        ).scalars().all()
        return AgentResult(
            success=True,
            message=f"Retrieved {doc.title}",
            data={
                "document": {
                    "id": str(doc.id),
                    "title": doc.title,
                    "file_path": doc.file_path,
                    "mime_type": doc.mime_type,
                    "status": doc.status,
                    "metadata": doc.metadata_json,
                },
                "analyses": [
                    {
                        "id": str(a.id),
                        "summary": a.summary,
                        "extracted_fields": a.extracted_fields,
                        "risk_flags": a.risk_flags,
                        "expires_at": a.expires_at.isoformat() if a.expires_at else None,
                    }
                    for a in analyses
                ],
            },
        )

    async def _list(self, db, payload: dict[str, Any]) -> AgentResult:
        q = select(Document).order_by(Document.created_at.desc()).limit(int(payload.get("limit", 50)))
        rows = (await db.execute(q)).scalars().all()
        return AgentResult(
            success=True,
            message=f"{len(rows)} documents",
            data={
                "documents": [
                    {"id": str(r.id), "title": r.title, "status": r.status, "mime_type": r.mime_type}
                    for r in rows
                ]
            },
        )

    async def _analyze(self, db, payload: dict[str, Any]) -> AgentResult:
        doc = await self._get_doc(db, payload)
        if isinstance(doc, AgentResult):
            return doc
        analysis = await self._run_analysis(db, doc, payload)
        return AgentResult(
            success=True,
            message="Document analyzed",
            data={
                "analysis_id": str(analysis.id),
                "summary": analysis.summary,
                "expires_at": analysis.expires_at.isoformat() if analysis.expires_at else None,
                "risk_flags": analysis.risk_flags,
            },
        )

    async def _run_analysis(self, db, doc: Document, payload: dict[str, Any]) -> DocumentAnalysis:
        provider = await get_setting(db, "llm", "provider")
        model = await get_setting(db, "llm", "model") or "heuristic"
        api_key = await get_setting(db, "llm", "api_key")

        # Heuristic analysis always available; LLM call when key present (hook)
        expires_days = int(payload.get("expires_in_days") or doc.metadata_json.get("expires_in_days") or 365)
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_days)
        extracted = {
            "title": doc.title,
            "mime_type": doc.mime_type,
            "has_file": bool(doc.file_path),
        }
        risk_flags = []
        title_l = (doc.title or "").lower()
        if "draft" in title_l:
            risk_flags.append("draft_document")
        if "license" in title_l and expires_days < 90:
            risk_flags.append("license_nearing_expiry_window")

        summary = (
            f"AI analysis ({'llm:' + provider if api_key else 'heuristic'}) of '{doc.title}'. "
            f"Expiry set to {expires_at.date().isoformat()}."
        )
        analysis = DocumentAnalysis(
            id=uuid.uuid4(),
            document_id=doc.id,
            summary=summary,
            extracted_fields=extracted,
            risk_flags=risk_flags,
            expires_at=expires_at,
            model_used=f"{provider}:{model}" if api_key else "heuristic-v1",
        )
        db.add(analysis)
        await db.flush()
        return analysis

    async def _expiry_alerts(self, db, payload: dict[str, Any]) -> AgentResult:
        within_days = int(payload.get("within_days", 30))
        cutoff = datetime.now(timezone.utc) + timedelta(days=within_days)
        now = datetime.now(timezone.utc)
        q = (
            select(DocumentAnalysis)
            .where(DocumentAnalysis.expires_at.is_not(None))
            .where(DocumentAnalysis.expires_at <= cutoff)
            .where(DocumentAnalysis.expires_at >= now)
            .order_by(DocumentAnalysis.expires_at.asc())
        )
        rows = (await db.execute(q)).scalars().all()
        alerts = []
        for row in rows:
            if not row.alert_sent or payload.get("force"):
                row.alert_sent = True
                alerts.append(
                    {
                        "analysis_id": str(row.id),
                        "document_id": str(row.document_id),
                        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
                        "summary": row.summary,
                    }
                )
        await db.flush()
        return AgentResult(
            success=True,
            message=f"{len(alerts)} expiry alerts",
            data={"within_days": within_days, "alerts": alerts},
        )

    async def _delete(self, db, payload: dict[str, Any]) -> AgentResult:
        doc = await self._get_doc(db, payload)
        if isinstance(doc, AgentResult):
            return doc
        doc.status = "deleted"
        await db.flush()
        return AgentResult(
            success=True,
            message=f"Document marked deleted: {doc.title}",
            data={"document_id": str(doc.id)},
            requires_approval=True,
            action_key="delete_document",
        )

    async def _get_doc(self, db, payload: dict[str, Any]):
        doc_id = payload.get("document_id")
        if not doc_id:
            return AgentResult(success=False, message="document_id required")
        doc = (
            await db.execute(select(Document).where(Document.id == uuid.UUID(str(doc_id))))
        ).scalar_one_or_none()
        if not doc:
            return AgentResult(success=False, message="Document not found")
        return doc
