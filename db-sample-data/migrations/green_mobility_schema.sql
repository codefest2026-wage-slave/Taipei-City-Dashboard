-- ========================================
-- 方案A：雙北綠色出行 DB_DASHBOARD 資料表
-- 目標資料庫: DB_DASHBOARD (dashboard)
-- ========================================

-- 1. 電動機車充電站（臺北）
CREATE TABLE IF NOT EXISTS ev_scooter_charging_tpe (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200),
    address VARCHAR(300),
    district VARCHAR(50),
    lat FLOAT,
    lng FLOAT,
    operator VARCHAR(100),
    slots INTEGER DEFAULT 0,
    data_time TIMESTAMP WITH TIME ZONE
);

-- 2. 電動機車充電站（新北）
CREATE TABLE IF NOT EXISTS ev_scooter_charging_ntpc (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200),
    address VARCHAR(300),
    district VARCHAR(50),
    lat FLOAT,
    lng FLOAT,
    operator VARCHAR(100),
    slots INTEGER DEFAULT 0,
    data_time TIMESTAMP WITH TIME ZONE
);

-- 3. 電動汽車充電站（臺北）
CREATE TABLE IF NOT EXISTS ev_car_charging_tpe (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200),
    address VARCHAR(300),
    district VARCHAR(50),
    lat FLOAT,
    lng FLOAT,
    charger_type VARCHAR(20),
    slots INTEGER DEFAULT 0,
    data_time TIMESTAMP WITH TIME ZONE
);

-- 4. 電動汽車充電站（新北）
CREATE TABLE IF NOT EXISTS ev_car_charging_ntpc (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200),
    address VARCHAR(300),
    district VARCHAR(50),
    lat FLOAT,
    lng FLOAT,
    charger_type VARCHAR(20),
    slots INTEGER DEFAULT 0,
    data_time TIMESTAMP WITH TIME ZONE
);

-- 5. 公車路線（臺北）
CREATE TABLE IF NOT EXISTS bus_route_map_tpe (
    id SERIAL PRIMARY KEY,
    route_uid VARCHAR(30),
    route_name VARCHAR(100),
    direction INTEGER DEFAULT 0,
    data_time TIMESTAMP WITH TIME ZONE
);

-- 6. 公車路線（新北）
CREATE TABLE IF NOT EXISTS bus_route_map_ntpc (
    id SERIAL PRIMARY KEY,
    route_uid VARCHAR(30),
    route_name VARCHAR(100),
    direction INTEGER DEFAULT 0,
    data_time TIMESTAMP WITH TIME ZONE
);

-- 7. 垃圾車收運路線（臺北）
CREATE TABLE IF NOT EXISTS garbage_truck_route_tpe (
    id SERIAL PRIMARY KEY,
    route_code VARCHAR(30),
    district VARCHAR(50),
    route_name VARCHAR(100),
    weekday VARCHAR(20),
    vehicle_no VARCHAR(20),
    data_time TIMESTAMP WITH TIME ZONE
);

-- 8. 垃圾車收運路線（新北）
CREATE TABLE IF NOT EXISTS garbage_truck_route_ntpc (
    id SERIAL PRIMARY KEY,
    route_code VARCHAR(30),
    district VARCHAR(50),
    route_name VARCHAR(100),
    weekday VARCHAR(20),
    vehicle_no VARCHAR(20),
    lat FLOAT,
    lng FLOAT,
    data_time TIMESTAMP WITH TIME ZONE
);
