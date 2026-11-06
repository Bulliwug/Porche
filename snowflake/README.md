# Porsche configurator in Snowflake – guida passo passo

Versione semplificata: **un modello** alla volta, solo da `configurator.porsche.com`
(optional, prezzi, prezzo base, dotazione di serie). Tutto gira dentro Snowflake:
una stored procedure Python scarica la pagina, decodifica i dati e scrive tre tabelle.

```
configurator.porsche.com ──► SCRAPE_PORSCHE_MODEL (Python) ──► PORSCHE_RAW / PORSCHE_MODELS / PORSCHE_OPTIONS
                                      ▲                                   │
                         TASK mensile (opzionale)               viste: ultimo listino, variazioni prezzo
```

## Prerequisiti
- Un account Snowflake su cui sia disponibile l'**External Network Access**
  (su alcuni account di prova non lo è).
- Un utente con ruolo **SYSADMIN** (o equivalente) e, per il passo 2, qualcuno con **ACCOUNTADMIN**.
- Via libera dell'ufficio legale sull'uso dei dati del configuratore.

## Passi

| # | Cosa | File | Chi |
|---|---|---|---|
| 1 | Warehouse XS, database `CAR_PRICING`, schema `PORSCHE` | `01_setup.sql` | SYSADMIN |
| 2 | Regola di rete + External Access Integration (solo `configurator.porsche.com`) | `02_network.sql` | ACCOUNTADMIN |
| 3 | Tabelle e viste | `03_tables.sql` | SYSADMIN |
| 4 | Stored procedure Python | `04_procedure.sql` | SYSADMIN |
| 5 | Primo test: `CALL SCRAPE_PORSCHE_MODEL('en-US','95BBW1');` | – | SYSADMIN |
| 6 | Controllo risultati | `06_queries.sql` | chiunque abbia accesso |
| 7 | (Opzionale) esecuzione mensile | `05_task.sql` | SYSADMIN + EXECUTE TASK |

In Snowsight: **Projects → Worksheets → + → SQL Worksheet**, incolla il contenuto del file,
seleziona tutto ed esegui (**Run All**). Un file per worksheet, in ordine.

Risultato atteso al passo 5:
```
OK Macan GTS (95BBW1, en-US): prezzo base 94200 USD, 238 optional (149 a pagamento), snapshot ...
```

## Codici utili
| Modello | Mercato | `LOCALE` | `MODEL_CODE` |
|---|---|---|---|
| Macan GTS (benzina) | USA | `en-US` | `95BBW1` |
| Macan GTS Electric | USA / Italia | `en-US` / `it-IT` | `XABDE1` |
| 911 Carrera GTS | Italia | `it-IT` | `992142` |

Il codice è l'ultima parte dell'URL del configuratore: `configurator.porsche.com/<locale>/mode/model/<codice>`.

## Notebook (opzionale)
Per analizzare i dati: **Projects → Notebooks → + Notebook**, database `CAR_PRICING`, schema `PORSCHE`,
warehouse `CAR_PRICING_WH`. Nelle celle SQL usa le query di `06_queries.sql`.
Se vuoi chiamare il sito direttamente da un notebook Python (invece che dalla procedura),
abilita `PORSCHE_CONFIGURATOR_EAI` nelle impostazioni del notebook (sezione *External access*).

## Problemi frequenti
| Errore | Causa | Soluzione |
|---|---|---|
| `Integration 'PORSCHE_CONFIGURATOR_EAI' does not exist or not authorized` | passo 2 non eseguito o manca il GRANT | eseguire `02_network.sql` come ACCOUNTADMIN |
| `ERRORE: HTTP 403` | il sito blocca gli indirizzi Snowflake | non aggirare: verificare con il legale / fonte alternativa |
| `KeyError: 'customer-configurator'` | la struttura della pagina è cambiata | aggiornare il decoder nella procedura |
| Il task non parte | task sospeso o manca EXECUTE TASK | `ALTER TASK ... RESUME` e il GRANT in `05_task.sql` |

Note: volume minimo (una pagina per modello, consentita dal `robots.txt` del configuratore);
i prezzi USA sono MSRP, quelli europei includono l'IVA.
