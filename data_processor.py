import pandas as pd
from typing import List, Dict
import os
from openpyxl.styles import PatternFill, Font, Alignment
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.utils import get_column_letter

class DataProcessor:
    def __init__(self):
        pass
        
    def process_and_save(self, leads: List[Dict[str, str]], output_path: str, category_filter: str = "Tutti"):
        if not leads:
            print("Nessun lead da salvare.")
            return None
            
        df = pd.DataFrame(leads)
        
        # Filtro per escludere rigorosamente il perimetro dolciario (gelaterie, cremerie, cioccolaterie, pasticcerie, ecc.)
        sweet_terms = ["gelater", "cremer", "cioccolat", "pasticc", "dolc", "confett", "torron", "biscott"]
        pattern = "|".join(sweet_terms)
        df = df[~df["Nome"].astype(str).str.lower().str.contains(pattern, na=False, regex=True)]
        
        # Filtro Tipologia (Ristoranti vs Negozi/Altro)
        if "Tipologia" not in df.columns:
            df["Tipologia"] = "Ristorante"
            
        if "ristoranti" in category_filter.lower() and "tutti" not in category_filter.lower() and "negozi" not in category_filter.lower():
            df = df[df["Tipologia"].astype(str).str.lower() == "ristorante"]
        elif "negozi" in category_filter.lower() and "tutti" not in category_filter.lower():
            df = df[df["Tipologia"].astype(str).str.lower() != "ristorante"]
            
        if df.empty:
            print("Nessun lead corrispondente ai filtri impostati.")
            return None
        
        # Pulizia e rimozione duplicati basati su Nome e Citta
        df = df.drop_duplicates(subset=["Nome", "Citta"], keep="first")
            
        # Gestione Link: se Sito Web o Link Pagina sono vuoti, usa l'altro come fallback così il link è sempre presente
        if "Link Pagina" not in df.columns:
            df["Link Pagina"] = df.get("Sito Web", "")
        if "Sito Web" not in df.columns:
            df["Sito Web"] = df.get("Link Pagina", "")
            
        df["Sito Web"] = df["Sito Web"].fillna("").astype(str)
        df["Link Pagina"] = df["Link Pagina"].fillna("").astype(str)
        
        # Se uno dei due è vuoto, copia l'altro
        df.loc[df["Sito Web"].str.strip() == "", "Sito Web"] = df["Link Pagina"]
        df.loc[df["Link Pagina"].str.strip() == "", "Link Pagina"] = df["Sito Web"]
            
        df["Esito Valutazione"] = ""
        df["Note Commerciali"] = ""
        
        # Ordine desiderato delle colonne (con Regione se disponibile)
        desired_columns = [
            "Nome", "Tipologia", "Regione", "Citta", "Indirizzo", "Telefono", 
            "Email", "Sito Web", "Link Pagina", "Fonte", 
            "Esito Valutazione", "Note Commerciali"
        ]
        for col in desired_columns:
            if col not in df.columns:
                df[col] = ""
        df = df[desired_columns]
        
        # Salvataggio in Excel con gestione automatica file aperto/bloccato
        actual_output_path = output_path
        base, ext = os.path.splitext(output_path)
        counter = 1
        
        while counter <= 10:
            try:
                with pd.ExcelWriter(actual_output_path, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='Leads Gastronomici')
                    workbook = writer.book
                    worksheet = writer.sheets['Leads Gastronomici']
                    
                    # Formattazione intestazione
                    header_fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
                    header_font = Font(color="FFFFFF", bold=True)
                    
                    for cell in worksheet[1]:
                        cell.fill = header_fill
                        cell.font = header_font
                        cell.alignment = Alignment(horizontal="center", vertical="center")
                        
                    # Auto-adattamento larghezza colonne
                    for column_cells in worksheet.columns:
                        length = max(len(str(cell.value)) for cell in column_cells)
                        col_letter = column_cells[0].column_letter
                        worksheet.column_dimensions[col_letter].width = min(length + 2, 50) # max width 50
                        
                    # Data Validation (Menu a tendina per Esito Valutazione)
                    val_col_idx = df.columns.get_loc("Esito Valutazione") + 1
                    val_col_letter = get_column_letter(val_col_idx)
                    
                    dv = DataValidation(type="list", formula1='"Da contattare,Contattato,Scartato - Non in target"', allow_blank=True)
                    worksheet.add_data_validation(dv)
                    
                    # Applica data validation alla colonna Esito
                    dv.add(f"{val_col_letter}2:{val_col_letter}1048576")
                    
                print(f"File salvato con successo in: {actual_output_path}")
                return actual_output_path
            except PermissionError:
                actual_output_path = f"{base}_{counter}{ext}"
                counter += 1
            except Exception as e:
                print(f"Errore durante il salvataggio: {e}")
                raise e
        return actual_output_path
