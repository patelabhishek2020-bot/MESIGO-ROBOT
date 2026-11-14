"""Agent 11 — Graphics & Document Design."""

import html
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.agents.base import AgentResult, BaseAgent
from app.agents.helpers import require_db
from app.core.config import get_settings
from app.models.operations import DesignJob

TEMPLATES = {
    "commercial_invoice": "Commercial Invoice",
    "packing_list": "Packing List",
    "proforma": "Proforma Invoice",
    "letterhead": "Company Letterhead",
}


class GraphicsAgent(BaseAgent):
    agent_id = "graphics"
    name = "Graphics & Document Design"
    description = "Branded docs, labels, visual assets"
    status = "ready"
    capabilities = [
        "design_document",
        "list_designs",
        "render_template",
        "list_templates",
    ]

    async def handle(self, intent: str, payload: dict[str, Any], context: dict[str, Any]) -> AgentResult:
        db = require_db(context)
        if intent in ("design_document", "render_template"):
            return await self._design(db, payload)
        if intent == "list_designs":
            return await self._list(db, payload)
        if intent == "list_templates":
            return AgentResult(
                success=True,
                message="Available templates",
                data={"templates": [{"id": k, "name": v} for k, v in TEMPLATES.items()]},
            )
        return self.unsupported(intent)

    async def _design(self, db, payload: dict[str, Any]) -> AgentResult:
        template = payload.get("template", "commercial_invoice")
        if template not in TEMPLATES:
            return AgentResult(success=False, message=f"Unknown template. Choose from: {list(TEMPLATES)}")
        title = payload.get("title") or TEMPLATES[template]
        data = payload.get("input_data") or payload.get("data") or {}
        preview = self._render_html(template, title, data)
        settings = get_settings()
        out_dir = Path(settings.upload_dir) / "designs"
        out_dir.mkdir(parents=True, exist_ok=True)
        job_id = uuid.uuid4()
        out_path = out_dir / f"{job_id}.html"
        out_path.write_text(preview, encoding="utf-8")

        job = DesignJob(
            id=job_id,
            title=title,
            template=template,
            status="ready",
            input_data=data,
            output_path=str(out_path),
            preview_html=preview[:5000],
        )
        db.add(job)
        await db.flush()
        return AgentResult(
            success=True,
            message=f"Designed {TEMPLATES[template]}",
            data={"design_id": str(job.id), "output_path": str(out_path), "template": template},
        )

    def _render_html(self, template: str, title: str, data: dict[str, Any]) -> str:
        rows = "".join(
            f"<tr><th>{html.escape(str(k))}</th><td>{html.escape(str(v))}</td></tr>"
            for k, v in data.items()
        )
        return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>
body{{font-family:IBM Plex Sans,Segoe UI,sans-serif;background:#0b1220;color:#e8f0ff;padding:2rem}}
.sheet{{max-width:800px;margin:auto;border:1px solid #2a3f5f;padding:2rem;background:#111c2c}}
h1{{letter-spacing:-.02em}} th{{text-align:left;color:#8ea3c0;padding:.35rem .5rem  .35rem 0}}
.badge{{color:#3dd6c6;font-family:monospace;font-size:.75rem}}
</style></head><body><div class="sheet">
<div class="badge">MESIGO AI · {html.escape(template)}</div>
<h1>{html.escape(title)}</h1>
<table>{rows or "<tr><td>No fields provided</td></tr>"}</table>
</div></body></html>"""

    async def _list(self, db, payload: dict[str, Any]) -> AgentResult:
        rows = (
            await db.execute(
                select(DesignJob).order_by(DesignJob.created_at.desc()).limit(int(payload.get("limit", 50)))
            )
        ).scalars().all()
        return AgentResult(
            success=True,
            message=f"{len(rows)} designs",
            data={
                "designs": [
                    {
                        "id": str(r.id),
                        "title": r.title,
                        "template": r.template,
                        "status": r.status,
                        "output_path": r.output_path,
                    }
                    for r in rows
                ]
            },
        )
