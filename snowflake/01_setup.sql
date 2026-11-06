-- =====================================================================
-- 01 – Warehouse, database e schema
-- Esegui in un Worksheet SQL di Snowsight con un ruolo che può creare
-- warehouse e database (es. SYSADMIN).
-- =====================================================================
USE ROLE SYSADMIN;

CREATE WAREHOUSE IF NOT EXISTS CAR_PRICING_WH
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60          -- si spegne dopo 60 s di inattività
  AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE;

CREATE DATABASE IF NOT EXISTS CAR_PRICING;
CREATE SCHEMA IF NOT EXISTS CAR_PRICING.PORSCHE;

USE WAREHOUSE CAR_PRICING_WH;
USE SCHEMA CAR_PRICING.PORSCHE;
