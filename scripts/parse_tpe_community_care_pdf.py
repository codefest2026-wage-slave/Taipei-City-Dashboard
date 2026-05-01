"""
DIS-D2-1: Parse the 臺北市社區照顧關懷據點 PDF (14 pages, 500+ rows)
into CSV with columns: 序號, 行政區, 里別, 據點名稱, 據點類型, 據點地址, 聯絡電話

Source: docs/assets/DIS-D2-1/115年臺北市社區照顧關懷據點㇐覽表115.04.pdf
Output: docs/assets/DIS-D2-1/tpe_community_care.csv

Run:
  python3 scripts/parse_tpe_community_care_pdf.py
"""
import csv
import os
import sys

import pdfplumber

PDF = "docs/assets/DIS-D2-1/115年臺北市社區照顧關懷據點㇐覽表115.04.pdf"
OUT = "docs/assets/DIS-D2-1/tpe_community_care.csv"

EXPECTED_COLS = ["序號", "行政區", "里別", "據點名稱", "據點類型", "據點地址", "聯絡電話"]


def clean_cell(s):
    if s is None:
        return ""
    return str(s).replace("\n", " ").strip()


def main():
    rows = []
    with pdfplumber.open(PDF) as pdf:
        for i, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            for tbl in tables:
                for r in tbl:
                    cells = [clean_cell(c) for c in r]
                    if not cells or len(cells) < 7:
                        continue
                    # Skip header rows
                    if cells[0].strip() in ("序號", "") and "行政區" in cells[1:]:
                        continue
                    if cells[0] == "序號":
                        continue
                    # Filter for rows that start with a numeric 序號
                    if not cells[0].isdigit():
                        continue
                    rows.append(cells[:7])
            print(f"  page {i+1}: cumulative rows={len(rows)}", file=sys.stderr)

    print(f"\nTotal rows extracted: {len(rows)}", file=sys.stderr)
    with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(EXPECTED_COLS)
        w.writerows(rows)
    print(f"Wrote {OUT}", file=sys.stderr)
    print("\n=== first 3 rows ===", file=sys.stderr)
    for r in rows[:3]:
        print("  " + " | ".join(c[:25] for c in r), file=sys.stderr)


if __name__ == "__main__":
    main()
