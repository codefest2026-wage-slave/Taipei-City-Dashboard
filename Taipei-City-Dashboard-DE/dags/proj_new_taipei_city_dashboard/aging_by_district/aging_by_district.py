# SPDX-License-Identifier: AGPL-3.0-or-later
from airflow import DAG
from operators.common_pipeline import CommonDag


def _transfer(**kwargs):
    import re
    import pandas as pd
    from sqlalchemy import create_engine
    from utils.extract_stage import NewTaipeiAPIClient
    from utils.load_stage import (
        save_dataframe_to_postgresql,
        update_lasttime_in_data_to_dataset_info,
    )
    from utils.get_time import get_tpe_now_time_str

    # Config
    ready_data_db_uri = kwargs.get("ready_data_db_uri")
    dag_infos = kwargs.get("dag_infos")
    dag_id = dag_infos.get("dag_id")
    load_behavior = dag_infos.get("load_behavior")
    default_table = dag_infos.get("ready_data_default_table")
    history_table = dag_infos.get("ready_data_history_table")

    # Extract
    # 與 dependency_ratio_and_aging_index 使用同一個 RID，但取行政區細分資料
    RID = "8308ab58-62d1-424e-8314-24b65b7ab492"
    client = NewTaipeiAPIClient(RID, input_format="json")
    res = client.get_all_data(size=1000)
    raw_data = pd.DataFrame(res)

    # Transform
    # field1 格式範例：「2024年 板橋區0 計」（行政區）、「2024年 新北市0 計」（全市總計）
    # 只保留行政區資料（男+女合計「計」），排除全市總計「新北市」
    pattern = re.compile(r"^(\d{4})年 (.+?)0 計$")
    parsed = []
    for _, row in raw_data.iterrows():
        m = pattern.match(str(row.get("field1", "")))
        if not m:
            continue
        year = int(m.group(1))
        district = m.group(2).strip()
        if district == "新北市":  # 排除全市總計
            continue
        parsed.append({
            "year": year,
            "district": district,
            "city": "新北市",
            # 欄位名稱與 dependency_ratio_and_aging_index_new_tpe 保持一致，方便對照
            "young_population": pd.to_numeric(row.get("percent24"), errors="coerce"),
            "young_population_pct": pd.to_numeric(row.get("percent25"), errors="coerce"),
            "working_age_population": pd.to_numeric(row.get("percent26"), errors="coerce"),
            "working_age_population_pct": pd.to_numeric(row.get("percent27"), errors="coerce"),
            "elderly_population": pd.to_numeric(row.get("percent28"), errors="coerce"),
            "elderly_population_pct": pd.to_numeric(row.get("percent29"), errors="coerce"),
            "elderly_dependency_ratio": pd.to_numeric(row.get("percent30"), errors="coerce"),
            "youth_dependency_ratio": pd.to_numeric(row.get("percent31"), errors="coerce"),
            "total_dependency_ratio": pd.to_numeric(row.get("percent32"), errors="coerce"),
            "aging_index": pd.to_numeric(row.get("percent33"), errors="coerce"),
        })

    data = pd.DataFrame(parsed)
    data["data_time"] = get_tpe_now_time_str(is_with_tz=True)

    # Load
    engine = create_engine(ready_data_db_uri)
    save_dataframe_to_postgresql(
        engine,
        data=data,
        load_behavior=load_behavior,
        default_table=default_table,
        history_table=history_table,
    )
    update_lasttime_in_data_to_dataset_info(engine, dag_id, data["data_time"].max())


dag = CommonDag(
    proj_folder="proj_new_taipei_city_dashboard",
    dag_folder="aging_by_district"
)
dag.create_dag(etl_func=_transfer)
