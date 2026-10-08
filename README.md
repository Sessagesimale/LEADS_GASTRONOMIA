# 🧀 Gastronomy Leads Agent

Software desktop per l'estrazione intelligente, l'arricchimento e la qualificazione commerciale di lead gastronomici ad alto valore (Ristoranti Gourmet e Botteghe/Negozi Gastronomici d'eccellenza) in tutta Italia.

---

## 🚀 Caratteristiche Principali

- **Fonti Ufficiali Integrate:**
  - 🌟 **Guida Michelin**: Ristoranti stellati, Bib Gourmand e selezionati con schede dettagliate.
  - 🧀 **Il Golosario**: Botteghe del formaggio, boutique del gusto e gastronomie d'eccellenza.
  - 🦞 **Gambero Rosso**: Ristoranti e locali gastronomici di rilievo.
  - ☕ **Le Guide de L'Espresso**: Ristoranti di punta con rating a cappelli.
- **Selezione Territoriale Flessibile:**
  - Scelta singola tra le 20 regioni italiane.
  - Macro-aree preimpostate: *Nord Italia (8 Regioni)*, *Centro Italia (4 Regioni)*, *Sud e Isole (8 Regioni)*.
  - Selezione multipla personalizzata (tutte le 20 regioni o combinazioni su misura).
- **Filtro Categoria Attività:**
  - `Tutti (Ristoranti e Negozi)`
  - `Solo Ristoranti`
  - `Solo Negozi / Botteghe Gastronomiche`
- **Filtro Rigoroso Dolciario:** Esclusione automatica di gelaterie, cremerie, cioccolaterie, pasticcerie e confetterie per mantenere i lead focalizzati su gastronomia e salato.
- **Arricchimento Contatti Google:** Se il numero di telefono non è disponibile sulla guida di origine, il sistema interroga automaticamente Google per reperire il contatto ufficiale.
- **Output Excel Professionale:**
  - Colonne: *Nome, Tipologia, Regione, Città, Indirizzo, Telefono, Email, Sito Web, Link Pagina, Fonte, Esito Valutazione, Note Commerciali*.
  - Intestazioni stilizzate e menu a tendina integrato per la qualificazione commerciale (*Da contattare, Contattato, Scartato - Non in target*).
  - Salvataggio sicuro anche se il file Excel è aperto sul computer (creazione automatica copia numerata).
  - Memorizzazione permanente della cartella di salvataggio scelta.
- **Browser Headless (Invisibile):** Lo scraping viene eseguito completamente in background senza finestre invasive.

---

## 💻 Come Installare ed Eseguire su un Nuovo PC

### Prerequisiti
1. Scarica e installa **Python 3.10+** (consigliato Python 3.11 o 3.12) da [python.org](https://www.python.org/).
   > ⚠️ **IMPORTANTE:** Durante l'installazione di Python, assicurati di spuntare la casella **"Add python.exe to PATH"**.

---

### Metodo 1: Installazione Automatica (Consigliato)
1. Clona o scarica questa cartella sul nuovo PC.
2. Fai doppio clic sul file **`install.bat`**.
   - Lo script creerà automaticamente l'ambiente virtuale (`venv`).
   - Installerà tutte le dipendenze da `requirements.txt`.
   - Scaricherà i componenti headless di Chromium per Playwright.
3. Al termine dell'installazione:
   - Per avviare subito l'applicazione: fai doppio clic su **`run.bat`**.
   - Per compilare l'eseguibile standalone (`.exe`): fai doppio clic su **`build_exe.bat`**.

---

### Metodo 2: Installazione Manuale da Riga di Comando
Apri un terminale (PowerShell o CMD) nella cartella del progetto ed esegui:

```bash
# 1. Crea l'ambiente virtuale
python -m venv venv

# 2. Attiva l'ambiente virtuale
# Su Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Su Windows (CMD):
.\venv\Scripts\activate.bat

# 3. Aggiorna pip e installa le dipendenze
python -m pip install --upgrade pip
pip install -r requirements.txt

# 4. Installa i browser per Playwright
playwright install chromium

# 5. Avvia l'applicazione
python main.py
```

---

## 🔨 Come Compilare l'Eseguibile (.exe)

Per creare la versione eseguibile standalone sul nuovo PC senza dover avviare Python:

```bash
.\build_exe.bat
```

L'eseguibile pronto per l'uso verrà generato nella directory `dist\GastronomyLeadsAgent\GastronomyLeadsAgent.exe` con l'icona personalizzata e i browser integrati.

---

## 📂 Struttura del Progetto

```
GastronomyLeadsAgent/
├── main.py                     # Interfaccia grafica CustomTkinter ed orchestratore
├── data_processor.py           # Pulizia lead, filtri categoria e generazione file Excel
├── app_icon.ico                # Icona ufficiale ad alta risoluzione
├── create_icon.py              # Script generatore dell'icona
├── requirements.txt            # Dipendenze Python
├── install.bat                 # Script di configurazione automatica per nuovi computer
├── run.bat                     # Avvio rapido con un clic
├── build_exe.bat               # Compilatore PyInstaller
├── .gitignore                  # File e cartelle escluse dal versionamento Git
├── scrapers/                   # Moduli di scraping per le diverse fonti
│   ├── base_scraper.py
│   ├── michelin_scraper.py     # Guida Michelin
│   ├── golosario_scraper.py    # Il Golosario
│   ├── gambero_rosso_scraper.py# Gambero Rosso
│   └── espresso_scraper.py     # Le Guide de L'Espresso
└── utils/
    └── enricher.py             # Ricerca Google per arricchimento numeri di telefono mancanti
```
