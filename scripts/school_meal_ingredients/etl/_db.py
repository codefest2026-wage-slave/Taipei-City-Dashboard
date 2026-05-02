"""Shared DB-connection helper for school_meal_ingredients ETL loaders.

Resolution order for each DB_* setting (first wins):
  1. Process environment (override at invocation)
  2. scripts/school_meal_ingredients/.env.script  (gitignored, user-maintained)
  3. docker/.env                                   (BE config, useful for docker hostnames)
  4. Hard defaults                                 (host-reachable local docker)
"""
import os
from pathlib import Path

SMI_ROOT = Path(__file__).resolve().parents[1]            # scripts/school_meal_ingredients/
REPO_ROOT = SMI_ROOT.parents[1]                            # repo root


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


_ENV_SCRIPT = _read_env(SMI_ROOT / ".env.script")
_ENV_DOCKER = _read_env(REPO_ROOT / "docker" / ".env")


def _resolve(key: str, default: str) -> str:
    return os.environ.get(key) or _ENV_SCRIPT.get(key) or _ENV_DOCKER.get(key) or default


def _normalize_host_port(host: str, port: str):
    if host == "postgres-data":
        return "localhost", "5433"
    return host, port


def db_kwargs() -> dict:
    """psycopg2.connect kwargs for the dashboard DB."""
    host = _resolve("DB_DASHBOARD_HOST", "localhost")
    port = _resolve("DB_DASHBOARD_PORT", "5433")
    host, port = _normalize_host_port(host, port)
    return {
        "host":     host,
        "port":     int(port),
        "dbname":   _resolve("DB_DASHBOARD_DBNAME", "dashboard"),
        "user":     _resolve("DB_DASHBOARD_USER", "postgres"),
        "password": _resolve("DB_DASHBOARD_PASSWORD", ""),
        "sslmode":  _resolve("DB_DASHBOARD_SSLMODE", "disable"),
    }


def fatrace_credentials() -> dict:
    """Return {'accesscode': ..., 'cookie': ...} for the OpenAPI."""
    return {
        "accesscode": _resolve("FATRACE_ACCESSCODE", ""),
        "cookie":     _resolve("FATRACE_COOKIE", ""),
    }
