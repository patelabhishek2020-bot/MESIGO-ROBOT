# Mesigo AI

Fully autonomous 24/7 **Import-Export Business Operating System**. After Setup Wizard, the owner runs the business through voice/text with full approval control — no ongoing developer dependency for credentials or day-to-day config.

## What's in this foundation PR

1. **Modular monorepo**
   - `apps/api` — FastAPI backend (Central Brain, auth, wizard, encrypted settings)
   - `apps/web` — Next.js scientific dark dashboard
2. **Docker Compose** for Hostinger VPS — Postgres, Redis, API, Web
3. **Postgres schema + Alembic migrations** — company/products/markets, encrypted settings, users/roles, audit logs, CRM stubs, documents, approval matrix, voice biometrics
4. **Master Setup Wizard** (first-launch + reopenable) — company, products, markets, emails, WhatsApp/Twilio/WeChat, social, banking/logistics/CHA, LLM keys, approval matrix, doc categories, staff roles, owner phones, voice biometric enrollment
5. **Auth** — username/password + voice biometric enrollment hooks
6. **Central AI Brain** orchestrator + agent registry stubs for agents 2–12
7. Logging, error handling, security headers, audit trail

> Owner secrets are **not** managed via `.env`. Infrastructure bootstrap vars only live in `.env`; integration credentials go through the Setup Wizard into **encrypted settings**.

## Agents

| # | Agent | Status |
|---|--------|--------|
| 1 | Central AI Brain (Master Orchestrator) | Foundation ready |
| 2 | Lead Generation & CRM | Stub |
| 3 | Communication | Stub |
| 4 | Supplier & Rate | Stub |
| 5 | Logistics & Documentation | Stub |
| 6 | Finance & Accounting | Stub |
| 7 | Compliance & Government Rules | Stub |
| 8 | Document Vault | Stub |
| 9 | HR & Office + Staff Panel | Stub |
| 10 | Self-Development | Stub |
| 11 | Graphics & Document Design | Stub |
| 12 | Social Media Management | Stub |

## Quick start (Docker / Hostinger VPS)

```bash
cp .env.example .env

# Generate strong secrets
openssl rand -hex 32   # -> SECRET_KEY
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# -> SETTINGS_ENCRYPTION_KEY

# Edit .env with the values above + strong POSTGRES_PASSWORD
# Set NEXT_PUBLIC_API_URL to your VPS public API URL when deploying

docker compose up -d --build
```

Services:

| Service | Default port | URL |
|---------|--------------|-----|
| Web dashboard | 3000 | http://HOST:3000 |
| API | 8000 | http://HOST:8000 |
| Postgres | 5432 | internal |
| Redis | 6379 | internal |

Bootstrap login (change immediately via wizard / change-password):

- Username: `owner` (or `BOOTSTRAP_OWNER_USERNAME`)
- Password: value of `BOOTSTRAP_OWNER_PASSWORD`

On first login the UI routes to the **Setup Wizard**.

## Local API development (without full Compose)

```bash
# Start only dependencies
docker compose up -d postgres redis

cd apps/api
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=postgresql+asyncpg://mesigo:change-me-strong-password@localhost:5432/mesigo
export DATABASE_URL_SYNC=postgresql://mesigo:change-me-strong-password@localhost:5432/mesigo
export SECRET_KEY=dev-secret
export SETTINGS_ENCRYPTION_KEY="$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

```bash
cd apps/web
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

## Key API routes

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/v1/auth/login` | Username/password login |
| GET | `/api/v1/auth/me` | Current user |
| POST | `/api/v1/auth/voice/enroll` | Voice biometric sample upload |
| GET/POST | `/api/v1/wizard/*` | Setup Wizard steps + reopen/complete |
| GET | `/api/v1/brain/status` | Orchestrator + agent registry |
| POST | `/api/v1/brain/route` | Route an intent through the Brain |
| GET | `/health` | Liveness |

## Security basics

- Passwords hashed with bcrypt
- JWT bearer auth
- Fernet-encrypted settings store (wizard-managed)
- Audit log for auth, wizard, and brain routing
- Security headers middleware (`X-Content-Type-Options`, `X-Frame-Options`, HSTS on HTTPS)
- CORS allow-list via `API_CORS_ORIGINS`
- API docs disabled when `ENVIRONMENT=production`

## Repository layout

```
apps/api/          FastAPI + Alembic + agents
apps/web/          Next.js dashboard
infra/postgres/    DB init extensions
docker-compose.yml VPS stack
.env.example       Infrastructure-only template
```

## Next build phases (out of scope here)

Full implementations of agents 2–12, Whisper STT/TTS speaker recognition model wiring, self-update pipeline, and production hardening beyond foundation.
