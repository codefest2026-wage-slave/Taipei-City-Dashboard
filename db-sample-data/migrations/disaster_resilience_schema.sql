-- Disaster Resilience Dashboard — Schema migration
-- Run against: postgres-data → dashboard DB
-- docker exec -i postgres-data psql -U postgres -d dashboard < disaster_resilience_schema.sql

CREATE TABLE IF NOT EXISTS disaster_shelter_tpe (
  id               SERIAL PRIMARY KEY,
  name             VARCHAR(200),
  district         VARCHAR(50),
  village          VARCHAR(50),
  address          VARCHAR(300),
  person           INTEGER DEFAULT 0,
  indoor_area      FLOAT,
  suit_flood       BOOLEAN DEFAULT FALSE,
  suit_mudflow     BOOLEAN DEFAULT FALSE,
  suit_earthquake  BOOLEAN DEFAULT FALSE,
  suit_tsunami     BOOLEAN DEFAULT FALSE,
  suit_weak        BOOLEAN DEFAULT FALSE,
  standing_shelter BOOLEAN DEFAULT FALSE,
  lat              DOUBLE PRECISION,
  lng              DOUBLE PRECISION,
  data_time        TIMESTAMP WITH TIME ZONE
);

CREATE TABLE IF NOT EXISTS disaster_shelter_ntpc (
  id               SERIAL PRIMARY KEY,
  name             VARCHAR(200),
  district         VARCHAR(50),
  village          VARCHAR(50),
  address          VARCHAR(300),
  person           INTEGER DEFAULT 0,
  indoor_area      FLOAT,
  suit_flood       BOOLEAN DEFAULT FALSE,
  suit_mudflow     BOOLEAN DEFAULT FALSE,
  suit_earthquake  BOOLEAN DEFAULT FALSE,
  suit_tsunami     BOOLEAN DEFAULT FALSE,
  suit_weak        BOOLEAN DEFAULT FALSE,
  standing_shelter BOOLEAN DEFAULT FALSE,
  lat              DOUBLE PRECISION,
  lng              DOUBLE PRECISION,
  data_time        TIMESTAMP WITH TIME ZONE
);

CREATE TABLE IF NOT EXISTS river_water_level_tpe (
  id           SERIAL PRIMARY KEY,
  station_no   VARCHAR(10),
  station_name VARCHAR(100),
  level_out    FLOAT,
  rec_time     VARCHAR(20),
  lat          DOUBLE PRECISION,
  lng          DOUBLE PRECISION,
  data_time    TIMESTAMP WITH TIME ZONE
);

CREATE TABLE IF NOT EXISTS slope_warning_tpe (
  id                 SERIAL PRIMARY KEY,
  slope_id           VARCHAR(20),
  district           VARCHAR(50),
  village            VARCHAR(50),
  name               VARCHAR(300),
  yellow_threshold   INTEGER,
  red_threshold      INTEGER,
  reference_station  VARCHAR(100),
  lat                DOUBLE PRECISION,
  lng                DOUBLE PRECISION,
  data_time          TIMESTAMP WITH TIME ZONE
);

CREATE TABLE IF NOT EXISTS old_settlement_tpe (
  id                 SERIAL PRIMARY KEY,
  district           VARCHAR(50),
  village            VARCHAR(50),
  name               VARCHAR(300),
  reference_station  VARCHAR(100),
  person_count       INTEGER DEFAULT 0,
  household_count    INTEGER DEFAULT 0,
  yellow_threshold   INTEGER,
  red_threshold      INTEGER,
  lat                DOUBLE PRECISION,
  lng                DOUBLE PRECISION,
  data_time          TIMESTAMP WITH TIME ZONE
);
