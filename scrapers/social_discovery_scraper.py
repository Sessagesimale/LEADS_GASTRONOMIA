import re
import urllib.parse
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests
from scrapers.base_scraper import BaseScraper
from utils.geo_utils import REGION_PROVINCES, extract_province
from utils.enricher import PhoneEnricher


class SocialDiscoveryScraper(BaseScraper):
    """
    Motore 'Social Buyer Discovery' (Instagram & Facebook):
    Individua Ristoranti, Osterie, Salumerie e Botteghe Alimentari che pubblicano
    attivamente post su Parmigiano Reggiano (stagionature 24/30/36+ mesi, Vacche Rosse,
    apertura forme, taglieri, fondute) e li valida tramite directory commerciali
    per garantire 0 perdite di tempo (escludendo food blogger e profili privati).
    """

    NOISE_WORDS = [
        "blogger", "foodblogger", "ricette", "recipe", "lover", "fan", "official",
        "consorzio", "parmigianoreggiano", "personal", "travel", "fitness", "dieta",
        "gelateria", "pasticceria", "cioccolateria", "cremeria"
    ]

    def __init__(self):
        self.source_name = "Social Buyer Discovery (IG/FB)"

    def scrape(self, region: str, page=None, category_filter: str = "Tutti", province_filter: Optional[str] = None) -> List[Dict[str, str]]:
        leads: List[Dict[str, str]] = []
        seen_names = set()

        provinces = REGION_PROVINCES.get(region, [{"code": "", "name": region}])
        if province_filter:
            provinces = [p for p in provinces if p["code"].upper() == province_filter.upper()]
            if not provinces:
                provinces = [{"code": province_filter.upper(), "name": region}]

        is_only_restaurants = "ristoranti" in category_filter.lower() and "tutti" not in category_filter.lower() and "negozi" not in category_filter.lower()
        is_only_shops = "negozi" in category_filter.lower() and "tutti" not in category_filter.lower()

        for prov_info in provinces:
            prov_code = prov_info["code"]
            prov_name = prov_info["name"]

            search_queries = []
            if not is_only_shops:
                search_queries.append((
                    f'site:instagram.com "Parmigiano Reggiano" (ristorante OR osteria OR trattoria) ("24 mesi" OR "30 mesi" OR "36 mesi" OR "Vacche Rosse" OR "fonduta") {prov_name}',
                    "Ristorante"
                ))
            if not is_only_restaurants:
                search_queries.append((
                    f'site:instagram.com "Parmigiano Reggiano" (gastronomia OR salumeria OR bottega OR formaggeria) ("forma" OR "mesi" OR "stagionatura" OR "Vacche Rosse") {prov_name}',
                    "Negozio / Gastronomia"
                ))
                search_queries.append((
                    f'site:facebook.com "Parmigiano Reggiano" (gastronomia OR salumeria OR bottega OR ristorante) ("30 mesi" OR "36 mesi" OR "Vacche Rosse" OR "apertura forma") {prov_name}',
                    "Negozio / Gastronomia"
                ))

            for raw_q, default_tipo in search_queries:
                try:
                    q_enc = urllib.parse.quote(raw_q)
                    r = cffi_requests.get(f"https://it.search.yahoo.com/search?p={q_enc}", impersonate="chrome", timeout=8)
                    if r.status_code != 200:
                        continue

                    soup = BeautifulSoup(r.text, "html.parser")
                    for a_tag in soup.find_all("a", href=True):
                        href_unquoted = urllib.parse.unquote(a_tag["href"])
                        m_soc = re.search(r'RU=(https?://(?:www\.)?(?:instagram\.com|facebook\.com)/[^/&?\s]+)', href_unquoted)
                        if not m_soc:
                            continue

                        social_url = m_soc.group(1).rstrip("/")
                        if any(skip in social_url.lower() for skip in ["/p/", "/reel/", "/posts/", "/photos/", "/videos/", "/explore", "/hashtag"]):
                            # Se è un link a un singolo post, teniamo comunque il titolo se contiene il nome pagina
                            pass

                        title_txt = a_tag.get_text(" ", strip=True)
                        # Pulisci il titolo di Yahoo/Instagram per estrarre il nome dell'attività
                        # Es: "www.instagram.com › osteria... Osteria del Gusto (@osteriadelgusto) - Instagram"
                        clean_title = re.sub(r'^.*?(?:instagram\.com|facebook\.com)\s*[›\->]\s*\S+\s*', '', title_txt, flags=re.I)
                        clean_title = re.sub(r'\s*[\(\[@].*$', '', clean_title)
                        clean_title = re.sub(r'\s*[\-\|•]\s*(?:Instagram|Facebook|Foto|Photos|Home).*$', '', clean_title, flags=re.I).strip()

                        if not clean_title or len(clean_title) < 3 or len(clean_title) > 65:
                            continue
                        if any(nw in clean_title.lower() or nw in social_url.lower() for nw in self.NOISE_WORDS):
                            continue
                        if clean_title.lower() in ("instagram", "facebook", "accedi", "login"):
                            continue

                        norm_key = clean_title.lower()
                        if norm_key in seen_names:
                            continue
                        seen_names.add(norm_key)

                        # Costruisci il lead candidato e validalo/arricchiscilo su PagineGialle
                        candidate = {
                            "Nome": clean_title,
                            "Tipologia": default_tipo,
                            "Regione": region,
                            "Provincia": prov_code,
                            "Citta": prov_name,
                            "Indirizzo": "",
                            "Telefono": "",
                            "Email": "",
                            "Sito Web": social_url,
                            "Social": social_url,
                            "Affinita Parmigiano": "🔥 ALTA - Scoperto da Post Social Parmigiano DOP",
                            "Link Pagina": social_url,
                            "Fonte": self.source_name,
                            "Note Commerciali": f"Attività individuata su Social per promozione attiva di Parmigiano Reggiano ({prov_name})"
                        }

                        enriched = PhoneEnricher.enrich(candidate)
                        # Filtriamo solo i lead che hanno trovato un riscontro reale (telefono o indirizzo valido)
                        # per garantire solo lead commerciali veri ed evitare qualsiasi falso positivo!
                        if enriched.get("Telefono") or enriched.get("Indirizzo"):
                            det_prov = extract_province(enriched.get("Citta", ""), enriched.get("Indirizzo", ""), region) or prov_code
                            enriched["Provincia"] = det_prov
                            if province_filter and det_prov.upper() != province_filter.upper():
                                continue
                            leads.append(enriched)

                except Exception as e:
                    print(f"[{self.source_name}] Errore ricerca social su {prov_name}: {e}")

        print(f"[{self.source_name}] Individuati e validati {len(leads)} Social Buyer per {region}.")
        return leads
