from typing import List, Dict
import time
import re
from scrapers.base_scraper import BaseScraper
from utils.resilient_extractor import ResilientExtractor
from utils.geo_utils import extract_province
from utils.enricher import PhoneEnricher


class MichelinScraper(BaseScraper):
    def __init__(self):
        self.source_name = "Guida Michelin"
        self.base_url = "https://guide.michelin.com"

    def scrape(self, region: str, page: 'playwright.sync_api.Page') -> List[Dict[str, str]]:
        formatted_region = region.lower().replace("'", "-").replace("’", "-").replace(" ", "-").strip()
        url = f"{self.base_url}/it/it/{formatted_region}/ristoranti"

        leads = []
        current_page = 1
        max_pages = 2

        while current_page <= max_pages:
            try:
                page_url = f"{url}/page/{current_page}" if current_page > 1 else url
                print(f"[{self.source_name}] Navigo verso: {page_url}")
                page.goto(page_url, timeout=30000, wait_until="domcontentloaded")
                time.sleep(2)

                if "challenge" in page.url or "captcha" in page.url:
                    print("Trovato blocco WAF/Captcha, provo ad attendere...")
                    time.sleep(5)

                # Selettori multipli resilienti per i link delle schede ristorante
                restaurant_links = []
                card_selectors = [
                    '.card__menu-content--title a',
                    'h3.card__menu-content--title a',
                    'div.card__menu a.link',
                    'a[href*="/ristorante/"]'
                ]
                seen_hrefs = set()
                for sel in card_selectors:
                    cards = page.locator(sel).all()
                    if cards:
                        for card in cards:
                            href = card.get_attribute('href')
                            if href and "/ristorante/" in href:
                                if f"/{formatted_region}/" not in href:
                                    continue
                                full_u = href if href.startswith("http") else (self.base_url + href)
                                if full_u not in seen_hrefs:
                                    seen_hrefs.add(full_u)
                                    restaurant_links.append(full_u)
                        if restaurant_links:
                            break

                if not restaurant_links:
                    print("Nessun ristorante trovato o fine risultati.")
                    break

                for detail_url in restaurant_links:
                    lead = self._scrape_detail(detail_url, page, region)
                    if lead:
                        leads.append(lead)
                    time.sleep(0.8)

                current_page += 1

            except Exception as e:
                print(f"Errore su {page_url}: {e}")
                break

        return leads

    def _scrape_detail(self, url: str, page: 'playwright.sync_api.Page', region: str = "") -> Dict[str, str]:
        try:
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            time.sleep(0.8)

            html_content = page.content()

            # LIVELLO 1: Estrazione da JSON-LD (Schema.org Restaurant)
            json_ld = ResilientExtractor.extract_json_ld(html_content)

            # LIVELLO 2: Cascata di Selettori CSS Multipli
            name = json_ld["Nome"] or ResilientExtractor.first_text_from_selectors(
                page, ['h1.data-sheet__title', 'h1.restaurant-details__heading--title', 'h1']
            ) or "Sconosciuto"

            address = json_ld["Indirizzo"] or ResilientExtractor.first_text_from_selectors(
                page, ['.data-sheet__block--text', '.restaurant-details__heading--address', '[class*="address"]']
            )

            city = json_ld["Citta"]
            if not city and address:
                parts = [p.strip() for p in address.split(',') if p.strip()]
                if parts:
                    if parts[-1].lower() in ("italia", "italy") and len(parts) > 1:
                        candidate = parts[-2]
                        if re.match(r'^\d{4,5}$', candidate) and len(parts) >= 3:
                            city = parts[-3]
                        else:
                            city = candidate
                    else:
                        city = parts[-1]

            phone = json_ld["Telefono"] or ResilientExtractor.first_text_from_selectors(
                page, ['a[href^="tel:"]', '.collapse__block-item a[href^="tel:"]']
            )
            if not phone:
                tel_href = ResilientExtractor.first_attr_from_selectors(page, ['a[href^="tel:"]'], "href")
                if tel_href:
                    phone = tel_href.replace("tel:", "").strip()

            email = json_ld["Email"]
            if not email:
                mail_href = ResilientExtractor.first_attr_from_selectors(page, ['a[href^="mailto:"]'], "href")
                if mail_href:
                    email = mail_href.replace("mailto:", "").strip()

            website = json_ld["Sito Web"]
            if not website or "michelin.com" in website:
                web_href = ResilientExtractor.first_attr_from_selectors(
                    page, ['a[data-event-type="website"]', 'a[href^="http"][target="_blank"][rel*="noopener"]'], "href"
                )
                if web_href and "michelin.com" not in web_href and not any(s in web_href for s in ["facebook.com", "instagram.com", "google.com"]):
                    website = web_href

            # LIVELLO 3: Fallback semantico Regex
            sem = ResilientExtractor.extract_semantic_patterns(html_content)
            if not phone and sem["Telefono"]:
                phone = sem["Telefono"]
            if not email and sem["Email"]:
                email = sem["Email"]

            sweet_terms = ["gelater", "cremer", "cioccolat", "pasticc", "dolc", "confett", "torron", "biscott"]
            if any(term in name.lower() for term in sweet_terms):
                return {}

            prov = json_ld["Provincia"] or extract_province(city, address, region)

            lead = {
                "Nome": name,
                "Tipologia": "Ristorante",
                "Regione": region,
                "Provincia": prov,
                "Indirizzo": address,
                "Citta": city,
                "Telefono": phone,
                "Email": email,
                "Sito Web": website if website else url,
                "Social": json_ld["Social"] or sem["Social"],
                "Link Pagina": url,
                "Fonte": self.source_name
            }

            return PhoneEnricher.enrich(lead, page)
        except Exception as e:
            print(f"Errore dettaglio Michelin {url}: {e}")
            return {}
