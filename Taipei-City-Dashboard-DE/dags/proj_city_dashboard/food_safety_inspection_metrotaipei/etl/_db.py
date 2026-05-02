"""Shared DB-connection helper for food_safety_inspection_metrotaipei ETL.

Resolution order for each DB_DASHBOARD_* setting (first wins):
  1. Process environment (override at invocation)
  2. scripts/food_safety_inspection_metrotaipei/.env.script  (gitignored)
  3. docker/.env                                              (BE config)
  4. Hard defaults                                            (local docker)

When DB_DASHBOARD_HOST is the docker-internal name `postgres-data`, that
hostname only resolves when this Python process runs INSIDE the
br_dashboard network. From the host, override DB_DASHBOARD_HOST to a
reachable address in .env.script (or use apply.sh which runs psql in a
sidecar container attached to br_dashboard).
"""
import os
from pathlib import Path

FS_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = FS_ROOT.parents[1]


def _read_env(path: Path) -> dict:
    out: dict = {}
    if not path or not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


_ENV_SCRIPT = _read_env(FS_ROOT / ".env.script")
_ENV_DOCKER = _read_env(REPO_ROOT / "docker" / ".env")


def _resolve(key: str, default: str) -> str:
    return os.environ.get(key) or _ENV_SCRIPT.get(key) or _ENV_DOCKER.get(key) or default


def db_kwargs() -> dict:
    """psycopg2.connect kwargs for the dashboard DB."""
    return {
        "host":     _resolve("DB_DASHBOARD_HOST", "postgres-data"),
        "port":     int(_resolve("DB_DASHBOARD_PORT", "5432")),
        "dbname":   _resolve("DB_DASHBOARD_DBNAME", "dashboard"),
        "user":     _resolve("DB_DASHBOARD_USER", "postgres"),
        "password": _resolve("DB_DASHBOARD_PASSWORD", "test1234"),
        "sslmode":  _resolve("DB_DASHBOARD_SSLMODE", "disable"),
    }
