"""
Fetch NTPC labor violation datasets and load into labor_violations_ntpc.

Data sources (data.ntpc.gov.tw):
  1. 勞基法 UUID: a3408b16-7b28-4fa5-9834-d147aae909bf  (~14,155 records)
  2. 性平法 UUID: d7b245c0-0ba7-4ee9-9021-5ca27ac52eb4  (~47 records)
  3. 職安法 UUID: 8ec84245-450b-45df-9bc5-510ab6e02e73  (~4,148 records)

Run from repo root:
  python scripts/load_labor_violations_ntpc.py

Then load:
  docker exec -i postgres-data psql -U postgres -d dashboard < /tmp/labor_violations_ntpc.sql
"""
import re
import sys

import requests

SQL_OUT = "/tmp/labor_violations_ntpc.sql"

DATASETS = [
    {
        "uuid": "a3408b16-7b28-4fa5-9834-d147aae909bf",
        "category": "勞基法",
        "expected": 14155,
    },
    {
        "uuid": "d7b245c0-0ba7-4ee9-9021-5ca27ac52eb4",
        "category": "性平法",
        "expected": 47,
    },
    {
        "uuid": "8ec84245-450b-45df-9bc5-510ab6e02e73",
        "category": "職安法",
        "expected": 4148,
    },
]

PAGE_SIZE = 1000


def q(s):
    """Escape single quotes for SQL string."""
    return str(s or "").replace("'", "''")


def parse_fine(v):
    """Strip non-digits; return SQL integer or NULL."""
    digits = re.sub(r"[^\d]", "", str(v or ""))
    return digits if digits else "NULL"


def parse_date(v):
    """Return SQL date literal or NULL."""
    s = str(v or "").strip()
    if not s:
        return "NULL"
    return f"'{q(s)}'"


def fetch_dataset(uuid, category):
    """Paginate through NTPC API and return all records for one dataset."""
    records = []
    page = 0
    while True:
        resp = requests.get(
            f"https://data.ntpc.gov.tw/api/datasets/{uuid}/json",
            params={"size": PAGE_SIZE, "page": page},
            timeout=60,
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        records.extend(batch)
        print(f"  [{category}] page {page}: {len(batch)} records (total {len(records)})")
        if len(batch) < PAGE_SIZE:
            break
        page += 1
    print(f"  [{category}] Done — {len(records)} total records")
    return records


def build_sql_rows(records, category):
    """Convert raw API records to SQL value tuples."""
    rows = []
    for r in records:
        penalty_date = parse_date(r.get("date"))
        law_article = f"'{q(r.get('law', ''))}'"
        company_name = f"'{q(r.get('name', ''))}'"
        principal = f"'{q(r.get('principal', ''))}'"
        tax_id = f"'{q(r.get('id', ''))}'"
        violation_content = f"'{q(r.get('lawcontent', ''))}'"
        doc_no = f"'{q(r.get('docno', ''))}'"
        fine_amount = parse_fine(r.get("amt_dollartwd"))

        rows.append(
            f"({penalty_date},"
            f"'{q(category)}',"
            f"{law_article},"
            f"{company_name},"
            f"{principal},"
            f"{tax_id},"
            f"{violation_content},"
            f"{doc_no},"
            f"{fine_amount})"
        )
    return rows


def main():
    print("=== Loading NTPC Labor Violations ===\n")

    all_sql_rows = []
    counts = {}

    for ds in DATASETS:
        uuid = ds["uuid"]
        category = ds["category"]
        expected = ds["expected"]

        print(f"Fetching {category} (UUID: {uuid})...")
        records = fetch_dataset(uuid, category)
        counts[category] = len(records)

        if abs(len(records) - expected) > expected * 0.1:
            print(
                f"  WARNING: expected ~{expected} but got {len(records)} "
                f"for {category}",
                file=sys.stderr,
            )

        rows = build_sql_rows(records, category)
        all_sql_rows.extend(rows)
        print()

    # Write SQL file
    print(f"Writing {len(all_sql_rows)} rows to {SQL_OUT}...")
    with open(SQL_OUT, "w", encoding="utf-8") as f:
        f.write("-- NTPC Labor Violations Data Injection\n")
        f.write(
            "-- Run: docker exec -i postgres-data psql -U postgres -d dashboard "
            "< /tmp/labor_violations_ntpc.sql\n\n"
        )
        f.write("TRUNCATE TABLE labor_violations_ntpc RESTART IDENTITY;\n\n")
        f.write(
            "INSERT INTO labor_violations_ntpc "
            "(penalty_date,law_category,law_article,company_name,"
            "principal,tax_id,violation_content,doc_no,fine_amount) VALUES\n"
        )
        # Write in chunks to avoid huge single lines
        chunk_size = 500
        chunks = [all_sql_rows[i:i + chunk_size] for i in range(0, len(all_sql_rows), chunk_size)]
        for ci, chunk in enumerate(chunks):
            if ci == 0:
                f.write(",\n".join(chunk))
            else:
                # End previous statement, start new INSERT for next chunk
                f.write(";\n\n")
                f.write(
                    "INSERT INTO labor_violations_ntpc "
                    "(penalty_date,law_category,law_article,company_name,"
                    "principal,tax_id,violation_content,doc_no,fine_amount) VALUES\n"
                )
                f.write(",\n".join(chunk))
        f.write(";\n\n")
        f.write("SELECT law_category, COUNT(*) FROM labor_violations_ntpc GROUP BY 1 ORDER BY 1;\n")

    print(f"SQL written to {SQL_OUT}")
    print("\nRecord counts:")
    for cat, cnt in counts.items():
        print(f"  {cat}: {cnt}")
    print(f"  TOTAL: {sum(counts.values())}")
    print("\nNext step:")
    print("  docker exec -i postgres-data psql -U postgres -d dashboard < /tmp/labor_violations_ntpc.sql")


if __name__ == "__main__":
    main()
