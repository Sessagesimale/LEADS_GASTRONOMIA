from typing import List, Dict
import time
from scrapers.base_scraper import BaseScraper
import re
from utils.enricher import PhoneEnricher

class GamberoRossoScraper(BaseScraper):
    def __init__(self):
        self.source_name = "Gambero Rosso"
        self.base_url = "https://www.gamberorosso.it"

    def scrape(self, region: str, page: 'playwright.sync_api.Page') -> List[Dict[str, str]]:
        formatted_region = region.lower().strip().replace(" ", "-")
        leads = []
        restaurant_links = []
        
        try:
            # 1. Ricerca mirata dei locali per regione tramite il motore di ricerca di Gambero Rosso
            clean_search = region.lower().replace("'", " ").replace("-", " ").strip()
            if "valle" in clean_search:
                search_terms = ["locali", "aosta"]
            else:
                search_terms = ["locali"] + clean_search.split()
            url = f"{self.base_url}/?s={'+'.join(search_terms)}"
            print(f"[{self.source_name}] Navigo verso: {url}")
            page.goto(url, timeout=25000, wait_until="domcontentloaded")
            page.wait_for_timeout(2500)
            
            sweet_terms = ['gelater', 'pasticc', 'caffebar', 'caffe-bar', 'cioccolat', 'cremer', 'dolc', 'confett', 'torron', 'biscott']
            
            cards = page.locator('a[href*="/luoghi/locali/"]').all()
            for card in cards:
                href = card.get_attribute('href')
                if href and '/luoghi/locali/' in href and href.count('/') >= 5:
                    if any(term in href.lower() for term in sweet_terms):
                        continue
                    full_href = href if href.startswith('http') else self.base_url + href
                    if full_href not in restaurant_links:
                        restaurant_links.append(full_href)
                        
            # Se la ricerca 'locali' restituisce pochi risultati, prova la pagina canonica
            if len(restaurant_links) < 5:
                alt_url = f"{self.base_url}/ristoranti/{formatted_region}/"
                try:
                    page.goto(alt_url, timeout=20000, wait_until="domcontentloaded")
                    page.wait_for_timeout(2000)
                    for card in page.locator('a[href*="/luoghi/locali/"], a[href*="/locali/"]').all():
                        h = card.get_attribute('href')
                        if h and h.count('/') >= 5:
                            if any(term in h.lower() for term in sweet_terms):
                                continue
                            fh = h if h.startswith('http') else self.base_url + h
                            if fh not in restaurant_links:
                                restaurant_links.append(fh)
                except Exception:
                    pass
                    
            print(f"[{self.source_name}] Trovati {len(restaurant_links)} locali salati/gastronomici per {region}.")
            
            # Limita a 25 per bilanciare completezza e velocità
            for detail_url in restaurant_links[:25]:
                lead = self._scrape_detail(detail_url, page)
                if lead and lead.get("Nome") and lead.get("Nome") != "Sconosciuto":
                    leads.append(lead)
                time.sleep(1)
                
        except Exception as e:
            print(f"[{self.source_name}] Errore su {region}: {e}")
            
        print(f"[{self.source_name}] Estratti {len(leads)} lead con successo.")
        return leads

    def _scrape_detail(self, url: str, page: 'playwright.sync_api.Page') -> Dict[str, str]:
        try:
            sweet_terms = ['gelater', 'cremer', 'cioccolat', 'pasticc', 'dolc', 'confett', 'torron', 'biscott']
            if any(term in url.lower() for term in sweet_terms):
                return {}

            page.goto(url, timeout=25000, wait_until="domcontentloaded")
            page.wait_for_timeout(1500)
            
            name = "Sconosciuto"
            if page.locator('meta[property="og:title"]').count() > 0:
                og_title = page.locator('meta[property="og:title"]').first.get_attribute('content')
                if og_title:
                    name = og_title.split('-')[0].split('|')[0].strip()
            if name == "Sconosciuto" and page.locator('h1').count() > 0:
                for h in page.locator('h1').all():
                    txt = h.inner_text().strip()
                    if txt and "gamberorosso" not in txt.lower():
                        name = txt
                        break
            if name == "Sconosciuto":
                title_txt = page.title()
                if title_txt and "ci siamo quasi" not in title_txt.lower():
                    name_candidate = title_txt.split('-')[0].split('|')[0].strip()
                    if name_candidate and "gambero rosso" not in name_candidate.lower():
                        name = name_candidate
                        
            if any(term in name.lower() for term in sweet_terms):
                return {}
                
            address = ""
            city = ""
            # Cerca l'indirizzo nei vari blocchi di Gambero Rosso escludendo footer / privacy
            for h in page.locator('.elementor-heading-title, .elementor-widget-text-editor, .address, p').all():
                txt = h.inner_text().strip()
                if any(w in txt.lower() for w in ['via ', 'corso ', 'piazza ', 'viale ', 'loc.', 'contrada ', 'vicolo ']):
                    if any(bad in txt.lower() for bad in ['privacy', 'gambero rosso', 'dpo@', 'responsabile', 'cookie', 'diritti']):
                        continue
                    address = txt
                    # Estrai città (es. "Palermo (PA)" o "Noto (SR)")
                    city_match = re.search(r'[\d\s,·\-/]+([A-Z][a-zA-Z\s\'.]+?)\s*\(([A-Z]{2})\)', address)
                    if city_match:
                        city = f"{city_match.group(1).strip()} ({city_match.group(2)})"
                    else:
                        parts = [p.strip() for p in re.split(r'[,·\-]', address) if p.strip()]
                        if parts:
                            city = parts[-1].replace(')', '').replace('(', '').strip()
                    break
                    
            phone = ""
            if page.locator('a[href^="tel:"]').count() > 0:
                phone = page.locator('a[href^="tel:"]').first.inner_text().strip()
                if not phone:
                    href = page.locator('a[href^="tel:"]').first.get_attribute('href')
                    if href:
                        phone = href.replace("tel:", "").strip()
                
            email = ""
            if page.locator('a[href^="mailto:"]').count() > 0:
                for mail_tag in page.locator('a[href^="mailto:"]').all():
                    href = mail_tag.get_attribute('href')
                    if href and '@' in href and not any(x in href.lower() for x in ['class.it', 'gamberorosso', 'privacy', 'dpo@']):
                        email = href.replace("mailto:", "").split('?')[0].strip()
                        break
            
            website = ""
            if page.locator('a[href^="http"]').count() > 0:
                for a_tag in page.locator('.contacts a, .info-block a, .elementor-widget-container a').all():
                    href = a_tag.get_attribute('href')
                    if href and not any(x in href.lower() for x in ['gamberorosso', 'facebook', 'instagram', 'google', 'twitter', 'linkedin', 'whatsapp', 'telegram']):
                        website = href.strip()
                        break
            
            tipologia = "Ristorante"
            url_lower = url.lower()
            shop_terms = ['gastronomia', 'pasta-fresca', 'panificio', 'panetteria', 'enoteca', 'bottega', 'alimentari', 'salumeria', 'formaggeria', 'pizza-a-taglio', 'street-food']
            if any(term in url_lower for term in shop_terms):
                tipologia = "Negozio / Gastronomia"
                
            lead = {
                "Nome": name,
                "Tipologia": tipologia,
                "Indirizzo": address,
                "Citta": city,
                "Telefono": phone,
                "Email": email,
                "Sito Web": website if website else url,
                "Link Pagina": url,
                "Fonte": self.source_name
            }
            
            # Se manca il telefono, arricchisci
            if not phone:
                lead = PhoneEnricher.enrich(lead, page)
                
            return lead
        except Exception as e:
            print(f"Errore dettaglio {url}: {e}")
            return {}
