def bus_route_etl(**kwargs):
    """
    ETL for Taipei + New Taipei Bus Route Shapes.
    Fetches WKT LINESTRING data from tcgbusfs, converts to GeoJSON,
    loads route metadata to DB_DASHBOARD.
    """
    import gzip
    import json
    import os
    import pandas as pd
    import requests
    from shapely import wkt as shapely_wkt
    from sqlalchemy import create_engine, text
    from utils.get_time import get_tpe_now_time_str

    ready_data_db_uri = kwargs.get("ready_data_db_uri")
    dag_infos = kwargs.get("dag_infos")
    dag_id = dag_infos.get("dag_id")
    data_time = get_tpe_now_time_str(is_with_tz=True)

    def wkt_to_coords(wkt_str):
        try:
            geom = shapely_wkt.loads(wkt_str)
            return list(geom.coords)
        except Exception:
            return None

    def fetch_and_parse(url, city_label, compressed=False):
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
        content = gzip.decompress(resp.content) if compressed else resp.content
        records = json.loads(content)
        print(f"  {city_label}: {len(records)} shapes fetched")

        features = []
        rows = []
        for r in records:
            # Field names vary; try multiple variants
            geom_wkt = (r.get("Geometry") or r.get("geometry") or
                        r.get("wkt") or r.get("Wkt") or "")
            if not geom_wkt:
                continue
            coords = wkt_to_coords(geom_wkt)
            if not coords or len(coords) < 2:
                continue

            route_uid = r.get("RouteUID") or r.get("routeUID") or r.get("routeUid") or ""
            route_name = r.get("RouteNameZh") or r.get("routeNameZh") or r.get("RouteName") or ""
            direction = int(r.get("Direction") or r.get("direction") or 0)

            features.append({
                "type": "Feature",
                "properties": {
                    "route_uid": route_uid,
                    "route_name": route_name,
                    "direction": direction,
                    "city": city_label,
                },
                "geometry": {"type": "LineString", "coordinates": coords},
            })
            rows.append({
                "route_uid": route_uid,
                "route_name": route_name,
                "direction": direction,
                "data_time": data_time,
            })
        return features, rows

    # Fetch Taipei bus routes (JSON)
    tpe_features, tpe_rows = fetch_and_parse(
        "https://tcgbusfs.blob.core.windows.net/blobbus/TstBusShape.json",
        "taipei", compressed=False
    )
    # Fetch New Taipei bus routes (GZ compressed)
    ntpc_features, ntpc_rows = fetch_and_parse(
        "https://tcgbusfs.blob.core.windows.net/ntpcbus/GetBusShape.gz",
        "newtaipei", compressed=True
    )

    all_features = tpe_features + ntpc_features

    # Export combined GeoJSON for Mapbox
    geojson = {"type": "FeatureCollection", "features": all_features}
    output_dir = os.environ.get(
        "MAPDATA_OUTPUT_DIR",
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..",
                     "Taipei-City-Dashboard-FE", "public", "mapData"),
    )
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, "bus_route_map.geojson")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False)
    print(f"Exported {len(all_features)} bus route features → {out_path}")

    # Load route metadata to DB_DASHBOARD
    engine = create_engine(ready_data_db_uri)
    with engine.connect() as conn:
        conn.execute(text("TRUNCATE TABLE bus_route_map_tpe"))
        conn.execute(text("TRUNCATE TABLE bus_route_map_ntpc"))
        conn.commit()

    if tpe_rows:
        pd.DataFrame(tpe_rows).to_sql("bus_route_map_tpe", engine, if_exists="append", index=False)
    if ntpc_rows:
        pd.DataFrame(ntpc_rows).to_sql("bus_route_map_ntpc", engine, if_exists="append", index=False)

    print(f"Loaded {len(tpe_rows)} TPE routes, {len(ntpc_rows)} NTPC routes to DB")

    from utils.load_stage import update_lasttime_in_data_to_dataset_info
    update_lasttime_in_data_to_dataset_info(engine, dag_id, data_time)
