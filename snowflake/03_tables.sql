-- =====================================================================
-- 03 – Tabelle (storico: ogni esecuzione aggiunge righe con SNAPSHOT_TS)
-- =====================================================================
USE ROLE SYSADMIN;
USE SCHEMA CAR_PRICING.PORSCHE;

-- Dati grezzi del configuratore (JSON decodificato), utili per rielaborare
CREATE TABLE IF NOT EXISTS PORSCHE_RAW (
  SNAPSHOT_TS   TIMESTAMP_NTZ,
  LOCALE        STRING,
  MODEL_CODE    STRING,
  URL           STRING,
  PAYLOAD       VARIANT
);

-- Un record per modello e per esecuzione
CREATE TABLE IF NOT EXISTS PORSCHE_MODELS (
  SNAPSHOT_TS            TIMESTAMP_NTZ,
  LOCALE                 STRING,
  MODEL_CODE             STRING,
  MODEL_NAME             STRING,
  MODEL_YEAR             NUMBER,
  MODEL_FAMILY           STRING,
  ENGINE_TYPE            STRING,
  BASE_PRICE             NUMBER(14,2),
  CURRENCY               STRING,
  BASE_PRICE_TEXT        STRING,
  STANDARD_WHEELS        STRING,
  STANDARD_TRANSMISSION  STRING,
  PRICE_LIST_DATE        STRING,
  N_OPTIONS              NUMBER,
  URL                    STRING
);

-- Un record per optional, per modello e per esecuzione
CREATE TABLE IF NOT EXISTS PORSCHE_OPTIONS (
  SNAPSHOT_TS        TIMESTAMP_NTZ,
  LOCALE             STRING,
  MODEL_CODE         STRING,
  MODEL_NAME         STRING,
  SECTION            STRING,
  CATEGORY           STRING,
  OPTION_GROUP       STRING,
  OPTION_CODE        STRING,
  OPTION_NAME        STRING,
  PRICE              NUMBER(14,2),
  CURRENCY           STRING,
  PRICE_TEXT         STRING,
  IS_STANDARD        BOOLEAN,
  IS_DEFAULT         BOOLEAN,
  OPTION_TYPE        STRING,
  COLOR_HEX          STRING,
  EXCLUSIVE_MANUFAKTUR BOOLEAN,
  DESCRIPTION        STRING,
  PACKAGE_CONTENTS   STRING
);

-- Ultimo listino disponibile per ogni modello/mercato
CREATE OR REPLACE VIEW V_OPTIONS_LATEST AS
SELECT *
FROM PORSCHE_OPTIONS
QUALIFY SNAPSHOT_TS = MAX(SNAPSHOT_TS) OVER (PARTITION BY LOCALE, MODEL_CODE);

-- Variazioni di prezzo tra un'esecuzione e la precedente
CREATE OR REPLACE VIEW V_PRICE_CHANGES AS
SELECT LOCALE, MODEL_CODE, MODEL_NAME, OPTION_CODE, OPTION_NAME, CURRENCY,
       PREV_PRICE, PRICE AS NEW_PRICE, PRICE - PREV_PRICE AS DELTA,
       PREV_TS, SNAPSHOT_TS
FROM (
  SELECT o.*,
         LAG(PRICE)       OVER (PARTITION BY LOCALE, MODEL_CODE, OPTION_CODE ORDER BY SNAPSHOT_TS) AS PREV_PRICE,
         LAG(SNAPSHOT_TS) OVER (PARTITION BY LOCALE, MODEL_CODE, OPTION_CODE ORDER BY SNAPSHOT_TS) AS PREV_TS
  FROM PORSCHE_OPTIONS o
)
WHERE PREV_PRICE IS NOT NULL AND PRICE <> PREV_PRICE;
