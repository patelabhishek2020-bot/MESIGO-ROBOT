#!/usr/bin/env bash
set -euo pipefail
echo "SECRET_KEY=$(openssl rand -hex 32)"
python3 - <<'PY'
from cryptography.fernet import Fernet
print(f"SETTINGS_ENCRYPTION_KEY={Fernet.generate_key().decode()}")
PY
