"""Master Setup Wizard — first launch + reopenable."""

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Request
from sqlalchemy import delete, select

from app.api.deps import CurrentUser, DbSession, OwnerUser, client_meta
from app.core.exceptions import MesigoError
from app.models.company import Company, Market, Product
from app.models.documents import DocumentCategory
from app.models.settings import ApprovalRule
from app.models.user import Role
from app.schemas.wizard import (
    ApprovalMatrixStep,
    BankingLogisticsStep,
    CompanyStep,
    DocCategoriesStep,
    EmailSettingsStep,
    LlmSettingsStep,
    MarketsStep,
    MessagingSettingsStep,
    OwnerPhonesStep,
    ProductsStep,
    SocialSettingsStep,
    StaffRolesStep,
    VoiceEnrollmentStep,
    WizardCompleteResponse,
    WizardStatus,
)
from app.services.audit import write_audit
from app.services.settings_store import (
    get_setting,
    get_system_state,
    is_masked_secret,
    list_settings_meta,
    set_system_state,
    settings_map,
    upsert_setting,
)

router = APIRouter(prefix="/wizard", tags=["setup-wizard"])

WIZARD_STEPS = [
    "company",
    "products",
    "markets",
    "emails",
    "messaging",
    "social",
    "banking_logistics",
    "llm",
    "approval_matrix",
    "doc_categories",
    "staff_roles",
    "owner_phones",
    "voice_biometric",
]


async def _wizard_state(db) -> dict[str, Any]:
    state = await get_system_state(db, "setup_wizard")
    if not state:
        state = {
            "completed": False,
            "current_step": "company",
            "completed_steps": [],
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        await set_system_state(db, "setup_wizard", state)
    return state


async def _mark_step(db, step: str) -> dict[str, Any]:
    state = await _wizard_state(db)
    completed = list(dict.fromkeys([*(state.get("completed_steps") or []), step]))
    # advance current to next incomplete
    next_step = step
    for s in WIZARD_STEPS:
        if s not in completed:
            next_step = s
            break
    else:
        next_step = WIZARD_STEPS[-1]
    state = {
        **state,
        "completed_steps": completed,
        "current_step": next_step,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await set_system_state(db, "setup_wizard", state)
    return state


@router.get("/status", response_model=WizardStatus)
async def wizard_status(db: DbSession, user: CurrentUser):
    state = await _wizard_state(db)
    return WizardStatus(
        completed=bool(state.get("completed")),
        current_step=state.get("current_step", "company"),
        completed_steps=state.get("completed_steps") or [],
        steps=WIZARD_STEPS,
    )


@router.post("/reopen")
async def reopen_wizard(db: DbSession, user: OwnerUser, request: Request):
    """Owner can reopen the wizard anytime without wiping encrypted settings."""
    state = await _wizard_state(db)
    state["completed"] = False
    state["reopened_at"] = datetime.now(timezone.utc).isoformat()
    if not state.get("current_step"):
        state["current_step"] = "company"
    await set_system_state(db, "setup_wizard", state)
    await write_audit(
        db,
        action="wizard.reopen",
        actor_user_id=user.id,
        actor_username=user.username,
        **client_meta(request),
    )
    return {"success": True, "status": state, "steps": WIZARD_STEPS}


@router.post("/company")
async def step_company(body: CompanyStep, db: DbSession, user: OwnerUser, request: Request):
    result = await db.execute(select(Company).where(Company.is_active.is_(True)).limit(1))
    company = result.scalar_one_or_none()
    if company:
        for field, value in body.model_dump().items():
            setattr(company, field, value)
    else:
        company = Company(id=uuid.uuid4(), **body.model_dump())
        db.add(company)
    await db.flush()
    state = await _mark_step(db, "company")
    await write_audit(
        db,
        action="wizard.company",
        actor_user_id=user.id,
        actor_username=user.username,
        resource_type="company",
        resource_id=str(company.id),
        **client_meta(request),
    )
    return {"success": True, "company_id": str(company.id), "wizard": state}


@router.post("/products")
async def step_products(body: ProductsStep, db: DbSession, user: OwnerUser, request: Request):
    company = (await db.execute(select(Company).where(Company.is_active.is_(True)).limit(1))).scalar_one_or_none()
    if not company:
        raise MesigoError("Complete company step first", code="wizard_order", status_code=400)
    await db.execute(delete(Product).where(Product.company_id == company.id))
    for p in body.products:
        db.add(Product(id=uuid.uuid4(), company_id=company.id, **p.model_dump()))
    state = await _mark_step(db, "products")
    await write_audit(
        db,
        action="wizard.products",
        actor_user_id=user.id,
        actor_username=user.username,
        details={"count": len(body.products)},
        **client_meta(request),
    )
    return {"success": True, "count": len(body.products), "wizard": state}


@router.post("/markets")
async def step_markets(body: MarketsStep, db: DbSession, user: OwnerUser, request: Request):
    company = (await db.execute(select(Company).where(Company.is_active.is_(True)).limit(1))).scalar_one_or_none()
    if not company:
        raise MesigoError("Complete company step first", code="wizard_order", status_code=400)
    await db.execute(delete(Market).where(Market.company_id == company.id))
    for m in body.markets:
        db.add(Market(id=uuid.uuid4(), company_id=company.id, **m.model_dump()))
    state = await _mark_step(db, "markets")
    await write_audit(
        db,
        action="wizard.markets",
        actor_user_id=user.id,
        actor_username=user.username,
        details={"count": len(body.markets)},
        **client_meta(request),
    )
    return {"success": True, "count": len(body.markets), "wizard": state}


def _is_secret_key(key: str, secret_keys: set[str]) -> bool:
    return (
        key in secret_keys
        or "password" in key
        or "token" in key
        or "secret" in key
        or key.endswith("api_key")
        or key == "api_key"
    )


async def _store_kv(
    db,
    category: str,
    data: dict[str, Any],
    *,
    user_id,
    secret_keys: set[str] | None = None,
):
    """Persist wizard fields. Skip empty values and masked secret placeholders (keep existing)."""
    secret_keys = secret_keys or set()
    for key, value in data.items():
        if value is None or value == "":
            continue
        if isinstance(value, (dict, list)):
            value = str(value)
        else:
            value = str(value)
        if _is_secret_key(key, secret_keys) and is_masked_secret(value):
            continue
        await upsert_setting(
            db,
            category=category,
            key=key,
            value=value,
            is_secret=_is_secret_key(key, secret_keys),
            updated_by=user_id,
        )


@router.post("/emails")
async def step_emails(body: EmailSettingsStep, db: DbSession, user: OwnerUser, request: Request):
    existing_pw = await get_setting(db, "email", "smtp_password")
    incoming = body.smtp_password
    if not incoming or is_masked_secret(incoming or ""):
        if not existing_pw:
            raise MesigoError("SMTP password is required", code="smtp_password_required", status_code=400)
    await _store_kv(
        db,
        "email",
        body.model_dump(),
        user_id=user.id,
        secret_keys={"smtp_password"},
    )
    state = await _mark_step(db, "emails")
    await write_audit(db, action="wizard.emails", actor_user_id=user.id, actor_username=user.username, **client_meta(request))
    return {"success": True, "wizard": state}


@router.post("/messaging")
async def step_messaging(body: MessagingSettingsStep, db: DbSession, user: OwnerUser, request: Request):
    await _store_kv(db, "messaging", body.model_dump(), user_id=user.id)
    state = await _mark_step(db, "messaging")
    await write_audit(db, action="wizard.messaging", actor_user_id=user.id, actor_username=user.username, **client_meta(request))
    return {"success": True, "wizard": state}


@router.post("/social")
async def step_social(body: SocialSettingsStep, db: DbSession, user: OwnerUser, request: Request):
    await _store_kv(db, "social", body.model_dump(), user_id=user.id)
    state = await _mark_step(db, "social")
    await write_audit(db, action="wizard.social", actor_user_id=user.id, actor_username=user.username, **client_meta(request))
    return {"success": True, "wizard": state}


@router.post("/banking-logistics")
async def step_banking(body: BankingLogisticsStep, db: DbSession, user: OwnerUser, request: Request):
    await _store_kv(
        db,
        "banking_logistics",
        body.model_dump(),
        user_id=user.id,
        secret_keys={"primary_bank_account", "logistics_api_key"},
    )
    state = await _mark_step(db, "banking_logistics")
    await write_audit(
        db, action="wizard.banking_logistics", actor_user_id=user.id, actor_username=user.username, **client_meta(request)
    )
    return {"success": True, "wizard": state}


@router.post("/llm")
async def step_llm(body: LlmSettingsStep, db: DbSession, user: OwnerUser, request: Request):
    existing_key = await get_setting(db, "llm", "api_key")
    incoming = body.api_key
    if not incoming or is_masked_secret(incoming or ""):
        if not existing_key:
            raise MesigoError("LLM API key is required", code="llm_key_required", status_code=400)
    await _store_kv(db, "llm", body.model_dump(), user_id=user.id, secret_keys={"api_key"})
    state = await _mark_step(db, "llm")
    await write_audit(db, action="wizard.llm", actor_user_id=user.id, actor_username=user.username, **client_meta(request))
    return {"success": True, "wizard": state}


@router.post("/approval-matrix")
async def step_approval(body: ApprovalMatrixStep, db: DbSession, user: OwnerUser, request: Request):
    for rule in body.rules:
        existing = (
            await db.execute(select(ApprovalRule).where(ApprovalRule.action_key == rule.action_key))
        ).scalar_one_or_none()
        if existing:
            existing.display_name = rule.display_name
            existing.agent_id = rule.agent_id
            existing.mode = rule.mode
            existing.amount_limit = rule.amount_limit
            existing.currency = rule.currency
            existing.requires_owner = rule.requires_owner
            existing.is_active = True
        else:
            db.add(ApprovalRule(id=uuid.uuid4(), **rule.model_dump()))
    state = await _mark_step(db, "approval_matrix")
    await write_audit(
        db,
        action="wizard.approval_matrix",
        actor_user_id=user.id,
        actor_username=user.username,
        details={"count": len(body.rules)},
        **client_meta(request),
    )
    return {"success": True, "wizard": state}


@router.get("/approval-matrix")
async def get_approval(db: DbSession, user: CurrentUser):
    result = await db.execute(select(ApprovalRule).order_by(ApprovalRule.action_key))
    rules = result.scalars().all()
    return {
        "rules": [
            {
                "action_key": r.action_key,
                "display_name": r.display_name,
                "agent_id": r.agent_id,
                "mode": r.mode,
                "amount_limit": float(r.amount_limit) if r.amount_limit is not None else None,
                "currency": r.currency,
                "requires_owner": r.requires_owner,
                "is_active": r.is_active,
            }
            for r in rules
        ]
    }


@router.post("/doc-categories")
async def step_docs(body: DocCategoriesStep, db: DbSession, user: OwnerUser, request: Request):
    for cat in body.categories:
        existing = (
            await db.execute(select(DocumentCategory).where(DocumentCategory.slug == cat.slug))
        ).scalar_one_or_none()
        if existing:
            existing.name = cat.name
            existing.description = cat.description
            existing.retention_days = cat.retention_days
        else:
            db.add(DocumentCategory(id=uuid.uuid4(), **cat.model_dump()))
    state = await _mark_step(db, "doc_categories")
    await write_audit(
        db, action="wizard.doc_categories", actor_user_id=user.id, actor_username=user.username, **client_meta(request)
    )
    return {"success": True, "wizard": state}


@router.post("/staff-roles")
async def step_roles(body: StaffRolesStep, db: DbSession, user: OwnerUser, request: Request):
    for role in body.roles:
        existing = (await db.execute(select(Role).where(Role.name == role.name))).scalar_one_or_none()
        if existing:
            if not existing.is_system:
                existing.description = role.description
                existing.permissions = role.permissions
        else:
            db.add(
                Role(
                    id=uuid.uuid4(),
                    name=role.name,
                    description=role.description,
                    permissions=role.permissions,
                    is_system=False,
                )
            )
    state = await _mark_step(db, "staff_roles")
    await write_audit(
        db, action="wizard.staff_roles", actor_user_id=user.id, actor_username=user.username, **client_meta(request)
    )
    return {"success": True, "wizard": state}


@router.post("/owner-phones")
async def step_phones(body: OwnerPhonesStep, db: DbSession, user: OwnerUser, request: Request):
    await upsert_setting(
        db,
        category="owner_phones",
        key="phones",
        value=",".join(body.phones),
        is_secret=True,
        description="Owner notification / approval phones",
        updated_by=user.id,
    )
    if body.primary_phone:
        await upsert_setting(
            db,
            category="owner_phones",
            key="primary_phone",
            value=body.primary_phone,
            is_secret=True,
            updated_by=user.id,
        )
    if body.primary_phone and not user.phone:
        user.phone = body.primary_phone
    state = await _mark_step(db, "owner_phones")
    await write_audit(
        db, action="wizard.owner_phones", actor_user_id=user.id, actor_username=user.username, **client_meta(request)
    )
    return {"success": True, "wizard": state}


@router.post("/voice-biometric")
async def step_voice(body: VoiceEnrollmentStep, db: DbSession, user: OwnerUser, request: Request):
    """Mark voice step; actual sample upload via /auth/voice/enroll."""
    await upsert_setting(
        db,
        category="voice",
        key="enrollment_phrase",
        value=body.enrollment_phrase,
        is_secret=False,
        updated_by=user.id,
    )
    state = await _mark_step(db, "voice_biometric")
    await write_audit(
        db, action="wizard.voice_biometric", actor_user_id=user.id, actor_username=user.username, **client_meta(request)
    )
    return {
        "success": True,
        "wizard": state,
        "message": "Upload voice sample via POST /api/v1/auth/voice/enroll to finish biometric enrollment.",
        "enrollment_phrase": body.enrollment_phrase,
    }


@router.post("/complete", response_model=WizardCompleteResponse)
async def complete_wizard(db: DbSession, user: OwnerUser, request: Request):
    state = await _wizard_state(db)
    missing = [s for s in WIZARD_STEPS if s not in (state.get("completed_steps") or [])]
    # Allow complete if core steps done; soft-warn on optional gaps
    core = {"company", "products", "markets", "llm", "approval_matrix", "owner_phones"}
    missing_core = [s for s in missing if s in core]
    if missing_core:
        raise MesigoError(
            f"Complete required steps first: {', '.join(missing_core)}",
            code="wizard_incomplete",
            status_code=400,
        )
    company = (await db.execute(select(Company).where(Company.is_active.is_(True)).limit(1))).scalar_one_or_none()
    state["completed"] = True
    state["completed_at"] = datetime.now(timezone.utc).isoformat()
    state["missing_optional"] = missing
    await set_system_state(db, "setup_wizard", state)
    await write_audit(
        db,
        action="wizard.complete",
        actor_user_id=user.id,
        actor_username=user.username,
        **client_meta(request),
        details={"missing_optional": missing},
    )
    return WizardCompleteResponse(
        completed=True,
        message="Setup complete. Credentials are encrypted in-system — no owner .env editing required.",
        company_id=company.id if company else None,
    )


@router.get("/settings-meta")
async def settings_meta(db: DbSession, user: OwnerUser, category: str | None = None):
    """List encrypted settings metadata (secrets masked)."""
    return {"settings": await list_settings_meta(db, category)}


@router.get("/data")
async def wizard_data(db: DbSession, user: OwnerUser):
    """
    Full wizard hydration payload for reopen / refresh.
    Secrets are masked (e.g. sk-…xxxx); non-secrets returned plaintext.
    """
    company = (
        await db.execute(select(Company).where(Company.is_active.is_(True)).limit(1))
    ).scalar_one_or_none()
    products = []
    markets = []
    if company:
        products = [
            {
                "name": p.name,
                "sku": p.sku,
                "hs_code": p.hs_code,
                "category": p.category,
                "description": p.description,
                "unit": p.unit,
                "is_import": p.is_import,
                "is_export": p.is_export,
            }
            for p in (
                await db.execute(select(Product).where(Product.company_id == company.id).order_by(Product.created_at))
            ).scalars().all()
        ]
        markets = [
            {
                "name": m.name,
                "country_code": m.country_code,
                "region": m.region,
                "currency": m.currency,
                "direction": m.direction,
                "notes": m.notes,
            }
            for m in (
                await db.execute(select(Market).where(Market.company_id == company.id).order_by(Market.created_at))
            ).scalars().all()
        ]

    approval = (
        await db.execute(select(ApprovalRule).where(ApprovalRule.is_active.is_(True)).order_by(ApprovalRule.action_key))
    ).scalars().all()
    categories = (
        await db.execute(select(DocumentCategory).order_by(DocumentCategory.name))
    ).scalars().all()
    roles = (await db.execute(select(Role).order_by(Role.name))).scalars().all()

    email = await settings_map(db, "email")
    messaging = await settings_map(db, "messaging")
    social = await settings_map(db, "social")
    banking = await settings_map(db, "banking_logistics")
    llm = await settings_map(db, "llm")
    owner_phones = await settings_map(db, "owner_phones")
    voice = await settings_map(db, "voice")

    phones_raw = owner_phones.get("phones") or ""
    # phones stored encrypted → masked as prefix…suffix; for display of CSV we decrypt via get_setting
    phones_plain = await get_setting(db, "owner_phones", "phones")
    primary_plain = await get_setting(db, "owner_phones", "primary_phone")

    state = await _wizard_state(db)
    return {
        "status": {
            "completed": bool(state.get("completed")),
            "current_step": state.get("current_step", "company"),
            "completed_steps": state.get("completed_steps") or [],
            "steps": WIZARD_STEPS,
        },
        "company": (
            {
                "legal_name": company.legal_name,
                "trade_name": company.trade_name,
                "registration_number": company.registration_number,
                "tax_id": company.tax_id,
                "country": company.country,
                "address": company.address,
                "website": company.website,
                "phone": company.phone,
                "email": company.email,
            }
            if company
            else None
        ),
        "products": products,
        "markets": markets,
        "emails": email,
        "messaging": messaging,
        "social": social,
        "banking_logistics": banking,
        "llm": llm,
        "approval_matrix": {
            "rules": [
                {
                    "action_key": r.action_key,
                    "display_name": r.display_name,
                    "agent_id": r.agent_id,
                    "mode": r.mode,
                    "amount_limit": float(r.amount_limit) if r.amount_limit is not None else None,
                    "currency": r.currency,
                    "requires_owner": r.requires_owner,
                }
                for r in approval
            ]
        },
        "doc_categories": {
            "categories": [
                {
                    "name": c.name,
                    "slug": c.slug,
                    "description": c.description,
                    "retention_days": c.retention_days,
                }
                for c in categories
            ]
        },
        "staff_roles": {
            "roles": [
                {
                    "name": r.name,
                    "description": r.description,
                    "permissions": r.permissions or {},
                    "is_system": r.is_system,
                }
                for r in roles
            ]
        },
        "owner_phones": {
            "phones": phones_plain or "",
            "primary_phone": primary_plain or "",
            # also expose masked variants for UI hinting if needed
            "phones_masked": owner_phones.get("phones"),
            "primary_phone_masked": owner_phones.get("primary_phone"),
        },
        "voice_biometric": {
            "enrollment_phrase": voice.get("enrollment_phrase")
            or "Mesigo AI authorize my voice for business operations",
            "label": "primary",
        },
    }
