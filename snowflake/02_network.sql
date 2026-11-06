-- =====================================================================
-- 02 – Accesso a internet (solo configurator.porsche.com)
-- Richiede ACCOUNTADMIN (o un ruolo con CREATE INTEGRATION):
-- di solito lo esegue l'amministratore Snowflake.
-- =====================================================================
USE ROLE ACCOUNTADMIN;

-- Regola di rete: l'unico host raggiungibile è il configuratore Porsche
CREATE OR REPLACE NETWORK RULE CAR_PRICING.PORSCHE.PORSCHE_CONFIGURATOR_RULE
  MODE = EGRESS
  TYPE = HOST_PORT
  VALUE_LIST = ('configurator.porsche.com');

-- Integrazione che la stored procedure userà per uscire su internet
CREATE OR REPLACE EXTERNAL ACCESS INTEGRATION PORSCHE_CONFIGURATOR_EAI
  ALLOWED_NETWORK_RULES = (CAR_PRICING.PORSCHE.PORSCHE_CONFIGURATOR_RULE)
  ENABLED = TRUE
  COMMENT = 'Accesso in uscita al configuratore Porsche per il progetto car pricing';

-- Permesso d'uso al ruolo che crea ed esegue la procedura
GRANT USAGE ON INTEGRATION PORSCHE_CONFIGURATOR_EAI TO ROLE SYSADMIN;
