-- =====================================================================
-- 06 – Query di controllo e analisi
-- =====================================================================
USE SCHEMA CAR_PRICING.PORSCHE;

-- Modello: prezzo base e numero di optional per esecuzione
SELECT SNAPSHOT_TS, LOCALE, MODEL_CODE, MODEL_NAME, BASE_PRICE, CURRENCY, N_OPTIONS
FROM PORSCHE_MODELS ORDER BY SNAPSHOT_TS DESC;

-- Optional dell'ultimo listino, dal più caro
SELECT SECTION, CATEGORY, OPTION_CODE, OPTION_NAME, PRICE, CURRENCY, IS_STANDARD
FROM V_OPTIONS_LATEST
WHERE MODEL_CODE = '95BBW1' AND LOCALE = 'en-US'
ORDER BY PRICE DESC NULLS LAST;

-- Riepilogo per sezione
SELECT SECTION, COUNT(*) AS N_OPTIONS,
       COUNT_IF(PRICE > 0) AS A_PAGAMENTO, COUNT_IF(IS_STANDARD) AS DI_SERIE,
       MAX(PRICE) AS PREZZO_MAX
FROM V_OPTIONS_LATEST
WHERE MODEL_CODE = '95BBW1' AND LOCALE = 'en-US'
GROUP BY SECTION ORDER BY N_OPTIONS DESC;

-- Variazioni di prezzo rispetto all'esecuzione precedente
SELECT * FROM V_PRICE_CHANGES ORDER BY SNAPSHOT_TS DESC, ABS(DELTA) DESC;
