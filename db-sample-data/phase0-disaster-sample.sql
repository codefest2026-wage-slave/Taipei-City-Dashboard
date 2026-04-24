-- =============================================================
-- Phase 0：韌性防災 — 本地測試用 sample data
-- 目標資料庫：dashboard（postgres-data 容器）
-- Usage:
--   docker exec -i postgres-data psql -U postgres -d dashboard \
--     < db-sample-data/phase0-disaster-sample.sql
-- =============================================================

-- 確保 PostGIS
CREATE EXTENSION IF NOT EXISTS postgis;

-- ── 1. 新北市淹水潛勢 ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.rainfall_flood_simulation_etl_ntpe (
    id           serial PRIMARY KEY,
    gridcode     int,
    category     text,
    type         text,
    area         float,
    city         text,
    wkb_geometry geometry(MultiPolygon, 4326),
    data_time    timestamptz DEFAULT NOW()
);
TRUNCATE public.rainfall_flood_simulation_etl_ntpe;
INSERT INTO public.rainfall_flood_simulation_etl_ntpe
    (gridcode, category, type, area, city, wkb_geometry)
VALUES
    (1,'一般','flood',1200000,'新北市',ST_GeomFromText('MULTIPOLYGON(((121.40 24.90,121.50 24.90,121.50 25.00,121.40 25.00,121.40 24.90)))',4326)),
    (2,'一般','flood', 800000,'新北市',ST_GeomFromText('MULTIPOLYGON(((121.50 24.90,121.60 24.90,121.60 25.00,121.50 25.00,121.50 24.90)))',4326)),
    (3,'高',  'flood', 500000,'新北市',ST_GeomFromText('MULTIPOLYGON(((121.60 24.90,121.70 24.90,121.70 25.00,121.60 25.00,121.60 24.90)))',4326)),
    (4,'高',  'flood', 200000,'新北市',ST_GeomFromText('MULTIPOLYGON(((121.70 24.90,121.80 24.90,121.80 25.00,121.70 25.00,121.70 24.90)))',4326)),
    (5,'極高','flood',  50000,'新北市',ST_GeomFromText('MULTIPOLYGON(((121.80 24.90,121.90 24.90,121.90 25.00,121.80 25.00,121.80 24.90)))',4326));

-- ── 2. 臺北市淹水潛勢 ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.rainfall_flood_simulation_etl_tpe (
    id           serial PRIMARY KEY,
    gridcode     int,
    category     text,
    type         text,
    area         float,
    city         text,
    wkb_geometry geometry(MultiPolygon, 4326),
    data_time    timestamptz DEFAULT NOW()
);
TRUNCATE public.rainfall_flood_simulation_etl_tpe;
INSERT INTO public.rainfall_flood_simulation_etl_tpe
    (gridcode, category, type, area, city, wkb_geometry)
VALUES
    (1,'一般','flood',900000,'臺北市',ST_GeomFromText('MULTIPOLYGON(((121.50 25.00,121.60 25.00,121.60 25.10,121.50 25.10,121.50 25.00)))',4326)),
    (2,'一般','flood',600000,'臺北市',ST_GeomFromText('MULTIPOLYGON(((121.60 25.00,121.70 25.00,121.70 25.10,121.60 25.10,121.60 25.00)))',4326)),
    (3,'高',  'flood',300000,'臺北市',ST_GeomFromText('MULTIPOLYGON(((121.70 25.00,121.80 25.00,121.80 25.10,121.70 25.10,121.70 25.00)))',4326));

-- ── 3. 新北市防空避難所 ───────────────────────────────────────
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
TRUNCATE public.urbn_air_raid_shelter_ntpe;
INSERT INTO public.urbn_air_raid_shelter_ntpe
    (town, person_capacity, address, lng, lat, wkb_geometry)
VALUES
    ('板橋區','500','新北市板橋區中山路1號',  121.460,25.014,ST_SetSRID(ST_MakePoint(121.460,25.014),4326)),
    ('板橋區','300','新北市板橋區文化路2號',  121.462,25.016,ST_SetSRID(ST_MakePoint(121.462,25.016),4326)),
    ('三重區','800','新北市三重區重新路3號',  121.492,25.063,ST_SetSRID(ST_MakePoint(121.492,25.063),4326)),
    ('新莊區','400','新北市新莊區中正路4號',  121.445,25.035,ST_SetSRID(ST_MakePoint(121.445,25.035),4326)),
    ('汐止區','600','新北市汐止區大同路5號',  121.660,25.067,ST_SetSRID(ST_MakePoint(121.660,25.067),4326));

-- ── 4. 臺北市防空避難所（table 名稱對應 query_charts）─────────
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
TRUNCATE public.urbn_air_raid_shelter;
INSERT INTO public.urbn_air_raid_shelter
    (town, address, area, person_capacity, is_accessible, lng, lat, wkb_geometry)
VALUES
    ('中正區','臺北市中正區重慶南路1號',  1200,600,true, 121.513,25.046,ST_SetSRID(ST_MakePoint(121.513,25.046),4326)),
    ('中正區','臺北市中正區愛國西路100號', 800,400,false,121.510,25.042,ST_SetSRID(ST_MakePoint(121.510,25.042),4326)),
    ('大安區','臺北市大安區羅斯福路2號',  900,450,true, 121.532,25.025,ST_SetSRID(ST_MakePoint(121.532,25.025),4326)),
    ('信義區','臺北市信義區信義路5號',   1500,750,true, 121.566,25.033,ST_SetSRID(ST_MakePoint(121.566,25.033),4326)),
    ('松山區','臺北市松山區南京東路4號',  700,350,true, 121.577,25.050,ST_SetSRID(ST_MakePoint(121.577,25.050),4326));

-- ── 5. 臺北市即時雨量站 ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.rainfall_realtime_tpe (
    id             serial PRIMARY KEY,
    station_id     text,
    station_name   text,
    district       text,
    rainfall_10min float,
    rainfall_today float,
    lng            float,
    lat            float,
    wkb_geometry   geometry(Point, 4326),
    data_time      timestamptz DEFAULT NOW()
);
TRUNCATE public.rainfall_realtime_tpe;
INSERT INTO public.rainfall_realtime_tpe
    (station_id, station_name, district, rainfall_10min, rainfall_today, lng, lat, wkb_geometry)
VALUES
    ('01','中正站','中正區',2.5, 35.0,121.513,25.046,ST_SetSRID(ST_MakePoint(121.513,25.046),4326)),
    ('02','大安站','大安區',3.0, 42.5,121.532,25.025,ST_SetSRID(ST_MakePoint(121.532,25.025),4326)),
    ('03','信義站','信義區',1.5, 28.0,121.566,25.033,ST_SetSRID(ST_MakePoint(121.566,25.033),4326)),
    ('04','松山站','松山區',4.0, 55.0,121.577,25.050,ST_SetSRID(ST_MakePoint(121.577,25.050),4326)),
    ('05','內湖站','內湖區',0.5, 12.0,121.587,25.075,ST_SetSRID(ST_MakePoint(121.587,25.075),4326));

\echo 'phase0-disaster-sample.sql loaded OK'
