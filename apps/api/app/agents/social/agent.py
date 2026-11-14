"""Agent 12 — Social Media Management."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.agents.base import AgentResult, BaseAgent
from app.agents.helpers import require_db
from app.models.operations import SocialPost
from app.services.settings_store import get_setting


class SocialAgent(BaseAgent):
    agent_id = "social"
    name = "Social Media Management"
    description = "Scheduled and approved social posting"
    status = "ready"
    capabilities = [
        "post_social",
        "schedule_post",
        "list_posts",
        "publish_due",
    ]

    async def handle(self, intent: str, payload: dict[str, Any], context: dict[str, Any]) -> AgentResult:
        db = require_db(context)
        if intent in ("post_social", "schedule_post"):
            return await self._create_post(db, payload, schedule=(intent == "schedule_post" or bool(payload.get("scheduled_at"))))
        if intent == "list_posts":
            return await self._list(db, payload)
        if intent == "publish_due":
            return await self._publish_due(db)
        return self.unsupported(intent)

    async def _create_post(self, db, payload: dict[str, Any], schedule: bool) -> AgentResult:
        content = payload.get("content")
        platform = payload.get("platform", "linkedin")
        if not content:
            return AgentResult(success=False, message="content required")
        post = SocialPost(
            id=uuid.uuid4(),
            platform=platform,
            content=content,
            media_urls=payload.get("media_urls") or [],
            status="scheduled" if schedule else "draft",
            scheduled_at=datetime.fromisoformat(payload["scheduled_at"]) if payload.get("scheduled_at") else None,
            metadata_json=payload.get("metadata") or {},
        )
        if payload.get("publish_now") and not schedule:
            ready, reason = await self._platform_ready(db, platform)
            post.status = "posted" if ready else "draft"
            if ready:
                post.posted_at = datetime.now(timezone.utc)
                post.external_id = f"dry-{uuid.uuid4().hex[:10]}"
            post.metadata_json = {**post.metadata_json, "publish_ready": ready, "reason": reason}
        db.add(post)
        await db.flush()
        return AgentResult(
            success=True,
            message=f"Social post {post.status} on {platform}",
            data={"post_id": str(post.id), "status": post.status, "platform": platform},
            requires_approval=True,
            action_key="post_social",
        )

    async def _list(self, db, payload: dict[str, Any]) -> AgentResult:
        q = select(SocialPost).order_by(SocialPost.created_at.desc()).limit(int(payload.get("limit", 50)))
        if payload.get("status"):
            q = q.where(SocialPost.status == payload["status"])
        rows = (await db.execute(q)).scalars().all()
        return AgentResult(
            success=True,
            message=f"{len(rows)} posts",
            data={
                "posts": [
                    {
                        "id": str(r.id),
                        "platform": r.platform,
                        "status": r.status,
                        "content": r.content[:200],
                        "scheduled_at": r.scheduled_at.isoformat() if r.scheduled_at else None,
                    }
                    for r in rows
                ]
            },
        )

    async def _publish_due(self, db) -> AgentResult:
        now = datetime.now(timezone.utc)
        q = (
            select(SocialPost)
            .where(SocialPost.status == "scheduled")
            .where(SocialPost.scheduled_at.is_not(None))
            .where(SocialPost.scheduled_at <= now)
        )
        rows = (await db.execute(q)).scalars().all()
        published = []
        for post in rows:
            ready, reason = await self._platform_ready(db, post.platform)
            if ready:
                post.status = "posted"
                post.posted_at = now
                post.external_id = f"pub-{uuid.uuid4().hex[:10]}"
            else:
                post.status = "failed"
                post.metadata_json = {**(post.metadata_json or {}), "failure": reason}
            published.append({"id": str(post.id), "status": post.status})
        await db.flush()
        return AgentResult(
            success=True,
            message=f"Processed {len(published)} due posts",
            data={"posts": published},
            requires_approval=True,
            action_key="post_social",
        )

    async def _platform_ready(self, db, platform: str) -> tuple[bool, str]:
        mapping = {
            "twitter": ("social", "twitter_api_key"),
            "x": ("social", "twitter_api_key"),
            "linkedin": ("social", "linkedin_access_token"),
            "facebook": ("social", "facebook_page_token"),
            "instagram": ("social", "instagram_access_token"),
        }
        key = mapping.get(platform.lower())
        if not key:
            return False, f"Unsupported platform {platform}"
        val = await get_setting(db, key[0], key[1])
        if not val:
            return False, f"Missing credentials for {platform} (configure in Setup Wizard)"
        return True, "credentials_present"
