# 方案A：雙北綠色出行儀表板 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 建立「雙北綠色出行儀表板」，包含 4 個雙北組件（電動機車充電站、電動汽車充電站、公車路線地圖、垃圾車收運路線），滿足競賽「至少 4 個雙北組件含至少 1 個地圖圖層」的門檻，並展示永續交通與綠色生活的空間分布。

**Architecture:** 遵循現有三層架構：Airflow ETL（拉取開放資料 → 載入 DB_DASHBOARD）→ Go BE（執行 query_chart SQL → 回傳結構化資料）→ Vue3 FE（DashboardComponent + Mapbox GL 地圖圖層）。地圖資料以靜態 GeoJSON 檔案儲存於 `Taipei-City-Dashboard-FE/public/mapData/`，由 ETL 腳本本地執行後提交至 repo。雙北支援透過同一 `index` 在 `query_charts` 表中建立兩筆記錄（city='taipei' 和 city='metrotaipei'），metrotaipei 版本 SQL 以 UNION ALL 合併雙北資料。

**Tech Stack:** Python/Airflow（ETL）, PostgreSQL（DB_DASHBOARD + DB_MANAGER）, Go/Gin（BE，無需修改）, Vue3/Pinia/Mapbox GL（FE，無需修改）

**資料來源：**
- 臺北電動機車充電站: `https://data.taipei/dataset/detail?id=759db528-77b5-4aa3-b6fa-2b857890214e`
- 新北電動機車充電站: `https://data.ntpc.gov.tw/api/datasets/1bb694e3-17c7-4ef0-ac75-52990c40edcd/json`
- 新北電動汽車充電站: `https://data.ntpc.gov.tw/api/datasets/edc3ad26-8ae7-4916-a00b-bc6048d19bf8/json`
- 臺北電動車充電停車位: `https://data.taipei/dataset/detail?id=dd7001c8-7a87-4294-a52a-e2c14bc49d88`
- 臺北公車路線軌跡: `https://tcgbusfs.blob.core.windows.net/blobbus/TstBusShape.json`
- 新北公車路線軌跡: `https://tcgbusfs.blob.core.windows.net/ntpcbus/GetBusShape.gz`
- 新北垃圾車路線（即時）: `https://data.ntpc.gov.tw/api/datasets/d7330ae1-5869-4ee7-8821-03b1d7d13822/json`
- 臺北垃圾車路線: `https://data.taipei/dataset/detail?id=34f4f00b-5386-43ab-bcc7-b0ae7ee3e305`

**組件清單（皆為雙北 ✓ + 地圖 ✓）：**

| index | 中文名稱 | 圖表類型 | 地圖類型 | DB_DASHBOARD 表 |
|-------|---------|---------|---------|----------------|
| `ev_scooter_charging` | 雙北電動機車充電站分布 | DistrictChart + BarChart | circle 點位 | `ev_scooter_charging_tpe`, `ev_scooter_charging_ntpc` |
| `ev_car_charging` | 雙北電動汽車充電站分布 | DonutChart + BarChart | circle 點位（依充電類型著色） | `ev_car_charging_tpe`, `ev_car_charging_ntpc` |
| `bus_route_map` | 雙北公車路線地圖 | MapLegend | line 線段（WKT） | `bus_route_map_tpe`, `bus_route_map_ntpc` |
| `garbage_truck_route` | 雙北垃圾車收運路線 | DistrictChart + MapLegend | line 線段 + circle 站點 | `garbage_truck_route_tpe`, `garbage_truck_route_ntpc` |

---

## Task 1：建立 Git 分支

**Files:**
- 無需建立新檔案，僅 git 操作

**Step 1.1: 從 feat/#bear 建立功能分支**
```bash
git checkout feat/#bear
git pull origin feat/#bear
git checkout -b feat/green-mobility-dashboard
```

**Step 1.2: 確認分支**
```bash
git branch --show-current
```
Expected output: `feat/green-mobility-dashboard`

---

## Task 2：DB_DASHBOARD — 建立資料表 Schema

**Files:**
- Create: `db-sample-data/migrations/green_mobility_schema.sql`

**Step 2.1: 建立 Migration SQL 檔**

建立 `db-sample-data/migrations/green_mobility_schema.sql`，內容如下：

```sql
-- ========================================
-- 方案A：雙北綠色出行 DB_DASHBOARD 資料表
-- 目標資料庫: DB_DASHBOARD (dashboard)
-- ========================================

-- 1. 電動機車充電站（臺北）
CREATE TABLE IF NOT EXISTS ev_scooter_charging_tpe (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200),
    address VARCHAR(300),
    district VARCHAR(50),
    lat FLOAT,
    lng FLOAT,
    operator VARCHAR(100),
    slots INTEGER DEFAULT 0,
    data_time TIMESTAMP WITH TIME ZONE
);

-- 2. 電動機車充電站（新北）
CREATE TABLE IF NOT EXISTS ev_scooter_charging_ntpc (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200),
    address VARCHAR(300),
    district VARCHAR(50),
    lat FLOAT,
    lng FLOAT,
    operator VARCHAR(100),
    slots INTEGER DEFAULT 0,
    data_time TIMESTAMP WITH TIME ZONE
);

-- 3. 電動汽車充電站（臺北）
CREATE TABLE IF NOT EXISTS ev_car_charging_tpe (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200),
    address VARCHAR(300),
    district VARCHAR(50),
    lat FLOAT,
    lng FLOAT,
    charger_type VARCHAR(20),  -- AC / DC / both
    slots INTEGER DEFAULT 0,
    data_time TIMESTAMP WITH TIME ZONE
);

-- 4. 電動汽車充電站（新北）
CREATE TABLE IF NOT EXISTS ev_car_charging_ntpc (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200),
    address VARCHAR(300),
    district VARCHAR(50),
    lat FLOAT,
    lng FLOAT,
    charger_type VARCHAR(20),
    slots INTEGER DEFAULT 0,
    data_time TIMESTAMP WITH TIME ZONE
);

-- 5. 公車路線（臺北）
CREATE TABLE IF NOT EXISTS bus_route_map_tpe (
    id SERIAL PRIMARY KEY,
    route_uid VARCHAR(30),
    route_name VARCHAR(100),
    direction INTEGER DEFAULT 0,  -- 0=去程 1=返程
    data_time TIMESTAMP WITH TIME ZONE
);

-- 6. 公車路線（新北）
CREATE TABLE IF NOT EXISTS bus_route_map_ntpc (
    id SERIAL PRIMARY KEY,
    route_uid VARCHAR(30),
    route_name VARCHAR(100),
    direction INTEGER DEFAULT 0,
    data_time TIMESTAMP WITH TIME ZONE
);

-- 7. 垃圾車收運路線（臺北）
CREATE TABLE IF NOT EXISTS garbage_truck_route_tpe (
    id SERIAL PRIMARY KEY,
    route_code VARCHAR(30),
    district VARCHAR(50),
    route_name VARCHAR(100),
    weekday VARCHAR(20),    -- 星期幾收運
    vehicle_no VARCHAR(20),
    data_time TIMESTAMP WITH TIME ZONE
);

-- 8. 垃圾車收運路線（新北）
CREATE TABLE IF NOT EXISTS garbage_truck_route_ntpc (
    id SERIAL PRIMARY KEY,
    route_code VARCHAR(30),
    district VARCHAR(50),
    route_name VARCHAR(100),
    weekday VARCHAR(20),
    vehicle_no VARCHAR(20),
    lat FLOAT,
    lng FLOAT,
    data_time TIMESTAMP WITH TIME ZONE
);
```

**Step 2.2: 執行 Migration（連接本地 DB_DASHBOARD）**

確認 docker/.env 中 DB_DASHBOARD 的連線參數，然後：
```bash
docker exec -it dashboard-postgres psql -U postgres -d dashboard -f /path/to/green_mobility_schema.sql
```

或使用 psql 直連：
```bash
psql -h localhost -U postgres -d dashboard -f db-sample-data/migrations/green_mobility_schema.sql
```

Expected output: `CREATE TABLE` × 8

**Step 2.3: 確認資料表建立成功**
```bash
psql -h localhost -U postgres -d dashboard -c "\dt ev_*; \dt bus_*; \dt garbage_*"
```

**Step 2.4: Commit**
```bash
git add db-sample-data/migrations/green_mobility_schema.sql
git commit -m "feat: add DB_DASHBOARD schema for green mobility dashboard"
```

---

## Task 3：ETL 腳本 — 雙北電動機車充電站

**Files:**
- Create: `Taipei-City-Dashboard-DE/dags/proj_city_dashboard/D_ev_scooter_tpe/D_ev_scooter_tpe.py`
- Create: `Taipei-City-Dashboard-DE/dags/proj_city_dashboard/D_ev_scooter_tpe/job_config.json`
- Create: `Taipei-City-Dashboard-DE/dags/proj_city_dashboard/D_ev_scooter_tpe/ev_scooter_etl.py`
- Create: `Taipei-City-Dashboard-DE/dags/proj_city_dashboard/D_ev_scooter_ntpc/D_ev_scooter_ntpc.py`
- Create: `Taipei-City-Dashboard-DE/dags/proj_city_dashboard/D_ev_scooter_ntpc/job_config.json`
- Create: `Taipei-City-Dashboard-DE/dags/proj_city_dashboard/D_ev_scooter_ntpc/ev_scooter_ntpc_etl.py`

**Step 3.1: 建立臺北電動機車充電站 job_config.json**

建立 `Taipei-City-Dashboard-DE/dags/proj_city_dashboard/D_ev_scooter_tpe/job_config.json`：

```json
{
    "dag_infos": {
        "dag_id": "D_ev_scooter_tpe",
        "start_date": "2026-04-18",
        "schedule_interval": "0 6 * * *",
        "catchup": false,
        "tags": ["ev_scooter_charging", "電動機車", "充電站", "臺北"],
        "description": "Taipei City EV Scooter Charging Stations",
        "default_args": {
            "owner": "airflow",
            "email": ["DEFAULT_EMAIL_LIST"],
            "email_on_retry": false,
            "email_on_failure": true,
            "retries": 1,
            "retry_delay": 60
        },
        "ready_data_db": "postgres_default",
        "ready_data_default_table": "ev_scooter_charging_tpe",
        "raw_data_db": "postgres_default",
        "raw_data_table": "",
        "load_behavior": "replace"
    },
    "data_infos": {
        "name_cn": "臺北市電動機車充電站",
        "airflow_update_freq": "06:00 every day",
        "source": "https://data.taipei/dataset/detail?id=759db528-77b5-4aa3-b6fa-2b857890214e",
        "source_type": "data.taipei JSON",
        "source_dept": "臺北市政府",
        "gis_format": "Point",
        "output_coordinate": "EPSG:4326",
        "is_geometry": 1,
        "dataset_description": "臺北市電動機車充電站位置資料",
        "sensitivity": "public"
    }
}
```

**Step 3.2: 建立臺北電動機車充電站 ETL 腳本**

建立 `Taipei-City-Dashboard-DE/dags/proj_city_dashboard/D_ev_scooter_tpe/ev_scooter_etl.py`：

```python
def ev_scooter_tpe_etl(**kwargs):
    """
    ETL for Taipei EV Scooter Charging Stations.
    Source: data.taipei API
    Steps: Extract → geocode addresses → load to DB → export GeoJSON
    """
    import json
    import time
    import requests
    import pandas as pd
    from sqlalchemy import create_engine, text
    from utils.get_time import get_tpe_now_time_str

    # Config
    ready_data_db_uri = kwargs.get("ready_data_db_uri")
    dag_infos = kwargs.get("dag_infos")
    dag_id = dag_infos.get("dag_id")
    default_table = dag_infos.get("ready_data_default_table")

    # Extract: 直接呼叫 data.taipei API
    # 先查詢 resource ID
    # 注意: 實際 API URL 需透過 data.taipei dataset 頁面確認 resource download URL
    TAIPEI_API = (
        "https://data.taipei/api/frontstage/tpeod/dataset/resource.download"
        "?rid=<替換為實際的resource_id>"
    )
    # 備用方案: 使用 data.taipei OpenAPI 的 JSON endpoint
    TAIPEI_API_V2 = "https://data.taipei/api/v1/dataset/759db528-77b5-4aa3-b6fa-2b857890214e?scope=resourceAquire"

    resp = requests.get(TAIPEI_API_V2, timeout=30)
    resp.raise_for_status()
    raw = resp.json()

    # data.taipei v1 API 回傳格式: {"result": {"results": [...]}}
    records = raw.get("result", {}).get("results", [])
    if not records:
        raise ValueError("No data returned from Taipei EV scooter API")

    df = pd.DataFrame(records)
    print(f"Extracted {len(df)} records from Taipei EV scooter API")

    # Transform: 統一欄位名稱
    # 注意: 實際欄位名稱需參照 data.taipei 資料集說明，以下為推測
    # 常見欄位: 站名/站名稱, 地址, 行政區, 緯度/lat, 經度/lng, 業者, 充電座數
    col_map = {
        "stationname": "name",
        "address": "address",
        "district": "district",
        "lat": "lat",
        "lng": "lng",
        "operator": "operator",
        "chargeslot": "slots",
    }
    # 僅保留存在的欄位
    existing_cols = {k: v for k, v in col_map.items() if k in df.columns}
    df = df.rename(columns=existing_cols)

    # 確保必要欄位存在
    for col in ["name", "address", "lat", "lng"]:
        if col not in df.columns:
            df[col] = None

    # 轉換數值欄位
    for col in ["lat", "lng", "slots"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # 過濾無效座標
    df = df[df["lat"].notna() & df["lng"].notna()]

    # 如果沒有座標欄位，需進行地理編碼（耗時，hackathon可先跳過無座標資料）
    if df["lat"].isna().all():
        print("WARNING: No coordinates in source data, geocoding required")
        df = geocode_addresses(df)

    # 添加行政區（如果沒有）
    if "district" not in df.columns or df["district"].isna().all():
        df = extract_district_from_address(df)

    df["data_time"] = get_tpe_now_time_str(is_with_tz=True)

    # 選取最終欄位
    final_cols = ["name", "address", "district", "lat", "lng", "operator", "slots", "data_time"]
    for col in final_cols:
        if col not in df.columns:
            df[col] = None
    df = df[final_cols]

    # Load to DB
    engine = create_engine(ready_data_db_uri)
    with engine.connect() as conn:
        conn.execute(text(f"TRUNCATE TABLE {default_table}"))
        conn.commit()
    df.to_sql(default_table, engine, if_exists="append", index=False)
    print(f"Loaded {len(df)} records to {default_table}")

    # Export GeoJSON for Mapbox
    export_geojson(df, dag_id, suffix="_tpe")

    # Update dataset_info
    from utils.load_stage import update_lasttime_in_data_to_dataset_info
    update_lasttime_in_data_to_dataset_info(engine, dag_id, df["data_time"].max())


def geocode_addresses(df):
    """
    Batch geocode addresses using TGOS geocoding API.
    Skip addresses that fail (return NaN lat/lng).
    """
    import requests
    TGOS_API = "https://api.tgos.tw/TGOS_API/api/geocoding"
    # 注意: TGOS API 需申請 API Key
    # 替代方案: 使用 Nominatim (OpenStreetMap) geocoding
    lats, lngs = [], []
    for addr in df.get("address", []):
        try:
            resp = requests.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": f"台灣{addr}", "format": "json", "limit": 1},
                headers={"User-Agent": "TaipeiDashboardHackathon/1.0"},
                timeout=5,
            )
            results = resp.json()
            if results:
                lats.append(float(results[0]["lat"]))
                lngs.append(float(results[0]["lon"]))
            else:
                lats.append(None)
                lngs.append(None)
            import time; time.sleep(1)  # Nominatim rate limit: 1 req/sec
        except Exception:
            lats.append(None)
            lngs.append(None)
    df["lat"] = lats
    df["lng"] = lngs
    return df


def extract_district_from_address(df):
    """Extract district from address string (e.g. '台北市信義區...' → '信義區')."""
    import re
    districts = []
    for addr in df.get("address", []):
        match = re.search(r"[\u4e00-\u9fff]{2}區", str(addr))
        districts.append(match.group(0) if match else None)
    df["district"] = districts
    return df


def export_geojson(df, dag_id, suffix=""):
    """
    Export DataFrame with lat/lng to GeoJSON file.
    GeoJSON is saved to FE public/mapData/ for Mapbox GL.
    """
    import json
    import os

    features = []
    for _, row in df.iterrows():
        if pd.isna(row.get("lat")) or pd.isna(row.get("lng")):
            continue
        feature = {
            "type": "Feature",
            "properties": {k: row[k] for k in row.index if k not in ["lat", "lng", "data_time"]},
            "geometry": {
                "type": "Point",
                "coordinates": [float(row["lng"]), float(row["lat"])],
            },
        }
        features.append(feature)

    geojson = {"type": "FeatureCollection", "features": features}

    # 輸出路徑: FE 的 public/mapData/ 目錄
    # 在 Docker 環境中需調整此路徑
    output_dir = os.environ.get(
        "MAPDATA_OUTPUT_DIR",
        "/workspace/Taipei-City-Dashboard-FE/public/mapData",
    )
    os.makedirs(output_dir, exist_ok=True)
    index_name = dag_id.replace("D_", "")  # e.g. "ev_scooter_tpe" → "ev_scooter_tpe"
    output_path = os.path.join(output_dir, f"{index_name}{suffix}.geojson")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False)
    print(f"Exported {len(features)} features to {output_path}")
```

**Step 3.3: 建立臺北電動機車充電站 DAG entry point**

建立 `Taipei-City-Dashboard-DE/dags/proj_city_dashboard/D_ev_scooter_tpe/D_ev_scooter_tpe.py`：

```python
from airflow import DAG
from operators.common_pipeline import CommonDag


def D_ev_scooter_tpe(**kwargs):
    from proj_city_dashboard.D_ev_scooter_tpe.ev_scooter_etl import ev_scooter_tpe_etl
    ev_scooter_tpe_etl(**kwargs)


dag = CommonDag(proj_folder="proj_city_dashboard", dag_folder="D_ev_scooter_tpe")
dag.create_dag(etl_func=D_ev_scooter_tpe)
```

**Step 3.4: 建立新北電動機車充電站 ETL 腳本**

建立 `Taipei-City-Dashboard-DE/dags/proj_city_dashboard/D_ev_scooter_ntpc/ev_scooter_ntpc_etl.py`：

```python
def ev_scooter_ntpc_etl(**kwargs):
    """
    ETL for New Taipei City EV Scooter Charging Stations.
    Source: data.ntpc.gov.tw API
    """
    import requests
    import pandas as pd
    from sqlalchemy import create_engine, text
    from utils.get_time import get_tpe_now_time_str

    ready_data_db_uri = kwargs.get("ready_data_db_uri")
    dag_infos = kwargs.get("dag_infos")
    dag_id = dag_infos.get("dag_id")
    default_table = dag_infos.get("ready_data_default_table")

    # Extract: data.ntpc.gov.tw JSON API
    NTPC_API = "https://data.ntpc.gov.tw/api/datasets/1bb694e3-17c7-4ef0-ac75-52990c40edcd/json"
    resp = requests.get(NTPC_API, timeout=30)
    resp.raise_for_status()
    records = resp.json()

    if not records:
        raise ValueError("No data returned from NTPC EV scooter API")

    df = pd.DataFrame(records)
    print(f"Extracted {len(df)} records from NTPC EV scooter API")

    # Transform: 統一欄位名稱（依 data.ntpc 實際欄位調整）
    # 常見欄位: 站名, 地址, 區別, 緯度, 經度, 業者, 充電座數
    col_map = {
        "stationname": "name",
        "address": "address",
        "district": "district",
        "lat": "lat",
        "lng": "lng",
        "lng": "lng",
        "operator": "operator",
        "slots": "slots",
    }
    existing_cols = {k: v for k, v in col_map.items() if k in df.columns}
    df = df.rename(columns=existing_cols)

    for col in ["name", "address", "lat", "lng"]:
        if col not in df.columns:
            df[col] = None

    for col in ["lat", "lng", "slots"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df[df["lat"].notna() & df["lng"].notna()]
    df["data_time"] = get_tpe_now_time_str(is_with_tz=True)

    final_cols = ["name", "address", "district", "lat", "lng", "operator", "slots", "data_time"]
    for col in final_cols:
        if col not in df.columns:
            df[col] = None
    df = df[final_cols]

    # Load to DB
    engine = create_engine(ready_data_db_uri)
    with engine.connect() as conn:
        conn.execute(text(f"TRUNCATE TABLE {default_table}"))
        conn.commit()
    df.to_sql(default_table, engine, if_exists="append", index=False)
    print(f"Loaded {len(df)} records to {default_table}")

    from utils.load_stage import update_lasttime_in_data_to_dataset_info
    update_lasttime_in_data_to_dataset_info(engine, dag_id, df["data_time"].max())

    # 匯出 GeoJSON（雙北合併版本由 Task 9 完成）
```

**Step 3.5: 建立新北 job_config.json 和 DAG entry point**

`job_config.json`：
```json
{
    "dag_infos": {
        "dag_id": "D_ev_scooter_ntpc",
        "start_date": "2026-04-18",
        "schedule_interval": "0 6 * * *",
        "catchup": false,
        "tags": ["ev_scooter_charging", "電動機車", "充電站", "新北"],
        "description": "New Taipei City EV Scooter Charging Stations",
        "default_args": {
            "owner": "airflow",
            "email": ["DEFAULT_EMAIL_LIST"],
            "email_on_retry": false,
            "email_on_failure": true,
            "retries": 1,
            "retry_delay": 60
        },
        "ready_data_db": "postgres_default",
        "ready_data_default_table": "ev_scooter_charging_ntpc",
        "raw_data_db": "postgres_default",
        "raw_data_table": "",
        "load_behavior": "replace"
    },
    "data_infos": {
        "name_cn": "新北市電動機車充電站",
        "airflow_update_freq": "06:00 every day",
        "source": "https://data.ntpc.gov.tw/datasets/1bb694e3-17c7-4ef0-ac75-52990c40edcd",
        "source_type": "data.ntpc JSON API",
        "source_dept": "新北市政府",
        "is_geometry": 1,
        "sensitivity": "public"
    }
}
```

`D_ev_scooter_ntpc.py`：
```python
from airflow import DAG
from operators.common_pipeline import CommonDag


def D_ev_scooter_ntpc(**kwargs):
    from proj_city_dashboard.D_ev_scooter_ntpc.ev_scooter_ntpc_etl import ev_scooter_ntpc_etl
    ev_scooter_ntpc_etl(**kwargs)


dag = CommonDag(proj_folder="proj_city_dashboard", dag_folder="D_ev_scooter_ntpc")
dag.create_dag(etl_func=D_ev_scooter_ntpc)
```

**Step 3.6: Commit**
```bash
git add Taipei-City-Dashboard-DE/dags/proj_city_dashboard/D_ev_scooter_tpe/
git add Taipei-City-Dashboard-DE/dags/proj_city_dashboard/D_ev_scooter_ntpc/
git commit -m "feat: add ETL DAGs for EV scooter charging stations (Taipei + New Taipei)"
```

---

## Task 4：ETL 腳本 — 雙北電動汽車充電站

**Files:**
- Create: `Taipei-City-Dashboard-DE/dags/proj_city_dashboard/D_ev_car_tpe/D_ev_car_tpe.py`
- Create: `Taipei-City-Dashboard-DE/dags/proj_city_dashboard/D_ev_car_tpe/job_config.json`
- Create: `Taipei-City-Dashboard-DE/dags/proj_city_dashboard/D_ev_car_tpe/ev_car_tpe_etl.py`
- Create: `Taipei-City-Dashboard-DE/dags/proj_city_dashboard/D_ev_car_ntpc/D_ev_car_ntpc.py`
- Create: `Taipei-City-Dashboard-DE/dags/proj_city_dashboard/D_ev_car_ntpc/job_config.json`
- Create: `Taipei-City-Dashboard-DE/dags/proj_city_dashboard/D_ev_car_ntpc/ev_car_ntpc_etl.py`

**Step 4.1: 建立臺北電動汽車充電站 ETL**

建立 `ev_car_tpe_etl.py`：

```python
def ev_car_tpe_etl(**kwargs):
    """
    ETL for Taipei City EV Car Charging Stations.
    Source: data.taipei (電動車充電停車位概況)
    Note: 台北充電站資料可能包含停車場名稱+充電類型，需解析
    """
    import requests
    import pandas as pd
    from sqlalchemy import create_engine, text
    from utils.get_time import get_tpe_now_time_str

    ready_data_db_uri = kwargs.get("ready_data_db_uri")
    dag_infos = kwargs.get("dag_infos")
    dag_id = dag_infos.get("dag_id")
    default_table = dag_infos.get("ready_data_default_table")

    # Extract: data.taipei v1 API
    TAIPEI_API = "https://data.taipei/api/v1/dataset/dd7001c8-7a87-4294-a52a-e2c14bc49d88?scope=resourceAquire"
    resp = requests.get(TAIPEI_API, timeout=30)
    resp.raise_for_status()
    raw = resp.json()
    records = raw.get("result", {}).get("results", [])

    df = pd.DataFrame(records)
    print(f"Extracted {len(df)} records from Taipei EV car API")

    # Transform: 依實際欄位調整
    col_map = {
        "parkname": "name",
        "address": "address",
        "district": "district",
        "lat": "lat",
        "lng": "lng",
        "chargetype": "charger_type",  # AC / DC / 交流 / 直流
        "slots": "slots",
    }
    existing_cols = {k: v for k, v in col_map.items() if k in df.columns}
    df = df.rename(columns=existing_cols)

    for col in ["name", "address", "lat", "lng", "charger_type", "slots"]:
        if col not in df.columns:
            df[col] = None

    for col in ["lat", "lng", "slots"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # 標準化充電類型
    if "charger_type" in df.columns:
        df["charger_type"] = df["charger_type"].replace({
            "交流": "AC", "直流": "DC", "交直流": "AC+DC",
        })

    df = df[df["lat"].notna() & df["lng"].notna()]
    df["data_time"] = get_tpe_now_time_str(is_with_tz=True)

    final_cols = ["name", "address", "district", "lat", "lng", "charger_type", "slots", "data_time"]
    for col in final_cols:
        if col not in df.columns:
            df[col] = None
    df = df[final_cols]

    engine = create_engine(ready_data_db_uri)
    with engine.connect() as conn:
        conn.execute(text(f"TRUNCATE TABLE {default_table}"))
        conn.commit()
    df.to_sql(default_table, engine, if_exists="append", index=False)
    print(f"Loaded {len(df)} records to {default_table}")

    from utils.load_stage import update_lasttime_in_data_to_dataset_info
    update_lasttime_in_data_to_dataset_info(engine, dag_id, df["data_time"].max())
```

**Step 4.2: 建立新北電動汽車充電站 ETL**

建立 `ev_car_ntpc_etl.py`（結構同 Task 3.4，資料來源改為新北）：

```python
def ev_car_ntpc_etl(**kwargs):
    import requests
    import pandas as pd
    from sqlalchemy import create_engine, text
    from utils.get_time import get_tpe_now_time_str

    ready_data_db_uri = kwargs.get("ready_data_db_uri")
    dag_infos = kwargs.get("dag_infos")
    dag_id = dag_infos.get("dag_id")
    default_table = dag_infos.get("ready_data_default_table")

    NTPC_API = "https://data.ntpc.gov.tw/api/datasets/edc3ad26-8ae7-4916-a00b-bc6048d19bf8/json"
    resp = requests.get(NTPC_API, timeout=30)
    resp.raise_for_status()
    records = resp.json()

    df = pd.DataFrame(records)
    print(f"Extracted {len(df)} records from NTPC EV car API")

    col_map = {
        "name": "name",
        "address": "address",
        "district": "district",
        "lat": "lat",
        "lng": "lng",
        "chargetype": "charger_type",
        "slots": "slots",
    }
    existing_cols = {k: v for k, v in col_map.items() if k in df.columns}
    df = df.rename(columns=existing_cols)

    for col in ["name", "address", "lat", "lng", "charger_type", "slots"]:
        if col not in df.columns:
            df[col] = None
    for col in ["lat", "lng", "slots"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["charger_type"] = df.get("charger_type", pd.Series(dtype=str)).replace({
        "交流": "AC", "直流": "DC", "交直流": "AC+DC",
    })
    df = df[df["lat"].notna() & df["lng"].notna()]
    df["data_time"] = get_tpe_now_time_str(is_with_tz=True)

    final_cols = ["name", "address", "district", "lat", "lng", "charger_type", "slots", "data_time"]
    for col in final_cols:
        if col not in df.columns:
            df[col] = None
    df = df[final_cols]

    engine = create_engine(ready_data_db_uri)
    with engine.connect() as conn:
        conn.execute(text(f"TRUNCATE TABLE {default_table}"))
        conn.commit()
    df.to_sql(default_table, engine, if_exists="append", index=False)
    from utils.load_stage import update_lasttime_in_data_to_dataset_info
    update_lasttime_in_data_to_dataset_info(engine, dag_id, df["data_time"].max())
```

**Step 4.3: job_config.json for ev_car_tpe:**
```json
{
    "dag_infos": {
        "dag_id": "D_ev_car_tpe",
        "start_date": "2026-04-18",
        "schedule_interval": "0 6 * * *",
        "catchup": false,
        "tags": ["ev_car_charging", "電動汽車", "充電站", "臺北"],
        "description": "Taipei City EV Car Charging Stations",
        "default_args": {"owner": "airflow", "email": ["DEFAULT_EMAIL_LIST"],
            "email_on_retry": false, "email_on_failure": true, "retries": 1, "retry_delay": 60},
        "ready_data_db": "postgres_default",
        "ready_data_default_table": "ev_car_charging_tpe",
        "raw_data_db": "postgres_default",
        "raw_data_table": "",
        "load_behavior": "replace"
    },
    "data_infos": {
        "name_cn": "臺北市電動汽車充電站",
        "source": "https://data.taipei/dataset/detail?id=dd7001c8-7a87-4294-a52a-e2c14bc49d88",
        "source_type": "data.taipei JSON",
        "is_geometry": 1,
        "sensitivity": "public"
    }
}
```

**Step 4.4: job_config.json for ev_car_ntpc:**
```json
{
    "dag_infos": {
        "dag_id": "D_ev_car_ntpc",
        "start_date": "2026-04-18",
        "schedule_interval": "0 6 * * *",
        "catchup": false,
        "tags": ["ev_car_charging", "電動汽車", "充電站", "新北"],
        "description": "New Taipei City EV Car Charging Stations",
        "default_args": {"owner": "airflow", "email": ["DEFAULT_EMAIL_LIST"],
            "email_on_retry": false, "email_on_failure": true, "retries": 1, "retry_delay": 60},
        "ready_data_db": "postgres_default",
        "ready_data_default_table": "ev_car_charging_ntpc",
        "raw_data_db": "postgres_default",
        "raw_data_table": "",
        "load_behavior": "replace"
    },
    "data_infos": {
        "name_cn": "新北市電動汽車充電站",
        "source": "https://data.ntpc.gov.tw/datasets/edc3ad26-8ae7-4916-a00b-bc6048d19bf8",
        "source_type": "data.ntpc JSON API",
        "is_geometry": 1,
        "sensitivity": "public"
    }
}
```

**Step 4.5: Commit**
```bash
git add Taipei-City-Dashboard-DE/dags/proj_city_dashboard/D_ev_car_tpe/
git add Taipei-City-Dashboard-DE/dags/proj_city_dashboard/D_ev_car_ntpc/
git commit -m "feat: add ETL DAGs for EV car charging stations (Taipei + New Taipei)"
```

---

## Task 5：ETL 腳本 — 雙北公車路線地圖

**Files:**
- Create: `Taipei-City-Dashboard-DE/dags/proj_city_dashboard/D_bus_route/D_bus_route.py`
- Create: `Taipei-City-Dashboard-DE/dags/proj_city_dashboard/D_bus_route/job_config.json`
- Create: `Taipei-City-Dashboard-DE/dags/proj_city_dashboard/D_bus_route/bus_route_etl.py`

**Step 5.1: 建立公車路線 ETL 腳本**

建立 `bus_route_etl.py`：

```python
def bus_route_etl(**kwargs):
    """
    ETL for Taipei + New Taipei Bus Route Shapes (WKT → GeoJSON).
    Sources:
      Taipei: https://tcgbusfs.blob.core.windows.net/blobbus/TstBusShape.json
      New Taipei: https://tcgbusfs.blob.core.windows.net/ntpcbus/GetBusShape.gz
    """
    import gzip
    import json
    import re
    import requests
    import pandas as pd
    from shapely import wkt
    from sqlalchemy import create_engine, text
    from utils.get_time import get_tpe_now_time_str

    ready_data_db_uri = kwargs.get("ready_data_db_uri")
    dag_infos = kwargs.get("dag_infos")
    dag_id = dag_infos.get("dag_id")

    # --- Extract Taipei bus routes ---
    TPE_URL = "https://tcgbusfs.blob.core.windows.net/blobbus/TstBusShape.json"
    resp_tpe = requests.get(TPE_URL, timeout=60)
    resp_tpe.raise_for_status()
    tpe_data = resp_tpe.json()
    # TstBusShape.json format: list of {RouteUID, RouteNameZh, Direction, Geometry (WKT LINESTRING)}

    # --- Extract New Taipei bus routes ---
    NTPC_URL = "https://tcgbusfs.blob.core.windows.net/ntpcbus/GetBusShape.gz"
    resp_ntpc = requests.get(NTPC_URL, timeout=60)
    resp_ntpc.raise_for_status()
    ntpc_data = json.loads(gzip.decompress(resp_ntpc.content))

    def wkt_to_coords(wkt_str):
        """Convert WKT LINESTRING to coordinate array for GeoJSON."""
        try:
            geom = wkt.loads(wkt_str)
            return list(geom.coords)
        except Exception:
            return None

    def build_geojson_features(records, city_label):
        """Build GeoJSON features from bus shape records."""
        features = []
        for r in records:
            # Adjust field names based on actual API response
            geom_wkt = r.get("Geometry") or r.get("geometry") or r.get("wkt")
            if not geom_wkt:
                continue
            coords = wkt_to_coords(geom_wkt)
            if not coords:
                continue
            features.append({
                "type": "Feature",
                "properties": {
                    "route_uid": r.get("RouteUID") or r.get("routeUID", ""),
                    "route_name": r.get("RouteNameZh") or r.get("routeNameZh", ""),
                    "direction": r.get("Direction", 0),
                    "city": city_label,
                },
                "geometry": {"type": "LineString", "coordinates": coords},
            })
        return features

    tpe_features = build_geojson_features(tpe_data, "taipei")
    ntpc_features = build_geojson_features(ntpc_data, "newtaipei")
    all_features = tpe_features + ntpc_features

    # Save combined GeoJSON for Mapbox
    geojson = {"type": "FeatureCollection", "features": all_features}
    import os
    output_dir = os.environ.get(
        "MAPDATA_OUTPUT_DIR",
        "/workspace/Taipei-City-Dashboard-FE/public/mapData",
    )
    os.makedirs(output_dir, exist_ok=True)
    geojson_path = os.path.join(output_dir, "bus_route_map.geojson")
    with open(geojson_path, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False)
    print(f"Exported {len(all_features)} bus route features to {geojson_path}")

    # Load route metadata to DB_DASHBOARD (for chart queries)
    data_time = get_tpe_now_time_str(is_with_tz=True)
    engine = create_engine(ready_data_db_uri)

    tpe_rows = [
        {"route_uid": r.get("RouteUID", ""), "route_name": r.get("RouteNameZh", ""),
         "direction": r.get("Direction", 0), "data_time": data_time}
        for r in tpe_data
    ]
    ntpc_rows = [
        {"route_uid": r.get("RouteUID", ""), "route_name": r.get("RouteNameZh", ""),
         "direction": r.get("Direction", 0), "data_time": data_time}
        for r in ntpc_data
    ]

    with engine.connect() as conn:
        conn.execute(text("TRUNCATE TABLE bus_route_map_tpe"))
        conn.execute(text("TRUNCATE TABLE bus_route_map_ntpc"))
        conn.commit()

    if tpe_rows:
        pd.DataFrame(tpe_rows).to_sql("bus_route_map_tpe", engine, if_exists="append", index=False)
    if ntpc_rows:
        pd.DataFrame(ntpc_rows).to_sql("bus_route_map_ntpc", engine, if_exists="append", index=False)

    print(f"Loaded {len(tpe_rows)} Taipei routes, {len(ntpc_rows)} New Taipei routes")

    from utils.load_stage import update_lasttime_in_data_to_dataset_info
    update_lasttime_in_data_to_dataset_info(engine, dag_infos.get("dag_id"), data_time)
```

**Step 5.2: 建立 job_config.json**

```json
{
    "dag_infos": {
        "dag_id": "D_bus_route",
        "start_date": "2026-04-18",
        "schedule_interval": "0 4 * * *",
        "catchup": false,
        "tags": ["bus_route_map", "公車路線", "雙北"],
        "description": "Taipei + New Taipei Bus Route Shapes",
        "default_args": {
            "owner": "airflow",
            "email": ["DEFAULT_EMAIL_LIST"],
            "email_on_retry": false,
            "email_on_failure": true,
            "retries": 1,
            "retry_delay": 60
        },
        "ready_data_db": "postgres_default",
        "ready_data_default_table": "bus_route_map_tpe",
        "raw_data_db": "postgres_default",
        "raw_data_table": "",
        "load_behavior": "replace"
    },
    "data_infos": {
        "name_cn": "雙北公車路線軌跡",
        "source": "https://tcgbusfs.blob.core.windows.net/blobbus/TstBusShape.json",
        "source_type": "tcgbusfs JSON/GZ",
        "is_geometry": 1,
        "sensitivity": "public"
    }
}
```

**Step 5.3: 建立 DAG entry point**

```python
from airflow import DAG
from operators.common_pipeline import CommonDag


def D_bus_route(**kwargs):
    from proj_city_dashboard.D_bus_route.bus_route_etl import bus_route_etl
    bus_route_etl(**kwargs)


dag = CommonDag(proj_folder="proj_city_dashboard", dag_folder="D_bus_route")
dag.create_dag(etl_func=D_bus_route)
```

**Step 5.4: Commit**
```bash
git add Taipei-City-Dashboard-DE/dags/proj_city_dashboard/D_bus_route/
git commit -m "feat: add ETL DAG for dual-city bus route map"
```

---

## Task 6：ETL 腳本 — 雙北垃圾車收運路線

**Files:**
- Create: `Taipei-City-Dashboard-DE/dags/proj_city_dashboard/D_garbage_route/D_garbage_route.py`
- Create: `Taipei-City-Dashboard-DE/dags/proj_city_dashboard/D_garbage_route/job_config.json`
- Create: `Taipei-City-Dashboard-DE/dags/proj_city_dashboard/D_garbage_route/garbage_route_etl.py`

**Step 6.1: 建立垃圾車路線 ETL 腳本**

建立 `garbage_route_etl.py`：

```python
def garbage_route_etl(**kwargs):
    """
    ETL for Taipei + New Taipei Garbage Truck Routes.
    New Taipei: data.ntpc JSON API (每日更新, 含 GPS 座標)
    Taipei: data.taipei API (路線資訊)
    """
    import json
    import requests
    import pandas as pd
    from sqlalchemy import create_engine, text
    from utils.get_time import get_tpe_now_time_str

    ready_data_db_uri = kwargs.get("ready_data_db_uri")
    dag_infos = kwargs.get("dag_infos")
    dag_id = dag_infos.get("dag_id")
    data_time = get_tpe_now_time_str(is_with_tz=True)
    engine = create_engine(ready_data_db_uri)

    # --- Extract New Taipei garbage truck routes (has GPS) ---
    NTPC_API = "https://data.ntpc.gov.tw/api/datasets/d7330ae1-5869-4ee7-8821-03b1d7d13822/json"
    resp = requests.get(NTPC_API, timeout=30)
    resp.raise_for_status()
    ntpc_records = resp.json()
    print(f"NTPC garbage: {len(ntpc_records)} records")

    ntpc_df = pd.DataFrame(ntpc_records)
    # 欄位映射（依 data.ntpc 實際欄位，常見: 路線代碼, 行政區, 路線名, 收運日, 車號, lat, lng）
    ntpc_col_map = {
        "routecode": "route_code",
        "district": "district",
        "routename": "route_name",
        "weekday": "weekday",
        "vehicleno": "vehicle_no",
        "lat": "lat",
        "lng": "lng",
    }
    existing = {k: v for k, v in ntpc_col_map.items() if k in ntpc_df.columns}
    ntpc_df = ntpc_df.rename(columns=existing)
    for col in ["route_code", "district", "route_name", "weekday", "vehicle_no", "lat", "lng"]:
        if col not in ntpc_df.columns:
            ntpc_df[col] = None
    for col in ["lat", "lng"]:
        ntpc_df[col] = pd.to_numeric(ntpc_df[col], errors="coerce")
    ntpc_df["data_time"] = data_time

    final_ntpc = ["route_code", "district", "route_name", "weekday", "vehicle_no", "lat", "lng", "data_time"]
    ntpc_df = ntpc_df[[c for c in final_ntpc if c in ntpc_df.columns]]

    with engine.connect() as conn:
        conn.execute(text("TRUNCATE TABLE garbage_truck_route_ntpc"))
        conn.commit()
    ntpc_df.to_sql("garbage_truck_route_ntpc", engine, if_exists="append", index=False)

    # --- Extract Taipei garbage truck routes ---
    TPE_API = "https://data.taipei/api/v1/dataset/34f4f00b-5386-43ab-bcc7-b0ae7ee3e305?scope=resourceAquire"
    try:
        resp_tpe = requests.get(TPE_API, timeout=30)
        resp_tpe.raise_for_status()
        tpe_records = resp_tpe.json().get("result", {}).get("results", [])
    except Exception as e:
        print(f"Taipei garbage API failed: {e}, skipping")
        tpe_records = []

    if tpe_records:
        tpe_df = pd.DataFrame(tpe_records)
        tpe_col_map = {
            "routecode": "route_code",
            "district": "district",
            "routename": "route_name",
            "weekday": "weekday",
            "vehicleno": "vehicle_no",
        }
        existing_tpe = {k: v for k, v in tpe_col_map.items() if k in tpe_df.columns}
        tpe_df = tpe_df.rename(columns=existing_tpe)
        for col in ["route_code", "district", "route_name", "weekday", "vehicle_no"]:
            if col not in tpe_df.columns:
                tpe_df[col] = None
        tpe_df["data_time"] = data_time
        final_tpe = ["route_code", "district", "route_name", "weekday", "vehicle_no", "data_time"]
        tpe_df = tpe_df[[c for c in final_tpe if c in tpe_df.columns]]

        with engine.connect() as conn:
            conn.execute(text("TRUNCATE TABLE garbage_truck_route_tpe"))
            conn.commit()
        tpe_df.to_sql("garbage_truck_route_tpe", engine, if_exists="append", index=False)
        print(f"Loaded {len(tpe_df)} Taipei garbage routes")

    # Export GeoJSON from New Taipei GPS data (Taipei has no GPS in this dataset)
    ntpc_with_coords = ntpc_df[ntpc_df["lat"].notna() & ntpc_df["lng"].notna()]
    features = [
        {
            "type": "Feature",
            "properties": {
                "route_code": row.get("route_code"),
                "district": row.get("district"),
                "route_name": row.get("route_name"),
                "weekday": row.get("weekday"),
                "city": "newtaipei",
            },
            "geometry": {
                "type": "Point",
                "coordinates": [float(row["lng"]), float(row["lat"])],
            },
        }
        for _, row in ntpc_with_coords.iterrows()
    ]
    import os
    geojson = {"type": "FeatureCollection", "features": features}
    output_dir = os.environ.get("MAPDATA_OUTPUT_DIR", "/workspace/Taipei-City-Dashboard-FE/public/mapData")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "garbage_truck_route.geojson")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False)
    print(f"Exported {len(features)} garbage truck features to {output_path}")

    from utils.load_stage import update_lasttime_in_data_to_dataset_info
    update_lasttime_in_data_to_dataset_info(engine, dag_id, data_time)
```

**Step 6.2: job_config.json**
```json
{
    "dag_infos": {
        "dag_id": "D_garbage_route",
        "start_date": "2026-04-18",
        "schedule_interval": "30 5 * * *",
        "catchup": false,
        "tags": ["garbage_truck_route", "垃圾車", "雙北"],
        "description": "Taipei + New Taipei Garbage Truck Routes",
        "default_args": {"owner": "airflow", "email": ["DEFAULT_EMAIL_LIST"],
            "email_on_retry": false, "email_on_failure": true, "retries": 1, "retry_delay": 60},
        "ready_data_db": "postgres_default",
        "ready_data_default_table": "garbage_truck_route_ntpc",
        "raw_data_db": "postgres_default", "raw_data_table": "",
        "load_behavior": "replace"
    },
    "data_infos": {
        "name_cn": "雙北垃圾車收運路線",
        "source": "https://data.ntpc.gov.tw/datasets/d7330ae1-5869-4ee7-8821-03b1d7d13822",
        "source_type": "data.ntpc JSON API",
        "is_geometry": 1,
        "sensitivity": "public"
    }
}
```

**Step 6.3: DAG entry point**

```python
from airflow import DAG
from operators.common_pipeline import CommonDag


def D_garbage_route(**kwargs):
    from proj_city_dashboard.D_garbage_route.garbage_route_etl import garbage_route_etl
    garbage_route_etl(**kwargs)


dag = CommonDag(proj_folder="proj_city_dashboard", dag_folder="D_garbage_route")
dag.create_dag(etl_func=D_garbage_route)
```

**Step 6.4: Commit**
```bash
git add Taipei-City-Dashboard-DE/dags/proj_city_dashboard/D_garbage_route/
git commit -m "feat: add ETL DAG for dual-city garbage truck routes"
```

---

## Task 7：本地執行 ETL，匯出 GeoJSON

在競賽環境中，Airflow 可能未完全配置。本 Task 提供直接本地執行 ETL 腳本並匯出 GeoJSON 的方式。

**Files:**
- Create: `scripts/run_green_mobility_etl.py`

**Step 7.1: 建立本地執行腳本**

建立 `scripts/run_green_mobility_etl.py`：

```python
"""
本地執行所有綠色出行 ETL 腳本並匯出 GeoJSON。
在 hackathon 環境中使用此腳本快速初始化資料。

使用方式:
    cd Taipei-City-Dashboard-DE/dags
    python ../../scripts/run_green_mobility_etl.py
"""
import os
import sys
import json
import gzip
import re
import requests
import pandas as pd

# 設定輸出路徑（相對於 repo root）
MAPDATA_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "Taipei-City-Dashboard-FE", "public", "mapData")
)
os.makedirs(MAPDATA_DIR, exist_ok=True)


def export_geojson(features, filename):
    path = os.path.join(MAPDATA_DIR, filename)
    geojson = {"type": "FeatureCollection", "features": features}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False)
    print(f"✓ Exported {len(features)} features → {path}")


def wkt_to_coords(wkt_str):
    from shapely import wkt
    try:
        geom = wkt.loads(wkt_str)
        return list(geom.coords)
    except Exception:
        return None


def run_ev_scooter():
    print("\n=== EV Scooter Charging Stations ===")
    # Taipei
    url_tpe = "https://data.taipei/api/v1/dataset/759db528-77b5-4aa3-b6fa-2b857890214e?scope=resourceAquire"
    # New Taipei
    url_ntpc = "https://data.ntpc.gov.tw/api/datasets/1bb694e3-17c7-4ef0-ac75-52990c40edcd/json"

    features = []
    for url, city in [(url_tpe, "taipei"), (url_ntpc, "newtaipei")]:
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            records = data.get("result", {}).get("results", data) if isinstance(data, dict) else data
            print(f"  {city}: {len(records)} records")
            for r in records:
                # 欄位名稱依實際 API 回傳調整
                lat = pd.to_numeric(r.get("lat") or r.get("Lat") or r.get("緯度"), errors="coerce")
                lng = pd.to_numeric(r.get("lng") or r.get("Lng") or r.get("經度"), errors="coerce")
                if pd.isna(lat) or pd.isna(lng):
                    continue
                features.append({
                    "type": "Feature",
                    "properties": {
                        "name": r.get("name") or r.get("stationname") or r.get("站名", ""),
                        "address": r.get("address") or r.get("地址", ""),
                        "district": r.get("district") or r.get("行政區", ""),
                        "slots": r.get("slots") or r.get("充電座數", 0),
                        "city": city,
                    },
                    "geometry": {"type": "Point", "coordinates": [float(lng), float(lat)]},
                })
        except Exception as e:
            print(f"  {city} FAILED: {e}")

    export_geojson(features, "ev_scooter_charging.geojson")


def run_ev_car():
    print("\n=== EV Car Charging Stations ===")
    url_tpe = "https://data.taipei/api/v1/dataset/dd7001c8-7a87-4294-a52a-e2c14bc49d88?scope=resourceAquire"
    url_ntpc = "https://data.ntpc.gov.tw/api/datasets/edc3ad26-8ae7-4916-a00b-bc6048d19bf8/json"

    features = []
    for url, city in [(url_tpe, "taipei"), (url_ntpc, "newtaipei")]:
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            records = data.get("result", {}).get("results", data) if isinstance(data, dict) else data
            print(f"  {city}: {len(records)} records")
            for r in records:
                lat = pd.to_numeric(r.get("lat") or r.get("Lat") or r.get("緯度"), errors="coerce")
                lng = pd.to_numeric(r.get("lng") or r.get("Lng") or r.get("經度"), errors="coerce")
                if pd.isna(lat) or pd.isna(lng):
                    continue
                charger_type = str(r.get("chargetype") or r.get("充電類型") or "AC").replace("交流", "AC").replace("直流", "DC")
                features.append({
                    "type": "Feature",
                    "properties": {
                        "name": r.get("name") or r.get("parkname") or r.get("站名", ""),
                        "address": r.get("address") or r.get("地址", ""),
                        "charger_type": charger_type,
                        "slots": r.get("slots") or r.get("充電座數", 0),
                        "city": city,
                    },
                    "geometry": {"type": "Point", "coordinates": [float(lng), float(lat)]},
                })
        except Exception as e:
            print(f"  {city} FAILED: {e}")

    export_geojson(features, "ev_car_charging.geojson")


def run_bus_routes():
    print("\n=== Bus Routes ===")
    features = []
    for url, city, compressed in [
        ("https://tcgbusfs.blob.core.windows.net/blobbus/TstBusShape.json", "taipei", False),
        ("https://tcgbusfs.blob.core.windows.net/ntpcbus/GetBusShape.gz", "newtaipei", True),
    ]:
        try:
            resp = requests.get(url, timeout=120)
            resp.raise_for_status()
            content = gzip.decompress(resp.content) if compressed else resp.content
            records = json.loads(content)
            print(f"  {city}: {len(records)} route shapes")
            for r in records:
                geom_wkt = r.get("Geometry") or r.get("geometry") or r.get("wkt", "")
                if not geom_wkt:
                    continue
                coords = wkt_to_coords(geom_wkt)
                if not coords or len(coords) < 2:
                    continue
                features.append({
                    "type": "Feature",
                    "properties": {
                        "route_uid": r.get("RouteUID") or r.get("routeUID", ""),
                        "route_name": r.get("RouteNameZh") or r.get("routeNameZh", ""),
                        "direction": r.get("Direction", 0),
                        "city": city,
                    },
                    "geometry": {"type": "LineString", "coordinates": coords},
                })
        except Exception as e:
            print(f"  {city} FAILED: {e}")

    export_geojson(features, "bus_route_map.geojson")


def run_garbage_routes():
    print("\n=== Garbage Truck Routes ===")
    features = []
    url_ntpc = "https://data.ntpc.gov.tw/api/datasets/d7330ae1-5869-4ee7-8821-03b1d7d13822/json"
    try:
        resp = requests.get(url_ntpc, timeout=30)
        resp.raise_for_status()
        records = resp.json()
        print(f"  newtaipei: {len(records)} records")
        for r in records:
            lat = pd.to_numeric(r.get("lat") or r.get("Lat"), errors="coerce")
            lng = pd.to_numeric(r.get("lng") or r.get("Lng"), errors="coerce")
            if pd.isna(lat) or pd.isna(lng):
                continue
            features.append({
                "type": "Feature",
                "properties": {
                    "district": r.get("district") or r.get("行政區", ""),
                    "route_name": r.get("routename") or r.get("路線名", ""),
                    "weekday": r.get("weekday") or r.get("星期", ""),
                    "city": "newtaipei",
                },
                "geometry": {"type": "Point", "coordinates": [float(lng), float(lat)]},
            })
    except Exception as e:
        print(f"  newtaipei FAILED: {e}")

    export_geojson(features, "garbage_truck_route.geojson")


if __name__ == "__main__":
    run_ev_scooter()
    run_ev_car()
    run_bus_routes()
    run_garbage_routes()
    print("\n✅ All GeoJSON files exported to:", MAPDATA_DIR)
```

**Step 7.2: 安裝 Python 依賴（如未安裝）**
```bash
pip install requests pandas shapely
```

**Step 7.3: 執行本地 ETL 腳本**
```bash
cd /Users/junhong/Project/Taipei-City-Dashboard
python scripts/run_green_mobility_etl.py
```

Expected output:
```
=== EV Scooter Charging Stations ===
  taipei: XX records
  newtaipei: XX records
✓ Exported XX features → .../mapData/ev_scooter_charging.geojson

=== EV Car Charging Stations ===
  taipei: XX records
  newtaipei: XX records
✓ Exported XX features → .../mapData/ev_car_charging.geojson

=== Bus Routes ===
  taipei: 1003 route shapes
  newtaipei: XXX route shapes
✓ Exported XXXX features → .../mapData/bus_route_map.geojson

=== Garbage Truck Routes ===
  newtaipei: XX records
✓ Exported XX features → .../mapData/garbage_truck_route.geojson

✅ All GeoJSON files exported to: .../public/mapData
```

**⚠️ 故障排除**：若 API 返回欄位名稱與腳本不符：
1. 先呼叫 API 查看實際欄位：`curl <URL> | python3 -m json.tool | head -50`
2. 更新 `run_*.py` 函數中的 `r.get("實際欄位名", ...)` 對應

**Step 7.4: 確認 GeoJSON 輸出正確**
```bash
python3 -c "
import json
for f in ['ev_scooter_charging', 'ev_car_charging', 'bus_route_map', 'garbage_truck_route']:
    with open(f'Taipei-City-Dashboard-FE/public/mapData/{f}.geojson') as fp:
        data = json.load(fp)
    print(f'{f}: {len(data[\"features\"])} features')
"
```

**Step 7.5: Commit GeoJSON 和腳本**
```bash
git add scripts/run_green_mobility_etl.py
git add Taipei-City-Dashboard-FE/public/mapData/ev_scooter_charging.geojson
git add Taipei-City-Dashboard-FE/public/mapData/ev_car_charging.geojson
git add Taipei-City-Dashboard-FE/public/mapData/bus_route_map.geojson
git add Taipei-City-Dashboard-FE/public/mapData/garbage_truck_route.geojson
git commit -m "feat: add GeoJSON map data for green mobility dashboard"
```

---

## Task 8：DB_MANAGER — 組件與儀表板註冊

這是核心設定步驟，將 4 個組件和儀表板登記至 DB_MANAGER（dashboardmanager 資料庫）。

**Files:**
- Create: `db-sample-data/migrations/green_mobility_manager.sql`

**Step 8.1: 建立 DB_MANAGER 插入 SQL**

建立 `db-sample-data/migrations/green_mobility_manager.sql`：

```sql
-- ================================================
-- 方案A：雙北綠色出行 DB_MANAGER 設定
-- 目標資料庫: DB_MANAGER (dashboardmanager)
-- 組件 IDs: 1001-1004  儀表板 ID: 101
-- ================================================

-- ========================
-- 1. 組件基本資料
-- ========================
INSERT INTO components (id, index, name) VALUES
(1001, 'ev_scooter_charging', '雙北電動機車充電站分布'),
(1002, 'ev_car_charging', '雙北電動汽車充電站分布'),
(1003, 'bus_route_map', '雙北公車路線地圖'),
(1004, 'garbage_truck_route', '雙北垃圾車收運路線')
ON CONFLICT (id) DO NOTHING;

-- ========================
-- 2. 圖表設定 (component_charts)
-- ========================
-- colors: 依主題色，綠色系代表永續交通
-- types: 第一個為預設圖表類型

INSERT INTO component_charts (index, color, types) VALUES
('ev_scooter_charging',
 ARRAY['#22c55e', '#16a34a', '#15803d', '#166534', '#4ade80', '#86efac', '#bbf7d0', '#052e16', '#dcfce7', '#f0fdf4'],
 ARRAY['DistrictChart', 'BarChart']),
('ev_car_charging',
 ARRAY['#06b6d4', '#0891b2', '#0e7490', '#22d3ee', '#67e8f9', '#a5f3fc', '#cffafe', '#164e63', '#083344', '#ecfeff'],
 ARRAY['DonutChart', 'BarChart']),
('bus_route_map',
 ARRAY['#f59e0b', '#d97706', '#b45309', '#fbbf24', '#fcd34d', '#fde68a', '#fef3c7', '#78350f', '#92400e', '#fffbeb'],
 ARRAY['MapLegend']),
('garbage_truck_route',
 ARRAY['#84cc16', '#65a30d', '#4d7c0f', '#a3e635', '#bef264', '#d9f99d', '#ecfccb', '#365314', '#3f6212', '#f7fee7'],
 ARRAY['DistrictChart', 'MapLegend'])
ON CONFLICT (index) DO NOTHING;

-- ========================
-- 3. 地圖圖層設定 (component_maps)
-- ========================

-- 3-1. 電動機車充電站地圖（圓點，依城市著色）
INSERT INTO component_maps (index, map_config_id, type, source, size, paint, property, filter) VALUES
('ev_scooter_charging', 1001, 'circle', 'geojson', 'medium',
 '{"circle-color": ["match", ["get", "city"], "taipei", "#22c55e", "newtaipei", "#16a34a", "#22c55e"], "circle-radius": 6, "circle-opacity": 0.8, "circle-stroke-width": 1, "circle-stroke-color": "#ffffff"}',
 '[{"key": "name", "name": "站名"}, {"key": "address", "name": "地址"}, {"key": "district", "name": "行政區"}, {"key": "slots", "name": "充電座數"}, {"key": "city", "name": "城市"}]',
 NULL)
ON CONFLICT (map_config_id) DO NOTHING;

-- 3-2. 電動汽車充電站地圖（依充電類型著色）
INSERT INTO component_maps (index, map_config_id, type, source, size, paint, property, filter) VALUES
('ev_car_charging', 1002, 'circle', 'geojson', 'medium',
 '{"circle-color": ["match", ["get", "charger_type"], "DC", "#ef4444", "AC+DC", "#8b5cf6", "#06b6d4"], "circle-radius": 7, "circle-opacity": 0.85, "circle-stroke-width": 1, "circle-stroke-color": "#ffffff"}',
 '[{"key": "name", "name": "站名"}, {"key": "address", "name": "地址"}, {"key": "charger_type", "name": "充電類型"}, {"key": "slots", "name": "充電座數"}, {"key": "city", "name": "城市"}]',
 NULL)
ON CONFLICT (map_config_id) DO NOTHING;

-- 3-3. 公車路線地圖（線段，依城市著色）
INSERT INTO component_maps (index, map_config_id, type, source, size, paint, property, filter) VALUES
('bus_route_map', 1003, 'line', 'geojson', NULL,
 '{"line-color": ["match", ["get", "city"], "taipei", "#f59e0b", "newtaipei", "#d97706", "#f59e0b"], "line-width": 1.5, "line-opacity": 0.7}',
 '[{"key": "route_name", "name": "路線名稱"}, {"key": "route_uid", "name": "路線代碼"}, {"key": "direction", "name": "方向"}, {"key": "city", "name": "城市"}]',
 NULL)
ON CONFLICT (map_config_id) DO NOTHING;

-- 3-4. 垃圾車路線地圖（圓點，依行政區）
INSERT INTO component_maps (index, map_config_id, type, source, size, paint, property, filter) VALUES
('garbage_truck_route', 1004, 'circle', 'geojson', 'small',
 '{"circle-color": "#84cc16", "circle-radius": 5, "circle-opacity": 0.75, "circle-stroke-width": 1, "circle-stroke-color": "#3f6212"}',
 '[{"key": "district", "name": "行政區"}, {"key": "route_name", "name": "路線名稱"}, {"key": "weekday", "name": "收運日"}, {"key": "city", "name": "城市"}]',
 NULL)
ON CONFLICT (map_config_id) DO NOTHING;

-- ========================
-- 4. 查詢設定 (query_charts)
-- 同一 index 兩筆：city='taipei' (單一城市) 和 city='metrotaipei' (雙北)
-- ========================

-- 4-1. 電動機車充電站 - 臺北
INSERT INTO query_charts
(index, history_config, map_config_ids, map_filter, time_from, time_to,
 update_freq, update_freq_unit, source, short_desc, long_desc, use_case,
 links, contributors, query_type, query_chart, query_history, city)
VALUES
('ev_scooter_charging',
 '{}',
 ARRAY[1001]::integer[],
 NULL,
 'static', 'static',
 1, 'day',
 '臺北市政府',
 '臺北市電動機車充電站各行政區分布統計',
 '整合臺北市開放資料的電動機車充電站位置，依行政區統計充電站密度，協助政府評估充電設施覆蓋率與空白區域。',
 '電動機車充電基礎設施空間評估',
 '["https://data.taipei/dataset/detail?id=759db528-77b5-4aa3-b6fa-2b857890214e"]',
 '["黑客松隊伍"]',
 'two_d',
 'SELECT district AS x_axis, COUNT(*) AS data FROM ev_scooter_charging_tpe WHERE district IS NOT NULL GROUP BY district ORDER BY data DESC',
 NULL,
 'taipei'),

-- 4-2. 電動機車充電站 - 雙北
('ev_scooter_charging',
 '{}',
 ARRAY[1001]::integer[],
 NULL,
 'static', 'static',
 1, 'day',
 '臺北市政府, 新北市政府',
 '雙北電動機車充電站各行政區分布統計',
 '整合臺北市與新北市電動機車充電站開放資料，比較雙北充電設施分布密度。',
 '雙北電動機車充電基礎設施評估',
 '["https://data.taipei/dataset/detail?id=759db528-77b5-4aa3-b6fa-2b857890214e","https://data.ntpc.gov.tw/datasets/1bb694e3-17c7-4ef0-ac75-52990c40edcd"]',
 '["黑客松隊伍"]',
 'two_d',
 'SELECT x_axis, SUM(data) AS data FROM (
    SELECT district AS x_axis, COUNT(*) AS data FROM ev_scooter_charging_tpe WHERE district IS NOT NULL GROUP BY district
    UNION ALL
    SELECT district AS x_axis, COUNT(*) AS data FROM ev_scooter_charging_ntpc WHERE district IS NOT NULL GROUP BY district
 ) combined GROUP BY x_axis ORDER BY data DESC',
 NULL,
 'metrotaipei'),

-- 4-3. 電動汽車充電站 - 臺北
('ev_car_charging',
 '{}',
 ARRAY[1002]::integer[],
 NULL,
 'static', 'static',
 1, 'day',
 '臺北市政府',
 '臺北市電動汽車充電站依充電類型統計',
 '整合臺北市電動汽車充電停車位資料，依AC/DC充電類型分析充電設施組成。',
 '電動汽車充電基礎設施類型分析',
 '["https://data.taipei/dataset/detail?id=dd7001c8-7a87-4294-a52a-e2c14bc49d88"]',
 '["黑客松隊伍"]',
 'two_d',
 'SELECT COALESCE(charger_type, ''未知'') AS x_axis, COUNT(*) AS data FROM ev_car_charging_tpe GROUP BY charger_type ORDER BY data DESC',
 NULL,
 'taipei'),

-- 4-4. 電動汽車充電站 - 雙北
('ev_car_charging',
 '{}',
 ARRAY[1002]::integer[],
 NULL,
 'static', 'static',
 1, 'day',
 '臺北市政府, 新北市政府',
 '雙北電動汽車充電站依充電類型統計',
 '整合雙北電動汽車充電站資料，比較AC/DC充電設施分布。',
 '雙北電動汽車充電基礎設施評估',
 '["https://data.taipei/dataset/detail?id=dd7001c8-7a87-4294-a52a-e2c14bc49d88","https://data.ntpc.gov.tw/datasets/edc3ad26-8ae7-4916-a00b-bc6048d19bf8"]',
 '["黑客松隊伍"]',
 'two_d',
 'SELECT x_axis, SUM(data) AS data FROM (
    SELECT COALESCE(charger_type, ''未知'') AS x_axis, COUNT(*) AS data FROM ev_car_charging_tpe GROUP BY charger_type
    UNION ALL
    SELECT COALESCE(charger_type, ''未知'') AS x_axis, COUNT(*) AS data FROM ev_car_charging_ntpc GROUP BY charger_type
 ) combined GROUP BY x_axis ORDER BY data DESC',
 NULL,
 'metrotaipei'),

-- 4-5. 公車路線地圖 - 臺北
('bus_route_map',
 '{}',
 ARRAY[1003]::integer[],
 NULL,
 'static', 'static',
 1, 'day',
 '臺北市公車路線',
 '臺北市公車路線軌跡地圖',
 '呈現臺北市聯營公車所有路線的地理軌跡，可在地圖上瀏覽路線分布。',
 '公共運輸路線覆蓋率分析',
 '["https://data.taipei/dataset/detail?id=efad90af-4bbe-4c6a-ac60-06f3e52d8a97"]',
 '["黑客松隊伍"]',
 'two_d',
 'SELECT ''臺北公車路線'' AS x_axis, COUNT(*) AS data FROM bus_route_map_tpe',
 NULL,
 'taipei'),

-- 4-6. 公車路線地圖 - 雙北
('bus_route_map',
 '{}',
 ARRAY[1003]::integer[],
 NULL,
 'static', 'static',
 1, 'day',
 '雙北公車路線',
 '雙北公車路線軌跡地圖',
 '整合臺北市與新北市公車路線軌跡，呈現雙北大眾運輸路線全貌。',
 '雙北大眾運輸路網覆蓋評估',
 '["https://data.taipei/dataset/detail?id=efad90af-4bbe-4c6a-ac60-06f3e52d8a97","https://data.ntpc.gov.tw/datasets/07f7ccb3-ed00-43c4-966d-08e9dab24e95"]',
 '["黑客松隊伍"]',
 'two_d',
 'SELECT city AS x_axis, COUNT(*) AS data FROM (
    SELECT ''臺北'' AS city FROM bus_route_map_tpe
    UNION ALL
    SELECT ''新北'' AS city FROM bus_route_map_ntpc
 ) combined GROUP BY city',
 NULL,
 'metrotaipei'),

-- 4-7. 垃圾車路線 - 臺北
('garbage_truck_route',
 '{}',
 ARRAY[1004]::integer[],
 NULL,
 'static', 'static',
 1, 'day',
 '臺北市環保局',
 '臺北市各行政區垃圾車收運路線統計',
 '呈現臺北市垃圾車各行政區路線數量分布，了解廢棄物收運覆蓋情況。',
 '廢棄物收運效率評估',
 '["https://data.taipei/dataset/detail?id=34f4f00b-5386-43ab-bcc7-b0ae7ee3e305"]',
 '["黑客松隊伍"]',
 'two_d',
 'SELECT COALESCE(district, ''未知'') AS x_axis, COUNT(*) AS data FROM garbage_truck_route_tpe GROUP BY district ORDER BY data DESC',
 NULL,
 'taipei'),

-- 4-8. 垃圾車路線 - 雙北
('garbage_truck_route',
 '{}',
 ARRAY[1004]::integer[],
 NULL,
 'static', 'static',
 1, 'day',
 '臺北市環保局, 新北市環保局',
 '雙北各行政區垃圾車收運路線統計',
 '整合雙北垃圾車收運路線，比較各行政區收運資源配置。',
 '雙北廢棄物收運效率對比',
 '["https://data.taipei/dataset/detail?id=34f4f00b-5386-43ab-bcc7-b0ae7ee3e305","https://data.ntpc.gov.tw/datasets/d7330ae1-5869-4ee7-8821-03b1d7d13822"]',
 '["黑客松隊伍"]',
 'two_d',
 'SELECT x_axis, SUM(data) AS data FROM (
    SELECT COALESCE(district, ''未知'') AS x_axis, COUNT(*) AS data FROM garbage_truck_route_tpe GROUP BY district
    UNION ALL
    SELECT COALESCE(district, ''未知'') AS x_axis, COUNT(*) AS data FROM garbage_truck_route_ntpc GROUP BY district
 ) combined GROUP BY x_axis ORDER BY data DESC',
 NULL,
 'metrotaipei');

-- ========================
-- 5. 儀表板設定 (dashboards)
-- ========================
INSERT INTO dashboards (id, name, index, icon, color, is_public, created_at, updated_at, components)
VALUES
(101, '雙北綠色出行', 'green_mobility', 'electric_bolt', '#22c55e', true,
 NOW(), NOW(),
 ARRAY[1001, 1002, 1003, 1004]::integer[])
ON CONFLICT (id) DO NOTHING;
```

> **⚠️ 重要提醒**：
> - `component_maps` 表的 `map_config_id` 欄位名稱需對照現有 schema 確認（可能為 `id`）
> - `query_charts` 的 COPY 格式欄位順序需對照 `dashboardmanager-demo.sql` 確認
> - `dashboards.components` 欄位型態需確認是否為 integer[]（可能是 JSON array）
> - 若使用 COPY 格式插入，需轉換為 INSERT 格式或調整語法

**Step 8.2: 確認現有 schema 欄位（避免 INSERT 欄位錯誤）**

```bash
psql -h localhost -U postgres -d dashboardmanager -c "\d component_maps"
psql -h localhost -U postgres -d dashboardmanager -c "\d query_charts"
psql -h localhost -U postgres -d dashboardmanager -c "\d dashboards"
```

根據輸出結果調整 Step 8.1 的 SQL（欄位名稱、型態、約束）。

**Step 8.3: 執行 DB_MANAGER 插入**
```bash
psql -h localhost -U postgres -d dashboardmanager -f db-sample-data/migrations/green_mobility_manager.sql
```

Expected: INSERT 0 X 各表無 error

**Step 8.4: 驗證插入成功**
```bash
psql -h localhost -U postgres -d dashboardmanager -c "
SELECT index, city FROM query_charts WHERE index IN ('ev_scooter_charging','ev_car_charging','bus_route_map','garbage_truck_route') ORDER BY index, city;
"
```

Expected: 8 rows（每組件 2 rows：taipei + metrotaipei）

**Step 8.5: Commit**
```bash
git add db-sample-data/migrations/green_mobility_manager.sql
git commit -m "feat: register green mobility dashboard components in DB_MANAGER"
```

---

## Task 9：FE 驗證 — 啟動開發伺服器確認儀表板渲染

**Files:**
- Modify: 視實際情況，可能需更新 `docker/.env` 或其他設定

**Step 9.1: 啟動 Docker 服務**

確認 DB 服務正常運行：
```bash
docker-compose -f docker/docker-compose-db.yaml up -d
docker-compose -f docker/docker-compose.yaml up -d
```

**Step 9.2: 啟動 FE 開發伺服器**

```bash
cd Taipei-City-Dashboard-FE
npm install
npm run dev
```

**Step 9.3: 確認儀表板出現**

1. 開啟瀏覽器 `http://localhost:8080`
2. Hold `Shift` + 點擊 TUIC logo → 以帳號密碼登入（admin 帳密在 docker/.env）
3. 在側邊欄確認「雙北綠色出行」儀表板出現

**Step 9.4: 驗證 4 個組件基本渲染**

對每個組件：
1. ✅ 顯示正確標題
2. ✅ 圖表 (DistrictChart/DonutChart/MapLegend) 有資料
3. ✅ 地圖圖層切換按鈕存在
4. ✅ 城市切換下拉選單存在（ev_scooter_charging、ev_car_charging、garbage_truck_route）
5. ✅ 地圖圖層在 toggle 後顯示 GeoJSON 點位/線段

**Step 9.5: 驗證地圖圖層**

對有地圖的組件：
1. 點擊地圖圖層 toggle
2. 確認地圖上出現充電站點位（circle）或公車路線（line）
3. 點擊地圖點位確認 popup 顯示正確欄位

**Step 9.6: 驗證城市切換**

對 ev_scooter_charging 組件：
1. 選擇「臺北市」→ DistrictChart 顯示臺北行政區資料
2. 選擇「雙北」→ DistrictChart 顯示合併雙北行政區資料

**Step 9.7: 修復渲染問題**

若圖表無資料（灰色 loading 狀態）：
- 確認 BE API 可連線：`curl http://localhost:8088/api/v1/component/1001/chart?city=taipei`
- 確認 DB_DASHBOARD 有資料：
  ```bash
  psql -h localhost -U postgres -d dashboard -c "SELECT COUNT(*) FROM ev_scooter_charging_tpe"
  ```
- 若 DB 無資料，先重新執行 Task 7 的本地 ETL 腳本，再執行 DB 載入

**Step 9.8: Final commit**
```bash
git add -A
git commit -m "feat: complete green mobility dashboard - 4 dual-city components with map layers"
```

---

## 競賽門檻確認清單

完成所有 Tasks 後，確認以下競賽要求：

- [ ] ✅ 4 個雙北組件（ev_scooter_charging, ev_car_charging, bus_route_map, garbage_truck_route）
- [ ] ✅ 至少 1 個雙北組件含地圖圖層（ev_scooter_charging 有 circle 地圖；bus_route_map 有 line 地圖）
- [ ] ✅ 所有資料來源為開放資料（data.taipei + data.ntpc.gov.tw）
- [ ] ✅ 城市切換功能（taipei ↔ metrotaipei UNION ALL）
- [ ] ✅ 未套用現有範例組件（全新 index，非複製官方組件）

---

## 故障排除指南

**問題1: GeoJSON 無資料點**
- 原因: API 欄位名稱與腳本中 `r.get()` 不符
- 解法: `curl <API_URL> | python3 -m json.tool | head -20` 查看實際欄位名稱，更新 `run_green_mobility_etl.py`

**問題2: component_maps INSERT 失敗**
- 原因: map_config_id 可能有 unique constraint 或欄位名稱不同
- 解法: `\d component_maps` 確認 schema，調整 INSERT 語法

**問題3: 公車路線 GeoJSON 過大導致地圖卡頓**
- 解法A: 在 ETL 中過濾只保留主要路線（如 direction=0）
- 解法B: 在 Mapbox style 加 `"zoom": [8, 0, 12, 1]` 使低縮放等級不顯示

**問題4: 電動充電站資料無座標**
- 解法: 使用 `geocode_addresses()` 函數對地址進行批次地理編碼（Nominatim），速度 ~1 req/sec
- 替代: 僅顯示行政區級統計（DistrictChart），不在地圖上顯示個別點位
