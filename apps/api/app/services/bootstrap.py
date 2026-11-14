"""First-boot seed: roles, owner user, default approval rules, doc categories."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security import hash_password
from app.models.documents import DocumentCategory
from app.models.settings import ApprovalRule
from app.models.user import Role, User, UserRole
from app.services.settings_store import get_system_state, set_system_state

logger = get_logger("bootstrap")

DEFAULT_ROLES = [
    ("owner", "Full system owner", {"*": True}, True),
    ("admin", "Administrative staff", {"wizard": True, "users": True, "audit": True}, True),
    ("manager", "Operations manager", {"crm": True, "docs": True, "finance_view": True}, True),
    ("staff", "General staff panel access", {"staff_panel": True}, True),
    ("viewer", "Read-only dashboard", {"dashboard": True}, True),
]

DEFAULT_APPROVALS = [
    ("send_email", "Send outbound email", "communication", "approval", None),
    ("send_whatsapp", "Send WhatsApp message", "communication", "approval", None),
    ("place_purchase_order", "Place purchase order", "supplier", "approval", 5000.0),
    ("pay_invoice", "Pay invoice / transfer funds", "finance", "approval", 1000.0),
    ("book_shipment", "Book logistics shipment", "logistics", "approval", None),
    ("file_compliance", "Submit compliance filing", "compliance", "approval", None),
    ("post_social", "Publish social media post", "social", "approval", None),
    ("self_update_deploy", "Self-update & deploy", "self_dev", "approval", None),
    ("hire_staff", "HR hire / role change", "hr", "approval", None),
    ("delete_document", "Delete vault document", "docs", "approval", None),
]

DEFAULT_DOC_CATEGORIES = [
    ("Commercial Invoice", "commercial-invoice", "Export/import invoices"),
    ("Packing List", "packing-list", "Shipment packing lists"),
    ("Bill of Lading", "bill-of-lading", "Ocean/air B/L"),
    ("Certificate of Origin", "certificate-of-origin", "COO documents"),
    ("Customs Declaration", "customs-declaration", "CHA / customs filings"),
    ("Bank Documents", "bank-documents", "LC, remittance, bank advice"),
    ("Contracts", "contracts", "Sales & purchase contracts"),
    ("Licenses & Permits", "licenses-permits", "Import/export licenses"),
    ("Internal", "internal", "Internal company documents"),
]


async def ensure_bootstrap(db: AsyncSession) -> None:
    settings = get_settings()

    # Roles
    for name, desc, perms, is_system in DEFAULT_ROLES:
        existing = await db.execute(select(Role).where(Role.name == name))
        if not existing.scalar_one_or_none():
            db.add(Role(id=uuid.uuid4(), name=name, description=desc, permissions=perms, is_system=is_system))

    await db.flush()

    # Owner user
    owner_result = await db.execute(select(User).where(User.is_owner.is_(True)))
    owner = owner_result.scalar_one_or_none()
    if not owner:
        owner = User(
            id=uuid.uuid4(),
            username=settings.bootstrap_owner_username,
            full_name="Owner",
            hashed_password=hash_password(settings.bootstrap_owner_password),
            is_owner=True,
            must_change_password=True,
            is_active=True,
        )
        db.add(owner)
        await db.flush()
        role_result = await db.execute(select(Role).where(Role.name == "owner"))
        owner_role = role_result.scalar_one()
        db.add(UserRole(id=uuid.uuid4(), user_id=owner.id, role_id=owner_role.id))
        logger.info("bootstrap_owner_created", username=owner.username)

    # Approval matrix defaults
    for action_key, display, agent_id, mode, limit in DEFAULT_APPROVALS:
        existing = await db.execute(select(ApprovalRule).where(ApprovalRule.action_key == action_key))
        if not existing.scalar_one_or_none():
            db.add(
                ApprovalRule(
                    id=uuid.uuid4(),
                    action_key=action_key,
                    display_name=display,
                    agent_id=agent_id,
                    mode=mode,
                    amount_limit=limit,
                    currency="USD" if limit is not None else None,
                    requires_owner=True,
                )
            )

    # Document categories
    count = await db.scalar(select(func.count()).select_from(DocumentCategory))
    if not count:
        for name, slug, desc in DEFAULT_DOC_CATEGORIES:
            db.add(
                DocumentCategory(
                    id=uuid.uuid4(),
                    name=name,
                    slug=slug,
                    description=desc,
                    is_system=True,
                )
            )

    # Setup wizard state
    wizard = await get_system_state(db, "setup_wizard")
    if not wizard:
        await set_system_state(
            db,
            "setup_wizard",
            {
                "completed": False,
                "current_step": "company",
                "completed_steps": [],
                "started_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    await db.flush()
    logger.info("bootstrap_complete")
