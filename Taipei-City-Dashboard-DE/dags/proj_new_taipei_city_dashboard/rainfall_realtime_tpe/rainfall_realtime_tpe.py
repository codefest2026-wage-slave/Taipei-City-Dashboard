# SPDX-License-Identifier: AGPL-3.0-or-later
from airflow import DAG
from operators.common_pipeline import CommonDag


def _transfer(**kwargs):
    """
    ETL pipeline for Taipei City real-time rainfall station data.

    Data source: 臺北市水利處雨量站即時資料
    Dataset page: https://data.taipei/dataset/detail?id=6f03a0b8-7b98-4eea-8bb9-ba6bfcdc2b8b
    Actual API:  https://wic.gov.taipei/OpenData/API/Rain/Get
    loginId/dataKey from resource rid: 6695350f-faac-4f0d-a53d-95d223bf43e5
    Update frequency: 10 minutes

    Actual JSON schema (verified 2026-04-24):
    {
        "count": 42,
        "data": [
            {
                "stationNo": "001",
                "stationName": "湖田國小",
                "recTime": "202604242216",   -- YYYYMMDDHHmm
                "rain": 15.0                 -- daily cumulative rainfall (mm)
            },
            ...
        ]
    }
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
    # 臺北市水利處雨量站即時資料（wic.gov.taipei）
    # dataset page: https://data.taipei/dataset/detail?id=6f03a0b8-7b98-4eea-8bb9-ba6bfcdc2b8b
    URL = "https://wic.gov.taipei/OpenData/API/Rain/Get?stationNo=&loginId=open_rain&dataKey=85452C1D"
    resp = requests.get(URL, timeout=30)
    resp.raise_for_status()
    payload = resp.json()

    # Response: {"count": N, "data": [{"stationNo", "stationName", "recTime", "rain"}, ...]}
    raw = payload.get("data", [])
    if not raw:
        raise ValueError(f"API returned empty data. Full response keys: {list(payload.keys())}")

    df = pd.DataFrame(raw)

    # --- Transform ---
    col_map = {
        "stationNo":   "station_id",
        "stationName": "station_name",
        "rain":        "rainfall_today",  # daily cumulative (mm)
        "recTime":     "rec_time",
    }
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

    # 雨量站無經緯度欄位，需用站碼對應靜態座標表（或暫填 None 留給 geocoding）
    # 此處先設為 None，待有座標資料時補充
    df["lng"] = None
    df["lat"] = None
    df["district"] = None
    df["rainfall_10min"] = 0.0  # 此 API 不提供 10min 值，填 0
    df["rainfall_today"] = pd.to_numeric(df.get("rainfall_today", 0), errors="coerce").fillna(0)

    df = df.dropna(subset=["station_id"])
    df["data_time"] = get_tpe_now_time_str(is_with_tz=True)

    # wkb_geometry 僅在有座標時建立；若為 None 則 geometry 為空
    df_with_coord = df.dropna(subset=["lng", "lat"])
    df_no_coord = df[df["lng"].isna() | df["lat"].isna()].copy()

    if not df_with_coord.empty:
        gdata = add_point_wkbgeometry_column_to_df(
            df_with_coord, df_with_coord["lng"], df_with_coord["lat"], from_crs=4326
        )
    else:
        # 無座標時，建立空 geometry column
        import geopandas as gpd
        from shapely.geometry import Point
        df["wkb_geometry"] = None
        gdata = gpd.GeoDataFrame(df, geometry="wkb_geometry", crs=4326)

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
