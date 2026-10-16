import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import sys
import json
import time
from scrapers.michelin_scraper import MichelinScraper
from scrapers.golosario_scraper import GolosarioScraper
from scrapers.gambero_rosso_scraper import GamberoRossoScraper
from scrapers.espresso_scraper import EspressoScraper
from scrapers.slowfood_scraper import SlowFoodScraper
from scrapers.eccellenze_scraper import EccellenzeScraper
from scrapers.social_discovery_scraper import SocialDiscoveryScraper
from utils.geo_utils import (
    REGION_PROVINCES,
    get_provinces_for_regions,
    parse_selected_province_code,
    extract_province
)
from utils.enricher import PhoneEnricher
from data_processor import DataProcessor
from playwright.sync_api import sync_playwright

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

ALL_ITALIAN_REGIONS = [
    "Abruzzo", "Basilicata", "Calabria", "Campania", "Emilia-Romagna",
    "Friuli-Venezia Giulia", "Lazio", "Liguria", "Lombardia", "Marche",
    "Molise", "Piemonte", "Puglia", "Sardegna", "Sicilia",
    "Toscana", "Trentino-Alto Adige", "Umbria", "Valle d'Aosta", "Veneto"
]

MACRO_REGIONS = {
    "Nord Italia (8 Regioni)": [
        "Emilia-Romagna", "Friuli-Venezia Giulia", "Liguria", "Lombardia",
        "Piemonte", "Trentino-Alto Adige", "Valle d'Aosta", "Veneto"
    ],
    "Centro Italia (4 Regioni)": [
        "Lazio", "Marche", "Toscana", "Umbria"
    ],
    "Sud e Isole (8 Regioni)": [
        "Abruzzo", "Basilicata", "Calabria", "Campania", "Molise",
        "Puglia", "Sardegna", "Sicilia"
    ]
}


def get_config_dir():
    appdata = os.getenv("APPDATA")
    if appdata:
        path = os.path.join(appdata, "GastronomyLeadsAgent")
        os.makedirs(path, exist_ok=True)
        return path
    return os.path.dirname(os.path.abspath(__file__))


def get_config_file():
    return os.path.join(get_config_dir(), "config.json")


class MultiRegionDialog(ctk.CTkToplevel):
    def __init__(self, parent, current_selected, callback):
        super().__init__(parent)
        self.title("Selezione Multipla Regioni")
        self.geometry("420x520")
        self.callback = callback
        self.transient(parent)
        self.grab_set()

        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - 210
        y = parent.winfo_y() + (parent.winfo_height() // 2) - 260
        self.geometry(f"+{max(0, x)}+{max(0, y)}")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        lbl = ctk.CTkLabel(self, text="Seleziona le Regioni da estrarre", font=ctk.CTkFont(size=16, weight="bold"))
        lbl.grid(row=0, column=0, padx=15, pady=(15, 10))

        frame_macros = ctk.CTkFrame(self)
        frame_macros.grid(row=1, column=0, padx=15, pady=(0, 10), sticky="ew")

        btn_all = ctk.CTkButton(frame_macros, text="Tutte (20)", width=75, height=28, command=self.select_all)
        btn_all.pack(side="left", padx=4, pady=5)

        btn_none = ctk.CTkButton(frame_macros, text="Nessuna", width=70, height=28, fg_color="gray50", hover_color="gray40", command=self.select_none)
        btn_none.pack(side="left", padx=4, pady=5)

        btn_nord = ctk.CTkButton(frame_macros, text="Nord", width=55, height=28, command=lambda: self.select_macro("Nord Italia (8 Regioni)"))
        btn_nord.pack(side="left", padx=4, pady=5)

        btn_centro = ctk.CTkButton(frame_macros, text="Centro", width=60, height=28, command=lambda: self.select_macro("Centro Italia (4 Regioni)"))
        btn_centro.pack(side="left", padx=4, pady=5)

        btn_sud = ctk.CTkButton(frame_macros, text="Sud/Isole", width=70, height=28, command=lambda: self.select_macro("Sud e Isole (8 Regioni)"))
        btn_sud.pack(side="left", padx=4, pady=5)

        self.scroll_frame = ctk.CTkScrollableFrame(self, height=300)
        self.scroll_frame.grid(row=2, column=0, padx=15, pady=0, sticky="nsew")

        self.region_vars = {}
        for reg in ALL_ITALIAN_REGIONS:
            var = ctk.BooleanVar(value=(reg in current_selected))
            chk = ctk.CTkCheckBox(self.scroll_frame, text=reg, variable=var)
            chk.pack(anchor="w", padx=10, pady=4)
            self.region_vars[reg] = var

        btn_confirm = ctk.CTkButton(self, text="Conferma Selezione", height=36, font=ctk.CTkFont(weight="bold"), command=self.confirm)
        btn_confirm.grid(row=3, column=0, padx=15, pady=15, sticky="ew")

    def select_all(self):
        for var in self.region_vars.values():
            var.set(True)

    def select_none(self):
        for var in self.region_vars.values():
            var.set(False)

    def select_macro(self, macro_name):
        macro_list = MACRO_REGIONS.get(macro_name, [])
        for reg, var in self.region_vars.items():
            var.set(reg in macro_list)

    def confirm(self):
        selected = [reg for reg, var in self.region_vars.items() if var.get()]
        if not selected:
            messagebox.showwarning("Attenzione", "Selezionare almeno una regione.")
            return
        self.callback(selected)
        self.destroy()


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Gastronomy Leads Agent V2.0 - Intelligence & Bilanci Parmigiano Reggiano")
        self.geometry("720x790")
        self.minsize(680, 740)

        self.setup_icon()

        # Stato iniziale
        self.selected_regions = ["Valle d'Aosta"]
        self.output_path = self.get_default_output_dir()

        self.load_config()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(7, weight=1)

        # Titolo
        self.lbl_title = ctk.CTkLabel(
            self,
            text="Estrattore Lead Gastronomici V2.0",
            font=ctk.CTkFont(size=21, weight="bold")
        )
        self.lbl_title.grid(row=0, column=0, padx=20, pady=(12, 6))

        # 1. Territorio: Regione + Provincia (Opzionale)
        self.frame_region = ctk.CTkFrame(self)
        self.frame_region.grid(row=1, column=0, padx=20, pady=5, sticky="ew")

        self.lbl_region_tag = ctk.CTkLabel(
            self.frame_region,
            text="1. Selezione Regione e Provincia (Opzionale):",
            font=ctk.CTkFont(weight="bold")
        )
        self.lbl_region_tag.pack(anchor="w", padx=15, pady=(8, 2))

        self.frame_region_controls = ctk.CTkFrame(self.frame_region, fg_color="transparent")
        self.frame_region_controls.pack(fill="x", padx=15, pady=(0, 4))

        combo_options = [
            "Tutte le 20 Regioni (Italia)",
            "Nord Italia (8 Regioni)",
            "Centro Italia (4 Regioni)",
            "Sud e Isole (8 Regioni)"
        ] + ALL_ITALIAN_REGIONS

        self.combo_region = ctk.CTkComboBox(
            self.frame_region_controls,
            values=combo_options,
            state="readonly",
            width=260,
            command=self.on_combo_region_changed
        )
        if len(self.selected_regions) == 1 and self.selected_regions[0] in ALL_ITALIAN_REGIONS:
            self.combo_region.set(self.selected_regions[0])
        elif len(self.selected_regions) == 20:
            self.combo_region.set("Tutte le 20 Regioni (Italia)")
        else:
            self.combo_region.set(f"Personalizzata ({len(self.selected_regions)} regioni)")
        self.combo_region.pack(side="left", fill="x", expand=True, padx=(0, 8), pady=4)

        self.btn_multi_region = ctk.CTkButton(
            self.frame_region_controls,
            text="Più Regioni...",
            width=115,
            command=self.open_multi_region_dialog
        )
        self.btn_multi_region.pack(side="left", padx=(0, 8), pady=4)

        # Menu a tendina Provincia (Opzionale)
        prov_options = get_provinces_for_regions(self.selected_regions)
        self.combo_province = ctk.CTkComboBox(
            self.frame_region_controls,
            values=prov_options,
            state="readonly",
            width=195,
            command=lambda _: self.save_config()
        )
        self.combo_province.set("Tutte le Province")
        self.combo_province.pack(side="left", pady=4)

        self.lbl_selected_summary = ctk.CTkLabel(
            self.frame_region,
            text=self.get_region_summary_text(),
            text_color="gray70",
            font=ctk.CTkFont(size=12)
        )
        self.lbl_selected_summary.pack(anchor="w", padx=15, pady=(0, 6))

        # 2. Filtro Tipologia / Categoria Attività
        self.frame_category = ctk.CTkFrame(self)
        self.frame_category.grid(row=2, column=0, padx=20, pady=5, sticky="ew")

        self.lbl_cat = ctk.CTkLabel(
            self.frame_category,
            text="2. Filtro Tipologia / Categoria Attività:",
            font=ctk.CTkFont(weight="bold")
        )
        self.lbl_cat.pack(anchor="w", padx=15, pady=(8, 2))

        self.cat_options = [
            "Tutti (Ristoranti, Negozi, Produttori & Ho.Re.Ca.)",
            "Solo Ristoranti",
            "Solo Negozi / Botteghe / Produttori / Ho.Re.Ca."
        ]
        self.combo_category = ctk.CTkComboBox(
            self.frame_category,
            values=self.cat_options,
            state="readonly",
            width=400,
            command=self.on_category_changed
        )
        self.combo_category.set(
            self.saved_category if hasattr(self, "saved_category") and self.saved_category in self.cat_options else self.cat_options[0]
        )
        self.combo_category.pack(fill="x", padx=15, pady=(0, 8))

        # 3. Selezione Fonti di Ricerca (7 Fonti V2)
        self.frame_sources = ctk.CTkFrame(self)
        self.frame_sources.grid(row=3, column=0, padx=20, pady=5, sticky="ew")
        self.frame_sources.grid_columnconfigure(0, weight=1)
        self.frame_sources.grid_columnconfigure(1, weight=1)

        self.lbl_sources = ctk.CTkLabel(
            self.frame_sources,
            text="3. Fonti Ufficiali & Nuove Sorgenti B2B:",
            font=ctk.CTkFont(weight="bold")
        )
        self.lbl_sources.grid(row=0, column=0, columnspan=2, padx=15, pady=(8, 4), sticky="w")

        self.var_michelin = ctk.BooleanVar(value=True)
        self.chk_michelin = ctk.CTkCheckBox(self.frame_sources, text="Guida Michelin (Ristoranti)", variable=self.var_michelin)
        self.chk_michelin.grid(row=1, column=0, padx=15, pady=3, sticky="w")

        self.var_golosario = ctk.BooleanVar(value=True)
        self.chk_golosario = ctk.CTkCheckBox(self.frame_sources, text="Il Golosario (Botteghe & Formaggerie)", variable=self.var_golosario)
        self.chk_golosario.grid(row=1, column=1, padx=15, pady=3, sticky="w")

        self.var_gambero = ctk.BooleanVar(value=True)
        self.chk_gambero = ctk.CTkCheckBox(self.frame_sources, text="Gambero Rosso (Ristoranti & Locali)", variable=self.var_gambero)
        self.chk_gambero.grid(row=2, column=0, padx=15, pady=3, sticky="w")

        self.var_espresso = ctk.BooleanVar(value=True)
        self.chk_espresso = ctk.CTkCheckBox(self.frame_sources, text="Le Guide de L'Espresso (Ristoranti)", variable=self.var_espresso)
        self.chk_espresso.grid(row=2, column=1, padx=15, pady=3, sticky="w")

        self.var_slowfood = ctk.BooleanVar(value=True)
        self.chk_slowfood = ctk.CTkCheckBox(
            self.frame_sources,
            text="Fondazione Slow Food (Produttori Presìdi & Cuochi)",
            variable=self.var_slowfood
        )
        self.chk_slowfood.grid(row=3, column=0, padx=15, pady=3, sticky="w")

        self.var_eccellenze = ctk.BooleanVar(value=True)
        self.chk_eccellenze = ctk.CTkCheckBox(
            self.frame_sources,
            text="Salumerie Storiche, Touring & Distributori Ho.Re.Ca.",
            variable=self.var_eccellenze
        )
        self.chk_eccellenze.grid(row=3, column=1, padx=15, pady=3, sticky="w")

        self.var_social_discovery = ctk.BooleanVar(value=True)
        self.chk_social_discovery = ctk.CTkCheckBox(
            self.frame_sources,
            text="🔥 Social Buyer Discovery (Chi compra Parmigiano su IG/FB)",
            variable=self.var_social_discovery
        )
        self.chk_social_discovery.grid(row=4, column=0, columnspan=2, padx=15, pady=(3, 8), sticky="w")

        # 4. Opzioni Bilanci, Social Intelligence & Fogli Provincia
        self.frame_v2_opts = ctk.CTkFrame(self)
        self.frame_v2_opts.grid(row=4, column=0, padx=20, pady=5, sticky="ew")

        self.lbl_v2_opts = ctk.CTkLabel(
            self.frame_v2_opts,
            text="4. Arricchimento Dati Camerali, Social & Struttura Excel:",
            font=ctk.CTkFont(weight="bold")
        )
        self.lbl_v2_opts.pack(anchor="w", padx=15, pady=(8, 4))

        self.var_bilancio = ctk.BooleanVar(value=True)
        self.chk_bilancio = ctk.CTkCheckBox(
            self.frame_v2_opts,
            text="Estrai Ultimo Bilancio Depositato (P.IVA, Fatturato, Utile/Perdita, Addetti, Anno)",
            variable=self.var_bilancio
        )
        self.chk_bilancio.pack(anchor="w", padx=15, pady=2)

        self.var_social_affinity = ctk.BooleanVar(value=True)
        self.chk_social_affinity = ctk.CTkCheckBox(
            self.frame_v2_opts,
            text="Analizza Menu & Social per rilevare utilizzo attivo di Parmigiano Reggiano DOP",
            variable=self.var_social_affinity
        )
        self.chk_social_affinity.pack(anchor="w", padx=15, pady=2)

        self.var_split_prov = ctk.BooleanVar(value=True)
        self.chk_split_prov = ctk.CTkCheckBox(
            self.frame_v2_opts,
            text="Dividi automaticamente l'Excel finale in Fogli separati per ogni Provincia",
            variable=self.var_split_prov
        )
        self.chk_split_prov.pack(anchor="w", padx=15, pady=(2, 8))

        # 5. Cartella Salvataggio
        self.frame_output = ctk.CTkFrame(self)
        self.frame_output.grid(row=5, column=0, padx=20, pady=5, sticky="ew")

        self.btn_folder = ctk.CTkButton(self.frame_output, text="Scegli Cartella Salvataggio", command=self.choose_folder)
        self.btn_folder.pack(side="left", padx=12, pady=8)

        self.lbl_folder = ctk.CTkLabel(self.frame_output, text=self.output_path, anchor="w")
        self.lbl_folder.pack(side="left", fill="x", expand=True, padx=(5, 12), pady=8)

        # 6. Pulsante Avvio
        self.btn_run = ctk.CTkButton(
            self,
            text="Avvia Estrazione & Arricchimento Lead V2",
            command=self.start_extraction,
            height=42,
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.btn_run.grid(row=6, column=0, padx=20, pady=8, sticky="ew")

        # 7. Stato e ProgressBar
        self.frame_status = ctk.CTkFrame(self)
        self.frame_status.grid(row=7, column=0, padx=20, pady=(0, 12), sticky="nsew")

        self.lbl_status = ctk.CTkLabel(
            self.frame_status,
            text="Pronto (Motore Resiliente V2 + Bilanci + Social Intelligence attivi)",
            font=ctk.CTkFont(size=13)
        )
        self.lbl_status.pack(pady=(8, 2))

        self.progressbar = ctk.CTkProgressBar(self.frame_status)
        self.progressbar.pack(fill="x", padx=20, pady=(4, 8))
        self.progressbar.set(0)

    def setup_icon(self):
        if getattr(sys, "frozen", False):
            base_dir = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))

        icon_path = os.path.join(base_dir, "app_icon.ico")
        if os.path.exists(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass

    def get_default_output_dir(self):
        onedrive_desktop = os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop")
        if os.path.exists(onedrive_desktop):
            return onedrive_desktop
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        if os.path.exists(desktop):
            return desktop
        return os.path.expanduser("~")

    def load_config(self):
        cfg_file = get_config_file()
        if os.path.exists(cfg_file):
            try:
                with open(cfg_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    saved_path = data.get("output_path", "")
                    if saved_path and os.path.exists(saved_path):
                        self.output_path = saved_path
                    saved_regions = data.get("selected_regions", [])
                    if isinstance(saved_regions, list) and saved_regions:
                        self.selected_regions = [r for r in saved_regions if r in ALL_ITALIAN_REGIONS]
                        if not self.selected_regions:
                            self.selected_regions = ["Valle d'Aosta"]
                    self.saved_category = data.get("category_filter", "Tutti (Ristoranti, Negozi, Produttori & Ho.Re.Ca.)")
            except Exception as e:
                print(f"Errore caricamento configurazione: {e}")

    def save_config(self):
        cfg_file = get_config_file()
        try:
            data = {
                "output_path": self.output_path,
                "selected_regions": self.selected_regions,
                "category_filter": self.combo_category.get() if hasattr(self, "combo_category") else ""
            }
            with open(cfg_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Errore salvataggio configurazione: {e}")

    def get_region_summary_text(self):
        n = len(self.selected_regions)
        if n == 20:
            return "Selezionate: Tutte le 20 Regioni Italiane"
        elif n == 1:
            return f"Regione selezionata: {self.selected_regions[0]}"
        elif n <= 4:
            return f"Regioni selezionate ({n}): {', '.join(self.selected_regions)}"
        else:
            first_few = ", ".join(self.selected_regions[:3])
            return f"Regioni selezionate ({n}): {first_few} e altre {n - 3} regioni"

    def _refresh_province_dropdown(self):
        prov_options = get_provinces_for_regions(self.selected_regions)
        self.combo_province.configure(values=prov_options)
        if self.combo_province.get() not in prov_options:
            self.combo_province.set("Tutte le Province")

    def on_combo_region_changed(self, choice):
        if choice == "Tutte le 20 Regioni (Italia)":
            self.selected_regions = list(ALL_ITALIAN_REGIONS)
        elif choice in MACRO_REGIONS:
            self.selected_regions = list(MACRO_REGIONS[choice])
        elif choice in ALL_ITALIAN_REGIONS:
            self.selected_regions = [choice]
        self.lbl_selected_summary.configure(text=self.get_region_summary_text())
        self._refresh_province_dropdown()
        self.save_config()

    def on_category_changed(self, choice):
        self.save_config()

    def open_multi_region_dialog(self):
        MultiRegionDialog(self, self.selected_regions, self.on_multi_region_confirmed)

    def on_multi_region_confirmed(self, selected):
        self.selected_regions = selected
        n = len(selected)
        if n == 20:
            self.combo_region.set("Tutte le 20 Regioni (Italia)")
        elif n == 1:
            self.combo_region.set(selected[0])
        else:
            matched_macro = None
            for m_name, m_list in MACRO_REGIONS.items():
                if set(selected) == set(m_list):
                    matched_macro = m_name
                    break
            if matched_macro:
                self.combo_region.set(matched_macro)
            else:
                self.combo_region.set(f"Personalizzata ({n} regioni)")
        self.lbl_selected_summary.configure(text=self.get_region_summary_text())
        self._refresh_province_dropdown()
        self.save_config()

    def choose_folder(self):
        folder = filedialog.askdirectory(initialdir=self.output_path)
        if folder:
            self.output_path = folder
            self.lbl_folder.configure(text=self.output_path)
            self.save_config()

    def start_extraction(self):
        if not self.selected_regions:
            messagebox.showwarning("Attenzione", "Selezionare almeno una regione.")
            return

        category_filter = self.combo_category.get().strip()
        province_code = parse_selected_province_code(self.combo_province.get())
        enable_bilancio = self.var_bilancio.get()
        enable_social = self.var_social_affinity.get()
        split_prov = self.var_split_prov.get()

        is_only_shops = "negozi" in category_filter.lower() and "tutti" not in category_filter.lower()
        is_only_restaurants = "ristoranti" in category_filter.lower() and "tutti" not in category_filter.lower() and "negozi" not in category_filter.lower()

        sources = []
        if not is_only_shops:
            if self.var_michelin.get():
                sources.append(MichelinScraper())
            if self.var_espresso.get():
                sources.append(EspressoScraper())

        if not is_only_restaurants:
            if self.var_golosario.get():
                sources.append(GolosarioScraper())

        if self.var_gambero.get():
            sources.append(GamberoRossoScraper())
        if self.var_slowfood.get():
            sources.append(SlowFoodScraper())
        if self.var_eccellenze.get():
            sources.append(EccellenzeScraper())
        if self.var_social_discovery.get():
            sources.append(SocialDiscoveryScraper())

        if not sources:
            messagebox.showwarning("Attenzione", "Selezionare almeno una fonte compatibile con la categoria scelta.")
            return

        self.btn_run.configure(state="disabled")
        self.progressbar.set(0)
        self.save_config()

        thread = threading.Thread(
            target=self.run_scrapers_v2,
            args=(list(self.selected_regions), sources, category_filter, province_code, enable_bilancio, enable_social, split_prov)
        )
        thread.start()

    def run_scrapers_v2(self, regions, sources, category_filter, province_code, enable_bilancio, enable_social, split_prov):
        all_leads = []
        total_steps = len(regions) * len(sources)
        current_step = 0

        self.update_status("Avvio motore d'estrazione invisibile V2...")
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=['--disable-blink-features=AutomationControlled']
                )
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                    viewport={"width": 1920, "height": 1080}
                )
                page = context.new_page()

                for r_idx, region in enumerate(regions):
                    for scraper in sources:
                        prov_tag = f" (Prov: {province_code})" if province_code else ""
                        self.update_status(f"[{region}{prov_tag} {r_idx+1}/{len(regions)}] Estrazione da {scraper.source_name}...")
                        try:
                            # Supporta i parametri extra per gli scraper V2
                            if isinstance(scraper, (EccellenzeScraper, SocialDiscoveryScraper)):
                                leads = scraper.scrape(region, page, category_filter=category_filter, province_filter=province_code)
                            elif isinstance(scraper, SlowFoodScraper):
                                leads = scraper.scrape(region, page, category_filter=category_filter)
                            else:
                                leads = scraper.scrape(region, page)

                            for item in leads:
                                if not item.get("Regione"):
                                    item["Regione"] = region
                                if not item.get("Provincia"):
                                    item["Provincia"] = extract_province(
                                        item.get("Citta", ""), item.get("Indirizzo", ""), region
                                    )
                            all_leads.extend(leads)
                        except Exception as e:
                            print(f"Errore su {region} - {scraper.source_name}: {e}")

                        current_step += 1
                        self.update_progress((current_step / total_steps) * 0.65)

                browser.close()
        except Exception as e:
            self.update_status("Errore nell'avvio del browser.")
            print(f"Playwright error: {e}")
            self.after(0, lambda err=e: messagebox.showerror("Errore Browser", f"Errore nell'avvio del browser: {str(err)}"))
            self.after(0, lambda: self.btn_run.configure(state="normal"))
            return

        # Pre-filtraggio geografico rigoroso per Regione e Provincia
        from utils.geo_utils import get_region_province_codes
        valid_region_prov_map = {reg: set(get_region_province_codes(reg)) for reg in regions}
        all_allowed_provs = set()
        for p_set in valid_region_prov_map.values():
            all_allowed_provs.update(p_set)

        filtered_geo_leads = []
        for l in all_leads:
            l_prov = (l.get("Provincia") or "").upper().strip()
            l_reg = l.get("Regione", "")

            # Se la provincia è ancora vuota o non valida, tenta ri-estrazione con la regione del lead
            if not l_prov or (all_allowed_provs and l_prov not in all_allowed_provs):
                l_prov = extract_province(l.get("Citta", ""), l.get("Indirizzo", ""), l_reg)
                if l_prov:
                    l["Provincia"] = l_prov

            # Se province_code è selezionato (es. 'PZ'), accetta solo quella provincia
            if province_code:
                if l_prov != province_code.upper():
                    continue
            else:
                # Se è 'Tutte le Province' della/e regione/i selezionate, scarta i lead che cadono fuori regione
                if all_allowed_provs and l_prov and l_prov not in all_allowed_provs:
                    continue

            filtered_geo_leads.append(l)

        all_leads = filtered_geo_leads

        unique_leads = []
        seen_keys = set()
        for l in all_leads:
            k = f"{str(l.get('Nome', '')).lower().strip()}_{str(l.get('Citta', '')).lower().strip()}"
            if k not in seen_keys and l.get("Nome"):
                seen_keys.add(k)
                unique_leads.append(l)
        all_leads = unique_leads

        # Fase 2: Arricchimento Parallelo Bilanci (UfficioCamerale) & Social Intelligence (Parmigiano Reggiano)
        if all_leads and (enable_bilancio or enable_social):
            total_l = len(all_leads)
            self.update_status(f"Arricchimento Bilanci Camerali e Social Intelligence su {total_l} lead...")
            completed_l = 0

            def _enrich_worker(lead_item):
                return PhoneEnricher.enrich_v2_deep(
                    lead_item,
                    enable_financial=enable_bilancio,
                    enable_social=enable_social
                )

            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(_enrich_worker, item) for item in all_leads]
                for fut in as_completed(futures):
                    completed_l += 1
                    if completed_l % 3 == 0 or completed_l == total_l:
                        self.update_status(f"Analisi Bilanci e Social Parmigiano: {completed_l}/{total_l} lead completati...")
                        self.update_progress(0.65 + 0.30 * (completed_l / total_l))

        self.update_status("Generazione file Excel V2 con divisione per Province...")

        if all_leads:
            processor = DataProcessor()
            prov_suffix = f"_Prov_{province_code}" if province_code else ""
            if len(regions) == 1:
                clean_name = regions[0].replace(' ', '_').replace("'", "")
                file_name = f"Leads_{clean_name}{prov_suffix}.xlsx"
            elif len(regions) == 20:
                file_name = f"Leads_Italia_Tutte_Le_Regioni{prov_suffix}.xlsx"
            else:
                file_name = f"Leads_Multiregione_{len(regions)}_Regioni{prov_suffix}.xlsx"

            full_path = os.path.join(self.output_path, file_name)

            try:
                saved_path = processor.process_and_save(
                    all_leads,
                    full_path,
                    category_filter=category_filter,
                    province_filter=province_code,
                    split_by_province=split_prov,
                    allowed_regions=regions
                )
                if saved_path:
                    self.update_status(f"Completato! Salvati lead qualificati in {os.path.basename(saved_path)}.")
                    self.after(0, lambda p=saved_path: messagebox.showinfo(
                        "Estrazione V2 Completata",
                        f"Estrazione e arricchimento V2 completati con successo!\n\nFile salvato in:\n{p}"
                    ))
                else:
                    self.update_status("Nessun lead corrispondente ai filtri.")
                    self.after(0, lambda: messagebox.showinfo("Risultato", "Nessun lead trovato corrispondente ai filtri specificati."))
            except Exception as e:
                self.update_status("Errore nel salvataggio del file Excel.")
                self.after(0, lambda err=e: messagebox.showerror("Errore", str(err)))
        else:
            self.update_status("Nessun lead estratto.")
            self.after(0, lambda: messagebox.showinfo("Risultato", "Nessun lead trovato per la selezione impostata."))

        self.after(0, lambda: self.btn_run.configure(state="normal"))
        self.update_progress(1)

    def update_status(self, text):
        self.after(0, lambda: self.lbl_status.configure(text=text))

    def update_progress(self, value):
        self.after(0, lambda: self.progressbar.set(value))


if __name__ == "__main__":
    app = App()
    app.mainloop()
