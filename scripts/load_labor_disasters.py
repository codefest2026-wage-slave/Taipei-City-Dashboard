"""
Fetch major workplace disaster (重大職災) records and load into PostgreSQL.

Data sources:
  - TPE: data.taipei dataset ab4ddbe2 (GPS-point records)
  - NTPC: data.ntpc dataset 80743c0e (district-level records)

Run from repo root:
  python scripts/load_labor_disasters.py

Then load:
  docker exec -i postgres-data psql -U postgres -d dashboard < /tmp/labor_disasters.sql
"""
import re
import json

import requests

SQL_OUT = "/tmp/labor_disasters.sql"


# ── Helpers ───────────────────────────────────────────────────────────────────

def q(s):
    """Escape single quotes for SQL string."""
    return str(s or "").replace("'", "''")


def roc_text_date(s):
    """Parse ROC text date like '113年12月31日' → '2024-12-31'."""
    m = re.match(r"(\d+)年(\d+)月(\d+)日", str(s or ""))
    if not m:
        return None
    return f"{int(m.group(1)) + 1911}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"


def roc_slash_date(s):
    """Parse ROC slash date like '108/02/01' → '2019-02-01'."""
    m = re.match(r"(\d+)/(\d+)/(\d+)", str(s or ""))
    if not m:
        return None
    return f"{int(m.group(1)) + 1911}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"


def parse_casualties(s):
    """Parse '1死0傷' → (deaths=1, injuries=0)."""
    m = re.match(r"(\d+)死(\d+)傷", str(s or ""))
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


# ── Dataset 1: TPE 重大職災 (GPS coordinates) ─────────────────────────────────

def build_tpe():
    print("Fetching TPE major workplace disasters (重大職災)...")
    base_url = "https://data.taipei/api/v1/dataset/ab4ddbe2-90f5-49a6-a7ad-45e5b6d14871"
    rows = []
    offset = 0
    limit = 1000
    while True:
        resp = requests.get(
            base_url,
            params={"scope": "resourceAquire", "limit": limit, "offset": offset},
            timeout=30,
        ).json()
        batch = resp["result"]["results"]
        rows.extend(batch)
        print(f"  offset={offset}: {len(batch)} records (total {len(rows)})")
        if len(batch) < limit:
            break
        offset += limit
    print(f"  Total raw TPE records: {len(rows)}")

    sql_rows = []
    skipped = 0
    for r in rows:
        # Parse coordinates
        try:
            lng = float(r.get("經度") or 0)
            lat = float(r.get("緯度") or 0)
        except (ValueError, TypeError):
            skipped += 1
            continue
        if lng == 0 or lat == 0:
            skipped += 1
            continue

        incident_date = roc_text_date(r.get("發生日期"))
        company_name = r.get("事業單位名稱", "")
        address = r.get("地址", "")
        disaster_type = r.get("災害類型", "")
        try:
            deaths = int(r.get("死亡人數") or 0)
        except (ValueError, TypeError):
            deaths = 0
        try:
            injuries = int(r.get("受傷人數") or 0)
        except (ValueError, TypeError):
            injuries = 0

        date_sql = f"'{incident_date}'" if incident_date else "NULL"
        sql_rows.append(
            f"({date_sql},'{q(company_name)}','{q(address)}',"
            f"'{q(disaster_type)}',{deaths},{injuries},{lng},{lat})"
        )

    print(f"  Skipped {skipped} records (invalid/zero coordinates)")
    print(f"  TPE rows to insert: {len(sql_rows)}")

    sql = "TRUNCATE TABLE labor_disasters_tpe RESTART IDENTITY;\n"
    if sql_rows:
        sql += (
            "INSERT INTO labor_disasters_tpe "
            "(incident_date,company_name,address,disaster_type,deaths,injuries,lng,lat) VALUES\n"
        )
        sql += ",\n".join(sql_rows) + ";\n"
    return sql, len(sql_rows)


# ── Dataset 2: NTPC 重大職災 (district-level) ─────────────────────────────────

def build_ntpc():
    print("Fetching NTPC major workplace disasters (重大職災)...")
    uuid = "80743c0e-b7e7-4d4a-825b-df354a542f65"
    records = []
    page = 0
    page_size = 1000
    while True:
        batch = requests.get(
            f"https://data.ntpc.gov.tw/api/datasets/{uuid}/json",
            params={"size": page_size, "page": page},
            timeout=30,
        ).json()
        if not batch:
            break
        records.extend(batch)
        print(f"  Page {page}: {len(batch)} records (total {len(records)})")
        if len(batch) < page_size:
            break
        page += 1
    print(f"  Total raw NTPC records: {len(records)}")

    sql_rows = []
    for r in records:
        incident_date = roc_slash_date(r.get("date"))
        disaster_type = r.get("type", "")
        deaths, injuries = parse_casualties(r.get("disaster"))
        district = r.get("location", "")
        industry = r.get("category", "")

        date_sql = f"'{incident_date}'" if incident_date else "NULL"
        sql_rows.append(
            f"({date_sql},'{q(disaster_type)}',{deaths},{injuries},"
            f"'{q(district)}','{q(industry)}')"
        )

    print(f"  NTPC rows to insert: {len(sql_rows)}")

    sql = "TRUNCATE TABLE labor_disasters_ntpc RESTART IDENTITY;\n"
    if sql_rows:
        sql += (
            "INSERT INTO labor_disasters_ntpc "
            "(incident_date,disaster_type,deaths,injuries,district,industry) VALUES\n"
        )
        sql += ",\n".join(sql_rows) + ";\n"
    return sql, len(sql_rows)


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== Loading Labor Disaster Data ===\n")

    tpe_sql, tpe_count = build_tpe()
    print()
    ntpc_sql, ntpc_count = build_ntpc()

    with open(SQL_OUT, "w", encoding="utf-8") as f:
        f.write("-- Major Workplace Disaster Data (重大職災)\n")
        f.write("-- TPE: GPS-point records from data.taipei\n")
        f.write("-- NTPC: District-level records from data.ntpc.gov.tw\n")
        f.write("-- Run: docker exec -i postgres-data psql -U postgres -d dashboard < /tmp/labor_disasters.sql\n\n")
        f.write(tpe_sql + "\n")
        f.write(ntpc_sql + "\n")
        f.write("SELECT 'Labor disaster data injected successfully' AS result;\n")

    print(f"\nSQL written to {SQL_OUT}")
    print(f"  TPE rows: {tpe_count}")
    print(f"  NTPC rows: {ntpc_count}")
    print("\nLoad with:")
    print("  docker exec -i postgres-data psql -U postgres -d dashboard < /tmp/labor_disasters.sql")
