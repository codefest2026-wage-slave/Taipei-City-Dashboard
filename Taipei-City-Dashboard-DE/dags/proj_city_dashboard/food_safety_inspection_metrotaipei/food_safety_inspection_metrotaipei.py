from airflow import DAG
from operators.common_pipeline import CommonDag


def _food_safety_inspection_metrotaipei(**kwargs):
    import pandas as pd
    from sqlalchemy import create_engine
    from settings.global_config import DAG_PATH
    from utils.load_stage import (
        save_dataframe_to_postgresql,
        update_lasttime_in_data_to_dataset_info,
    )
    from utils.transform_time import convert_str_to_time_format
    from utils.get_time import get_tpe_now_time_str

    # Config
    ready_data_db_uri = kwargs.get("ready_data_db_uri")
    dag_infos = kwargs.get("dag_infos")
    dag_id = dag_infos.get("dag_id")
    load_behavior = dag_infos.get("load_behavior")
    default_table = dag_infos.get("ready_data_default_table")
    history_table = dag_infos.get("ready_data_history_table")

    DAG_FOLDER = f"{DAG_PATH}/proj_city_dashboard/food_safety_inspection_metrotaipei"
    SOURCES = [
        ("個人農場", f"{DAG_FOLDER}/食品查核及檢驗資訊平台2026-05-02_台北新北_個人農場_v2.csv"),
        ("商業業者", f"{DAG_FOLDER}/食品查核及檢驗資訊平台2026-05-02_台北新北_商業業者_v2.csv"),
    ]

    # Extract — read both CSVs and tag with business_type
    frames = []
    for business_type, path in SOURCES:
        df = pd.read_csv(path, encoding="utf-8")
        df["business_type"] = business_type
        frames.append(df)
    raw_data = pd.concat(frames, ignore_index=True)

    # Transform — rename to snake_case English columns
    data = raw_data.rename(columns={
        "項次": "source_id",
        "業者名稱(市招)": "business_name",
        "業者地址": "address",
        "產品名稱": "product_name",
        "稽查日期": "inspection_date",
        "稽查/檢驗項目": "inspection_item",
        "稽查/檢驗結果": "inspection_result",
        "違反之食安法條及相關法": "violated_law_raw",
        "裁罰金額": "fine_amount",
        "備註": "note",
        "違反之食安法條及相關法_標準化": "violated_law_standardized",
        "危害等級": "hazard_level",
        "危害判斷依據": "hazard_basis",
    })

    # Strip whitespace on string columns
    str_cols = [
        "business_name", "address", "product_name",
        "inspection_item", "inspection_result",
        "violated_law_raw", "note",
        "violated_law_standardized", "hazard_level", "hazard_basis",
    ]
    for c in str_cols:
        data[c] = data[c].astype("string").str.strip()

    # Normalize 台北市 → 臺北市 so city/district extraction is consistent
    data["address"] = data["address"].str.replace("台北市", "臺北市", regex=False)

    # Derive city / district from leading address chars (e.g. 臺北市中山區...)
    addr = data["address"].fillna("")
    head3 = addr.str[:3]
    data["city"] = head3.where(head3.isin(["臺北市", "新北市"]))
    data["district"] = addr.where(data["city"].notna()).str[3:6]

    # Convert ROC date (e.g. 110/11/2) to AD date; invalid → NaT
    data["inspection_date"] = convert_str_to_time_format(
        data["inspection_date"].astype("string"),
        from_format="%TY/%m/%d",
        output_level="date",
        errors="coerce",
    )

    # Numeric coercion
    data["source_id"] = pd.to_numeric(data["source_id"], errors="coerce").astype("Int64")
    data["fine_amount"] = pd.to_numeric(data["fine_amount"], errors="coerce")

    data["data_time"] = get_tpe_now_time_str(is_with_tz=True)

    # Final column order
    ready_data = data[[
        "data_time",
        "business_type",
        "source_id",
        "business_name",
        "address",
        "city",
        "district",
        "product_name",
        "inspection_date",
        "inspection_item",
        "inspection_result",
        "violated_law_raw",
        "fine_amount",
        "note",
        "violated_law_standardized",
        "hazard_level",
        "hazard_basis",
    ]]

    # Load
    engine = create_engine(ready_data_db_uri)
    save_dataframe_to_postgresql(
        engine,
        data=ready_data,
        load_behavior=load_behavior,
        default_table=default_table,
        history_table=history_table,
    )
    update_lasttime_in_data_to_dataset_info(engine, dag_id, get_tpe_now_time_str())


dag = CommonDag(
    proj_folder="proj_city_dashboard",
    dag_folder="food_safety_inspection_metrotaipei",
)
dag.create_dag(etl_func=_food_safety_inspection_metrotaipei)
