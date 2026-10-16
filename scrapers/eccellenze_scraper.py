import re
import urllib.parse
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests
from scrapers.base_scraper import BaseScraper
from utils.geo_utils import REGION_PROVINCES, extract_province


class EccellenzeScraper(BaseScraper):
    """
    Scraper per Nuove Sorgenti di Qualità B2B:
    1. Salumerie Storiche, Formaggerie & Gastronomie d'Élite
    2. Distributori & Grossisti Lattiero-Caseari / Ho.Re.Ca.
    3. Ristoranti selezionati Guida Touring Club / Cucina del Territorio
    """

    SWEET_TERMS = ["gelater", "cremer", "cioccolat", "pasticc", "dolc", "confett", "torron", "biscott", "yogurt"]

    def __init__(self):
        self.source_name = "Botteghe Storiche, Touring & Ho.Re.Ca."

    def scrape(self, region: str, page=None, category_filter: str = "Tutti", province_filter: Optional[str] = None) -> List[Dict[str, str]]:
        leads: List[Dict[str, str]] = []
        seen_keys = set()

        provinces = REGION_PROVINCES.get(region, [{"code": "", "name": region}])
        if province_filter:
            provinces = [p for p in provinces if p["code"].upper() == province_filter.upper()]
            if not provinces:
                provinces = [{"code": province_filter.upper(), "name": region}]

        is_only_restaurants = "ristoranti" in category_filter.lower() and "tutti" not in category_filter.lower() and "negozi" not in category_filter.lower()
        is_only_shops = "negozi" in category_filter.lower() and "tutti" not in category_filter.lower()

        # Definiamo le query ad alto valore commerciale per ciascuna provincia
        queries = []
        if not is_only_restaurants:
            queries.append(("salumeria formaggeria gastronomia", "Negozio / Gastronomia", "Salumerie & Formaggerie Gourmet"))
            queries.append(("ingrosso formaggi latticini alimentari", "Negozio / Distributore Ho.Re.Ca.", "Distributori Ho.Re.Ca. & Latticini"))
        if not is_only_shops:
            queries.append(("ristorante guida touring", "Ristorante", "Selezione Touring / Tradizione"))

        for prov_info in provinces:
            prov_code = prov_info["code"]
            prov_name = prov_info["name"]

            for q_text, default_tipo, sub_source in queries:
                q_enc = urllib.parse.quote(q_text)
                loc_enc = urllib.parse.quote(prov_name)
                url = f"https://www.paginegialle.it/ricerca/{q_enc}/{loc_enc}"

                try:
                    r = cffi_requests.get(url, impersonate="chrome", timeout=10)
                    if r.status_code != 200:
                        continue
                    soup = BeautifulSoup(r.text, "html.parser")
                    cards = soup.select(".search-itm")

                    for card in cards[:12]:
                        title_el = card.select_one(".search-itm__rag, h2")
                        if not title_el:
                            continue
                        name = title_el.get_text(" ", strip=True)
                        if not name:
                            continue

                        # Escludi dolciario o supermercati GDO generici
                        name_low = name.lower()
                        if any(sw in name_low for sw in self.SWEET_TERMS):
                            continue
                        if any(gdo in name_low for gdo in ["conad", "coop ", "carrefour", "esselunga", "lidl", "eurospin", "md ", "penny"]):
                            continue

                        # Indirizzo, Città e Provincia
                        adr_el = card.select_one(".search-itm__adr")
                        address = adr_el.get_text(" ", strip=True) if adr_el else ""
                        city = prov_name
                        m_city = re.search(r'\b\d{5}\s+([A-Za-zÀ-ÿ\s\'\-]+?)(?:\s*\([A-Z]{2}\))?$', address)
                        if m_city:
                            city = m_city.group(1).strip()

                        detected_prov = extract_province(city, address, region)
                        # Se PagineGialle restituisce un'azienda fuori provincia/regione (es. nelle vicinanze), scartala rigorosamente
                        if detected_prov and detected_prov.upper() != prov_code.upper():
                            continue
                        if not detected_prov:
                            detected_prov = prov_code

                        if province_filter and detected_prov.upper() != province_filter.upper():
                            continue

                        dedup_key = f"{name_low}_{city.lower()}"
                        if dedup_key in seen_keys:
                            continue
                        seen_keys.add(dedup_key)

                        # Telefono
                        phone = ""
                        phone_el = card.select_one(".search-itm__phone-item")
                        if phone_el:
                            phone = phone_el.get_text(" ", strip=True)

                        # Link scheda e Sito Web esterno
                        page_link = url
                        a_main = card.select_one("a.remove_blank_for_app")
                        if a_main and a_main.get("href", "").startswith("http"):
                            page_link = a_main["href"].strip()

                        website = ""
                        web_el = card.select_one("a[data-pag='www']")
                        if web_el and web_el.get("href", "").startswith("http"):
                            website = web_el["href"].strip()

                        # Badge di qualità (es. Presente su Gambero Rosso, Guida Touring, Michelin)
                        badges = [b.get_text(" ", strip=True) for b in card.select(".search-itm__kwd-label")]
                        badge_note = ", ".join(badges[:4]) if badges else sub_source

                        lead = {
                            "Nome": name,
                            "Tipologia": default_tipo,
                            "Regione": region,
                            "Provincia": detected_prov,
                            "Citta": city,
                            "Indirizzo": address,
                            "Telefono": phone,
                            "Email": "",
                            "Sito Web": website if website else page_link,
                            "Link Pagina": page_link,
                            "Fonte": f"Eccellenze ({sub_source})",
                            "Note Commerciali": badge_note
                        }
                        leads.append(lead)
                except Exception as e:
                    print(f"[{self.source_name}] Errore su {prov_name} ({q_text}): {e}")

        print(f"[{self.source_name}] Estratti {len(leads)} lead qualificati per {region}.")
        return leads
