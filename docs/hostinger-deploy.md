# Hostinger VPS deploy (Mesigo AI)

**Status:** Docs/scripts only. Do **not** SSH deploy until the owner provides VPS IP, SSH user, and credentials.

## Prerequisites (owner to provide)

- VPS public IP / hostname
- SSH user (e.g. `root` or `ubuntu`)
- SSH auth (password or private key)
- Optional: domain name for HTTPS

## On the VPS (once credentials arrive)

```bash
# 1) Install Docker + Compose plugin
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER"   # re-login after

# 2) Clone main
sudo mkdir -p /opt/mesigo && sudo chown "$USER":"$USER" /opt/mesigo
cd /opt/mesigo
git clone https://github.com/patelabhishek2020-bot/MESIGO-ROBOT.git .
git checkout main

# 3) Infrastructure .env only (owner secrets go through Setup Wizard)
cp .env.example .env
./scripts/gen-secrets.sh   # paste SECRET_KEY + SETTINGS_ENCRYPTION_KEY into .env
# Also set strong POSTGRES_PASSWORD and BOOTSTRAP_OWNER_PASSWORD
# Set NEXT_PUBLIC_API_URL=http://YOUR_IP:8000  (or https://api.yourdomain)
# Set API_CORS_ORIGINS to the web origin(s)

# 4) Launch
docker compose up -d --build
docker compose ps
curl -fsS http://127.0.0.1:8000/health

# 5) Open firewall (Hostinger panel or ufw)
# allow 22, 80/443 (if reverse proxy), 3000, 8000 — or proxy 80→web and /api→api
```

## First login

1. Open `http://YOUR_IP:3000`
2. Login with bootstrap owner user from `.env`
3. Complete **Setup Wizard** (LLM, messaging, banking, approval matrix, phones, voice)
4. Change password immediately

## Updates (later)

```bash
cd /opt/mesigo
git pull origin main
docker compose up -d --build
```

Self-Development agent records approved deploys in-app; container swap remains an ops step with owner approval.

## Helper script

From a machine that will SSH in (after credentials exist):

```bash
export MESIGO_VPS_HOST=x.x.x.x
export MESIGO_VPS_USER=root
# export MESIGO_SSH_KEY=~/.ssh/mesigo_vps
./scripts/vps-bootstrap.sh
```

The script refuses to run if host/user are unset.
