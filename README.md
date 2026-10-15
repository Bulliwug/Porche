# Porsche configurator scraper

Estrae dal sito Porsche Italia tutti i modelli configurabili, con optional, prezzi, scheda tecnica e
dotazione di serie. Funziona con semplici richieste HTTP: nessun browser, nessun login.

## Fonti dati
| Dato | Fonte |
|---|---|
| Elenco modelli, prezzo base, carrozzeria, trazione, cambio | `www.porsche.com/italy/models/` (props Astro nella pagina) |
| Optional: sezione/categoria/gruppo, prezzo, di serie, descrizione | `configurator.porsche.com/it-IT/mode/model/<codice>` (loaderData React Router, formato turbo-stream) |
| Scheda tecnica completa | `www.porsche.com/pcom-model-pages-isr/api/it-IT/technical-data/<codice>/` |
| Equipaggiamento di serie | `www.porsche.com/pcom-model-pages-isr/api/it-IT/standard-equipment/<codice>/` |

## Uso
```bash
pip install -r requirements.txt
python scrape.py --out data                 # tutti i modelli (~83), circa 7 minuti
python scrape.py --models 992142 --out data # solo alcuni modelli
python extract.py --data data --xlsx porsche_configuratore.xlsx
```
Altri mercati: `--locale de-DE --market germany` (i nomi delle colonne chiave della scheda tecnica
nel foglio Modelli sono riconosciuti sulle etichette italiane).

## Output (`porsche_configuratore.xlsx` + un CSV per foglio)
- **Modelli** – codice, nome, anno, gamma, carrozzeria, trazione, cambio, prezzo base, potenza, 0-100, velocità max, consumi, dimensioni…
- **Optional** – ogni optional per modello: sezione, categoria, gruppo, codice, nome, prezzo €, di serie, descrizione, contenuto pacchetti
- **DatiTecnici** – scheda tecnica completa in formato lungo (modello, categoria, voce, valore)
- **DotazioneSerie** – equipaggiamento di serie per modello

Prezzi IVA inclusa, listino del configuratore (colonna `data_listino`). Le combinazioni tra optional
(incompatibilità/obblighi) non sono incluse: il configuratore le calcola lato server a ogni scelta.
