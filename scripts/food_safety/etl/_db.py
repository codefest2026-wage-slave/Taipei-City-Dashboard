"""Shared DB-connection helper for food_safety ETL loaders.

Resolution order for each DB_* setting (first wins):
  1. Process environment (override at invocation)
  2. scripts/food_safety/.env.script  (gitignored, user-maintained)
  3. docker/.env                        (BE config, useful only for docker hostnames)
  4. Hard defaults                      (host-reachable local docker)

Translates docker-internal hostnames `postgres-data` / `postgres-manager`
to the host-published `localhost:5433` / `localhost:5432` so the same
connection logic works whether you're on host running against local
docker or pointing at a cloud DB.
"""
import os
from pathlib import Path

FS_ROOT = Path(__file__).resolve().parents[1]            # scripts/food_safety/
REPO_ROOT = FS_ROOT.parents[1]                            # repo root


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


def _normalize_host_port(host: str, port: str, internal_name: str, external_port: str):
    """Translate docker-internal hostnames to host-reachable values."""
    if host == internal_name:
        return "localhost", external_port
    return host, port


def _kwargs(prefix: str, internal_name: str, external_port: str, default_dbname: str) -> dict:
    host = _resolve(f"{prefix}_HOST", "localhost")
    port = _resolve(f"{prefix}_PORT", external_port)
    host, port = _normalize_host_port(host, port, internal_name, external_port)
    return {
        "host":     host,
        "port":     int(port),
        "dbname":   _resolve(f"{prefix}_DBNAME", default_dbname),
        "user":     _resolve(f"{prefix}_USER", "postgres"),
        "password": _resolve(f"{prefix}_PASSWORD", ""),
        "sslmode":  _resolve(f"{prefix}_SSLMODE", "disable"),
    }


def db_kwargs() -> dict:
    """psycopg2.connect kwargs for the dashboard DB."""
    return _kwargs("DB_DASHBOARD", "postgres-data", "5433", "dashboard")


def manager_kwargs() -> dict:
    """psycopg2.connect kwargs for the dashboardmanager DB."""
    return _kwargs("DB_MANAGER", "postgres-manager", "5432", "dashboardmanager")
