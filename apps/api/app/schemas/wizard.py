"""Setup Wizard schemas — first launch + reopenable."""

from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class WizardStatus(BaseModel):
    completed: bool
    current_step: str
    completed_steps: list[str] = []
    steps: list[str]


class CompanyStep(BaseModel):
    legal_name: str = Field(min_length=1, max_length=255)
    trade_name: Optional[str] = None
    registration_number: Optional[str] = None
    tax_id: Optional[str] = None
    country: Optional[str] = None
    address: Optional[str] = None
    website: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None


class ProductIn(BaseModel):
    name: str
    sku: Optional[str] = None
    hs_code: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    unit: Optional[str] = None
    is_import: bool = True
    is_export: bool = True


class ProductsStep(BaseModel):
    products: list[ProductIn] = Field(min_length=1)


class MarketIn(BaseModel):
    name: str
    country_code: str = Field(min_length=2, max_length=8)
    region: Optional[str] = None
    currency: Optional[str] = None
    direction: str = "both"
    notes: Optional[str] = None


class MarketsStep(BaseModel):
    markets: list[MarketIn] = Field(min_length=1)


class EmailSettingsStep(BaseModel):
    smtp_host: str
    smtp_port: int = 587
    smtp_user: str
    smtp_password: str
    from_email: EmailStr
    from_name: Optional[str] = None
    use_tls: bool = True


class MessagingSettingsStep(BaseModel):
    # WhatsApp / Twilio / WeChat — all optional individually but stored encrypted
    twilio_account_sid: Optional[str] = None
    twilio_auth_token: Optional[str] = None
    twilio_whatsapp_from: Optional[str] = None
    whatsapp_business_token: Optional[str] = None
    wechat_app_id: Optional[str] = None
    wechat_app_secret: Optional[str] = None


class SocialSettingsStep(BaseModel):
    twitter_api_key: Optional[str] = None
    twitter_api_secret: Optional[str] = None
    linkedin_access_token: Optional[str] = None
    facebook_page_token: Optional[str] = None
    instagram_access_token: Optional[str] = None


class BankingLogisticsStep(BaseModel):
    primary_bank_name: Optional[str] = None
    primary_bank_account: Optional[str] = None
    swift_code: Optional[str] = None
    logistics_partner: Optional[str] = None
    logistics_api_key: Optional[str] = None
    cha_name: Optional[str] = None
    cha_license: Optional[str] = None
    cha_contact: Optional[str] = None


class LlmSettingsStep(BaseModel):
    provider: str = "openai"  # openai|anthropic|azure|custom
    api_key: str
    model: str = "gpt-4o"
    base_url: Optional[str] = None


class ApprovalRuleIn(BaseModel):
    action_key: str
    display_name: str
    agent_id: Optional[str] = None
    mode: str = Field(pattern="^(auto|approval|deny)$")
    amount_limit: Optional[float] = None
    currency: Optional[str] = "USD"
    requires_owner: bool = True


class ApprovalMatrixStep(BaseModel):
    rules: list[ApprovalRuleIn]


class DocCategoryIn(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    retention_days: Optional[int] = None


class DocCategoriesStep(BaseModel):
    categories: list[DocCategoryIn]


class StaffRoleIn(BaseModel):
    name: str
    description: Optional[str] = None
    permissions: dict[str, Any] = Field(default_factory=dict)


class StaffRolesStep(BaseModel):
    roles: list[StaffRoleIn]


class OwnerPhonesStep(BaseModel):
    phones: list[str] = Field(min_length=1)
    primary_phone: Optional[str] = None


class VoiceEnrollmentStep(BaseModel):
    enrollment_phrase: str = "Mesigo AI authorize my voice for business operations"
    label: str = "primary"
    # Actual audio uploaded via multipart endpoint; this marks step complete after enroll


class WizardCompleteResponse(BaseModel):
    completed: bool
    message: str
    company_id: Optional[UUID] = None
