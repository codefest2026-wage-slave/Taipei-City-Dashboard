"""
Load GCIS company registration CSVs (22 files, A-Z industries × TPE/NTPC) plus
the industrial classification XML into the dashboard DB.

Source files in docs/assets/L-01-1/:
  - 台北市公司登記資料-{A..Z}{業別}.csv   × 11
  - 新北市公司登記資料-{A..Z}{業別}.csv   × 11
  - industrial.xml  (主計總處 第12次修正 行業分類)

Output tables (in dashboard DB):
  - gcis_companies_tpe (tax_id, company_name, address, industry_code,
                        industry_name, capital, established_date)
  - gcis_companies_ntpc (same)
  - industry_codes (code, name, level)

Run:
  python3 scripts/load_gcis_companies.py
  docker exec -i postgres-data psql -U postgres -d dashboard < /tmp/gcis_companies.sql
"""

import csv
import glob
import os
import re
import sys
import xml.etree.ElementTree as ET

ASSETS_DIR = "docs/assets/L-01-1"
SQL_OUT = "/tmp/gcis_companies.sql"
INDUSTRIAL_XML = os.path.join(ASSETS_DIR, "industrial.xml")


def esc(s):
    if s is None:
        return "NULL"
    s = str(s).strip()
    if s == "" or s == "-":
        return "NULL"
    return "'" + s.replace("'", "''") + "'"


def roc_to_iso(roc):
    """Convert民國 date '1131022' or '1130101' → '2024-10-22'."""
    if not roc:
        return None
    roc = str(roc).strip()
    if not roc.isdigit() or len(roc) < 6:
        return None
    # Pad to 7 digits if needed (e.g. 991231 → 0991231)
    if len(roc) == 6:
        roc = "0" + roc
    if len(roc) != 7:
        return None
    try:
        year = int(roc[:3]) + 1911
        month = int(roc[3:5])
        day = int(roc[5:7])
        if not (1 <= month <= 12 and 1 <= day <= 31):
            return None
        return f"{year:04d}-{month:02d}-{day:02d}"
    except ValueError:
        return None


def first_industry_code(raw):
    """'011999,639099,723000,' → '0119' (4-digit primary class)."""
    if not raw:
        return None
    raw = raw.strip()
    if not raw:
        return None
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        return None
    code = parts[0]
    # Codes are typically 6-digit; primary class is first 4 digits
    digits = re.sub(r"\D", "", code)
    if len(digits) >= 4:
        return digits[:4]
    return digits or None


def parse_industrial_xml():
    """Return list of (code, name) from industrial.xml."""
    rows = []
    tree = ET.parse(INDUSTRIAL_XML)
    root = tree.getroot()
    for row in root.findall("Row"):
        code = row.findtext("行業類別", "").strip()
        name = row.findtext("行業名稱", "").strip()
        if code and name:
            rows.append((code, name))
    return rows


def parse_company_csv(path):
    """Yield dicts of company records from a single GCIS CSV."""
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            tax_id = (r.get("統一編號") or "").strip()
            name = (r.get("公司名稱") or "").strip()
            if not tax_id or not name:
                continue
            yield {
                "tax_id": tax_id,
                "company_name": name,
                "address": (r.get("公司地址") or "").strip(),
                "industry_code": first_industry_code(
                    r.get("行業代號（財政資訊中心匯入）", "")
                ),
                "capital": (r.get("資本總額") or "").strip(),
                "established_date": roc_to_iso(r.get("核准設立日期", "")),
            }


def write_sql(out_handle, table, rows):
    """Generate INSERT SQL for one city table."""
    out_handle.write(f"\n-- ── {table}: {len(rows)} rows ──\n")
    out_handle.write(f"DROP TABLE IF EXISTS {table};\n")
    out_handle.write(
        f"""CREATE TABLE {table} (
    tax_id           VARCHAR(20) PRIMARY KEY,
    company_name     VARCHAR(300) NOT NULL,
    address          VARCHAR(400),
    industry_code    VARCHAR(10),
    capital          BIGINT,
    established_date DATE
);
"""
    )
    if not rows:
        return
    BATCH = 500
    for i in range(0, len(rows), BATCH):
        chunk = rows[i : i + BATCH]
        values = []
        for r in chunk:
            cap = r["capital"]
            cap_sql = "NULL"
            if cap and cap.strip().isdigit():
                cap_sql = cap.strip()
            values.append(
                "({tid},{cname},{addr},{icode},{cap},{est})".format(
                    tid=esc(r["tax_id"]),
                    cname=esc(r["company_name"]),
                    addr=esc(r["address"]),
                    icode=esc(r["industry_code"]),
                    cap=cap_sql,
                    est=esc(r["established_date"]),
                )
            )
        out_handle.write(
            f"INSERT INTO {table} (tax_id, company_name, address, industry_code, capital, established_date) VALUES\n"
            + ",\n".join(values)
            + "\nON CONFLICT (tax_id) DO NOTHING;\n"
        )
    out_handle.write(f"CREATE INDEX idx_{table}_name ON {table}(company_name);\n")
    out_handle.write(f"CREATE INDEX idx_{table}_industry ON {table}(industry_code);\n")


def write_industry_codes(out_handle, rows):
    out_handle.write(f"\n-- ── industry_codes: {len(rows)} rows ──\n")
    out_handle.write("DROP TABLE IF EXISTS industry_codes;\n")
    out_handle.write(
        """CREATE TABLE industry_codes (
    code  VARCHAR(10) PRIMARY KEY,
    name  VARCHAR(200) NOT NULL,
    level INTEGER  -- 1=大類(A-Z), 2=中類(2位), 3=小類(3位), 4=細類(4位)
);
"""
    )
    BATCH = 500
    for i in range(0, len(rows), BATCH):
        chunk = rows[i : i + BATCH]
        values = []
        for code, name in chunk:
            digits = re.sub(r"\D", "", code)
            if not digits and len(code) == 1 and code.isalpha():
                level = 1
            else:
                level = len(digits)
            values.append(f"({esc(code)},{esc(name)},{level})")
        out_handle.write(
            "INSERT INTO industry_codes (code, name, level) VALUES\n"
            + ",\n".join(values)
            + "\nON CONFLICT (code) DO NOTHING;\n"
        )


def main():
    if not os.path.isdir(ASSETS_DIR):
        sys.exit(f"Missing dir: {ASSETS_DIR}")
    if not os.path.isfile(INDUSTRIAL_XML):
        sys.exit(f"Missing file: {INDUSTRIAL_XML}")

    print("Parsing industrial.xml …", file=sys.stderr)
    industry_rows = parse_industrial_xml()
    print(f"  → {len(industry_rows)} industry codes", file=sys.stderr)

    tpe_rows = []
    ntpc_rows = []
    seen_tpe = set()
    seen_ntpc = set()
    for path in sorted(glob.glob(os.path.join(ASSETS_DIR, "*公司登記資料-*.csv"))):
        fn = os.path.basename(path)
        is_tpe = fn.startswith("台北市")
        is_ntpc = fn.startswith("新北市")
        if not (is_tpe or is_ntpc):
            continue
        n = 0
        for r in parse_company_csv(path):
            tid = r["tax_id"]
            if is_tpe:
                if tid in seen_tpe:
                    continue
                seen_tpe.add(tid)
                tpe_rows.append(r)
            else:
                if tid in seen_ntpc:
                    continue
                seen_ntpc.add(tid)
                ntpc_rows.append(r)
            n += 1
        print(f"  {fn}: {n}", file=sys.stderr)

    print(
        f"\nTotal: TPE={len(tpe_rows)}, NTPC={len(ntpc_rows)}, codes={len(industry_rows)}",
        file=sys.stderr,
    )

    with open(SQL_OUT, "w", encoding="utf-8") as f:
        f.write("BEGIN;\n")
        write_industry_codes(f, industry_rows)
        write_sql(f, "gcis_companies_tpe", tpe_rows)
        write_sql(f, "gcis_companies_ntpc", ntpc_rows)
        f.write("COMMIT;\n")
    print(f"Wrote SQL → {SQL_OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
