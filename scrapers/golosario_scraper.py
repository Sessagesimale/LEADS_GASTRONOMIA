from typing import List, Dict
import time
import json
import html
import re
from scrapers.base_scraper import BaseScraper
from utils.enricher import PhoneEnricher

class GolosarioScraper(BaseScraper):
    def __init__(self):
        self.source_name = "Il Golosario"
        self.base_url = "https://www.ilgolosario.it"

    def scrape(self, region: str, page: 'playwright.sync_api.Page') -> List[Dict[str, str]]:
        clean_reg = region.lower().strip()
        golosario_regions = {
            "abruzzo": "abruzzo",
            "basilicata": "basilicata",
            "calabria": "calabria",
            "campania": "campania",
            "emilia-romagna": "emilia%20romagna",
            "friuli-venezia giulia": "friuli%20venezia%20giulia",
            "lazio": "lazio",
            "liguria": "liguria",
            "lombardia": "lombardia",
            "marche": "marche",
            "molise": "molise",
            "piemonte": "piemonte",
            "puglia": "puglia",
            "sardegna": "sardegna",
            "sicilia": "sicilia",
            "toscana": "toscana",
            "trentino-alto adige": "trentino",
            "umbria": "umbria",
            "valle d'aosta": "valle%20d'aosta",
            "veneto": "veneto"
        }
        formatted_region = golosario_regions.get(clean_reg, clean_reg.replace(" ", "%20"))
        
        # Categorie specifiche per alta gastronomia e vendita formaggi (evitando agriturismi generici)
        categories = [
            ("boutique%20del%20formaggio", "Boutique del Formaggio"),
            ("gastronomia", "Gastronomia"),
            ("boutique%20del%20gusto", "Boutique del Gusto")
        ]
        
        leads = []
        seen_names = set()
        
        for cat_slug, cat_label in categories:
            url = f"{self.base_url}/mosaic/it/negozi/{formatted_region}/{cat_slug}"
            try:
                print(f"[{self.source_name}] Navigo verso {cat_label}: {url}")
                page.goto(url, timeout=25000, wait_until="domcontentloaded")
                page.wait_for_timeout(2000)
                
                cards = page.locator('.col-md-3.negozi, .wrapperanagrafica').all()
                print(f"[{self.source_name}] Trovate {len(cards)} schede per {cat_label}")
                
                for card in cards:
                    try:
                        anagrafica = card.locator('.wrapperanagrafica').first if card.locator('.wrapperanagrafica').count() > 0 else card
                        data_obj_raw = anagrafica.get_attribute('data-obj')
                        
                        name = ""
                        address = ""
                        city = ""
                        website = ""
                        
                        if data_obj_raw:
                            data = json.loads(html.unescape(data_obj_raw))
                            name = data.get("title", "").strip()
                            address = data.get("street", "") or data.get("address", "")
                            city = data.get("city", "").strip()
                            path = data.get("path", "")
                            if path:
                                website = f"{self.base_url}{path}" if path.startswith('/') else path
                        else:
                            h3 = card.locator('h3').first
                            if h3.count() > 0:
                                name = h3.inner_text().strip()
                                
                        if not name or name in seen_names:
                            continue
                            
                        # Filtro per escludere agriturismi e tutto il perimetro dolciario (gelaterie, cremerie, cioccolaterie, pasticcerie, ecc.)
                        sweet_terms = ["gelater", "cremer", "cioccolat", "pasticc", "dolc", "confett", "torron", "biscott"]
                        if any(term in name.lower() for term in ["agriturismo", "azienda agricola", "fattoria"] + sweet_terms):
                            continue
                            
                        seen_names.add(name)
                        
                        # Estrazione telefono presente nella card
                        inner_html = card.evaluate("el => el.innerHTML")
                        phones = re.findall(r'telefono["\s>:]*([0-9\s+-]{7,15})', inner_html, re.IGNORECASE)
                        phone = phones[0].strip() if phones else ""
                        
                        from utils.geo_utils import extract_province
                        prov = extract_province(city, address, region)
                        
                        lead = {
                            "Nome": name,
                            "Tipologia": "Negozio / Gastronomia",
                            "Regione": region,
                            "Provincia": prov,
                            "Indirizzo": address,
                            "Citta": city,
                            "Telefono": phone,
                            "Email": "",
                            "Sito Web": website,
                            "Link Pagina": website if website else url,
                            "Fonte": self.source_name
                        }
                        
                        lead = PhoneEnricher.enrich(lead, page)
                        leads.append(lead)
                    except Exception as e:
                        pass
                        
            except Exception as e:
                print(f"Errore su {url}: {e}")
                
        print(f"[{self.source_name}] Totale negozi gourmet estratti: {len(leads)}")
        return leads
