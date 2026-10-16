from typing import List, Dict
import requests
from scrapers.base_scraper import BaseScraper
from utils.enricher import PhoneEnricher

class EspressoScraper(BaseScraper):
    def __init__(self):
        self.source_name = "Le Guide de L'Espresso"
        self.api_base = "https://bfc-media-api.menatcode.it"

    def scrape(self, region: str, page: 'playwright.sync_api.Page') -> List[Dict[str, str]]:
        leads = []
        try:
            print(f"[{self.source_name}] Recupero ID regione per: {region}")
            reg_res = requests.get(f"{self.api_base}/restaurants/regions", timeout=12)
            regions_data = reg_res.json().get('payload', [])
            
            region_id = None
            clean_search = region.lower().strip().replace("-", " ")
            for r in regions_data:
                r_val = r.get('value', '').lower().replace("-", " ")
                if clean_search in r_val or r_val in clean_search:
                    region_id = r.get('id')
                    break
                    
            if not region_id:
                print(f"[{self.source_name}] Nessuna regione trovata per {region}")
                return []
                
            url = f"{self.api_base}/restaurants?region_id={region_id}&per_page=100&status=published"
            print(f"[{self.source_name}] Interrogo API: {url}")
            res = requests.get(url, timeout=15)
            data = res.json()
            items = data.get('payload', {}).get('data', [])
            print(f"[{self.source_name}] Trovati {len(items)} ristoranti da L'Espresso")
            
            for item in items:
                name = item.get('name', '').strip()
                if not name:
                    continue
                    
                sweet_terms = ["gelater", "cremer", "cioccolat", "pasticc", "dolc", "confett", "torron", "biscott"]
                if any(term in name.lower() for term in sweet_terms):
                    continue
                    
                phone = (item.get('phone_number') or '').strip()
                email = (item.get('email') or '').strip()
                website = (item.get('url') or '').strip()
                if website and not website.startswith('http'):
                    website = f"https://{website}"
                    
                address = (item.get('address') or '').strip()
                city = str(item.get('location') or item.get('city') or '').strip()
                raw_prov = str(item.get('province') or '').strip()
                
                from utils.geo_utils import extract_province
                prov = extract_province(f"{city} ({raw_prov})" if raw_prov else city, address, region)
                
                slug = item.get('slug')
                page_link = f"https://guideespresso.it/ristoranti/{slug}" if slug else "https://guideespresso.it"
                
                lead = {
                    "Nome": name,
                    "Tipologia": "Ristorante",
                    "Regione": region,
                    "Provincia": prov,
                    "Indirizzo": address,
                    "Citta": city,
                    "Telefono": phone,
                    "Email": email,
                    "Sito Web": website if website else page_link,
                    "Link Pagina": page_link,
                    "Fonte": self.source_name
                }
                
                lead = PhoneEnricher.enrich(lead, page)
                leads.append(lead)
                
        except Exception as e:
            print(f"[{self.source_name}] Errore estrazione: {e}")
            
        print(f"[{self.source_name}] Estratti {len(leads)} lead con successo.")
        return leads
