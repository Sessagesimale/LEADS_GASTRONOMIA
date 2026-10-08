from typing import List, Dict
import time
from scrapers.base_scraper import BaseScraper
import re

class MichelinScraper(BaseScraper):
    def __init__(self):
        self.source_name = "Guida Michelin"
        self.base_url = "https://guide.michelin.com"

    def scrape(self, region: str, page: 'playwright.sync_api.Page') -> List[Dict[str, str]]:
        # La regione deve essere formattata per l'URL (es. "valle-d-aosta", "emilia-romagna")
        formatted_region = region.lower().replace("'", "-").replace("’", "-").replace(" ", "-").strip()
        url = f"{self.base_url}/it/it/{formatted_region}/ristoranti"
        
        leads = []
        current_page = 1
        max_pages = 2 # Limitiamo a 2 per ora, altrimenti ci mette troppo nell'esempio
        
        while current_page <= max_pages:
            try:
                page_url = f"{url}/page/{current_page}" if current_page > 1 else url
                print(f"[{self.source_name}] Navigo verso: {page_url}")
                page.goto(page_url, timeout=30000, wait_until="domcontentloaded")
                time.sleep(2) # attesa caricamento dinamico
                
                # Se appare la pagina del challenge di AWS, Playwright potrebbe gestirlo se impostato, 
                # ma se ci blocca dobbiamo gestire l'errore o aspettare.
                if "challenge" in page.url or "captcha" in page.url:
                    print("Trovato blocco WAF/Captcha, provo ad attendere...")
                    time.sleep(5)
                
                # Trova tutti i link dei ristoranti
                restaurant_links = []
                cards = page.locator('.card__menu-content--title a').all()
                for card in cards:
                    href = card.get_attribute('href')
                    if href:
                        # Assicura che il ristorante appartenga alla regione cercata (Michelin include consigli da altre regioni in fondo alla pagina)
                        if f"/{formatted_region}/" not in href:
                            continue
                        restaurant_links.append(self.base_url + href)
                        
                if not restaurant_links:
                    print("Nessun ristorante trovato o fine risultati.")
                    break
                
                for detail_url in restaurant_links:
                    lead = self._scrape_detail(detail_url, page)
                    if lead:
                        leads.append(lead)
                    time.sleep(1) # Rispetto per il server
                    
                current_page += 1
                
            except Exception as e:
                print(f"Errore su {page_url}: {e}")
                break
                
        return leads

    def _scrape_detail(self, url: str, page: 'playwright.sync_api.Page') -> Dict[str, str]:
        try:
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            time.sleep(1)
            
            name = "Sconosciuto"
            if page.locator('h1').count() > 0:
                name = page.locator('h1').first.inner_text().strip()
                
            address = ""
            if page.locator('.data-sheet__block--text').count() > 0:
                address = page.locator('.data-sheet__block--text').first.inner_text().strip()
            
            city = ""
            if address:
                parts = [p.strip() for p in address.split(',') if p.strip()]
                if parts:
                    if parts[-1].lower() == "italia" and len(parts) > 1:
                        candidate = parts[-2]
                        if re.match(r'^\d{4,5}$', candidate) and len(parts) >= 3:
                            city = parts[-3]
                        else:
                            city = candidate
                    else:
                        city = parts[-1]
                    
            phone = ""
            if page.locator('a[href^="tel:"]').count() > 0:
                phone = page.locator('a[href^="tel:"]').first.inner_text().strip()
                if not phone:
                    href = page.locator('a[href^="tel:"]').first.get_attribute('href')
                    if href:
                        phone = href.replace("tel:", "").strip()
                
            email = ""
            if page.locator('a[href^="mailto:"]').count() > 0:
                email_href = page.locator('a[href^="mailto:"]').first.get_attribute('href')
                if email_href:
                    email = email_href.replace("mailto:", "").strip()
            
            website = ""
            if page.locator('a[data-event-type="website"]').count() > 0:
                website_href = page.locator('a[data-event-type="website"]').first.get_attribute('href')
                if website_href:
                    website = website_href.strip()
            
            sweet_terms = ["gelater", "cremer", "cioccolat", "pasticc", "dolc", "confett", "torron", "biscott"]
            if any(term in name.lower() for term in sweet_terms):
                return {}
            
            lead = {
                "Nome": name,
                "Tipologia": "Ristorante",
                "Indirizzo": address,
                "Citta": city,
                "Telefono": phone,
                "Email": email,
                "Sito Web": website if website else url,
                "Link Pagina": url,
                "Fonte": self.source_name
            }
            
            from utils.enricher import PhoneEnricher
            return PhoneEnricher.enrich(lead, page)
        except Exception as e:
            print(f"Errore dettaglio {url}: {e}")
            return {}
