# School Meal Ingredients ETL — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver `scripts/school_meal_ingredients/` — two ETL pipelines that (1) crawl 校園食材登入平台 OpenAPI for 雙北 全年月 CSV snapshots, (2) dedupe 食材名稱 across snapshots into a new `school_meal_ingredient_names` table — mirroring `scripts/labor_safety/` pattern. **Code only; no DB writes, no API calls performed by Claude.** User runs `apply.sh` themselves.

**Architecture:** Mirror `scripts/labor_safety/` exactly. Shell orchestrators (`apply.sh`/`rollback.sh`/`backup_db.sh`) source `_db_env.sh`, run psql via `docker run --rm postgres:17`, then invoke Python ETL. Python ETL connects via psycopg2 with kwargs from `_db.py`. Snapshot crawler is resumable via `manifest.json` and exits gracefully on token expiry. Dedupe loader is `TRUNCATE … RESTART IDENTITY` + `execute_values`.

**Tech Stack:** Bash, Python 3 (`requests`, `psycopg2`), PostgreSQL 16/17 (via docker), psql in `postgres:17` container.

**Spec:** `docs/superpowers/specs/2026-05-02-school-meal-ingredients-design.md`

**Worktree base:** `/Users/teddy_peng/Projects/my/Taipei-City-Dashboard/.worktrees/school-meal-ingredients/`. All paths below are relative to that base.

**Standing rules**
- After every task, `git add` only the files that task created/modified, then commit with the exact message shown.
- Do **not** run `apply.sh`, `rollback.sh`, `backup_db.sh`, `snapshot_apis.py`, or `load_ingredient_names.py` against any DB or external API in any task. Verification = file existence + `python3 -c "import ast; ast.parse(open(p).read())"` for python files + `bash -n` for shell scripts.
- Do **not** modify `scripts/labor_safety/`.
- All file content shown is **literal**; copy verbatim.

---

## Task 1: Scaffold directory + gitignore + env example + backups placeholder

**Files:**
- Create: `scripts/school_meal_ingredients/.gitignore`
- Create: `scripts/school_meal_ingredients/.env.script.example`
- Create: `scripts/school_meal_ingredients/backups/.gitkeep`
- Create: `scripts/school_meal_ingredients/etl/__init__.py` (empty file, makes the directory importable)
- Create: `scripts/school_meal_ingredients/migrations/.gitkeep`
- Create: `scripts/school_meal_ingredients/snapshots/.gitkeep`

- [ ] **Step 1: Create directory tree**

```bash
mkdir -p scripts/school_meal_ingredients/{etl,migrations,snapshots,backups}
```

- [ ] **Step 2: Write `scripts/school_meal_ingredients/.gitignore`**

```gitignore
backups/*
!backups/.gitkeep
.env.script
__pycache__/
*.pyc
```

(Note: `snapshots/*.csv` and `snapshots/manifest.json` are NOT ignored — they ship in git per spec Q5=A.)

- [ ] **Step 3: Write `scripts/school_meal_ingredients/.env.script.example`**

```bash
# scripts/school_meal_ingredients/.env.script.example
#
# Copy to scripts/school_meal_ingredients/.env.script (gitignored) and fill in
# the right values. Sourced by _db_env.sh which is in turn sourced by
# apply.sh / rollback.sh / backup_db.sh and read by the Python ETL loaders.

# ── 校園食材登入平台 OpenAPI credentials ─────────────────────────────
# accesscode contains a timestamp; expires per-session. Update before each
# long crawl. Get a fresh value by visiting the platform's OpenAPI page.
FATRACE_ACCESSCODE=
# JSESSIONID cookie value (just the value, not the full Cookie: header).
FATRACE_COOKIE=

# ── DB target (only DASHBOARD is used by this project; manager unused) ──
# Local docker
DB_DASHBOARD_HOST=localhost
DB_DASHBOARD_PORT=5433
DB_DASHBOARD_USER=postgres
DB_DASHBOARD_PASSWORD=test1234
DB_DASHBOARD_DBNAME=dashboard
DB_DASHBOARD_SSLMODE=disable

# Postgres client image used by docker run (server is 16.x; 17 client is
# forward-compatible).
# PG_CLIENT_IMAGE=postgres:17

# ── Cloud (uncomment + adjust) ──────────────────────────────────────
# DB_DASHBOARD_HOST=your-cloud-host.example.com
# DB_DASHBOARD_PORT=5432
# DB_DASHBOARD_USER=your_user
# DB_DASHBOARD_PASSWORD=your_password
# DB_DASHBOARD_DBNAME=dashboard
# DB_DASHBOARD_SSLMODE=require
```

- [ ] **Step 4: Create empty marker files**

```bash
touch scripts/school_meal_ingredients/backups/.gitkeep
touch scripts/school_meal_ingredients/migrations/.gitkeep
touch scripts/school_meal_ingredients/snapshots/.gitkeep
touch scripts/school_meal_ingredients/etl/__init__.py
```

- [ ] **Step 5: Verify file presence**

Run: `find scripts/school_meal_ingredients -type f | sort`
Expected output (exactly):
```
scripts/school_meal_ingredients/.env.script.example
scripts/school_meal_ingredients/.gitignore
scripts/school_meal_ingredients/backups/.gitkeep
scripts/school_meal_ingredients/etl/__init__.py
scripts/school_meal_ingredients/migrations/.gitkeep
scripts/school_meal_ingredients/snapshots/.gitkeep
```

- [ ] **Step 6: Commit**

```bash
git add scripts/school_meal_ingredients/
git commit -m "feat(school-meal): scaffold directory + gitignore + env example"
```

---

## Task 2: `_db_env.sh` (shell DB env helper)

**Files:**
- Create: `scripts/school_meal_ingredients/_db_env.sh`

**Why:** Shell scripts (`apply.sh` / `rollback.sh` / `backup_db.sh`) source this to get `DB_URL_DASHBOARD` and `pg_psql` / `pg_dump_to` helpers. Adapted from `scripts/labor_safety/_db_env.sh` but **DASHBOARD-only** (this project does not touch `dashboardmanager`).

- [ ] **Step 1: Write `scripts/school_meal_ingredients/_db_env.sh`**

```bash
# scripts/school_meal_ingredients/_db_env.sh
#
# Source this from apply.sh / rollback.sh / backup_db.sh to populate
# DB_URL_DASHBOARD plus a `pg_psql` shell function that runs psql against
# the dashboard DB (host's local docker, or cloud).
#
# Credential resolution order (first wins per key):
#   1. value already in environment (override at invocation)
#   2. scripts/school_meal_ingredients/.env.script   (user-maintained, gitignored)
#   3. docker/.env                                   (BE config; only useful for local docker)
#   4. defaults below                                (host-reachable local docker)

_SMI_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_SMI_REPO="$(cd "$_SMI_ROOT/../.." && pwd)"

_load_env_file() {
  local f="$1"
  [ -f "$f" ] || return 0
  while IFS='=' read -r key val; do
    case "$key" in
      DB_DASHBOARD_*|FATRACE_*)
        if [ -z "${!key+x}" ]; then
          val="${val%$'\r'}"
          val="${val#\"}"; val="${val%\"}"
          val="${val#\'}"; val="${val%\'}"
          export "$key=$val"
        fi
        ;;
    esac
  done < <(grep -E '^(DB_DASHBOARD|FATRACE)_[A-Z_]+=' "$f" 2>/dev/null)
}

_load_env_file "$_SMI_ROOT/.env.script"
_load_env_file "$_SMI_REPO/docker/.env"

: "${PG_CLIENT_IMAGE:=postgres:17}"
export PG_CLIENT_IMAGE

# Defaults — local docker postgres exposed on host
: "${DB_DASHBOARD_HOST:=localhost}"
: "${DB_DASHBOARD_PORT:=5433}"
: "${DB_DASHBOARD_USER:=postgres}"
: "${DB_DASHBOARD_PASSWORD:=test1234}"
: "${DB_DASHBOARD_DBNAME:=dashboard}"
: "${DB_DASHBOARD_SSLMODE:=disable}"

# Translate docker-internal hostname (BE config bleed-through) to localhost.
case "$DB_DASHBOARD_HOST" in
  postgres-data) DB_DASHBOARD_HOST=localhost; DB_DASHBOARD_PORT=5433 ;;
esac

_urlenc() { python3 -c "import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=''))" "$1"; }

DB_URL_DASHBOARD="postgresql://${DB_DASHBOARD_USER}:$(_urlenc "$DB_DASHBOARD_PASSWORD")@${DB_DASHBOARD_HOST}:${DB_DASHBOARD_PORT}/${DB_DASHBOARD_DBNAME}?sslmode=${DB_DASHBOARD_SSLMODE}"

export DB_URL_DASHBOARD
export DB_DASHBOARD_HOST DB_DASHBOARD_PORT DB_DASHBOARD_USER DB_DASHBOARD_PASSWORD DB_DASHBOARD_DBNAME DB_DASHBOARD_SSLMODE

# pg_psql -1 < some.sql        — run psql with single-transaction file
# pg_psql -c "SELECT ..."      — run psql with arbitrary args
pg_psql() {
  docker run --rm -i --network=host "$PG_CLIENT_IMAGE" psql "$DB_URL_DASHBOARD" -v ON_ERROR_STOP=1 "$@"
}

# pg_dump_to FILE              — pg_dump dashboard DB to FILE
pg_dump_to() {
  local out="$1"
  docker run --rm --network=host "$PG_CLIENT_IMAGE" pg_dump "$DB_URL_DASHBOARD" > "$out"
}
```

- [ ] **Step 2: Verify shell syntax**

Run: `bash -n scripts/school_meal_ingredients/_db_env.sh`
Expected: no output (success).

- [ ] **Step 3: Commit**

```bash
git add scripts/school_meal_ingredients/_db_env.sh
git commit -m "feat(school-meal): add _db_env.sh (shell DB env, dashboard-only)"
```

---

## Task 3: `etl/_db.py` (Python psycopg2 kwargs helper)

**Files:**
- Create: `scripts/school_meal_ingredients/etl/_db.py`

**Why:** Python loaders need `psycopg2.connect(**kwargs)` parameters resolved with the same precedence as the shell. Adapted from `scripts/labor_safety/etl/_db.py` but DASHBOARD-only.

- [ ] **Step 1: Write `scripts/school_meal_ingredients/etl/_db.py`**

```python
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
```

- [ ] **Step 2: Verify python syntax**

Run: `python3 -c "import ast; ast.parse(open('scripts/school_meal_ingredients/etl/_db.py').read())"`
Expected: no output (success).

- [ ] **Step 3: Commit**

```bash
git add scripts/school_meal_ingredients/etl/_db.py
git commit -m "feat(school-meal): add etl/_db.py (DB kwargs + FATRACE creds)"
```

---

## Task 4: Migration up + down

**Files:**
- Create: `scripts/school_meal_ingredients/migrations/001_create_ingredient_names.up.sql`
- Create: `scripts/school_meal_ingredients/migrations/001_create_ingredient_names.down.sql`

- [ ] **Step 1: Write `migrations/001_create_ingredient_names.up.sql`**

```sql
-- scripts/school_meal_ingredients/migrations/001_create_ingredient_names.up.sql
-- Project: 校園食材登入平台 食材名稱去重表
-- Purpose: Create school_meal_ingredient_names dictionary table in `dashboard`.
--          Idempotent (CREATE TABLE IF NOT EXISTS) and transactional.
-- down:    migrations/001_create_ingredient_names.down.sql
BEGIN;

CREATE TABLE IF NOT EXISTS school_meal_ingredient_names (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(200) UNIQUE NOT NULL,
    occurrence      INTEGER       NOT NULL DEFAULT 0,
    first_seen_ym   VARCHAR(7),                       -- 'YYYY-MM'
    last_seen_ym    VARCHAR(7),                       -- 'YYYY-MM'
    source_counties TEXT[]                            -- e.g. {'臺北市','新北市'}
);

CREATE INDEX IF NOT EXISTS idx_school_meal_ingredient_names_name
    ON school_meal_ingredient_names (name);

COMMIT;
```

- [ ] **Step 2: Write `migrations/001_create_ingredient_names.down.sql`**

```sql
-- scripts/school_meal_ingredients/migrations/001_create_ingredient_names.down.sql
BEGIN;
DROP TABLE IF EXISTS school_meal_ingredient_names;
COMMIT;
```

- [ ] **Step 3: Verify SQL syntax (parse-only)**

```bash
# psql --no-psqlrc -c "" prints the SQL parse error if any. We just want
# to ensure it's valid SQL; we run it with --dry-run-equivalent: just
# check the file exists and has BEGIN/COMMIT.
grep -c '^BEGIN;$' scripts/school_meal_ingredients/migrations/001_create_ingredient_names.up.sql
grep -c '^COMMIT;$' scripts/school_meal_ingredients/migrations/001_create_ingredient_names.up.sql
grep -c '^BEGIN;$' scripts/school_meal_ingredients/migrations/001_create_ingredient_names.down.sql
grep -c '^COMMIT;$' scripts/school_meal_ingredients/migrations/001_create_ingredient_names.down.sql
```
Expected: each prints `1`.

- [ ] **Step 4: Remove `migrations/.gitkeep` (no longer needed)**

```bash
rm scripts/school_meal_ingredients/migrations/.gitkeep
```

- [ ] **Step 5: Commit**

```bash
git add scripts/school_meal_ingredients/migrations/
git commit -m "feat(school-meal): add 001_create_ingredient_names migration"
```

---

## Task 5: `apply.sh`

**Files:**
- Create: `scripts/school_meal_ingredients/apply.sh`

- [ ] **Step 1: Write `scripts/school_meal_ingredients/apply.sh`**

```bash
#!/usr/bin/env bash
# Apply school meal ingredients migrations and load deduped names.
# Idempotent: safe to run multiple times. Use rollback.sh to revert.
#
# Connects via env vars resolved by _db_env.sh — works for local docker
# postgres or cloud DB depending on scripts/school_meal_ingredients/.env.script.
#
# IMPORTANT: This does NOT call snapshot_apis.py. Run that manually to
# refresh the committed CSVs in snapshots/ before running apply.sh.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=./_db_env.sh
source "$ROOT/_db_env.sh"

echo "▶ target dashboard: $DB_DASHBOARD_HOST:$DB_DASHBOARD_PORT/$DB_DASHBOARD_DBNAME (sslmode=$DB_DASHBOARD_SSLMODE)"
echo

echo "1/3 migrations up ..."
pg_psql -1 < "$ROOT/migrations/001_create_ingredient_names.up.sql"

echo "2/3 ETL ..."
python3 "$ROOT/etl/load_ingredient_names.py"

echo "3/3 verify row count ..."
pg_psql -c "SELECT 'school_meal_ingredient_names' AS t, COUNT(*) FROM school_meal_ingredient_names;"

echo "✅ apply complete"
```

- [ ] **Step 2: chmod +x**

```bash
chmod +x scripts/school_meal_ingredients/apply.sh
```

- [ ] **Step 3: Verify shell syntax**

Run: `bash -n scripts/school_meal_ingredients/apply.sh`
Expected: no output.

- [ ] **Step 4: Commit**

```bash
git add scripts/school_meal_ingredients/apply.sh
git commit -m "feat(school-meal): add apply.sh (migrations + ETL + verify)"
```

---

## Task 6: `rollback.sh`

**Files:**
- Create: `scripts/school_meal_ingredients/rollback.sh`

- [ ] **Step 1: Write `scripts/school_meal_ingredients/rollback.sh`**

```bash
#!/usr/bin/env bash
# Rollback school meal ingredients: drop school_meal_ingredient_names.
# Idempotent: safe even if apply was never run.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=./_db_env.sh
source "$ROOT/_db_env.sh"

echo "▶ target dashboard: $DB_DASHBOARD_HOST:$DB_DASHBOARD_PORT/$DB_DASHBOARD_DBNAME (sslmode=$DB_DASHBOARD_SSLMODE)"
echo

echo "1/1 down: drop tables ..."
pg_psql -1 < "$ROOT/migrations/001_create_ingredient_names.down.sql"

echo "✅ rollback complete"
```

- [ ] **Step 2: chmod +x**

```bash
chmod +x scripts/school_meal_ingredients/rollback.sh
```

- [ ] **Step 3: Verify shell syntax**

Run: `bash -n scripts/school_meal_ingredients/rollback.sh`
Expected: no output.

- [ ] **Step 4: Commit**

```bash
git add scripts/school_meal_ingredients/rollback.sh
git commit -m "feat(school-meal): add rollback.sh"
```

---

## Task 7: `backup_db.sh`

**Files:**
- Create: `scripts/school_meal_ingredients/backup_db.sh`

- [ ] **Step 1: Write `scripts/school_meal_ingredients/backup_db.sh`**

```bash
#!/usr/bin/env bash
# Backup the dashboard database before any apply/rollback.
# Output: scripts/school_meal_ingredients/backups/<UTC-timestamp>/dashboard.sql
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=./_db_env.sh
source "$ROOT/_db_env.sh"

TS="$(date -u +%Y%m%d-%H%M%SZ)"
OUT="$ROOT/backups/$TS"
mkdir -p "$OUT"

echo "▶ target dashboard: $DB_DASHBOARD_HOST:$DB_DASHBOARD_PORT/$DB_DASHBOARD_DBNAME (sslmode=$DB_DASHBOARD_SSLMODE)"
echo

echo "▶ Dumping dashboard …"
pg_dump_to "$OUT/dashboard.sql"

echo
echo "✅ backup → $OUT"
ls -lh "$OUT"
echo
echo "Restore example:"
echo "  cat $OUT/dashboard.sql | docker run --rm -i --network=host $PG_CLIENT_IMAGE psql \"\$DB_URL_DASHBOARD\""
```

- [ ] **Step 2: chmod +x**

```bash
chmod +x scripts/school_meal_ingredients/backup_db.sh
```

- [ ] **Step 3: Verify shell syntax**

Run: `bash -n scripts/school_meal_ingredients/backup_db.sh`
Expected: no output.

- [ ] **Step 4: Commit**

```bash
git add scripts/school_meal_ingredients/backup_db.sh
git commit -m "feat(school-meal): add backup_db.sh"
```

---

## Task 8: `etl/snapshot_apis.py` (resumable API crawler)

**Files:**
- Create: `scripts/school_meal_ingredients/etl/snapshot_apis.py`

- [ ] **Step 1: Write `scripts/school_meal_ingredients/etl/snapshot_apis.py`**

```python
#!/usr/bin/env python3
"""Crawl 校園食材登入平台 OpenAPI for 雙北 全年月 CSV datasets.

Endpoints (POST, JSON body):
  /cateringservice/openapi/county/            list counties
  /cateringservice/openapi/opendatadataset/   list datasets for (year, month, county)
  /cateringservice/openapi/opendatadownload/  get CSV download link

Auth: accesscode in body + JSESSIONID cookie. Both ephemeral.

Output: scripts/school_meal_ingredients/snapshots/
  - <county-code>_<YYYYMM>_<grade>_<datasetname>.csv
  - food_chinese_names.csv  (for the one-shot 食材中文名稱資料集)
  - manifest.json           (resumable index)

Usage:
    # First run — uses .env.script + defaults (year-from=2020/01 to current)
    python3 scripts/school_meal_ingredients/etl/snapshot_apis.py

    # Override token at invocation:
    FATRACE_ACCESSCODE=xxxxx python3 .../snapshot_apis.py

    # Restrict range:
    python3 .../snapshot_apis.py --year-from 2024 --month-from 1 \\
                                  --year-to 2024 --month-to 12

When the API rejects the token, the script prints an actionable message,
saves the manifest, and exits 0. Rerun with a fresh token to resume.
"""
import argparse
import datetime
import io
import json
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _db import fatrace_credentials  # noqa: E402

SMI_ROOT      = Path(__file__).resolve().parent.parent
SNAPSHOTS_DIR = SMI_ROOT / "snapshots"
MANIFEST_PATH = SNAPSHOTS_DIR / "manifest.json"

API_BASE = "https://fatraceschool.k12ea.gov.tw/cateringservice/openapi"
TARGET_COUNTIES = ["臺北市", "新北市"]
COUNTY_CODE = {"臺北市": "tpe", "新北市": "ntpc", "全國": "nation"}
SLEEP_BETWEEN_REQ = 0.5

ONE_SHOT_DATASET = "食材中文名稱資料集"
ONE_SHOT_FILENAME = "food_chinese_names.csv"


# ── manifest IO ─────────────────────────────────────────────────────

def load_manifest():
    if not MANIFEST_PATH.exists():
        return {"completed": [], "empty_months": [], "last_run_at": None}
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def save_manifest(m):
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    m["last_run_at"] = datetime.datetime.utcnow().isoformat() + "Z"
    MANIFEST_PATH.write_text(
        json.dumps(m, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def completed_keys(m):
    """Set of (year, month, county, grade, datasetname) tuples already done."""
    return {(e["year"], e["month"], e["county"], e["grade"], e["datasetname"])
            for e in m["completed"]}


def empty_month_keys(m):
    """Set of (year, month, county) for which datasetList was empty."""
    return {(e["year"], e["month"], e["county"]) for e in m["empty_months"]}


# ── filename ────────────────────────────────────────────────────────

def filename_for(entry):
    """entry: dict with year/month/county/grade/datasetname.

    Returns the CSV filename to write under snapshots/."""
    if entry["datasetname"] == ONE_SHOT_DATASET:
        return ONE_SHOT_FILENAME
    code = COUNTY_CODE.get(entry["county"], entry["county"])
    yyyymm = f"{entry['year']}{int(entry['month']):02d}"
    grade_part = f"_{entry['grade']}" if entry["grade"] else ""
    return f"{code}_{yyyymm}{grade_part}_{entry['datasetname']}.csv"


# ── filter ──────────────────────────────────────────────────────────

def should_download(entry, queried_county, seen_completed):
    """Return True if we want this entry (per spec Q3=A)."""
    if entry["datasetname"] == ONE_SHOT_DATASET:
        return ("", "", "", "", ONE_SHOT_DATASET) not in seen_completed

    county = entry["county"]
    grade = entry["grade"]

    # city × grade — always
    if county == queried_county and grade in ("國中小", "高中職"):
        return True

    # 全國-only (county=全國, grade=""), once per (year, month)
    if county == "全國" and grade == "":
        return True

    # 全國 × grade — skip
    return False


# ── HTTP ────────────────────────────────────────────────────────────

class TokenExpired(Exception):
    pass


TOKEN_FAIL_HINTS = ("授權", "token", "失效", "認證", "登入")


def _post_json(path, body, cookie):
    url = f"{API_BASE}/{path}/"
    headers = {"Content-Type": "application/json"}
    if cookie:
        headers["Cookie"] = cookie if "=" in cookie else f"JSESSIONID={cookie}"
    resp = requests.post(url, json=body, headers=headers, timeout=60)
    if resp.status_code in (401, 403):
        raise TokenExpired(f"HTTP {resp.status_code}")
    resp.raise_for_status()
    data = resp.json()
    msg = (data.get("message") or "").lower()
    # Heuristic: only surface as TokenExpired if message mentions auth and
    # there's no expected payload key (datasetList / link).
    if any(h.lower() in msg for h in TOKEN_FAIL_HINTS) and \
            "datasetList" not in data and "link" not in data:
        raise TokenExpired(data.get("message"))
    return data


def list_datasets(accesscode, cookie, year, month, county):
    body = {"accesscode": accesscode, "year": year, "month": month, "county": county}
    return _post_json("opendatadataset", body, cookie).get("datasetList", []) or []


def get_download_link(accesscode, cookie, entry):
    body = {
        "accesscode":  accesscode,
        "year":        entry["year"],
        "month":       entry["month"],
        "county":      entry["county"],
        "grade":       entry["grade"],
        "datasetname": entry["datasetname"],
    }
    return _post_json("opendatadownload", body, cookie).get("link") or ""


def download_csv(link, cookie):
    headers = {}
    if cookie:
        headers["Cookie"] = cookie if "=" in cookie else f"JSESSIONID={cookie}"
    resp = requests.get(link, headers=headers, timeout=120)
    resp.raise_for_status()
    return resp.content


# ── main loop ───────────────────────────────────────────────────────

def months_in_range(yf, mf, yt, mt):
    y, m = yf, mf
    while (y, m) <= (yt, mt):
        yield y, m
        m += 1
        if m > 12:
            y += 1; m = 1


def count_csv_rows(content_bytes):
    try:
        text = content_bytes.decode("utf-8-sig", errors="replace")
        return max(0, sum(1 for _ in io.StringIO(text)) - 1)  # minus header
    except Exception:
        return -1


def graceful_exit(manifest, msg):
    save_manifest(manifest)
    print(f"\n⚠️  {msg}", file=sys.stderr)
    print(f"   manifest saved: {MANIFEST_PATH}", file=sys.stderr)
    print(f"   completed: {len(manifest['completed'])}, "
          f"empty months: {len(manifest['empty_months'])}", file=sys.stderr)
    print( "   Update FATRACE_ACCESSCODE / FATRACE_COOKIE and rerun to resume.",
          file=sys.stderr)
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--year-from",  type=int, default=2020)
    parser.add_argument("--month-from", type=int, default=1)
    today = datetime.date.today()
    parser.add_argument("--year-to",  type=int, default=today.year)
    parser.add_argument("--month-to", type=int, default=today.month)
    parser.add_argument("--accesscode", default=None,
                        help="Override FATRACE_ACCESSCODE")
    parser.add_argument("--cookie", default=None,
                        help="Override FATRACE_COOKIE (JSESSIONID value or full Cookie header)")
    args = parser.parse_args()

    creds = fatrace_credentials()
    accesscode = args.accesscode or creds["accesscode"]
    cookie     = args.cookie     or creds["cookie"]

    if not accesscode:
        print("❌ FATRACE_ACCESSCODE not set. Provide via --accesscode, env, or .env.script.",
              file=sys.stderr)
        sys.exit(2)

    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest()
    completed = completed_keys(manifest)
    empties   = empty_month_keys(manifest)
    errors = []

    print(f"▶ snapshot range: {args.year_from}/{args.month_from:02d} → "
          f"{args.year_to}/{args.month_to:02d}")
    print(f"▶ already completed: {len(completed)}, empty months: {len(empties)}")

    for year, month in months_in_range(args.year_from, args.month_from,
                                       args.year_to,   args.month_to):
        ym_str = f"{year}/{month:02d}"
        for queried_county in TARGET_COUNTIES:
            if (str(year), str(month).zfill(2), queried_county) in empties:
                continue
            try:
                ds_list = list_datasets(accesscode, cookie, str(year),
                                        str(month).zfill(2), queried_county)
            except TokenExpired as e:
                graceful_exit(manifest,
                              f"FATRACE token expired during list_datasets {ym_str} {queried_county}: {e}")
            except requests.RequestException as e:
                msg = f"⚠️  list_datasets {ym_str} {queried_county}: {e}"
                print(msg, file=sys.stderr)
                errors.append(msg)
                continue

            if not ds_list:
                manifest["empty_months"].append({
                    "county": queried_county,
                    "year":   str(year),
                    "month":  str(month).zfill(2),
                })
                save_manifest(manifest)
                print(f"  {ym_str} {queried_county}: empty datasetList")
                continue

            for entry in ds_list:
                key = (entry.get("year", ""), entry.get("month", ""),
                       entry.get("county", ""), entry.get("grade", ""),
                       entry.get("datasetname", ""))
                if key in completed:
                    continue
                if not should_download(entry, queried_county, completed):
                    continue

                try:
                    link = get_download_link(accesscode, cookie, entry)
                    if not link:
                        msg = f"⚠️  no link for {key}"
                        print(msg, file=sys.stderr)
                        errors.append(msg)
                        time.sleep(SLEEP_BETWEEN_REQ)
                        continue
                    csv_bytes = download_csv(link, cookie)
                except TokenExpired as e:
                    graceful_exit(manifest,
                                  f"FATRACE token expired during download {key}: {e}")
                except requests.RequestException as e:
                    msg = f"⚠️  download {key}: {e}"
                    print(msg, file=sys.stderr)
                    errors.append(msg)
                    time.sleep(SLEEP_BETWEEN_REQ)
                    continue

                if not csv_bytes:
                    msg = f"⚠️  empty body for {key}"
                    print(msg, file=sys.stderr)
                    errors.append(msg)
                    time.sleep(SLEEP_BETWEEN_REQ)
                    continue

                fn = filename_for(entry)
                out_path = SNAPSHOTS_DIR / fn
                out_path.write_bytes(csv_bytes)
                rows = count_csv_rows(csv_bytes)
                manifest["completed"].append({
                    "year":          entry.get("year", ""),
                    "month":         entry.get("month", ""),
                    "county":        entry.get("county", ""),
                    "grade":         entry.get("grade", ""),
                    "datasetname":   entry.get("datasetname", ""),
                    "filename":      fn,
                    "downloaded_at": datetime.datetime.utcnow().isoformat() + "Z",
                    "rows":          rows,
                })
                completed.add(key)
                save_manifest(manifest)
                print(f"  ✅ {fn}: {rows:,} rows")
                time.sleep(SLEEP_BETWEEN_REQ)

    save_manifest(manifest)
    print("\n── summary ──")
    print(f"  total completed: {len(manifest['completed'])}")
    print(f"  empty months:    {len(manifest['empty_months'])}")
    print(f"  errors:          {len(errors)}")
    if errors:
        for e in errors[:20]:
            print(f"    {e}")
        if len(errors) > 20:
            print(f"    … and {len(errors) - 20} more")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: chmod +x**

```bash
chmod +x scripts/school_meal_ingredients/etl/snapshot_apis.py
```

- [ ] **Step 3: Verify python syntax**

Run: `python3 -c "import ast; ast.parse(open('scripts/school_meal_ingredients/etl/snapshot_apis.py').read())"`
Expected: no output.

- [ ] **Step 4: Verify pure-function helpers (no DB / no network)**

Run:
```bash
python3 - <<'PY'
import sys
sys.path.insert(0, "scripts/school_meal_ingredients/etl")
import snapshot_apis as s

# filename
e_city = {"year":"2024","month":"10","county":"臺北市","grade":"國中小",
          "datasetname":"午餐食材及供應商資料集"}
assert s.filename_for(e_city) == "tpe_202410_國中小_午餐食材及供應商資料集.csv"

e_nation = {"year":"2024","month":"10","county":"全國","grade":"",
            "datasetname":"學校供餐團膳業者資料集"}
assert s.filename_for(e_nation) == "nation_202410_學校供餐團膳業者資料集.csv"

e_oneshot = {"year":"","month":"","county":"","grade":"",
             "datasetname":"食材中文名稱資料集"}
assert s.filename_for(e_oneshot) == "food_chinese_names.csv"

# should_download
seen = set()
assert s.should_download(e_city, "臺北市", seen) is True
assert s.should_download(e_city, "新北市", seen) is False  # wrong queried city
assert s.should_download(e_nation, "臺北市", seen) is True

e_skip = {"year":"2024","month":"10","county":"全國","grade":"國中小",
          "datasetname":"午餐食材及供應商資料集"}
assert s.should_download(e_skip, "臺北市", seen) is False  # 全國 × grade — skip

assert s.should_download(e_oneshot, "臺北市", seen) is True
seen.add(("","","","","食材中文名稱資料集"))
assert s.should_download(e_oneshot, "臺北市", seen) is False  # already seen

# months_in_range
months = list(s.months_in_range(2024, 11, 2025, 2))
assert months == [(2024,11),(2024,12),(2025,1),(2025,2)], months

# count_csv_rows
csv = b"a,b\n1,2\n3,4\n"
assert s.count_csv_rows(csv) == 2

print("OK")
PY
```
Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add scripts/school_meal_ingredients/etl/snapshot_apis.py
git commit -m "feat(school-meal): add snapshot_apis.py (resumable API crawler)"
```

---

## Task 9: `etl/load_ingredient_names.py` (dedupe loader)

**Files:**
- Create: `scripts/school_meal_ingredients/etl/load_ingredient_names.py`

- [ ] **Step 1: Write `scripts/school_meal_ingredients/etl/load_ingredient_names.py`**

```python
#!/usr/bin/env python3
"""Aggregate unique 食材名稱 across all snapshot CSVs into school_meal_ingredient_names.

Reads scripts/school_meal_ingredients/snapshots/*.csv (CSVs only — no
HTTP), detects the 食材名稱 column per file, aggregates name -> {count,
first_ym, last_ym, counties_set}, and writes the result via TRUNCATE +
INSERT into the dashboard DB.

Dual-city compliance (CLAUDE.md): aborts if either 臺北市 or 新北市 is
missing from the aggregated source_counties.
"""
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _db import db_kwargs  # noqa: E402

SMI_ROOT      = Path(__file__).resolve().parent.parent
SNAPSHOTS_DIR = SMI_ROOT / "snapshots"

INGREDIENT_HEADER = "食材名稱"
FALLBACK_HEADERS  = ("品名", "食材", "菜色")  # warn when used

INSERT_SQL = """
INSERT INTO school_meal_ingredient_names
    (name, occurrence, first_seen_ym, last_seen_ym, source_counties)
VALUES %s
"""

CITY_FROM_PREFIX = {"tpe": "臺北市", "ntpc": "新北市", "nation": "全國"}


def parse_filename(path: Path):
    """Return (year, month, county) — strings; (None, None, None) for one-shot."""
    name = path.name
    if name == "food_chinese_names.csv":
        return None, None, None
    m = re.match(r"^(tpe|ntpc|nation)_(\d{4})(\d{2})(?:_[^_]+)?_.+\.csv$", name)
    if not m:
        return None, None, None
    prefix, yyyy, mm = m.group(1), m.group(2), m.group(3)
    return yyyy, mm, CITY_FROM_PREFIX.get(prefix)


def detect_ingredient_column(reader_fieldnames, path):
    """Return the field name in this CSV that holds 食材名稱, or None."""
    if not reader_fieldnames:
        return None
    fnmap = {f.strip(): f for f in reader_fieldnames if f}
    if INGREDIENT_HEADER in fnmap:
        return fnmap[INGREDIENT_HEADER]
    for fb in FALLBACK_HEADERS:
        for clean, original in fnmap.items():
            if fb in clean:
                print(f"  ⚠️  {path.name}: using fallback column {original!r} (no '食材名稱')",
                      file=sys.stderr)
                return original
    return None


def aggregate():
    agg = {}  # name -> [count, first_ym, last_ym, counties_set]
    skipped = []
    file_count = 0
    row_count = 0

    csv_files = sorted(SNAPSHOTS_DIR.glob("*.csv"))
    if not csv_files:
        print("❌ no snapshot CSVs found — run snapshot_apis.py first.", file=sys.stderr)
        sys.exit(1)

    for path in csv_files:
        year, month, county = parse_filename(path)
        ym = f"{year}-{month}" if (year and month) else None

        try:
            with path.open(encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                col = detect_ingredient_column(reader.fieldnames, path)
                if col is None:
                    skipped.append((path.name, "no ingredient column"))
                    continue
                file_count += 1
                for row in reader:
                    raw = row.get(col)
                    name = (raw or "").strip()
                    if not name:
                        continue
                    name = name[:200]  # match VARCHAR(200)
                    rec = agg.get(name)
                    if rec is None:
                        rec = [0, ym, ym, set()]
                        agg[name] = rec
                    rec[0] += 1
                    if ym:
                        if rec[1] is None or ym < rec[1]:
                            rec[1] = ym
                        if rec[2] is None or ym > rec[2]:
                            rec[2] = ym
                    if county and county != "全國":
                        rec[3].add(county)
                    row_count += 1
        except Exception as e:
            skipped.append((path.name, f"read error: {e}"))
            continue

    return agg, skipped, file_count, row_count


def main():
    print("=== load_ingredient_names ===")
    agg, skipped, file_count, row_count = aggregate()

    print(f"  files used:   {file_count}")
    print(f"  rows seen:    {row_count:,}")
    print(f"  unique names: {len(agg):,}")
    if skipped:
        print(f"  skipped files: {len(skipped)}")
        for fn, reason in skipped[:10]:
            print(f"    {fn} — {reason}")
        if len(skipped) > 10:
            print(f"    … and {len(skipped) - 10} more")

    if not agg:
        print("❌ no ingredient names aggregated", file=sys.stderr)
        sys.exit(1)

    # Dual-city enforcement (CLAUDE.md)
    all_counties = set()
    for v in agg.values():
        all_counties |= v[3]
    print(f"  counties seen: {sorted(all_counties)}")
    if "臺北市" not in all_counties or "新北市" not in all_counties:
        print("❌ dual-city requirement not met — both 臺北市 AND 新北市 must appear in source_counties",
              file=sys.stderr)
        sys.exit(1)

    rows = []
    for name, (count, first_ym, last_ym, counties) in agg.items():
        rows.append((name, count, first_ym, last_ym, sorted(counties)))

    with psycopg2.connect(**db_kwargs()) as conn, conn.cursor() as cur:
        cur.execute("BEGIN")
        cur.execute("TRUNCATE school_meal_ingredient_names RESTART IDENTITY")
        execute_values(cur, INSERT_SQL, rows, page_size=500)
        cur.execute("COMMIT")

    print(f"✅ {len(rows):,} rows → school_meal_ingredient_names")

    # Top 20 by occurrence
    top = sorted(agg.items(), key=lambda kv: kv[1][0], reverse=True)[:20]
    print("\n── top 20 by occurrence ──")
    for name, (count, *_rest) in top:
        print(f"  {count:>6,}  {name}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: chmod +x**

```bash
chmod +x scripts/school_meal_ingredients/etl/load_ingredient_names.py
```

- [ ] **Step 3: Verify python syntax**

Run: `python3 -c "import ast; ast.parse(open('scripts/school_meal_ingredients/etl/load_ingredient_names.py').read())"`
Expected: no output.

- [ ] **Step 4: Verify pure-function helpers (parse_filename + detect_ingredient_column)**

Run:
```bash
python3 - <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, "scripts/school_meal_ingredients/etl")
import load_ingredient_names as L

# parse_filename — happy paths
assert L.parse_filename(Path("tpe_202410_國中小_午餐食材及供應商資料集.csv")) == ("2024","10","臺北市")
assert L.parse_filename(Path("ntpc_202503_高中職_午餐菜色及食材資料集.csv")) == ("2025","03","新北市")
assert L.parse_filename(Path("nation_202410_學校供餐團膳業者資料集.csv")) == ("2024","10","全國")
assert L.parse_filename(Path("food_chinese_names.csv")) == (None, None, None)
assert L.parse_filename(Path("garbage.csv")) == (None, None, None)

# detect_ingredient_column
assert L.detect_ingredient_column(["序號","食材名稱","供應商"], Path("x")) == "食材名稱"
# fallback (warning is allowed; we just need a non-None column)
got = L.detect_ingredient_column(["序號","品名","供應商"], Path("x"))
assert got == "品名", got
# no match
assert L.detect_ingredient_column(["序號","廠商","電話"], Path("x")) is None
assert L.detect_ingredient_column(None, Path("x")) is None

print("OK")
PY
```
Expected: `OK` (a "fallback column" warning printed to stderr is fine).

- [ ] **Step 5: Commit**

```bash
git add scripts/school_meal_ingredients/etl/load_ingredient_names.py
git commit -m "feat(school-meal): add load_ingredient_names.py (CSV → dedup → DB)"
```

---

## Task 10: `README.md`

**Files:**
- Create: `scripts/school_meal_ingredients/README.md`

- [ ] **Step 1: Write `scripts/school_meal_ingredients/README.md`**

````markdown
# School Meal Ingredients — 校園食材登入平台 ETL

Crawl 校園食材登入平台 OpenAPI for 雙北 全年月 CSV datasets, then dedupe
食材名稱 into a dictionary table for downstream AI consumers.

Mirrors the layout and conventions of `scripts/labor_safety/`.

## Quick start

```bash
# 0. Copy and edit env file
cp scripts/school_meal_ingredients/.env.script.example \
   scripts/school_meal_ingredients/.env.script
$EDITOR scripts/school_meal_ingredients/.env.script
# Set FATRACE_ACCESSCODE, FATRACE_COOKIE, DB_DASHBOARD_*

# 1. (Optional) Refresh CSV snapshots from the live API
#    Long-running. Use --year-from/--year-to to limit scope.
python3 scripts/school_meal_ingredients/etl/snapshot_apis.py

# 2. Backup before applying (idempotent migration, but be safe)
./scripts/school_meal_ingredients/backup_db.sh

# 3. Apply: migrations + dedupe loader + verify
./scripts/school_meal_ingredients/apply.sh

# 4. Rollback (drops the table)
./scripts/school_meal_ingredients/rollback.sh
```

## Layout

```
scripts/school_meal_ingredients/
├── README.md                    # this file
├── .env.script.example          # FATRACE_* + DB_DASHBOARD_* template
├── .gitignore                   # backups/, .env.script, __pycache__
├── apply.sh                     # idempotent: migrations + ETL + verify
├── rollback.sh                  # drop table
├── backup_db.sh                 # pg_dump dashboard
├── _db_env.sh                   # shell env (sourced by *.sh)
├── etl/
│   ├── _db.py                   # psycopg2 kwargs + FATRACE creds resolver
│   ├── snapshot_apis.py         # resumable API crawler (manual run)
│   └── load_ingredient_names.py # CSV → dedupe → DB (called by apply.sh)
├── snapshots/                   # committed CSVs + manifest.json
└── migrations/
    ├── 001_create_ingredient_names.up.sql
    └── 001_create_ingredient_names.down.sql
```

## Data flow

```
                 (manual)
fatraceschool API ─────► snapshot_apis.py ─► snapshots/*.csv + manifest.json
                                                       │
                                          (apply.sh)   │
                                                       ▼
                                       load_ingredient_names.py
                                                       │
                                                       ▼
                                  dashboard.school_meal_ingredient_names
```

`apply.sh` reads only committed CSVs; it does **not** call the live API.
Run `snapshot_apis.py` separately when you want to refresh the snapshots.

## Datasets in scope

The platform exposes 6 unique `datasetname` values; we download:

| Dataset | County / grade | Source of 食材名稱? |
|---|---|---|
| 學校供餐團膳業者資料集 | 全國 | no |
| 調味料及供應商資料集 | 全國 | maybe |
| 午餐食材及供應商資料集 | 臺北市 / 新北市 × 國中小 / 高中職 | **yes** |
| 午餐菜色資料集 | 臺北市 / 新北市 × 國中小 / 高中職 | no |
| 午餐菜色及食材資料集 | 臺北市 / 新北市 × 國中小 / 高中職 | **yes** |
| 食材中文名稱資料集 | one-shot | yes (standard names) |

The `全國 × 國中小/高中職` variants are **skipped** to avoid superset
duplication of the city-specific data.

## Snapshot crawler — token expiry

`accesscode` and `JSESSIONID` expire per session. When the API rejects
the token, `snapshot_apis.py`:

1. Saves `manifest.json` with what's been completed.
2. Prints `⚠️  FATRACE token expired …` to stderr.
3. Exits **0** (so a wrapper script can rerun cleanly).

Refresh `FATRACE_ACCESSCODE` / `FATRACE_COOKIE` and rerun — it picks up
where it left off.

## Time range

Default: `2020/01` → current month. Override:

```bash
python3 .../snapshot_apis.py --year-from 2024 --month-from 1 \
                             --year-to 2024 --month-to 12
```

Months that return empty `datasetList` are recorded so subsequent runs
skip them.

## Dual-city compliance

Per project CLAUDE.md, the loader **aborts** if neither 臺北市 nor 新北市
appears in the aggregated `source_counties`. This catches accidental
single-city snapshots before they reach the DB.

## Restore from backup

```bash
source scripts/school_meal_ingredients/_db_env.sh
cat scripts/school_meal_ingredients/backups/<TS>/dashboard.sql \
  | docker run --rm -i --network=host "$PG_CLIENT_IMAGE" psql "$DB_URL_DASHBOARD"
```
````

- [ ] **Step 2: Commit**

```bash
git add scripts/school_meal_ingredients/README.md
git commit -m "docs(school-meal): add README"
```

---

## Task 11: Final tree verification + delivery checklist

**Files:** none changed; verification only.

- [ ] **Step 1: Verify final tree**

Run: `find scripts/school_meal_ingredients -type f -not -path '*/__pycache__/*' | sort`
Expected (exact list):
```
scripts/school_meal_ingredients/.env.script.example
scripts/school_meal_ingredients/.gitignore
scripts/school_meal_ingredients/README.md
scripts/school_meal_ingredients/_db_env.sh
scripts/school_meal_ingredients/apply.sh
scripts/school_meal_ingredients/backup_db.sh
scripts/school_meal_ingredients/backups/.gitkeep
scripts/school_meal_ingredients/etl/__init__.py
scripts/school_meal_ingredients/etl/_db.py
scripts/school_meal_ingredients/etl/load_ingredient_names.py
scripts/school_meal_ingredients/etl/snapshot_apis.py
scripts/school_meal_ingredients/migrations/001_create_ingredient_names.down.sql
scripts/school_meal_ingredients/migrations/001_create_ingredient_names.up.sql
scripts/school_meal_ingredients/rollback.sh
scripts/school_meal_ingredients/snapshots/.gitkeep
scripts/school_meal_ingredients/README.md
```

(Note: `migrations/.gitkeep` removed in Task 4. `snapshots/.gitkeep` stays — it's a placeholder for the directory that will hold downloaded CSVs once the user runs `snapshot_apis.py`.)

- [ ] **Step 2: Verify executable bits**

Run:
```bash
ls -la scripts/school_meal_ingredients/*.sh \
       scripts/school_meal_ingredients/etl/*.py
```
Expected: `apply.sh`, `rollback.sh`, `backup_db.sh`, `etl/snapshot_apis.py`, `etl/load_ingredient_names.py` all have `x` in their permission bits.

- [ ] **Step 3: Verify all shell scripts parse**

```bash
for f in scripts/school_meal_ingredients/*.sh \
         scripts/school_meal_ingredients/_db_env.sh; do
  bash -n "$f" && echo "OK $f"
done
```
Expected: 4 lines, each `OK <path>`.

- [ ] **Step 4: Verify all python files parse**

```bash
for f in scripts/school_meal_ingredients/etl/*.py; do
  python3 -c "import ast; ast.parse(open('$f').read())" && echo "OK $f"
done
```
Expected: 3 lines, each `OK <path>`.

- [ ] **Step 5: Verify NO DB connection / API call was performed by Claude**

```bash
git -C . log --oneline origin/feat/labor-safety-radar..HEAD
```
Expected: ~10 commits, all under `feat(school-meal)` / `docs(school-meal)`. None mentions running `apply.sh` / `snapshot_apis.py` against any DB or API.

- [ ] **Step 6: Print delivery summary**

Print to console:
```
✅ school_meal_ingredients ETL ready for review.

Worktree: .worktrees/school-meal-ingredients/  (branch feat/school-meal-ingredients-etl)
Files:    scripts/school_meal_ingredients/

Next steps for the USER (not Claude):
  1. Edit scripts/school_meal_ingredients/.env.script with real values
  2. python3 scripts/school_meal_ingredients/etl/snapshot_apis.py  # populates snapshots/
  3. ./scripts/school_meal_ingredients/backup_db.sh                # safety backup
  4. ./scripts/school_meal_ingredients/apply.sh                    # creates table + loads dedupe
  5. (Optional) ./scripts/school_meal_ingredients/rollback.sh      # drops the table

Reminder: nothing has been written to any DB. The user explicitly opted to
run apply.sh themselves.
```

---

## Self-review

**Spec coverage check:**

| Spec section | Implementing task |
|---|---|
| Datasets in scope (6 unique, city×grade + 全國-only + one-shot) | Task 8 (`should_download`) |
| Time range (auto-probe 2020/01 → current) | Task 8 (`months_in_range` + argparse defaults) |
| Project layout | Task 1, 2, 3, 4, 5, 6, 7, 8, 9, 10 |
| Snapshot crawler inputs (CLI > env > .env.script) | Task 8 (argparse `--accesscode/--cookie` + `_db.py::fatrace_credentials`) |
| Filename convention | Task 8 (`filename_for`) |
| Manifest.json schema | Task 8 (load/save/append) |
| Failure modes (TokenExpired, network, empty body) | Task 8 (`graceful_exit`, error list) |
| Migration up/down on `dashboard` DB | Task 4 |
| Dedupe column detection (exact + fallback warning + skip) | Task 9 (`detect_ingredient_column`) |
| Aggregation (count, first/last ym, counties) | Task 9 (`aggregate`) |
| Dual-city enforcement | Task 9 (abort if either city missing) |
| TRUNCATE + execute_values write | Task 9 (`main`) |
| `apply.sh` 1/3 migrations / 2/3 ETL / 3/3 verify | Task 5 |
| `rollback.sh` (down) | Task 6 |
| `backup_db.sh` (pg_dump dashboard) | Task 7 |
| README documents dual-city + token expiry | Task 10 |
| No DB writes during code authoring | Standing rule + Task 11 step 5 |

**Placeholder scan:** All steps contain literal code or exact commands. No "TBD", "TODO", "implement later". The two open questions in the spec ("exact column header", "accesscode rotation") are handled live by the loader's fallback heuristic and the crawler's TokenExpired detector — no code TODOs needed.

**Type / name consistency:** `db_kwargs()`, `fatrace_credentials()`, `filename_for()`, `should_download()`, `parse_filename()`, `detect_ingredient_column()`, `aggregate()`, `months_in_range()`, `count_csv_rows()`, `graceful_exit()`, `pg_psql`, `pg_dump_to`, `DB_URL_DASHBOARD`, `PG_CLIENT_IMAGE`, `school_meal_ingredient_names` — all referenced consistently across tasks.
