def garbage_route_etl(**kwargs):
    """
    ETL for Taipei + New Taipei Garbage Truck Routes.
    New Taipei: data.ntpc JSON API (includes GPS coordinates)
    Taipei: data.taipei API (route metadata only, no GPS)
    """
    import json
    import os
    import pandas as pd
    import requests
    from sqlalchemy import create_engine, text
    from utils.get_time import get_tpe_now_time_str

    ready_data_db_uri = kwargs.get("ready_data_db_uri")
    dag_infos = kwargs.get("dag_infos")
    dag_id = dag_infos.get("dag_id")
    data_time = get_tpe_now_time_str(is_with_tz=True)
    engine = create_engine(ready_data_db_uri)

    # --- New Taipei (has GPS coordinates) ---
    NTPC_API = "https://data.ntpc.gov.tw/api/datasets/d7330ae1-5869-4ee7-8821-03b1d7d13822/json"
    resp_ntpc = requests.get(NTPC_API, timeout=30)
    resp_ntpc.raise_for_status()
    ntpc_records = resp_ntpc.json()
    print(f"NTPC garbage: {len(ntpc_records)} records")

    ntpc_df = pd.DataFrame(ntpc_records)
    ntpc_df.columns = [c.lower() for c in ntpc_df.columns]

    ntpc_col_map = {
        "routecode": "route_code", "路線代碼": "route_code",
        "district": "district", "行政區": "district",
        "routename": "route_name", "路線名": "route_name",
        "weekday": "weekday", "星期": "weekday",
        "vehicleno": "vehicle_no", "車號": "vehicle_no",
        "lat": "lat", "latitude": "lat", "緯度": "lat",
        "lng": "lng", "lon": "lng", "longitude": "lng", "經度": "lng",
    }
    ntpc_df = ntpc_df.rename(columns={k: v for k, v in ntpc_col_map.items() if k in ntpc_df.columns})

    for col in ["route_code", "district", "route_name", "weekday", "vehicle_no", "lat", "lng"]:
        if col not in ntpc_df.columns:
            ntpc_df[col] = None

    ntpc_df["lat"] = pd.to_numeric(ntpc_df["lat"], errors="coerce")
    ntpc_df["lng"] = pd.to_numeric(ntpc_df["lng"], errors="coerce")
    ntpc_df["data_time"] = data_time

    final_ntpc = ["route_code", "district", "route_name", "weekday", "vehicle_no", "lat", "lng", "data_time"]
    ntpc_ready = ntpc_df[[c for c in final_ntpc if c in ntpc_df.columns]].copy()

    with engine.connect() as conn:
        conn.execute(text("TRUNCATE TABLE garbage_truck_route_ntpc"))
        conn.commit()
    ntpc_ready.to_sql("garbage_truck_route_ntpc", engine, if_exists="append", index=False)
    print(f"Loaded {len(ntpc_ready)} NTPC garbage routes to DB")

    # --- Taipei (no GPS in this dataset) ---
    TPE_API = "https://data.taipei/api/v1/dataset/34f4f00b-5386-43ab-bcc7-b0ae7ee3e305?scope=resourceAquire"
    try:
        resp_tpe = requests.get(TPE_API, timeout=30)
        resp_tpe.raise_for_status()
        tpe_records = resp_tpe.json().get("result", {}).get("results", [])
    except Exception as e:
        print(f"Taipei garbage API failed ({e}), skipping")
        tpe_records = []

    if tpe_records:
        tpe_df = pd.DataFrame(tpe_records)
        tpe_df.columns = [c.lower() for c in tpe_df.columns]
        tpe_col_map = {
            "routecode": "route_code", "路線代碼": "route_code",
            "district": "district", "行政區": "district",
            "routename": "route_name", "路線名": "route_name",
            "weekday": "weekday", "星期": "weekday",
            "vehicleno": "vehicle_no", "車號": "vehicle_no",
        }
        tpe_df = tpe_df.rename(columns={k: v for k, v in tpe_col_map.items() if k in tpe_df.columns})
        for col in ["route_code", "district", "route_name", "weekday", "vehicle_no"]:
            if col not in tpe_df.columns:
                tpe_df[col] = None
        tpe_df["data_time"] = data_time
        final_tpe = ["route_code", "district", "route_name", "weekday", "vehicle_no", "data_time"]
        tpe_ready = tpe_df[[c for c in final_tpe if c in tpe_df.columns]].copy()

        with engine.connect() as conn:
            conn.execute(text("TRUNCATE TABLE garbage_truck_route_tpe"))
            conn.commit()
        tpe_ready.to_sql("garbage_truck_route_tpe", engine, if_exists="append", index=False)
        print(f"Loaded {len(tpe_ready)} TPE garbage routes to DB")

    # Export GeoJSON from NTPC data (has GPS)
    ntpc_with_coords = ntpc_ready[ntpc_ready["lat"].notna() & ntpc_ready["lng"].notna()]
    features = [
        {
            "type": "Feature",
            "properties": {
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
    geojson = {"type": "FeatureCollection", "features": features}
    output_dir = os.environ.get(
        "MAPDATA_OUTPUT_DIR",
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..",
                     "Taipei-City-Dashboard-FE", "public", "mapData"),
    )
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, "garbage_truck_route.geojson")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False)
    print(f"Exported {len(features)} garbage truck features → {out_path}")

    from utils.load_stage import update_lasttime_in_data_to_dataset_info
    update_lasttime_in_data_to_dataset_info(engine, dag_id, data_time)
