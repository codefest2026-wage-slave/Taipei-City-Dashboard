-- =============================================================
-- Local test seed: 韌性防災 disaster prevention mock tables
-- Usage: loaded BEFORE dashboardmanager-demo.sql in local test only
-- Creates minimal schemas + sample rows for SQL validation
-- =============================================================

-- Enable PostGIS
CREATE EXTENSION IF NOT EXISTS postgis;

-- ── Manager DB schema (normally created by GORM AutoMigrate) ─
CREATE TABLE IF NOT EXISTS public.components (
    id    serial PRIMARY KEY,
    index varchar UNIQUE NOT NULL,
    name  varchar NOT NULL
);

CREATE TABLE IF NOT EXISTS public.component_charts (
    index varchar PRIMARY KEY,
    color text[],
    types text[],
    unit  varchar
);

CREATE TABLE IF NOT EXISTS public.component_maps (
    id       serial PRIMARY KEY,
    index    varchar NOT NULL,
    title    varchar NOT NULL,
    type     varchar NOT NULL,
    source   varchar NOT NULL,
    size     varchar,
    icon     varchar,
    paint    json,
    property json
);

CREATE TABLE IF NOT EXISTS public.query_charts (
    index            varchar,
    city             text,
    query_type       varchar,
    query_chart      text,
    query_history    text,
    map_config_ids   integer[],
    history_config   json,
    map_filter       json,
    time_from        varchar,
    time_to          varchar,
    update_freq      integer,
    update_freq_unit varchar,
    source           varchar,
    short_desc       text,
    long_desc        text,
    use_case         text,
    links            text[],
    contributors     text[],
    created_at       timestamptz NOT NULL DEFAULT NOW(),
    updated_at       timestamptz NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.dashboards (
    id         serial PRIMARY KEY,
    index      varchar UNIQUE NOT NULL,
    name       varchar NOT NULL,
    components int[],
    icon       varchar,
    updated_at timestamptz NOT NULL DEFAULT NOW(),
    created_at timestamptz NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.groups (
    id           serial PRIMARY KEY,
    name         varchar,
    dashboard_id integer,
    color        varchar,
    icon         varchar,
    order_id     integer
);
CREATE EXTENSION IF NOT EXISTS postgis;

-- ── rainfall_flood_simulation_etl_ntpe (新北市淹水潛勢) ──────
CREATE TABLE IF NOT EXISTS public.rainfall_flood_simulation_etl_ntpe (
    id          serial PRIMARY KEY,
    gridcode    int,
    category    text,
    type        text,
    area        float,
    city        text,
    wkb_geometry geometry(MultiPolygon, 4326),
    data_time   timestamptz DEFAULT NOW()
);
INSERT INTO public.rainfall_flood_simulation_etl_ntpe (gridcode, category, type, area, city, wkb_geometry)
VALUES
    (1, '一般', 'flood', 1200000, '新北市', ST_GeomFromText('MULTIPOLYGON(((121.4 24.9, 121.5 24.9, 121.5 25.0, 121.4 25.0, 121.4 24.9)))', 4326)),
    (2, '一般', 'flood', 800000,  '新北市', ST_GeomFromText('MULTIPOLYGON(((121.5 24.9, 121.6 24.9, 121.6 25.0, 121.5 25.0, 121.5 24.9)))', 4326)),
    (3, '高',   'flood', 500000,  '新北市', ST_GeomFromText('MULTIPOLYGON(((121.6 24.9, 121.7 24.9, 121.7 25.0, 121.6 25.0, 121.6 24.9)))', 4326)),
    (4, '高',   'flood', 200000,  '新北市', ST_GeomFromText('MULTIPOLYGON(((121.7 24.9, 121.8 24.9, 121.8 25.0, 121.7 25.0, 121.7 24.9)))', 4326)),
    (5, '極高', 'flood', 50000,   '新北市', ST_GeomFromText('MULTIPOLYGON(((121.8 24.9, 121.9 24.9, 121.9 25.0, 121.8 25.0, 121.8 24.9)))', 4326));

-- ── rainfall_flood_simulation_etl_tpe (臺北市淹水潛勢) ──────
CREATE TABLE IF NOT EXISTS public.rainfall_flood_simulation_etl_tpe (
    id          serial PRIMARY KEY,
    gridcode    int,
    category    text,
    type        text,
    area        float,
    city        text,
    wkb_geometry geometry(MultiPolygon, 4326),
    data_time   timestamptz DEFAULT NOW()
);
INSERT INTO public.rainfall_flood_simulation_etl_tpe (gridcode, category, type, area, city, wkb_geometry)
VALUES
    (1, '一般', 'flood', 900000, '臺北市', ST_GeomFromText('MULTIPOLYGON(((121.5 25.0, 121.6 25.0, 121.6 25.1, 121.5 25.1, 121.5 25.0)))', 4326)),
    (2, '一般', 'flood', 600000, '臺北市', ST_GeomFromText('MULTIPOLYGON(((121.6 25.0, 121.7 25.0, 121.7 25.1, 121.6 25.1, 121.6 25.0)))', 4326)),
    (3, '高',   'flood', 300000, '臺北市', ST_GeomFromText('MULTIPOLYGON(((121.7 25.0, 121.8 25.0, 121.8 25.1, 121.7 25.1, 121.7 25.0)))', 4326));

-- ── urbn_air_raid_shelter_ntpe (新北市防空避難所) ────────────
CREATE TABLE IF NOT EXISTS public.urbn_air_raid_shelter_ntpe (
    id              serial PRIMARY KEY,
    data_time       timestamptz DEFAULT NOW(),
    town            text,
    person_capacity text,
    address         text,
    lng             float,
    lat             float,
    wkb_geometry    geometry(Point, 4326)
);
INSERT INTO public.urbn_air_raid_shelter_ntpe (town, person_capacity, address, lng, lat, wkb_geometry)
VALUES
    ('板橋區', '500', '新北市板橋區中山路1號', 121.460, 25.014, ST_SetSRID(ST_MakePoint(121.460, 25.014), 4326)),
    ('板橋區', '300', '新北市板橋區文化路2號', 121.462, 25.016, ST_SetSRID(ST_MakePoint(121.462, 25.016), 4326)),
    ('三重區', '800', '新北市三重區重新路3號', 121.492, 25.063, ST_SetSRID(ST_MakePoint(121.492, 25.063), 4326)),
    ('新莊區', '400', '新北市新莊區中正路4號', 121.445, 25.035, ST_SetSRID(ST_MakePoint(121.445, 25.035), 4326));

-- ── urbn_air_raid_shelter (臺北市防空避難所, D020105) ────────
CREATE TABLE IF NOT EXISTS public.urbn_air_raid_shelter (
    id              serial PRIMARY KEY,
    data_time       timestamptz DEFAULT NOW(),
    town            text,
    address         text,
    area            float,
    person_capacity numeric,
    is_accessible   boolean,
    lng             float,
    lat             float,
    wkb_geometry    geometry(Point, 4326)
);
INSERT INTO public.urbn_air_raid_shelter (town, address, area, person_capacity, is_accessible, lng, lat, wkb_geometry)
VALUES
    ('中正區', '臺北市中正區重慶南路1號', 1200, 600, true,  121.513, 25.046, ST_SetSRID(ST_MakePoint(121.513, 25.046), 4326)),
    ('中正區', '臺北市中正區愛國西路100號', 800, 400, false, 121.510, 25.042, ST_SetSRID(ST_MakePoint(121.510, 25.042), 4326)),
    ('大安區', '臺北市大安區羅斯福路2號', 900, 450, true,  121.532, 25.025, ST_SetSRID(ST_MakePoint(121.532, 25.025), 4326)),
    ('信義區', '臺北市信義區信義路5號',   1500, 750, true,  121.566, 25.033, ST_SetSRID(ST_MakePoint(121.566, 25.033), 4326));

-- ── rainfall_realtime_tpe (臺北市即時雨量站) ─────────────────
CREATE TABLE IF NOT EXISTS public.rainfall_realtime_tpe (
    id              serial PRIMARY KEY,
    station_id      text,
    station_name    text,
    district        text,
    rainfall_10min  float,
    rainfall_today  float,
    lng             float,
    lat             float,
    wkb_geometry    geometry(Point, 4326),
    data_time       timestamptz DEFAULT NOW()
);
INSERT INTO public.rainfall_realtime_tpe (station_id, station_name, district, rainfall_10min, rainfall_today, lng, lat, wkb_geometry)
VALUES
    ('01', '中正站',  '中正區', 2.5,  35.0, 121.513, 25.046, ST_SetSRID(ST_MakePoint(121.513, 25.046), 4326)),
    ('02', '大安站',  '大安區', 3.0,  42.5, 121.532, 25.025, ST_SetSRID(ST_MakePoint(121.532, 25.025), 4326)),
    ('03', '信義站',  '信義區', 1.5,  28.0, 121.566, 25.033, ST_SetSRID(ST_MakePoint(121.566, 25.033), 4326)),
    ('04', '松山站',  '松山區', 4.0,  55.0, 121.577, 25.050, ST_SetSRID(ST_MakePoint(121.577, 25.050), 4326)),
    ('05', '內湖站',  '內湖區', 0.5,  12.0, 121.587, 25.075, ST_SetSRID(ST_MakePoint(121.587, 25.075), 4326));
