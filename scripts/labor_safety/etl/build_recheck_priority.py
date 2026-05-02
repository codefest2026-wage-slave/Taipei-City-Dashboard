#!/usr/bin/env python3
"""Run build_recheck_priority.sql to materialize labor_recheck_priority_{tpe,ntpc}.

The SQL itself does CREATE TABLE AS (drops & rebuilds), so this is idempotent
and safe to re-run. We invoke it via psycopg2 (not docker exec psql) so we
don't shell out and so connection settings stay consistent with the other loaders.
"""
from pathlib import Path

import psycopg2

from _db import db_kwargs

SQL_FILE = Path(__file__).resolve().parent.parent / "migrations" / "build_recheck_priority.sql"


def main():
    sql = SQL_FILE.read_text(encoding="utf-8")
    with psycopg2.connect(**db_kwargs()) as conn:
        conn.autocommit = False  # let the SQL's own BEGIN/COMMIT drive
        with conn.cursor() as cur:
            cur.execute(sql)
        # The SQL ends with COMMIT; an extra commit is a no-op.
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM labor_recheck_priority_tpe")
            tpe_n = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM labor_recheck_priority_ntpc")
            ntpc_n = cur.fetchone()[0]
    print(f"✅ {tpe_n:,} rows → labor_recheck_priority_tpe")
    print(f"✅ {ntpc_n:,} rows → labor_recheck_priority_ntpc")


if __name__ == "__main__":
    main()
