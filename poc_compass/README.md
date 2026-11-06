# COMPASS POC – lato Porsche (Macan GTS, USA)

Estrazione per il POC "COMPetitor Price & Spec Analysis System": Porsche Macan GTS vs
Maserati Grecale V6 Trofeo, mercato USA.

```bash
python poc_compass/porsche_us.py --model 95BBW1 \
  --std-eq-cache poc_us/raw/95BBW1/standard_equipment.json --out poc_compass/output
```

Output `COMPASS_POC_Porsche_MacanGTS_95BBW1_USA_<data>.xlsx`:
- **Riepilogo** – prezzo Visual (MSRP base), destination charge, data listino, conteggi
- **Dotazioni di serie** – terminologia Porsche, descrizione, categoria, area veicolo, fonte
- **Optional singoli** – perimetro POC (componenti singoli con prezzo)
- **Optional (tutti)** – ogni voce con tipo, in perimetro (Sì / No / Da validare) e motivo
- **Pacchetti (fuori perim.)** – esclusi dal POC, con contenuto
- **Template Maserati** – formato concordabile per i dati Grecale forniti dal cliente
- **Log aree di verifica** – esito delle aree 01–06 della proposta (base per il report di fattibilità)

`95BBW1` = Macan GTS a benzina (MY2026). La Macan GTS Electric è `XABDE1`.
