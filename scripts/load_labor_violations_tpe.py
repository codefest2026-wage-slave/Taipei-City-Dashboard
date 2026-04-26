"""
Load TPE labor violation datasets into labor_violations_tpe table.

Data sources:
  1. 勞基法 CSV: docs/assets/違法名單總表-CSV檔1150105勞基.csv  (~15007 records)
  2. 性平法 CSV: docs/assets/臺北市政府勞動局違反性別平等工作法事業單位及事業主公布總表【公告月份：11504】.csv
  3. 職安法 API: data.taipei RID 90d05db5-d46f-4900-a450-b284b0f20fb9

Run from repo root:
  python3 scripts/load_labor_violations_tpe.py

Then load:
  docker exec -i postgres-data psql -U postgres -d dashboard < /tmp/labor_violations_tpe.sql
"""
import csv
import re
import sys

import requests

SQL_OUT = "/tmp/labor_violations_tpe.sql"

LABR_CSV = "docs/assets/違法名單總表-CSV檔1150105勞基.csv"
GENDER_CSV = (
    "docs/assets/"
    "臺北市政府勞動局違反性別平等工作法事業單位及事業主公布總表【公告月份：11504】.csv"
)
SAFETY_RID = "90d05db5-d46f-4900-a450-b284b0f20fb9"
PAGE_SIZE = 1000


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def q(s):
    """Escape single quotes for SQL string."""
    return str(s or "").replace("'", "''")


def parse_fine(v):
    """Strip non-digits; return SQL integer literal or NULL."""
    digits = re.sub(r"[^\d]", "", str(v or ""))
    return digits if digits else "NULL"


def roc_yyymmdd(s):
    """Convert ROC YYYMMDD (or similar) string to ISO date string or None."""
    s = re.sub(r"[^\d]", "", str(s or ""))
    if len(s) < 7:
        return None
    return f"{int(s[:3]) + 1911}-{s[3:5]}-{s[5:7]}"


def date_sql(raw):
    """Return SQL date literal (quoted) or NULL."""
    iso = roc_yyymmdd(raw)
    if iso is None:
        return "NULL"
    return f"'{iso}'"


def str_sql(v):
    """Return a SQL-safe quoted string, or NULL if empty."""
    s = str(v or "").strip()
    if not s:
        return "NULL"
    return f"'{q(s)}'"


def make_row(announcement_date, penalty_date, doc_no, company_name,
             principal, law_category, law_article, violation_content,
             fine_amount):
    """Build one SQL VALUES tuple string."""
    return (
        f"({date_sql(announcement_date)},"
        f"{date_sql(penalty_date)},"
        f"{str_sql(doc_no)},"
        f"'{q(str(company_name).strip())}',"  # NOT NULL
        f"{str_sql(principal)},"
        f"'{q(law_category)}',"               # NOT NULL
        f"{str_sql(law_article)},"
        f"{str_sql(violation_content)},"
        f"{fine_amount})"
    )


# ---------------------------------------------------------------------------
# Source 1: 勞基法 CSV
# ---------------------------------------------------------------------------

def load_labor_csv():
    """Read 勞基法 CSV and return list of SQL row strings."""
    rows = []
    with open(LABR_CSV, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for rec in reader:
            company = rec.get("事業單位或事業主之名稱", "").strip()
            if not company:
                continue
            rows.append(make_row(
                announcement_date=rec.get("公告日期"),
                penalty_date=rec.get("處分日期"),
                doc_no=rec.get("處分字號"),
                company_name=company,
                principal=rec.get("負責人姓名"),
                law_category="勞基法",
                law_article=rec.get("違反勞動基準法條款"),
                violation_content=rec.get("違反法規內容"),
                fine_amount=parse_fine(rec.get("罰鍰金額")),
            ))
    print(f"  [勞基法] {len(rows)} records loaded from CSV")
    return rows


# ---------------------------------------------------------------------------
# Source 2: 性平法 CSV
# ---------------------------------------------------------------------------

def find_clause_col(headers):
    """Return the index of the column whose name contains '條款'."""
    for i, h in enumerate(headers):
        if "條款" in h:
            return i
    return None


def load_gender_csv():
    """Read 性平法 CSV and return list of SQL row strings."""
    rows = []
    with open(GENDER_CSV, encoding="big5", errors="replace", newline="") as f:
        reader = csv.reader(f)
        headers = next(reader)
        clause_idx = find_clause_col(headers)

        for rec in reader:
            # Pad short rows
            while len(rec) < len(headers):
                rec.append("")

            company = rec[headers.index("事業單位名稱/自然人姓名")].strip()
            # Skip empty / placeholder rows
            if not company or company in ("無",) or not company.strip():
                continue

            law_article = rec[clause_idx].strip() if clause_idx is not None else ""
            fine_amount = parse_fine(rec[headers.index("罰鍰金額")])

            rows.append(make_row(
                announcement_date=rec[headers.index("公告日期")],
                penalty_date=rec[headers.index("處分日期")],
                doc_no=rec[headers.index("處分字號")],
                company_name=company,
                principal=rec[headers.index("事業單位代表人")],
                law_category="性平法",
                law_article=law_article,
                violation_content=rec[headers.index("違反法規內容")],
                fine_amount=fine_amount,
            ))
    print(f"  [性平法] {len(rows)} records loaded from CSV")
    return rows


# ---------------------------------------------------------------------------
# Source 3: 職安法 API (data.taipei)
# ---------------------------------------------------------------------------

def fetch_safety_api():
    """Paginate data.taipei API for 職安法 violations and return SQL rows."""
    url = f"https://data.taipei/api/v1/dataset/{SAFETY_RID}"
    rows = []
    offset = 0
    while True:
        resp = requests.get(
            url,
            params={"scope": "resourceAquire", "limit": PAGE_SIZE, "offset": offset},
            timeout=60,
        )
        resp.raise_for_status()
        batch = resp.json().get("result", {}).get("results", [])
        if not batch:
            break
        for rec in batch:
            company = rec.get("事業單位或事業組織名稱", "").strip()
            if not company:
                continue
            rows.append(make_row(
                announcement_date=rec.get("公告日期"),
                penalty_date=rec.get("處分日期"),
                doc_no=rec.get("處分字號"),
                company_name=company,
                principal=rec.get("負責人姓名"),
                law_category="職安法",
                law_article=rec.get("違反職業安全衛生法條款"),
                violation_content=rec.get("違反法規內容"),
                fine_amount="NULL",  # no fine field in this dataset
            ))
        print(f"  [職安法] offset {offset}: {len(batch)} records (total {len(rows)})")
        if len(batch) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    print(f"  [職安法] Done — {len(rows)} total records")
    return rows


# ---------------------------------------------------------------------------
# Write SQL
# ---------------------------------------------------------------------------

def write_sql(all_rows):
    chunk_size = 500
    with open(SQL_OUT, "w", encoding="utf-8") as f:
        f.write("-- TPE Labor Violations Data Injection\n")
        f.write(
            "-- Run: docker exec -i postgres-data psql -U postgres -d dashboard "
            "< /tmp/labor_violations_tpe.sql\n\n"
        )
        f.write("TRUNCATE TABLE labor_violations_tpe RESTART IDENTITY;\n\n")

        cols = (
            "announcement_date,penalty_date,doc_no,company_name,"
            "principal,law_category,law_article,violation_content,fine_amount"
        )
        insert_header = f"INSERT INTO labor_violations_tpe ({cols}) VALUES\n"

        chunks = [all_rows[i:i + chunk_size] for i in range(0, len(all_rows), chunk_size)]
        for ci, chunk in enumerate(chunks):
            f.write(insert_header)
            f.write(",\n".join(chunk))
            f.write(";\n\n")

        f.write(
            "SELECT law_category, COUNT(*), MIN(penalty_date), MAX(penalty_date) "
            "FROM labor_violations_tpe GROUP BY 1 ORDER BY 1;\n"
        )
    print(f"\nSQL written to {SQL_OUT} ({len(all_rows)} total rows)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=== Loading TPE Labor Violations ===\n")

    all_rows = []

    print("Loading 勞基法 CSV...")
    labr_rows = load_labor_csv()
    all_rows.extend(labr_rows)

    print("\nLoading 性平法 CSV...")
    gender_rows = load_gender_csv()
    all_rows.extend(gender_rows)

    print("\nFetching 職安法 API...")
    safety_rows = fetch_safety_api()
    all_rows.extend(safety_rows)

    print(f"\nTotal records: {len(all_rows)}")
    print(f"  勞基法:  {len(labr_rows)}")
    print(f"  性平法:  {len(gender_rows)}")
    print(f"  職安法:  {len(safety_rows)}")

    write_sql(all_rows)

    print("\nNext step:")
    print("  docker exec -i postgres-data psql -U postgres -d dashboard < /tmp/labor_violations_tpe.sql")


if __name__ == "__main__":
    main()
