#!/usr/bin/env bash
# Bootstrap Mesigo on a Hostinger VPS over SSH.
# Does NOTHING unless MESIGO_VPS_HOST and MESIGO_VPS_USER are set.
# Do not run until the owner provides IP, user, and credentials.

set -euo pipefail

if [[ -z "${MESIGO_VPS_HOST:-}" || -z "${MESIGO_VPS_USER:-}" ]]; then
  cat <<'EOF'
Refusing to connect: set MESIGO_VPS_HOST and MESIGO_VPS_USER first.

Example:
  export MESIGO_VPS_HOST=203.0.113.10
  export MESIGO_VPS_USER=root
  export MESIGO_SSH_KEY=~/.ssh/mesigo_vps   # optional
  ./scripts/vps-bootstrap.sh
EOF
  exit 1
fi

SSH_OPTS=(-o StrictHostKeyChecking=accept-new)
if [[ -n "${MESIGO_SSH_KEY:-}" ]]; then
  SSH_OPTS+=(-i "${MESIGO_SSH_KEY}")
fi

REMOTE="${MESIGO_VPS_USER}@${MESIGO_VPS_HOST}"
echo "Connecting to ${REMOTE} ..."

ssh "${SSH_OPTS[@]}" "$REMOTE" 'bash -s' <<'REMOTE'
set -euo pipefail
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
fi
sudo mkdir -p /opt/mesigo
sudo chown "$(whoami)":"$(whoami)" /opt/mesigo
cd /opt/mesigo
if [[ ! -d .git ]]; then
  git clone https://github.com/patelabhishek2020-bot/MESIGO-ROBOT.git .
fi
git fetch origin main
git checkout main
git pull origin main
if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env — edit secrets before: docker compose up -d --build"
  echo "Generate with: ./scripts/gen-secrets.sh"
else
  docker compose up -d --build
  docker compose ps
  curl -fsS http://127.0.0.1:8000/health || true
fi
REMOTE

echo "Done. Complete Setup Wizard in the browser; do not put owner API keys in .env."
