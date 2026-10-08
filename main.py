import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
import os
import sys
import json
import time
from scrapers.michelin_scraper import MichelinScraper
from scrapers.golosario_scraper import GolosarioScraper
from scrapers.gambero_rosso_scraper import GamberoRossoScraper
from scrapers.espresso_scraper import EspressoScraper
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
        
        # Center dialog
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - 210
        y = parent.winfo_y() + (parent.winfo_height() // 2) - 260
        self.geometry(f"+{max(0, x)}+{max(0, y)}")
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        
        lbl = ctk.CTkLabel(self, text="Seleziona le Regioni da estrarre", font=ctk.CTkFont(size=16, weight="bold"))
        lbl.grid(row=0, column=0, padx=15, pady=(15, 10))
        
        # Macro buttons
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
        
        # Scrollable list of regions
        self.scroll_frame = ctk.CTkScrollableFrame(self, height=300)
        self.scroll_frame.grid(row=2, column=0, padx=15, pady=0, sticky="nsew")
        
        self.region_vars = {}
        for reg in ALL_ITALIAN_REGIONS:
            var = ctk.BooleanVar(value=(reg in current_selected))
            chk = ctk.CTkCheckBox(self.scroll_frame, text=reg, variable=var)
            chk.pack(anchor="w", padx=10, pady=4)
            self.region_vars[reg] = var
            
        # Bottom confirm button
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
        
        self.title("Gastronomy Leads Agent - Parmigiano Reggiano")
        self.geometry("640x660")
        self.minsize(600, 620)
        
        # Icon setup
        self.setup_icon()
        
        # State
        self.selected_regions = ["Valle d'Aosta"]
        self.output_path = self.get_default_output_dir()
        
        # Load persistent configuration
        self.load_config()
        
        # Grid layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(6, weight=1)
        
        # Title
        self.lbl_title = ctk.CTkLabel(
            self, 
            text="Estrattore Lead Gastronomici", 
            font=ctk.CTkFont(size=21, weight="bold")
        )
        self.lbl_title.grid(row=0, column=0, padx=20, pady=(15, 8))
        
        # 1. Region selection frame
        self.frame_region = ctk.CTkFrame(self)
        self.frame_region.grid(row=1, column=0, padx=20, pady=6, sticky="ew")
        
        self.lbl_region_tag = ctk.CTkLabel(self.frame_region, text="Regione / Territorio:", font=ctk.CTkFont(weight="bold"))
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
            width=320,
            command=self.on_combo_region_changed
        )
        if len(self.selected_regions) == 1 and self.selected_regions[0] in ALL_ITALIAN_REGIONS:
            self.combo_region.set(self.selected_regions[0])
        elif len(self.selected_regions) == 20:
            self.combo_region.set("Tutte le 20 Regioni (Italia)")
        else:
            self.combo_region.set(f"Personalizzata ({len(self.selected_regions)} regioni)")
            
        self.combo_region.pack(side="left", fill="x", expand=True, padx=(0, 10), pady=4)
        
        self.btn_multi_region = ctk.CTkButton(
            self.frame_region_controls, 
            text="Personalizza...", 
            width=130, 
            command=self.open_multi_region_dialog
        )
        self.btn_multi_region.pack(side="left", pady=4)
        
        self.lbl_selected_summary = ctk.CTkLabel(
            self.frame_region, 
            text=self.get_region_summary_text(), 
            text_color="gray70",
            font=ctk.CTkFont(size=12)
        )
        self.lbl_selected_summary.pack(anchor="w", padx=15, pady=(0, 8))
        
        # 2. Category / Tipologia Filter frame
        self.frame_category = ctk.CTkFrame(self)
        self.frame_category.grid(row=2, column=0, padx=20, pady=6, sticky="ew")
        
        self.lbl_cat = ctk.CTkLabel(self.frame_category, text="Tipologia / Categoria Attività:", font=ctk.CTkFont(weight="bold"))
        self.lbl_cat.pack(anchor="w", padx=15, pady=(8, 2))
        
        self.cat_options = [
            "Tutti (Ristoranti e Negozi)",
            "Solo Ristoranti",
            "Solo Negozi / Botteghe Gastronomiche"
        ]
        self.combo_category = ctk.CTkComboBox(
            self.frame_category,
            values=self.cat_options,
            state="readonly",
            width=360,
            command=self.on_category_changed
        )
        self.combo_category.set(self.saved_category if hasattr(self, 'saved_category') and self.saved_category in self.cat_options else self.cat_options[0])
        self.combo_category.pack(fill="x", padx=15, pady=(0, 8))
        
        # 3. Source Selection Frame
        self.frame_sources = ctk.CTkFrame(self)
        self.frame_sources.grid(row=3, column=0, padx=20, pady=6, sticky="ew")
        
        self.lbl_sources = ctk.CTkLabel(self.frame_sources, text="Fonti di Ricerca:", font=ctk.CTkFont(weight="bold"))
        self.lbl_sources.grid(row=0, column=0, columnspan=2, padx=15, pady=(8, 4), sticky="w")
        
        self.var_michelin = ctk.BooleanVar(value=True)
        self.chk_michelin = ctk.CTkCheckBox(self.frame_sources, text="Guida Michelin (Ristoranti)", variable=self.var_michelin)
        self.chk_michelin.grid(row=1, column=0, padx=20, pady=3, sticky="w")
        
        self.var_golosario = ctk.BooleanVar(value=True)
        self.chk_golosario = ctk.CTkCheckBox(self.frame_sources, text="Il Golosario (Botteghe & Formaggerie)", variable=self.var_golosario)
        self.chk_golosario.grid(row=1, column=1, padx=20, pady=3, sticky="w")
        
        self.var_gambero = ctk.BooleanVar(value=True)
        self.chk_gambero = ctk.CTkCheckBox(self.frame_sources, text="Gambero Rosso (Ristoranti & Locali)", variable=self.var_gambero)
        self.chk_gambero.grid(row=2, column=0, padx=20, pady=3, sticky="w")
        
        self.var_espresso = ctk.BooleanVar(value=True)
        self.chk_espresso = ctk.CTkCheckBox(self.frame_sources, text="Le Guide de L'Espresso (Ristoranti)", variable=self.var_espresso)
        self.chk_espresso.grid(row=2, column=1, padx=20, pady=(3, 8), sticky="w")
        
        # 4. Output Folder Frame
        self.frame_output = ctk.CTkFrame(self)
        self.frame_output.grid(row=4, column=0, padx=20, pady=6, sticky="ew")
        
        self.btn_folder = ctk.CTkButton(self.frame_output, text="Scegli Cartella Salvataggio", command=self.choose_folder)
        self.btn_folder.pack(side="left", padx=12, pady=10)
        
        self.lbl_folder = ctk.CTkLabel(self.frame_output, text=self.output_path, anchor="w")
        self.lbl_folder.pack(side="left", fill="x", expand=True, padx=(5, 12), pady=10)
        
        # 5. Run Button
        self.btn_run = ctk.CTkButton(
            self, 
            text="Avvia Estrazione Lead", 
            command=self.start_extraction, 
            height=42,
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.btn_run.grid(row=5, column=0, padx=20, pady=12, sticky="ew")
        
        # 6. Progress and Status
        self.frame_status = ctk.CTkFrame(self)
        self.frame_status.grid(row=6, column=0, padx=20, pady=(0, 15), sticky="nsew")
        
        self.lbl_status = ctk.CTkLabel(self.frame_status, text="Pronto all'estrazione (Browser invisibile attivo)", font=ctk.CTkFont(size=13))
        self.lbl_status.pack(pady=(8, 2))
        
        self.progressbar = ctk.CTkProgressBar(self.frame_status)
        self.progressbar.pack(fill="x", padx=20, pady=(5, 8))
        self.progressbar.set(0)

    def setup_icon(self):
        if getattr(sys, 'frozen', False):
            base_dir = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
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
                    self.saved_category = data.get("category_filter", "Tutti (Ristoranti e Negozi)")
            except Exception as e:
                print(f"Errore caricamento configurazione: {e}")

    def save_config(self):
        cfg_file = get_config_file()
        try:
            data = {
                "output_path": self.output_path,
                "selected_regions": self.selected_regions,
                "category_filter": self.combo_category.get() if hasattr(self, 'combo_category') else "Tutti (Ristoranti e Negozi)"
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

    def on_combo_region_changed(self, choice):
        if choice == "Tutte le 20 Regioni (Italia)":
            self.selected_regions = list(ALL_ITALIAN_REGIONS)
        elif choice in MACRO_REGIONS:
            self.selected_regions = list(MACRO_REGIONS[choice])
        elif choice in ALL_ITALIAN_REGIONS:
            self.selected_regions = [choice]
        self.lbl_selected_summary.configure(text=self.get_region_summary_text())
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
        
        # Optimize sources according to category filter
        sources = []
        is_only_shops = "negozi" in category_filter.lower() and "tutti" not in category_filter.lower()
        is_only_restaurants = "ristoranti" in category_filter.lower() and "tutti" not in category_filter.lower() and "negozi" not in category_filter.lower()
        
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
            
        if not sources:
            messagebox.showwarning("Attenzione", "Nessuna fonte attiva per la categoria selezionata.")
            return
            
        self.btn_run.configure(state="disabled")
        self.progressbar.set(0)
        self.save_config()
        
        # Run in background thread
        thread = threading.Thread(
            target=self.run_scrapers_multiregion, 
            args=(list(self.selected_regions), sources, category_filter)
        )
        thread.start()

    def run_scrapers_multiregion(self, regions, sources, category_filter):
        all_leads = []
        total_steps = len(regions) * len(sources)
        current_step = 0
        
        self.update_status("Avvio del motore browser invisibile (headless)...")
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
                    for s_idx, scraper in enumerate(sources):
                        self.update_status(f"[{region} {r_idx+1}/{len(regions)}] Estrazione da {scraper.source_name}...")
                        try:
                            leads = scraper.scrape(region, page)
                            for item in leads:
                                if not item.get("Regione"):
                                    item["Regione"] = region
                            all_leads.extend(leads)
                        except Exception as e:
                            print(f"Errore su {region} - {scraper.source_name}: {e}")
                            
                        current_step += 1
                        self.update_progress(current_step / total_steps)
                
                browser.close()
        except Exception as e:
            self.update_status("Errore nell'avvio del browser.")
            print(f"Playwright error: {e}")
            self.after(0, lambda err=e: messagebox.showerror("Errore Browser", f"Errore nell'avvio del browser: {str(err)}"))
            self.after(0, lambda: self.btn_run.configure(state="normal"))
            return
            
        self.update_status("Elaborazione, filtraggio e salvataggio file Excel...")
        
        if all_leads:
            processor = DataProcessor()
            if len(regions) == 1:
                clean_name = regions[0].replace(' ', '_').replace("'", "")
                file_name = f"Leads_{clean_name}.xlsx"
            elif len(regions) == 20:
                file_name = "Leads_Italia_Tutte_Le_Regioni.xlsx"
            else:
                file_name = f"Leads_Multiregione_{len(regions)}_Regioni.xlsx"
                
            full_path = os.path.join(self.output_path, file_name)
            
            try:
                saved_path = processor.process_and_save(all_leads, full_path, category_filter=category_filter)
                if saved_path:
                    self.update_status(f"Completato con successo! Salvati {len(all_leads)} lead.")
                    self.after(0, lambda p=saved_path: messagebox.showinfo(
                        "Estrazione Completata", 
                        f"Estrazione completata con successo!\n\nFile salvato in:\n{p}"
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
