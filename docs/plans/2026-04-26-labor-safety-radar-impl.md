# Labor Safety Radar — 工作安全燈號 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a "工作安全燈號" dashboard with 6 components — a searchable violation table, a dual-layer disaster map, and 4 statistical charts — covering both Taipei (TPE) and New Taipei City (NTPC).

**Architecture:** Six PostgreSQL tables in the `dashboard` DB store ETL-loaded data. Two custom Vue components (`SearchableViolationTable`, dual-layer map) plus four standard chart types render the data. All components registered in `dashboardmanager` DB under a new dashboard (ID 502).

**Tech Stack:** Python 3 (data loaders), PostgreSQL (docker), Mapbox GL JS (disaster map), Vue 3 + Pinia (frontend)

---

## Verified Dataset Registry

### Violation Datasets (for search table + charts)

| # | Dataset | Source | Rows | RID / UUID | Encoding | Date Field |
|---|---------|--------|------|-----------|---------|------------|
| 1 | TPE 勞基法違規 | CSV `docs/assets/違法名單總表-CSV檔1150105勞基.csv` | 15,007 | — | UTF-8 BOM | `處分日期` YYYMMDD |
| 2 | TPE 性平法違規 | CSV `docs/assets/臺北市政府勞動局違反性別平等工作法...csv` | 231 | — | Big5 | `處分日期` YYYMMDD |
| 3 | TPE 職安法違規 | API RID `90d05db5-d46f-4900-a450-b284b0f20fb9` | ~數千 | RID已驗證 | API JSON | `處分日期` YYYMMDD |
| 4 | NTPC 勞基法違規 | API UUID `a3408b16-7b28-4fa5-9834-d147aae909bf` | 14,155 | — | API JSON | `date` ISO |
| 5 | NTPC 性平法違規 | API UUID `d7b245c0-0ba7-4ee9-9021-5ca27ac52eb4` | 47 | — | API JSON | `date` ISO |
| 6 | NTPC 職安法違規 | API UUID `8ec84245-450b-45df-9bc5-510ab6e02e73` | 4,148 | — | API JSON | `date` ISO |

### Map Datasets (for disaster map)

| # | Dataset | Source | Rows | 地理精度 | Key Fields |
|---|---------|--------|------|---------|------------|
| 7 | TPE 重大職災 | API RID `ab4ddbe2-90f5-49a6-a7ad-45e5b6d14871` | ~數百 | WGS84 GPS ✅ | `經度`,`緯度`,`災害類型`,`死亡人數`,`受傷人數`,`事業單位名稱`,`發生日期` |
| 8 | NTPC 重大職災 | API UUID `80743c0e-b7e7-4d4a-825b-df354a542f65` | 206 | 行政區層級 | `location`(區),`type`,`disaster`(死傷),`category`(業別),`date` |

### Statistical Datasets

| # | Dataset | Source | Rows | Key Fields |
|---|---------|--------|------|-----------|
| 9 | TPE 勞資爭議統計依行業別 | CSV `docs/assets/勞資爭議統計依行業別區分(11503).csv` | 133 | `年度`,`行業別`,`案件數（數量）` (Big5) |
| 10 | TPE 勞保及就業服務月別 | CSV `docs/assets/臺北市勞工保險及就業服務按月別.csv` | 338 | `統計期`,`勞工保險投保人數[人]`,`新登記求職人數`,`推介就業人數` |

---

## Field Name Reference

**TPE violations (actual CSV headers):**
- 勞基法: `公告日期` `處分日期` `處分字號` `事業單位或事業主之名稱` `負責人姓名` `違反勞動基準法條款` `違反法規內容` `罰鍰金額` `備註`
- 性平法: `編號` `公告日期` `處分日期` `處分字號` `事業單位名稱/自然人姓名` `事業單位代表人` `違反性別平等工作法（...）條款` `違反法規內容` `罰鍰金額` `備註`
- 職安法: `公告日期` `處分日期` `處分字號` `事業單位或事業組織名稱` `負責人姓名` `違反職業安全衛生法條款` `違反法規內容` `備註` (**無罰鍰金額**)

**NTPC violations (API fields):** `principal` `date`(ISO) `law` `name` `id` `lawcontent` `docno` `amt_dollartwd`

**TPE disaster (API fields):** `經度` `緯度` `發生日期`(民國文字"113年12月31日") `工程名稱` `事業單位名稱` `地址` `災害類型` `死亡人數` `受傷人數`

**NTPC disaster (API fields):** `no` `date`("108/02/01" ROC/MM/DD) `type` `disaster`("1死0傷") `location`(行政區) `category`(業別)

---

## Date Parsing Reference

```python
import re

def roc_yyymmdd(s: str):
    """'1150105' → '2026-01-05'"""
    s = re.sub(r"[^\d]", "", str(s or ""))
    if len(s) < 7:
        return None
    return f"{int(s[:3]) + 1911}-{s[3:5]}-{s[5:7]}"

def roc_text_date(s: str):
    """'113年12月31日' → '2024-12-31'"""
    m = re.match(r"(\d+)年(\d+)月(\d+)日", str(s or ""))
    if not m:
        return None
    return f"{int(m.group(1)) + 1911}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

def roc_slash_date(s: str):
    """'108/02/01' → '2019-02-01'"""
    m = re.match(r"(\d+)/(\d+)/(\d+)", str(s or ""))
    if not m:
        return None
    return f"{int(m.group(1)) + 1911}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

def roc_year_month(s: str):
    """'87年 1月' → '1998-01-01'"""
    m = re.match(r"(\d+)年\s*(\d+)月", str(s or ""))
    if not m:
        return None
    return f"{int(m.group(1)) + 1911}-{int(m.group(2)):02d}-01"

def parse_ntpc_disaster_casualties(s: str):
    """'1死0傷' → (deaths=1, injuries=0)"""
    m = re.match(r"(\d+)死(\d+)傷", str(s or ""))
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)
```

---

## DB IDs

| Item | Value |
|------|-------|
| Next component IDs | 1005–1010 |
| Dashboard ID | 502 |
| Dashboard index | `labor_safety_radar` |
| Groups | 2 (taipei) + 3 (metrotaipei) |

---

## Task 1: Create DB Tables

**Files:**
- Create: `scripts/labor_safety_create_tables.sql`

```sql
-- Unified violation records
DROP TABLE IF EXISTS labor_violations_tpe;
CREATE TABLE labor_violations_tpe (
    id                SERIAL PRIMARY KEY,
    announcement_date DATE,
    penalty_date      DATE,
    doc_no            VARCHAR(200),
    company_name      VARCHAR(300) NOT NULL,
    principal         VARCHAR(100),
    law_category      VARCHAR(20) NOT NULL,  -- '勞基法' '性平法' '職安法'
    law_article       VARCHAR(500),
    violation_content TEXT,
    fine_amount       INTEGER               -- NULL for 職安法 (no fine field)
);

DROP TABLE IF EXISTS labor_violations_ntpc;
CREATE TABLE labor_violations_ntpc (
    id                SERIAL PRIMARY KEY,
    penalty_date      DATE,
    law_category      VARCHAR(20) NOT NULL,
    law_article       VARCHAR(500),
    company_name      VARCHAR(300) NOT NULL,
    principal         VARCHAR(100),
    tax_id            VARCHAR(50),
    violation_content TEXT,
    doc_no            VARCHAR(200),
    fine_amount       INTEGER
);

-- Disaster point records (TPE: GPS, NTPC: district)
DROP TABLE IF EXISTS labor_disasters_tpe;
CREATE TABLE labor_disasters_tpe (
    id              SERIAL PRIMARY KEY,
    incident_date   DATE,
    company_name    VARCHAR(300),
    address         VARCHAR(300),
    disaster_type   VARCHAR(100),
    deaths          INTEGER DEFAULT 0,
    injuries        INTEGER DEFAULT 0,
    lng             NUMERIC(11,7),
    lat             NUMERIC(11,7)
);

DROP TABLE IF EXISTS labor_disasters_ntpc;
CREATE TABLE labor_disasters_ntpc (
    id              SERIAL PRIMARY KEY,
    incident_date   DATE,
    disaster_type   VARCHAR(100),
    deaths          INTEGER DEFAULT 0,
    injuries        INTEGER DEFAULT 0,
    district        VARCHAR(20),
    industry        VARCHAR(100)
);

-- Statistical tables
DROP TABLE IF EXISTS labor_disputes_industry_tpe;
CREATE TABLE labor_disputes_industry_tpe (
    id          SERIAL PRIMARY KEY,
    year        INTEGER NOT NULL,
    period      VARCHAR(20),
    industry    VARCHAR(100) NOT NULL,
    case_count  INTEGER NOT NULL
);

DROP TABLE IF EXISTS labor_insurance_monthly_tpe;
CREATE TABLE labor_insurance_monthly_tpe (
    id               SERIAL PRIMARY KEY,
    period_label     VARCHAR(20) NOT NULL,
    period_date      DATE NOT NULL,
    insured_units    INTEGER,
    insured_persons  INTEGER,
    benefit_cases    INTEGER,
    benefit_amount   BIGINT,
    new_seekers      INTEGER,
    new_openings     INTEGER,
    placed_seekers   INTEGER,
    placed_openings  INTEGER,
    placement_rate   NUMERIC(5,2),
    utilization_rate NUMERIC(5,2),
    accident_cases   INTEGER,
    accident_deaths  INTEGER
);
```

**Run:**
```bash
docker exec -i postgres-data psql -U postgres -d dashboard < scripts/labor_safety_create_tables.sql
```

**Verify:**
```bash
docker exec postgres-data psql -U postgres -d dashboard -c "\dt labor_*"
```
Expected: 6 tables.

**Commit:**
```bash
git add scripts/labor_safety_create_tables.sql
git commit -m "feat: create labor safety DB tables (violations + disasters + stats)"
```

---

## Task 2: Load TPE Violation Data (3 laws)

**Files:**
- Create: `scripts/load_labor_violations_tpe.py`

```python
#!/usr/bin/env python3
"""Load TPE violations (勞基法 + 性平法 from CSV; 職安法 from API) → labor_violations_tpe."""

import csv, re, requests

TPE_LABOR_CSV  = "docs/assets/違法名單總表-CSV檔1150105勞基.csv"
TPE_GENDER_CSV = "docs/assets/臺北市政府勞動局違反性別平等工作法事業單位及事業主公布總表【公告月份：11504】.csv"
TPE_SAFETY_RID = "90d05db5-d46f-4900-a450-b284b0f20fb9"
OUTPUT_SQL     = "/tmp/labor_violations_tpe.sql"


def roc_yyymmdd(s):
    s = re.sub(r"[^\d]", "", str(s or ""))
    if len(s) < 7: return None
    return f"{int(s[:3])+1911}-{s[3:5]}-{s[5:7]}"

def esc(v):
    if v is None: return "NULL"
    return "'" + str(v).replace("'", "''").strip() + "'"

def parse_fine(v):
    c = re.sub(r"[^\d]", "", str(v or ""))
    return c if c else "NULL"


rows = []

# 勞基法 (UTF-8 BOM)
with open(TPE_LABOR_CSV, encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        name = r.get("事業單位或事業主之名稱", "").strip()
        if not name: continue
        rows.append((roc_yyymmdd(r.get("公告日期")), roc_yyymmdd(r.get("處分日期")),
                     r.get("處分字號","").strip(), name, r.get("負責人姓名","").strip(),
                     "勞基法", r.get("違反勞動基準法條款","").strip(),
                     r.get("違反法規內容","").strip(), parse_fine(r.get("罰鍰金額",""))))

# 性平法 (Big5)
with open(TPE_GENDER_CSV, encoding="big5", errors="replace") as f:
    for r in csv.DictReader(f):
        name = r.get("事業單位名稱/自然人姓名", "").strip()
        if not name or name == "無": continue
        law_col = next((v for k, v in r.items() if "條款" in k), "")
        rows.append((roc_yyymmdd(r.get("公告日期")), roc_yyymmdd(r.get("處分日期")),
                     r.get("處分字號","").strip(), name, r.get("事業單位代表人","").strip(),
                     "性平法", law_col.strip(),
                     r.get("違反法規內容","").strip(), parse_fine(r.get("罰鍰金額",""))))

# 職安法 (API pagination)
offset = 0
while True:
    resp = requests.get(f"https://data.taipei/api/v1/dataset/{TPE_SAFETY_RID}",
                        params={"scope":"resourceAquire","limit":1000,"offset":offset},
                        timeout=30).json()
    batch = resp.get("result", {}).get("results", [])
    if not batch: break
    for r in batch:
        name = r.get("事業單位或事業組織名稱", "").strip()
        if not name: continue
        rows.append((roc_yyymmdd(r.get("公告日期")), roc_yyymmdd(r.get("處分日期")),
                     r.get("處分字號","").strip(), name, r.get("負責人姓名","").strip(),
                     "職安法", r.get("違反職業安全衛生法條款","").strip(),
                     r.get("違反法規內容","").strip(), "NULL"))
    if len(batch) < 1000: break
    offset += 1000

lines = ["TRUNCATE TABLE labor_violations_tpe RESTART IDENTITY;",
         "INSERT INTO labor_violations_tpe "
         "(announcement_date,penalty_date,doc_no,company_name,principal,"
         "law_category,law_article,violation_content,fine_amount) VALUES"]
vals = []
for ad, pd, doc, name, prin, law, article, content, fine in rows:
    vals.append(f"  ({f'{chr(39)}{ad}{chr(39)}' if ad else 'NULL'},"
                f"{f'{chr(39)}{pd}{chr(39)}' if pd else 'NULL'},"
                f"{esc(doc)},{esc(name)},{esc(prin)},"
                f"{esc(law)},{esc(article)},{esc(content)},{fine})")
lines.append(",\n".join(vals) + ";")

with open(OUTPUT_SQL, "w") as f:
    f.write("\n".join(lines))
print(f"TPE violations: {len(rows)} rows → {OUTPUT_SQL}")
```

**Run:**
```bash
python3 scripts/load_labor_violations_tpe.py
docker exec -i postgres-data psql -U postgres -d dashboard < /tmp/labor_violations_tpe.sql
```

**Verify:**
```bash
docker exec postgres-data psql -U postgres -d dashboard -c \
  "SELECT law_category, COUNT(*), MIN(penalty_date), MAX(penalty_date) FROM labor_violations_tpe GROUP BY 1;"
```
Expected: 勞基法 ~15,007 / 性平法 ~231 / 職安法 ~數千 rows.

**Commit:**
```bash
git add scripts/load_labor_violations_tpe.py
git commit -m "feat: load TPE labor violations (勞基法+性平法+職安法)"
```

---

## Task 3: Load NTPC Violation Data (3 laws)

**Files:**
- Create: `scripts/load_labor_violations_ntpc.py`

```python
#!/usr/bin/env python3
"""Fetch NTPC violations (3 laws) from API → labor_violations_ntpc."""

import re, requests

NTPC_DATASETS = {
    "勞基法": "a3408b16-7b28-4fa5-9834-d147aae909bf",
    "性平法": "d7b245c0-0ba7-4ee9-9021-5ca27ac52eb4",
    "職安法": "8ec84245-450b-45df-9bc5-510ab6e02e73",
}
OUTPUT_SQL = "/tmp/labor_violations_ntpc.sql"


def fetch_all(uuid, label):
    records, page = [], 0
    while True:
        batch = requests.get(f"https://data.ntpc.gov.tw/api/datasets/{uuid}/json",
                             params={"size":1000,"page":page}, timeout=60).json()
        records.extend(batch)
        print(f"  {label} page {page}: {len(batch)}")
        if len(batch) < 1000: break
        page += 1
    return records

def esc(v):
    if v is None: return "NULL"
    return "'" + str(v).replace("'","''").strip() + "'"

def parse_fine(v):
    c = re.sub(r"[^\d]", "", str(v or ""))
    return c if c else "NULL"


rows = []
for law_cat, uuid in NTPC_DATASETS.items():
    print(f"Fetching NTPC {law_cat}...")
    for r in fetch_all(uuid, law_cat):
        name = (r.get("name") or "").strip()
        if not name: continue
        rows.append(((r.get("date") or "").strip(), law_cat,
                     (r.get("law") or "").strip(), name,
                     (r.get("principal") or "").strip(),
                     (r.get("id") or "").strip(),
                     (r.get("lawcontent") or "").strip(),
                     (r.get("docno") or "").strip(),
                     parse_fine(r.get("amt_dollartwd"))))

lines = ["TRUNCATE TABLE labor_violations_ntpc RESTART IDENTITY;",
         "INSERT INTO labor_violations_ntpc "
         "(penalty_date,law_category,law_article,company_name,principal,"
         "tax_id,violation_content,doc_no,fine_amount) VALUES"]
vals = []
for pd, law, article, name, prin, tid, content, doc, fine in rows:
    vals.append(f"  ({f'{chr(39)}{pd}{chr(39)}' if pd else 'NULL'},"
                f"{esc(law)},{esc(article)},{esc(name)},{esc(prin)},"
                f"{esc(tid)},{esc(content)},{esc(doc)},{fine})")
lines.append(",\n".join(vals) + ";")

with open(OUTPUT_SQL, "w") as f:
    f.write("\n".join(lines))
print(f"NTPC violations: {len(rows)} rows → {OUTPUT_SQL}")
```

**Run:**
```bash
python3 scripts/load_labor_violations_ntpc.py
docker exec -i postgres-data psql -U postgres -d dashboard < /tmp/labor_violations_ntpc.sql
```

**Verify:**
```bash
docker exec postgres-data psql -U postgres -d dashboard -c \
  "SELECT law_category, COUNT(*) FROM labor_violations_ntpc GROUP BY 1;"
```
Expected: 勞基法 14,155 / 性平法 47 / 職安法 4,148.

**Commit:**
```bash
git add scripts/load_labor_violations_ntpc.py
git commit -m "feat: load NTPC labor violations (勞基法+性平法+職安法)"
```

---

## Task 4: Load Disaster Data (TPE + NTPC)

**Files:**
- Create: `scripts/load_labor_disasters.py`

```python
#!/usr/bin/env python3
"""Fetch TPE (GPS) + NTPC (district) disaster records."""

import re, requests

TPE_DISASTER_RID  = "ab4ddbe2-90f5-49a6-a7ad-45e5b6d14871"
NTPC_DISASTER_UUID = "80743c0e-b7e7-4d4a-825b-df354a542f65"
OUTPUT_SQL = "/tmp/labor_disasters.sql"


def roc_text_date(s):
    """'113年12月31日' → '2024-12-31'"""
    m = re.match(r"(\d+)年(\d+)月(\d+)日", str(s or ""))
    if not m: return None
    return f"{int(m.group(1))+1911}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

def roc_slash_date(s):
    """'108/02/01' → '2019-02-01'"""
    m = re.match(r"(\d+)/(\d+)/(\d+)", str(s or ""))
    if not m: return None
    return f"{int(m.group(1))+1911}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

def parse_casualties(s):
    """'1死0傷' → (1, 0)"""
    m = re.match(r"(\d+)死(\d+)傷", str(s or ""))
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)

def esc(v):
    if v is None: return "NULL"
    return "'" + str(v).replace("'","''").strip() + "'"


# TPE disasters (GPS)
tpe_rows, offset = [], 0
while True:
    batch = requests.get(f"https://data.taipei/api/v1/dataset/{TPE_DISASTER_RID}",
                         params={"scope":"resourceAquire","limit":1000,"offset":offset},
                         timeout=30).json().get("result",{}).get("results",[])
    if not batch: break
    for r in batch:
        try:
            lng = float(r.get("經度", 0) or 0)
            lat = float(r.get("緯度", 0) or 0)
        except ValueError:
            lng, lat = None, None
        if not lng or not lat: continue
        tpe_rows.append((roc_text_date(r.get("發生日期")),
                         r.get("事業單位名稱","").strip(),
                         r.get("地址","").strip(),
                         r.get("災害類型","").strip(),
                         int(r.get("死亡人數",0) or 0),
                         int(r.get("受傷人數",0) or 0),
                         lng, lat))
    if len(batch) < 1000: break
    offset += 1000

# NTPC disasters (district)
ntpc_raw = []
page = 0
while True:
    batch = requests.get(f"https://data.ntpc.gov.tw/api/datasets/{NTPC_DISASTER_UUID}/json",
                         params={"size":1000,"page":page}, timeout=30).json()
    ntpc_raw.extend(batch)
    if len(batch) < 1000: break
    page += 1

ntpc_rows = []
for r in ntpc_raw:
    deaths, injuries = parse_casualties(r.get("disaster",""))
    ntpc_rows.append((roc_slash_date(r.get("date")),
                      r.get("type","").strip(),
                      deaths, injuries,
                      r.get("location","").strip(),
                      r.get("category","").strip()))

lines = []

lines.append("TRUNCATE TABLE labor_disasters_tpe RESTART IDENTITY;")
lines.append("INSERT INTO labor_disasters_tpe "
             "(incident_date,company_name,address,disaster_type,deaths,injuries,lng,lat) VALUES")
vals = [f"  ({f'{chr(39)}{d[0]}{chr(39)}' if d[0] else 'NULL'},"
        f"{esc(d[1])},{esc(d[2])},{esc(d[3])},{d[4]},{d[5]},{d[6]},{d[7]})"
        for d in tpe_rows]
lines.append(",\n".join(vals) + ";")

lines.append("TRUNCATE TABLE labor_disasters_ntpc RESTART IDENTITY;")
lines.append("INSERT INTO labor_disasters_ntpc "
             "(incident_date,disaster_type,deaths,injuries,district,industry) VALUES")
vals = [f"  ({f'{chr(39)}{d[0]}{chr(39)}' if d[0] else 'NULL'},"
        f"{esc(d[1])},{d[2]},{d[3]},{esc(d[4])},{esc(d[5])})"
        for d in ntpc_rows]
lines.append(",\n".join(vals) + ";")

with open(OUTPUT_SQL, "w") as f:
    f.write("\n".join(lines))
print(f"TPE disasters: {len(tpe_rows)}, NTPC disasters: {len(ntpc_rows)} → {OUTPUT_SQL}")
```

**Run:**
```bash
python3 scripts/load_labor_disasters.py
docker exec -i postgres-data psql -U postgres -d dashboard < /tmp/labor_disasters.sql
```

**Verify:**
```bash
docker exec postgres-data psql -U postgres -d dashboard -c \
  "SELECT MIN(incident_date), MAX(incident_date), COUNT(*) FROM labor_disasters_tpe;"
docker exec postgres-data psql -U postgres -d dashboard -c \
  "SELECT district, COUNT(*) FROM labor_disasters_ntpc GROUP BY district ORDER BY 2 DESC LIMIT 5;"
```

**Commit:**
```bash
git add scripts/load_labor_disasters.py
git commit -m "feat: load TPE+NTPC major workplace disaster records"
```

---

## Task 5: Load TPE Statistical Data

**Files:**
- Create: `scripts/load_labor_stats_tpe.py`

```python
#!/usr/bin/env python3
"""Load TPE labor dispute (by industry) and labor insurance monthly stats."""
import csv, re

DISPUTES_CSV  = "docs/assets/勞資爭議統計依行業別區分(11503).csv"
INSURANCE_CSV = "docs/assets/臺北市勞工保險及就業服務按月別.csv"
OUTPUT_SQL    = "/tmp/labor_stats_tpe.sql"


def esc(v):
    if v is None: return "NULL"
    return "'" + str(v).replace("'","''").strip() + "'"

def to_int(v):
    try: return str(int(str(v).replace(",","").strip()))
    except: return "NULL"

def to_num(v):
    try: return str(float(str(v).replace(",","").strip()))
    except: return "NULL"

def roc_year_month(s):
    m = re.match(r"(\d+)年\s*(\d+)月", str(s))
    if not m: return None
    return f"{int(m.group(1))+1911}-{int(m.group(2)):02d}-01"


# Disputes
dispute_rows = []
with open(DISPUTES_CSV, encoding="big5", errors="replace") as f:
    for r in csv.DictReader(f):
        yr = r.get("年度","").strip()
        ind = r.get("行業別","").strip()
        if not yr or not ind: continue
        try: yr_ad = int(yr) + 1911
        except: continue
        dispute_rows.append((yr_ad, r.get("統計月份","").strip(), ind,
                              to_int(r.get("案件數（數量）",""))))

# Insurance
ins_rows = []
with open(INSURANCE_CSV, encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        label = r.get("統計期","").strip()
        pd = roc_year_month(label)
        if not pd: continue
        ins_rows.append((label, pd,
                         to_int(r.get("勞工保險投保單位數[家]","")),
                         to_int(r.get("勞工保險投保人數[人]","")),
                         to_int(r.get("勞工保險給付件數[件]","")),
                         to_int(r.get("勞工保險給付金額[千元]","")),
                         to_int(r.get("市府推介就業服務/新登記求職人數[人]","")),
                         to_int(r.get("市府推介就業服務/新登記求才人數[人]","")),
                         to_int(r.get("市府推介就業服務/有效求職推介就業人數[人]","")),
                         to_int(r.get("市府推介就業服務/有效求才僱用人數[人]","")),
                         to_num(r.get("市府推介就業服務/求職就業率[%]","")),
                         to_num(r.get("市府推介就業服務/求才利用率[%]","")),
                         to_int(r.get("重大職業災害發生件數[件]","")),
                         to_int(r.get("重大職業災害死亡人數[人]",""))))

lines = []
lines.append("TRUNCATE TABLE labor_disputes_industry_tpe RESTART IDENTITY;")
lines.append("INSERT INTO labor_disputes_industry_tpe (year,period,industry,case_count) VALUES")
lines.append(",\n".join(
    f"  ({y},{esc(p)},{esc(i)},{c})" for y,p,i,c in dispute_rows) + ";")

lines.append("TRUNCATE TABLE labor_insurance_monthly_tpe RESTART IDENTITY;")
lines.append("INSERT INTO labor_insurance_monthly_tpe "
             "(period_label,period_date,insured_units,insured_persons,benefit_cases,"
             "benefit_amount,new_seekers,new_openings,placed_seekers,placed_openings,"
             "placement_rate,utilization_rate,accident_cases,accident_deaths) VALUES")
lines.append(",\n".join(
    f"  ({esc(r[0])},'{r[1]}',{','.join(str(v) for v in r[2:])})" for r in ins_rows) + ";")

with open(OUTPUT_SQL, "w") as f:
    f.write("\n".join(lines))
print(f"Disputes: {len(dispute_rows)}, Insurance: {len(ins_rows)} rows → {OUTPUT_SQL}")
```

**Run:**
```bash
python3 scripts/load_labor_stats_tpe.py
docker exec -i postgres-data psql -U postgres -d dashboard < /tmp/labor_stats_tpe.sql
```

**Verify:**
```bash
docker exec postgres-data psql -U postgres -d dashboard -c \
  "SELECT year, COUNT(*) FROM labor_disputes_industry_tpe GROUP BY year ORDER BY year;"
docker exec postgres-data psql -U postgres -d dashboard -c \
  "SELECT MIN(period_date), MAX(period_date), COUNT(*) FROM labor_insurance_monthly_tpe;"
```

**Commit:**
```bash
git add scripts/load_labor_stats_tpe.py
git commit -m "feat: load TPE labor disputes by industry and insurance monthly stats"
```

---

## Task 6: Build SearchableViolationTable Vue Component

**Files:**
- Create: `Taipei-City-Dashboard-FE/src/components/charts/SearchableViolationTable.vue`
- Modify: `Taipei-City-Dashboard-FE/src/components/DashboardComponent.vue` (add case for new type)

**Component spec:**

The component receives `chartData` (array of violation rows loaded by `contentStore`) and renders:
1. Search input (filters `company_name` case-insensitively)
2. Three filter dropdowns: 城市 / 法規類別 / 年度
3. Results table with columns: 城市 | 日期 | 公司名稱 | 法規 | 違規內容 | 罰款
4. Row count indicator
5. Fine shown as `$XX,XXX` or `—` if null

**Step 1: Create the component**

```vue
<!-- Taipei-City-Dashboard-FE/src/components/charts/SearchableViolationTable.vue -->
<template>
  <div class="searchable-violation-table">
    <div class="svt-controls">
      <div class="svt-search">
        <span class="material-icons">search</span>
        <input
          v-model="searchQuery"
          type="text"
          placeholder="輸入公司名稱搜尋違規記錄..."
          class="svt-input"
        />
        <button v-if="searchQuery" class="svt-clear" @click="searchQuery = ''">
          <span class="material-icons">close</span>
        </button>
      </div>
      <div class="svt-filters">
        <select v-model="filterCity" class="svt-select">
          <option value="">全部城市</option>
          <option value="臺北">臺北市</option>
          <option value="新北">新北市</option>
        </select>
        <select v-model="filterLaw" class="svt-select">
          <option value="">全部法規</option>
          <option value="勞基法">勞動基準法</option>
          <option value="性平法">性別平等工作法</option>
          <option value="職安法">職業安全衛生法</option>
        </select>
        <select v-model="filterYear" class="svt-select">
          <option value="">全部年度</option>
          <option v-for="y in availableYears" :key="y" :value="y">{{ y }}</option>
        </select>
      </div>
    </div>

    <div class="svt-result-count">
      共 <strong>{{ filteredRows.length.toLocaleString() }}</strong> 筆記錄
      <span v-if="isFiltered" class="svt-clear-all" @click="clearAll">清除篩選</span>
    </div>

    <div class="svt-table-wrapper">
      <table class="svt-table">
        <thead>
          <tr>
            <th>城市</th>
            <th @click="sortBy('penalty_date')" class="svt-sortable">
              日期 <span class="material-icons">{{ sortIcon('penalty_date') }}</span>
            </th>
            <th>公司名稱</th>
            <th>法規</th>
            <th>違規內容</th>
            <th @click="sortBy('fine_amount')" class="svt-sortable">
              罰款 <span class="material-icons">{{ sortIcon('fine_amount') }}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(row, i) in pagedRows"
            :key="i"
            :class="['svt-row', row.law_category]"
          >
            <td>
              <span :class="['svt-city-badge', row.city === '臺北' ? 'tpe' : 'ntpc']">
                {{ row.city }}
              </span>
            </td>
            <td class="svt-date">{{ row.penalty_date || '—' }}</td>
            <td class="svt-company">{{ row.company_name }}</td>
            <td>
              <span :class="['svt-law-badge', row.law_category]">
                {{ row.law_category }}
              </span>
            </td>
            <td class="svt-content">{{ truncate(row.violation_content, 40) }}</td>
            <td class="svt-fine">
              {{ row.fine_amount ? '$' + Number(row.fine_amount).toLocaleString() : '—' }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="svt-pagination" v-if="totalPages > 1">
      <button :disabled="page === 1" @click="page--">‹</button>
      <span>{{ page }} / {{ totalPages }}</span>
      <button :disabled="page === totalPages" @click="page++">›</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from "vue";

const props = defineProps({ chartData: Array });

const searchQuery = ref("");
const filterCity  = ref("");
const filterLaw   = ref("");
const filterYear  = ref("");
const sortKey     = ref("penalty_date");
const sortDir     = ref(-1); // -1 = desc
const page        = ref(1);
const PAGE_SIZE   = 20;

const availableYears = computed(() => {
  const years = new Set(
    (props.chartData || [])
      .map(r => r.penalty_date?.slice(0, 4))
      .filter(Boolean)
  );
  return [...years].sort((a, b) => b - a);
});

const isFiltered = computed(() =>
  searchQuery.value || filterCity.value || filterLaw.value || filterYear.value
);

const filteredRows = computed(() => {
  let rows = props.chartData || [];
  const q = searchQuery.value.toLowerCase();
  if (q) rows = rows.filter(r => r.company_name?.toLowerCase().includes(q));
  if (filterCity.value) rows = rows.filter(r => r.city === filterCity.value);
  if (filterLaw.value)  rows = rows.filter(r => r.law_category === filterLaw.value);
  if (filterYear.value) rows = rows.filter(r => r.penalty_date?.startsWith(filterYear.value));

  return [...rows].sort((a, b) => {
    const av = a[sortKey.value] ?? "";
    const bv = b[sortKey.value] ?? "";
    if (sortKey.value === "fine_amount") {
      return sortDir.value * ((Number(bv) || 0) - (Number(av) || 0));
    }
    return sortDir.value * String(bv).localeCompare(String(av));
  });
});

const totalPages = computed(() => Math.ceil(filteredRows.value.length / PAGE_SIZE));
const pagedRows  = computed(() =>
  filteredRows.value.slice((page.value - 1) * PAGE_SIZE, page.value * PAGE_SIZE)
);

watch([searchQuery, filterCity, filterLaw, filterYear], () => { page.value = 1; });

function sortBy(key) {
  if (sortKey.value === key) sortDir.value *= -1;
  else { sortKey.value = key; sortDir.value = -1; }
  page.value = 1;
}

function sortIcon(key) {
  if (sortKey.value !== key) return "unfold_more";
  return sortDir.value === -1 ? "expand_more" : "expand_less";
}

function truncate(s, n) {
  if (!s) return "—";
  return s.length > n ? s.slice(0, n) + "…" : s;
}

function clearAll() {
  searchQuery.value = "";
  filterCity.value = "";
  filterLaw.value = "";
  filterYear.value = "";
}
</script>

<style scoped>
.searchable-violation-table {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
  font-size: 13px;
}

.svt-controls { display: flex; flex-direction: column; gap: 8px; }

.svt-search {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--color-component-background, #1e1e1e);
  border: 1px solid var(--color-border, #333);
  border-radius: 6px;
  padding: 6px 10px;
}
.svt-input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: var(--color-text, #fff);
  font-size: 13px;
}
.svt-clear { background: none; border: none; cursor: pointer; color: #888; }

.svt-filters { display: flex; gap: 8px; flex-wrap: wrap; }
.svt-select {
  background: var(--color-component-background, #1e1e1e);
  border: 1px solid var(--color-border, #333);
  border-radius: 4px;
  color: var(--color-text, #fff);
  padding: 4px 8px;
  font-size: 12px;
  cursor: pointer;
}

.svt-result-count { color: #aaa; font-size: 12px; }
.svt-clear-all {
  margin-left: 8px;
  color: #4fc3f7;
  cursor: pointer;
  text-decoration: underline;
}

.svt-table-wrapper { flex: 1; overflow-y: auto; }
.svt-table { width: 100%; border-collapse: collapse; }
.svt-table th {
  position: sticky;
  top: 0;
  background: var(--color-component-background, #1e1e1e);
  color: #aaa;
  font-weight: 500;
  text-align: left;
  padding: 8px 6px;
  border-bottom: 1px solid #333;
  white-space: nowrap;
}
.svt-sortable { cursor: pointer; user-select: none; }
.svt-sortable:hover { color: #fff; }
.svt-table th .material-icons { font-size: 14px; vertical-align: middle; }

.svt-table td {
  padding: 7px 6px;
  border-bottom: 1px solid #222;
  vertical-align: top;
}
.svt-row:hover td { background: rgba(255,255,255,0.03); }

.svt-city-badge {
  display: inline-block;
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
}
.svt-city-badge.tpe { background: #1565C0; color: #fff; }
.svt-city-badge.ntpc { background: #E65100; color: #fff; }

.svt-law-badge {
  display: inline-block;
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 11px;
  white-space: nowrap;
}
.svt-law-badge.勞基法 { background: rgba(229,57,53,0.2); color: #EF9A9A; }
.svt-law-badge.性平法 { background: rgba(142,36,170,0.2); color: #CE93D8; }
.svt-law-badge.職安法 { background: rgba(255,109,0,0.2); color: #FFCC80; }

.svt-date  { white-space: nowrap; color: #aaa; }
.svt-company { font-weight: 500; color: #fff; }
.svt-content { color: #bbb; max-width: 200px; }
.svt-fine { white-space: nowrap; font-weight: 500; color: #EF9A9A; }

.svt-pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
}
.svt-pagination button {
  background: none;
  border: 1px solid #444;
  color: #fff;
  padding: 4px 10px;
  cursor: pointer;
  border-radius: 3px;
}
.svt-pagination button:disabled { opacity: 0.3; cursor: default; }
</style>
```

**Step 2: Register new chart type in DashboardComponent.vue**

In `Taipei-City-Dashboard-FE/src/components/DashboardComponent.vue`, find the section where chart types are mapped and add:

```javascript
// In the chart component imports at the top:
import SearchableViolationTable from "./charts/SearchableViolationTable.vue";

// In the component map / switch-case:
case "SearchableViolationTable":
  return SearchableViolationTable;
```

**Step 3: Verify component renders**

Start the dev server and open a component using `SearchableViolationTable` type. Confirm:
- Search input filters rows in real time
- City / law / year dropdowns work
- Sort by date and fine amount works
- Pagination works for large datasets

**Commit:**
```bash
git add Taipei-City-Dashboard-FE/src/components/charts/SearchableViolationTable.vue
git add Taipei-City-Dashboard-FE/src/components/DashboardComponent.vue
git commit -m "feat: add SearchableViolationTable chart component for violation lookup"
```

---

## Task 7: Build Disaster Dual-Layer Map GeoJSON

**Files:**
- Create: `Taipei-City-Dashboard-FE/public/mapData/labor_disasters_tpe.geojson`
- Create: `Taipei-City-Dashboard-FE/public/mapData/labor_disasters_ntpc.geojson`
- Create: `scripts/generate_labor_disaster_geojson.py`

**Step 1: Write the GeoJSON generator**

```python
#!/usr/bin/env python3
"""Generate GeoJSON for labor disaster map layers from PostgreSQL."""

import json, subprocess

def run_sql(sql):
    result = subprocess.run(
        ["docker", "exec", "postgres-data", "psql", "-U", "postgres",
         "-d", "dashboard", "-t", "-A", "-F", "\t", "-c", sql],
        capture_output=True, text=True
    )
    rows = []
    for line in result.stdout.strip().split("\n"):
        if line.strip():
            rows.append(line.split("\t"))
    return rows

# TPE: point features with GPS
tpe_rows = run_sql("""
    SELECT lng, lat, incident_date, company_name, address,
           disaster_type, deaths, injuries
    FROM labor_disasters_tpe
    WHERE lng IS NOT NULL AND lat IS NOT NULL
    ORDER BY incident_date DESC
""")

tpe_features = []
for row in tpe_rows:
    lng, lat, date, company, addr, dtype, deaths, injuries = row
    tpe_features.append({
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [float(lng), float(lat)]},
        "properties": {
            "city": "taipei",
            "incident_date": date,
            "company_name": company,
            "address": addr,
            "disaster_type": dtype,
            "deaths": int(deaths or 0),
            "injuries": int(injuries or 0),
            "severity": "fatal" if int(deaths or 0) > 0 else "injury"
        }
    })

# NTPC: one feature per district (aggregated)
ntpc_rows = run_sql("""
    SELECT district, COUNT(*) AS incidents,
           SUM(deaths) AS total_deaths,
           SUM(injuries) AS total_injuries
    FROM labor_disasters_ntpc
    WHERE district IS NOT NULL
    GROUP BY district
""")

ntpc_features = []
for row in ntpc_rows:
    district, incidents, deaths, injuries = row
    ntpc_features.append({
        "type": "Feature",
        "geometry": None,  # polygon will be merged from NTPC district GeoJSON
        "properties": {
            "city": "newtaipei",
            "district": district,
            "incidents": int(incidents or 0),
            "total_deaths": int(deaths or 0),
            "total_injuries": int(injuries or 0)
        }
    })

# Write TPE GeoJSON
tpe_geojson = {"type": "FeatureCollection", "features": tpe_features}
with open("Taipei-City-Dashboard-FE/public/mapData/labor_disasters_tpe.geojson", "w") as f:
    json.dump(tpe_geojson, f, ensure_ascii=False)
print(f"TPE disaster GeoJSON: {len(tpe_features)} features")

# Write NTPC stats JSON (to be merged with district polygons)
with open("Taipei-City-Dashboard-FE/public/mapData/labor_disasters_ntpc.geojson", "w") as f:
    json.dump({"type": "FeatureCollection", "features": ntpc_features}, f, ensure_ascii=False)
print(f"NTPC disaster stats: {len(ntpc_features)} districts")
```

**Step 2: Run generator**
```bash
python3 scripts/generate_labor_disaster_geojson.py
```

**Step 3: Merge NTPC stats into district polygons**

The NTPC choropleth needs district polygon geometry. The existing `disaster_shelter_ntpc.geojson` contains NTPC district polygons. Extract and merge:

```bash
python3 - <<'EOF'
import json

# Load existing NTPC polygon reference (from disaster shelter which has NTPC districts)
with open("Taipei-City-Dashboard-FE/public/mapData/disaster_shelter_ntpc.geojson") as f:
    shelter = json.load(f)

# Get unique district polygons by district name
district_polys = {}
for feat in shelter["features"]:
    d = feat["properties"].get("district") or feat["properties"].get("行政區")
    if d and d not in district_polys:
        district_polys[d] = feat["geometry"]

# Load NTPC disaster stats
with open("Taipei-City-Dashboard-FE/public/mapData/labor_disasters_ntpc.geojson") as f:
    disaster = json.load(f)

# Merge geometry into disaster features
merged = []
for feat in disaster["features"]:
    dist = feat["properties"]["district"]
    # Map short district name to full name if needed
    geom = district_polys.get(dist) or district_polys.get(dist + "區")
    if geom:
        feat["geometry"] = geom
        merged.append(feat)
    else:
        print(f"WARNING: no polygon found for district '{dist}'")

disaster["features"] = merged
with open("Taipei-City-Dashboard-FE/public/mapData/labor_disasters_ntpc.geojson", "w") as f:
    json.dump(disaster, f, ensure_ascii=False)
print(f"Merged {len(merged)} NTPC district features")
EOF
```

**Commit:**
```bash
git add scripts/generate_labor_disaster_geojson.py
git add Taipei-City-Dashboard-FE/public/mapData/labor_disasters_tpe.geojson
git add Taipei-City-Dashboard-FE/public/mapData/labor_disasters_ntpc.geojson
git commit -m "feat: generate labor disaster GeoJSON (TPE points + NTPC district choropleth)"
```

---

## Task 8: Register All Components in dashboardmanager DB

**Files:**
- Create: `scripts/register_labor_safety.sql`

```sql
-- scripts/register_labor_safety.sql
-- Order: components → component_charts → component_maps → query_charts → dashboards → dashboard_groups

-- ── 1. components ────────────────────────────────────────────────────────────
INSERT INTO components (id, index, name) VALUES
  (1005, 'labor_violation_search',   '雙北雇主違規快查'),
  (1006, 'labor_disaster_map',       '雙北重大職災熱點地圖'),
  (1007, 'labor_violations_monthly', '雙北月度違規趨勢'),
  (1008, 'labor_disputes_industry',  '臺北行業別勞資爭議'),
  (1009, 'labor_law_category',       '雙北違規法規分布'),
  (1010, 'labor_market_health',      '臺北勞動市場健康指標')
ON CONFLICT (index) DO NOTHING;

-- ── 2. component_charts ──────────────────────────────────────────────────────
INSERT INTO component_charts (index, color, types, unit) VALUES
  ('labor_violation_search',   ARRAY['#E53935','#8E24AA','#FF6D00'], ARRAY['SearchableViolationTable'], '件'),
  ('labor_disaster_map',       ARRAY['#D50000','#FF6D00','#BF360C'], ARRAY['MapLegend'], '件'),
  ('labor_violations_monthly', ARRAY['#1565C0','#E65100','#42A5F5'], ARRAY['BarChart'], '件'),
  ('labor_disputes_industry',  ARRAY['#F57F17','#FF8F00','#FFCA28'], ARRAY['BarChart'], '件'),
  ('labor_law_category',       ARRAY['#E53935','#8E24AA','#FF6D00'], ARRAY['DonutChart'], '件'),
  ('labor_market_health',      ARRAY['#1B5E20','#2E7D32','#66BB6A'], ARRAY['BarChart'], '人')
ON CONFLICT (index) DO NOTHING;

-- ── 3. component_maps ────────────────────────────────────────────────────────
INSERT INTO component_maps (index, title, type, source, size, paint) VALUES
  ('labor_disasters_tpe', '臺北職災點位', 'circle', '勞動部', 'big',
   '{"circle-color":["match",["get","severity"],"fatal","#D50000","#FF6D00"],"circle-radius":7,"circle-opacity":0.85}'::json),
  ('labor_disasters_ntpc', '新北行政區職災密度', 'fill', '勞動局', NULL,
   '{"fill-color":["interpolate",["linear"],["get","incidents"],0,"#FFF3E0",1,"#FFCCBC",5,"#FF8A65",10,"#F4511E",20,"#BF360C"],"fill-opacity":0.75}'::json);

-- ── 4. query_charts ──────────────────────────────────────────────────────────

-- 1005: 違規快查 (SearchableViolationTable)
-- The frontend component loads data directly; query returns all records for client-side filtering
INSERT INTO query_charts (index, query_type, query_chart, city, source, short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit, map_config_ids, map_filter, links, contributors, created_at, updated_at) VALUES
('labor_violation_search', 'two_d',
 'SELECT company_name, penalty_date, law_category, violation_content, fine_amount, ''臺北'' AS city FROM labor_violations_tpe WHERE penalty_date IS NOT NULL ORDER BY penalty_date DESC',
 'taipei', '勞動局',
 '查詢臺北市雇主勞動違規記錄（勞基法、性平法、職安法）。',
 '整合臺北市三大勞動法規的違規事業單位公告資料，支援公司名稱模糊搜尋與多維篩選。',
 '求職者確認雇主違規記錄，或政策研究者分析違規趨勢。',
 'static', '', 1, 'day', '{}', '{}', '{}', '{doit}', NOW(), NOW()),
('labor_violation_search', 'two_d',
 'SELECT company_name, penalty_date, law_category, violation_content, fine_amount, city FROM (SELECT company_name, penalty_date, law_category, violation_content, fine_amount, ''臺北'' AS city FROM labor_violations_tpe UNION ALL SELECT company_name, penalty_date, law_category, violation_content, fine_amount, ''新北'' AS city FROM labor_violations_ntpc) combined WHERE penalty_date IS NOT NULL ORDER BY penalty_date DESC',
 'metrotaipei', '勞動局',
 '查詢雙北雇主勞動違規記錄（勞基法、性平法、職安法）。',
 '整合臺北市與新北市三大勞動法規違規事業單位資料，為全台首個雙城合一可搜尋查詢工具。',
 '求職者查詢目標雇主是否有違規記錄，工會追蹤特定企業違規歷史。',
 'static', '', 1, 'day', '{}', '{}', '{}', '{doit,ntpc}', NOW(), NOW()),

-- 1006: 職災地圖 (map only — no chart query needed)
('labor_disaster_map', 'two_d',
 'SELECT EXTRACT(YEAR FROM incident_date)::text AS x_axis, COUNT(*) AS data FROM labor_disasters_tpe GROUP BY 1 ORDER BY 1',
 'taipei', '勞動部',
 '顯示臺北市重大職災發生地點（精確 GPS 點位）。',
 '每筆職災以紅色（死亡）或橙色（僅受傷）標記於地圖，點擊查看事業單位名稱與災害類型。',
 '勞動局稽查資源配置、工安研究者分析職災空間分布。',
 'static', '', 1, 'year',
 ARRAY(SELECT id FROM component_maps WHERE index = 'labor_disasters_tpe'),
 '{}', '{}', '{doit}', NOW(), NOW()),
('labor_disaster_map', 'two_d',
 'SELECT EXTRACT(YEAR FROM incident_date)::text AS x_axis, COUNT(*) AS data FROM (SELECT incident_date FROM labor_disasters_tpe UNION ALL SELECT incident_date FROM labor_disasters_ntpc) combined GROUP BY 1 ORDER BY 1',
 'metrotaipei', '勞動部',
 '顯示雙北重大職災熱點（臺北點位 + 新北行政區密度）。',
 '雙層疊合地圖：臺北市以精確 GPS 點位標示，新北市以行政區多邊形顏色深淺表示事故密度。',
 '勞動局稽查資源配置、市民了解自身工作區域的職安狀況。',
 'static', '', 1, 'year',
 ARRAY(SELECT id FROM component_maps WHERE index IN ('labor_disasters_tpe','labor_disasters_ntpc') ORDER BY id),
 '{}', '{}', '{doit,ntpc}', NOW(), NOW()),

-- 1007: 月度趨勢
('labor_violations_monthly', 'two_d',
 'SELECT TO_CHAR(DATE_TRUNC(''month'',penalty_date),''YYYY-MM'') AS x_axis, COUNT(*) AS data FROM labor_violations_tpe WHERE penalty_date >= ''2022-01-01'' GROUP BY 1 ORDER BY 1',
 'taipei', '勞動局', '顯示臺北市每月違規件數趨勢。', '統計臺北市三大法規每月處分件數。', '觀察稽查力度週期性變化。',
 'static','',1,'day','{}','{}','{}','{doit}', NOW(), NOW()),
('labor_violations_monthly', 'two_d',
 'SELECT TO_CHAR(d,''YYYY-MM'') AS x_axis, SUM(cnt) AS data FROM (SELECT DATE_TRUNC(''month'',penalty_date) AS d, COUNT(*) AS cnt FROM labor_violations_tpe WHERE penalty_date >= ''2022-01-01'' GROUP BY 1 UNION ALL SELECT DATE_TRUNC(''month'',penalty_date) AS d, COUNT(*) AS cnt FROM labor_violations_ntpc WHERE penalty_date >= ''2022-01-01'' GROUP BY 1) t GROUP BY 1 ORDER BY 1',
 'metrotaipei', '勞動局', '顯示雙北每月違規件數趨勢。', '整合臺北市與新北市每月處分件數。', '比較雙城稽查規模。',
 'static','',1,'day','{}','{}','{}','{doit,ntpc}', NOW(), NOW()),

-- 1008: 行業別勞資爭議
('labor_disputes_industry', 'two_d',
 'SELECT industry AS x_axis, SUM(case_count) AS data FROM labor_disputes_industry_tpe WHERE year >= 2021 GROUP BY industry ORDER BY data DESC LIMIT 15',
 'taipei', '勞動局', '臺北市行業別勞資爭議件數排行。', '統計2021年迄今各行業勞資爭議累計件數。', '識別高爭議行業。',
 'static','',1,'year','{}','{}','{}','{doit}', NOW(), NOW()),
('labor_disputes_industry', 'two_d',
 'SELECT industry AS x_axis, SUM(case_count) AS data FROM labor_disputes_industry_tpe WHERE year >= 2021 GROUP BY industry ORDER BY data DESC LIMIT 15',
 'metrotaipei', '勞動局', '臺北市行業別勞資爭議件數排行（注：目前僅含臺北市資料）。', '統計2021年迄今各行業勞資爭議累計件數。', '識別高爭議行業。',
 'static','',1,'year','{}','{}','{}','{doit}', NOW(), NOW()),

-- 1009: 法規類別圓餅
('labor_law_category', 'two_d',
 'SELECT law_category AS x_axis, COUNT(*) AS data FROM labor_violations_tpe GROUP BY law_category ORDER BY data DESC',
 'taipei', '勞動局', '臺北市違規法規類別占比。', '勞基法、性平法、職安法三大法規違規件數比例。', '了解執法重點。',
 'static','',1,'day','{}','{}','{}','{doit}', NOW(), NOW()),
('labor_law_category', 'two_d',
 'SELECT law_category AS x_axis, COUNT(*) AS data FROM (SELECT law_category FROM labor_violations_tpe UNION ALL SELECT law_category FROM labor_violations_ntpc) combined GROUP BY law_category ORDER BY data DESC',
 'metrotaipei', '勞動局', '雙北違規法規類別占比。', '整合雙北三大法規違規件數比例。', '比較雙城執法側重。',
 'static','',1,'day','{}','{}','{}','{doit,ntpc}', NOW(), NOW()),

-- 1010: 勞動市場健康
('labor_market_health', 'two_d',
 'SELECT TO_CHAR(period_date,''YYYY-MM'') AS x_axis, insured_persons AS data FROM labor_insurance_monthly_tpe WHERE period_date >= ''2020-01-01'' ORDER BY period_date',
 'taipei', '勞動局', '臺北市勞保投保人數月趨勢（2020起）。', '反映勞動市場景氣的投保人數月度變化。', '監測勞動市場健康度，投保人數下降預警裁員。',
 'static','',1,'month','{}','{}','{}','{doit}', NOW(), NOW()),
('labor_market_health', 'two_d',
 'SELECT TO_CHAR(period_date,''YYYY-MM'') AS x_axis, insured_persons AS data FROM labor_insurance_monthly_tpe WHERE period_date >= ''2020-01-01'' ORDER BY period_date',
 'metrotaipei', '勞動局', '臺北市勞保投保人數月趨勢（注：目前僅含臺北市資料）。', '反映勞動市場景氣的投保人數月度變化。', '監測勞動市場健康度。',
 'static','',1,'month','{}','{}','{}','{doit}', NOW(), NOW());

-- ── 5. dashboards ────────────────────────────────────────────────────────────
INSERT INTO dashboards (id, index, name, components, icon, created_at, updated_at) VALUES
  (502, 'labor_safety_radar', '工作安全燈號',
   ARRAY[1005,1006,1007,1008,1009,1010], 'work', NOW(), NOW())
ON CONFLICT (index) DO NOTHING;

-- ── 6. dashboard_groups ──────────────────────────────────────────────────────
INSERT INTO dashboard_groups (dashboard_id, group_id) VALUES
  (502, 2),
  (502, 3)
ON CONFLICT DO NOTHING;
```

**Run:**
```bash
docker exec -i postgres-manager psql -U postgres -d dashboardmanager < scripts/register_labor_safety.sql
```

**Verify:**
```bash
docker exec postgres-manager psql -U postgres -d dashboardmanager -c \
  "SELECT id, name FROM components WHERE id BETWEEN 1005 AND 1010;"
docker exec postgres-manager psql -U postgres -d dashboardmanager -c \
  "SELECT index, city FROM query_charts WHERE index LIKE 'labor_%' ORDER BY index, city;"
docker exec postgres-manager psql -U postgres -d dashboardmanager -c \
  "SELECT id, name, components FROM dashboards WHERE id=502;"
```

**Commit:**
```bash
git add scripts/register_labor_safety.sql
git commit -m "feat: register labor safety radar dashboard — 6 components (1005-1010)"
```

---

## Task 9: Frontend Verification

**Step 1: Restart backend**
```bash
docker-compose -f docker/docker-compose.yaml restart dashboard-be
```

**Step 2: Start FE dev server**
```bash
cd Taipei-City-Dashboard-FE && npm run dev
```

**Step 3: Navigate to dashboard**

Open `http://localhost:8080`, switch to 雙北 city mode. Confirm "工作安全燈號" appears in sidebar.

**Step 4: Verify each component**

| Component | 臺北視角 | 雙北視角 |
|-----------|---------|---------|
| 雇主違規快查 | 臺北違規可搜尋 | 雙北合併可搜尋，城市欄位顯示正確 |
| 職災地圖 | 臺北點位 (紅/橙) | 臺北點位 + 新北 choropleth |
| 月度趨勢 | 單線 (TPE) | 合計趨勢 |
| 行業別爭議 | 15 行業橫向長條 | 同上 |
| 法規類別 | 三色圓餅 | 雙北合計 |
| 勞動市場 | 投保人數折線 | 同上 |

**Step 5: Final commit**
```bash
git add -A
git commit -m "feat: complete 工作安全燈號 dashboard — labor safety radar"
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| TPE 職安法 API 無資料 | RID `90d05db5` 驗證有效；若 offset 分頁無效，改用 CSV 下載 URL |
| NTPC district polygon 找不到 | district 名稱可能缺「區」字，在 merge script 中加上 `+ "區"` fallback |
| SearchableViolationTable 不顯示 | 確認 `DashboardComponent.vue` 已加 import 和 case |
| 地圖 choropleth 無色 | 確認 NTPC GeoJSON `incidents` 欄位為 integer not string |
| 月度趨勢空白 | 檢查 `penalty_date` 欄位值：`SELECT MIN(penalty_date) FROM labor_violations_tpe` |
| duplicate key on components | `DELETE FROM components WHERE id BETWEEN 1005 AND 1010` 先清除 |
