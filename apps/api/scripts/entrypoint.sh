#!/bin/sh
set -e

echo "[mesigo-api] waiting for database..."
python - <<'PY'
import os, time, sys
import psycopg2

url = os.environ.get("DATABASE_URL_SYNC", "")
# strip +asyncpg if somehow present
url = url.replace("postgresql+asyncpg://", "postgresql://")
for i in range(60):
    try:
        conn = psycopg2.connect(url)
        conn.close()
        print("[mesigo-api] database ready")
        sys.exit(0)
    except Exception as e:
        print(f"[mesigo-api] db not ready ({i}): {e}")
        time.sleep(1)
print("[mesigo-api] database timeout", file=sys.stderr)
sys.exit(1)
PY

echo "[mesigo-api] running migrations..."
alembic upgrade head

echo "[mesigo-api] starting API..."
exec "$@"
