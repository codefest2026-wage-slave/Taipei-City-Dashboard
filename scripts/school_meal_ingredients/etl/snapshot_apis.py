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
