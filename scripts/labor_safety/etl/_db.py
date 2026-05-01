"""Shared DB-connection helper for labor_safety ETL loaders.

Reads docker/.env from repo root and returns kwargs for psycopg2.connect()
pointing at the postgres-data container exposed on localhost:5433.
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def _resolve_env_file() -> Path:
    """Locate docker/.env. Prefer the current worktree; fall back to the
    main checkout (worktrees often don't carry an own .env)."""
    candidate = REPO_ROOT / "docker" / ".env"
    if candidate.exists():
        return candidate
    # Walk up to the parent that holds .worktrees/ and use its docker/.env.
    parts = REPO_ROOT.parts
    if ".worktrees" in parts:
        idx = parts.index(".worktrees")
        main_root = Path(*parts[:idx])
        alt = main_root / "docker" / ".env"
        if alt.exists():
            return alt
    return candidate  # return the not-existing one for clean error


ENV_FILE = _resolve_env_file()


def _read_env(path: Path) -> dict:
    """Tiny dotenv parser (no external dep) — KEY=VALUE per line, # comments."""
    out = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def db_kwargs() -> dict:
    """Return kwargs for psycopg2.connect() to the dashboard DB."""
    env = _read_env(ENV_FILE)
    return {
        "host":     "localhost",
        "port":     5433,  # postgres-data exposed port (verified via `docker port postgres-data`)
        "dbname":   env.get("DB_DASHBOARD_DBNAME", "dashboard"),
        "user":     env.get("DB_DASHBOARD_USER", "postgres"),
        "password": env.get("DB_DASHBOARD_PASSWORD", ""),
    }
