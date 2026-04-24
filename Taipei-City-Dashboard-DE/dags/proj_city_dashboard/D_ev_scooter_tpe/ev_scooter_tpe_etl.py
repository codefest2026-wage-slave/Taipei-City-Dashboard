def ev_scooter_tpe_etl(**kwargs):
    """ETL for Taipei EV Scooter Charging Stations from data.taipei."""
    import re
    import pandas as pd
    import requests
    from sqlalchemy import create_engine, text
    from utils.get_time import get_tpe_now_time_str

    ready_data_db_uri = kwargs.get("ready_data_db_uri")
    dag_infos = kwargs.get("dag_infos")
    dag_id = dag_infos.get("dag_id")
    default_table = dag_infos.get("ready_data_default_table")

    # data.taipei v1 API — returns {"result": {"results": [...]}}
    API_URL = "https://data.taipei/api/v1/dataset/759db528-77b5-4aa3-b6fa-2b857890214e?scope=resourceAquire"
    resp = requests.get(API_URL, timeout=30)
    resp.raise_for_status()
    raw = resp.json()
    records = raw.get("result", {}).get("results", [])
    if not records:
        raise ValueError("No data returned from Taipei EV scooter API")

    df = pd.DataFrame(records)
    print(f"Extracted {len(df)} records from Taipei EV scooter API")
    print(f"Columns: {list(df.columns)}")

    # Normalize column names to lowercase
    df.columns = [c.lower() for c in df.columns]

    # Map common field name variants to standard names
    col_map = {
        "stationname": "name", "站名": "name", "name": "name",
        "address": "address", "地址": "address",
        "district": "district", "行政區": "district", "dist": "district",
        "lat": "lat", "latitude": "lat", "緯度": "lat",
        "lng": "lng", "lon": "lng", "longitude": "lng", "經度": "lng",
        "operator": "operator", "業者": "operator",
        "chargeslot": "slots", "slots": "slots", "充電座數": "slots",
    }
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

    for col in ["name", "address", "district", "lat", "lng", "operator", "slots"]:
        if col not in df.columns:
            df[col] = None

    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lng"] = pd.to_numeric(df["lng"], errors="coerce")
    df["slots"] = pd.to_numeric(df["slots"], errors="coerce").fillna(0).astype(int)

    # Extract district from address if not present
    if df["district"].isna().all() and "address" in df.columns:
        def extract_district(addr):
            m = re.search(r"[\u4e00-\u9fff]{2}區", str(addr))
            return m.group(0) if m else None
        df["district"] = df["address"].apply(extract_district)

    df["data_time"] = get_tpe_now_time_str(is_with_tz=True)

    final_cols = ["name", "address", "district", "lat", "lng", "operator", "slots", "data_time"]
    ready = df[final_cols].copy()

    engine = create_engine(ready_data_db_uri)
    with engine.connect() as conn:
        conn.execute(text(f"TRUNCATE TABLE {default_table}"))
        conn.commit()
    ready.to_sql(default_table, engine, if_exists="append", index=False)
    print(f"Loaded {len(ready)} records to {default_table}")

    from utils.load_stage import update_lasttime_in_data_to_dataset_info
    update_lasttime_in_data_to_dataset_info(engine, dag_id, ready["data_time"].max())
