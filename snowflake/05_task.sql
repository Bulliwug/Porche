-- =====================================================================
-- 05 – Esecuzione automatica mensile (opzionale)
-- Il ruolo che possiede il task deve avere EXECUTE TASK:
--   USE ROLE ACCOUNTADMIN; GRANT EXECUTE TASK ON ACCOUNT TO ROLE SYSADMIN;
-- =====================================================================
USE ROLE SYSADMIN;
USE SCHEMA CAR_PRICING.PORSCHE;

CREATE OR REPLACE TASK TASK_PORSCHE_MACAN_GTS_US
  WAREHOUSE = CAR_PRICING_WH
  SCHEDULE = 'USING CRON 0 6 1 * * Europe/Rome'   -- il 1° di ogni mese alle 06:00
  COMMENT = 'Listino mensile Porsche Macan GTS, mercato USA'
AS
  CALL SCRAPE_PORSCHE_MODEL('en-US', '95BBW1');

ALTER TASK TASK_PORSCHE_MACAN_GTS_US RESUME;     -- i task nascono sospesi

-- Per provarlo subito senza aspettare il cron:
-- EXECUTE TASK TASK_PORSCHE_MACAN_GTS_US;
-- Storico esecuzioni:
-- SELECT * FROM TABLE(INFORMATION_SCHEMA.TASK_HISTORY(TASK_NAME => 'TASK_PORSCHE_MACAN_GTS_US'))
-- ORDER BY SCHEDULED_TIME DESC;
