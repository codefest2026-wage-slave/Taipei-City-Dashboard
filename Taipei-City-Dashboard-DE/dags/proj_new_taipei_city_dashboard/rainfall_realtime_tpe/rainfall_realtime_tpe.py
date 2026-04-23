# SPDX-License-Identifier: AGPL-3.0-or-later
from airflow import DAG
from operators.common_pipeline import CommonDag


def _transfer(**kwargs):
    """
    ETL pipeline for Taipei City real-time rainfall station data.

    Data source: Taipei City Open Data Platform (data.taipei)
    Dataset: 臺北市雨量站即時資料
    RID: a664fdca-62be-48f6-9b4e-5b2e7dd13a91
    Update frequency: 10 minutes

    Expected JSON schema:
    [
        {
            "StationID": "1",
            "StationName": "文山",
            "District": "文山區",
            "Longitude": "121.5547",
            "Latitude": "25.0008",
            "Now": "0.0",      -- 10-min rainfall (mm)
            "Today": "12.5"    -- cumulative daily rainfall (mm)
        },
        ...
    ]
    """
    import pandas as pd
    import requests
    from sqlalchemy import create_engine
    from utils.load_stage import (
        save_geodataframe_to_postgresql,
        update_lasttime_in_data_to_dataset_info,
    )
    from utils.transform_geometry import add_point_wkbgeometry_column_to_df
    from utils.get_time import get_tpe_now_time_str

    ready_data_db_uri = kwargs.get("ready_data_db_uri")
    dag_infos = kwargs.get("dag_infos")
    dag_id = dag_infos.get("dag_id")
    load_behavior = dag_infos.get("load_behavior")
    default_table = dag_infos.get("ready_data_default_table")
    history_table = dag_infos.get("ready_data_history_table")

    # --- Extract ---
    # Primary: data.taipei open data API
    RID = "a664fdca-62be-48f6-9b4e-5b2e7dd13a91"
    URL = f"https://data.taipei/api/v1/dataset/{RID}/resource/{RID}/download?limit=1000&offset=0"
    resp = requests.get(URL, timeout=30)
    resp.raise_for_status()
    payload = resp.json()

    # data.taipei wraps response in {"result": {"results": [...]}}
    if isinstance(payload, dict) and "result" in payload:
        raw = payload["result"].get("results", payload["result"])
    elif isinstance(payload, list):
        raw = payload
    else:
        raw = payload

    df = pd.DataFrame(raw)

    # --- Transform ---
    col_map = {
        "StationID":   "station_id",
        "StationName": "station_name",
        "District":    "district",
        "Longitude":   "lng",
        "Latitude":    "lat",
        "Now":         "rainfall_10min",
        "Today":       "rainfall_today",
    }
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

    required = ["station_id", "station_name", "lng", "lat"]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Column '{col}' not found in API response. "
                             f"Available columns: {list(df.columns)}")

    df["lng"] = pd.to_numeric(df["lng"], errors="coerce")
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["rainfall_10min"] = pd.to_numeric(df.get("rainfall_10min", 0), errors="coerce").fillna(0)
    df["rainfall_today"] = pd.to_numeric(df.get("rainfall_today", 0), errors="coerce").fillna(0)
    if "district" not in df.columns:
        df["district"] = None

    df = df.dropna(subset=["lng", "lat"])
    df["data_time"] = get_tpe_now_time_str(is_with_tz=True)

    gdata = add_point_wkbgeometry_column_to_df(df, df["lng"], df["lat"], from_crs=4326)
    ready_data = gdata[[
        "station_id", "station_name", "district",
        "rainfall_10min", "rainfall_today",
        "lng", "lat", "wkb_geometry", "data_time",
    ]]

    # --- Load ---
    engine = create_engine(ready_data_db_uri)
    save_geodataframe_to_postgresql(
        engine,
        gdata=ready_data,
        load_behavior=load_behavior,
        default_table=default_table,
        history_table=history_table,
        geometry_type="Point",
    )
    update_lasttime_in_data_to_dataset_info(engine, dag_id, ready_data["data_time"].max())


dag = CommonDag(
    proj_folder="proj_new_taipei_city_dashboard",
    dag_folder="rainfall_realtime_tpe",
)
dag.create_dag(etl_func=_transfer)
