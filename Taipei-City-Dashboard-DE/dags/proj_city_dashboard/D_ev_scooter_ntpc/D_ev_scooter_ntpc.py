from airflow import DAG
from operators.common_pipeline import CommonDag


def D_ev_scooter_ntpc(**kwargs):
    from proj_city_dashboard.D_ev_scooter_ntpc.ev_scooter_ntpc_etl import ev_scooter_ntpc_etl
    ev_scooter_ntpc_etl(**kwargs)


dag = CommonDag(proj_folder="proj_city_dashboard", dag_folder="D_ev_scooter_ntpc")
dag.create_dag(etl_func=D_ev_scooter_ntpc)
