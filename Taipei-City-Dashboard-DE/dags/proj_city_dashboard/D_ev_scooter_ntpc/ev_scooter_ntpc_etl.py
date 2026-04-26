def ev_scooter_ntpc_etl(**kwargs):
    """ETL for New Taipei City EV Scooter Charging Stations from data.ntpc.gov.tw."""
    import re
    import pandas as pd
    import requests
    from sqlalchemy import create_engine, text
    from utils.get_time import get_tpe_now_time_str

    ready_data_db_uri = kwargs.get("ready_data_db_uri")
    dag_infos = kwargs.get("dag_infos")
    dag_id = dag_infos.get("dag_id")
    default_table = dag_infos.get("ready_data_default_table")

    # Fetch all pages (API default limit is 30)
    API_URL = "https://data.ntpc.gov.tw/api/datasets/1bb694e3-17c7-4ef0-ac75-52990c40edcd/json"
    records = []
    page = 0
    page_size = 100
    while True:
        resp = requests.get(API_URL, params={"size": page_size, "page": page}, timeout=30)
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        records.extend(batch)
        if len(batch) < page_size:
            break
        page += 1
    if not records:
        raise ValueError("No data returned from NTPC EV scooter API")

    df = pd.DataFrame(records)
    print(f"Extracted {len(df)} records from NTPC EV scooter API")
    print(f"Columns: {list(df.columns)}")

    df.columns = [c.lower() for c in df.columns]

    # API fields: sta (name), dis (district), add (address), das (facility type), fee, sty, number
    col_map = {
        "stationname": "name", "站名": "name", "name": "name",
        "sta": "name",
        "address": "address", "地址": "address",
        "add": "address",
        "district": "district", "行政區": "district", "dist": "district",
        "dis": "district",
        "lat": "lat", "latitude": "lat", "緯度": "lat",
        "lng": "lng", "lon": "lng", "longitude": "lng", "經度": "lng",
        "operator": "operator", "業者": "operator",
        "das": "operator",
        "slots": "slots", "充電座數": "slots",
        "number": "slots",
    }
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

    for col in ["name", "address", "district", "lat", "lng", "operator", "slots"]:
        if col not in df.columns:
            df[col] = None

    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lng"] = pd.to_numeric(df["lng"], errors="coerce")
    df["slots"] = pd.to_numeric(df["slots"], errors="coerce").fillna(0).astype(int)

    if df["district"].isna().all() and "address" in df.columns:
        def extract_district(addr):
            m = re.search(r"[一-鿿]{2}區", str(addr))
            return m.group(0) if m else None
        df["district"] = df["address"].apply(extract_district)

    # Geocode rows missing coordinates using ArcGIS World Geocoder
    null_mask = df["lat"].isna() | df["lng"].isna()
    if null_mask.any():
        print(f"  Geocoding {null_mask.sum()} records missing coordinates...")
        _geocode_cache = {}

        def _geocode_address(addr):
            addr = re.sub(r"\d+~?\d*樓.*$", "", str(addr or "")).strip()
            if not addr:
                return None
            if addr in _geocode_cache:
                return _geocode_cache[addr]
            try:
                r = requests.get(
                    "https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates",
                    params={"SingleLine": addr, "f": "json", "outSR": '{"wkid":4326}', "maxLocations": 1},
                    timeout=10,
                )
                r.raise_for_status()
                cands = r.json().get("candidates", [])
                if cands and cands[0].get("score", 0) >= 80:
                    loc = cands[0]["location"]
                    result = (loc["x"], loc["y"])
                    _geocode_cache[addr] = result
                    return result
            except Exception:
                pass
            _geocode_cache[addr] = None
            return None

        for idx in df[null_mask].index:
            coords = _geocode_address(df.at[idx, "address"] or "")
            if coords:
                df.at[idx, "lng"] = coords[0]
                df.at[idx, "lat"] = coords[1]
        geocoded = null_mask.sum() - (df["lat"].isna() | df["lng"].isna()).sum()
        print(f"  Geocoded {geocoded}/{null_mask.sum()} records successfully")

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
