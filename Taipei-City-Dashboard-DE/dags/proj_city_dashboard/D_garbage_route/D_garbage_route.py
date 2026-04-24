from airflow import DAG
from operators.common_pipeline import CommonDag


def D_garbage_route(**kwargs):
    from proj_city_dashboard.D_garbage_route.garbage_route_etl import garbage_route_etl
    garbage_route_etl(**kwargs)


dag = CommonDag(proj_folder="proj_city_dashboard", dag_folder="D_garbage_route")
dag.create_dag(etl_func=D_garbage_route)
