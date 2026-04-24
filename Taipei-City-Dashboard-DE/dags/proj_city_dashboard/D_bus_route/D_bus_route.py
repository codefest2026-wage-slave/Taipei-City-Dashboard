from airflow import DAG
from operators.common_pipeline import CommonDag


def D_bus_route(**kwargs):
    from proj_city_dashboard.D_bus_route.bus_route_etl import bus_route_etl
    bus_route_etl(**kwargs)


dag = CommonDag(proj_folder="proj_city_dashboard", dag_folder="D_bus_route")
dag.create_dag(etl_func=D_bus_route)
