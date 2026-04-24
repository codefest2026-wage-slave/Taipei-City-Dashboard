from airflow import DAG
from operators.common_pipeline import CommonDag


def D_ev_car_tpe(**kwargs):
    from proj_city_dashboard.D_ev_car_tpe.ev_car_tpe_etl import ev_car_tpe_etl
    ev_car_tpe_etl(**kwargs)


dag = CommonDag(proj_folder="proj_city_dashboard", dag_folder="D_ev_car_tpe")
dag.create_dag(etl_func=D_ev_car_tpe)
