import re
from typing import List, Dict
from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests
from scrapers.base_scraper import BaseScraper
from utils.geo_utils import extract_province
from utils.enricher import PhoneEnricher


class SlowFoodScraper(BaseScraper):
    """
    Scraper ufficiale per Fondazione Slow Food Italia:
    1. Presìdi Slow Food -> Estrae tutti i Produttori dalla scheda 'Produttori' (#produttori) di ciascun Presidio regionale.
    2. Alleanza Slow Food dei Cuochi -> Estrae i Ristoranti e le Osterie partner Slow Food della regione.
    """

    REGION_SLUGS = {
        "abruzzo": "abruzzo-it",
        "basilicata": "basilicata-it",
        "calabria": "calabria-it",
        "campania": "campania-it",
        "emilia-romagna": "emilia-romagna-it",
        "friuli-venezia giulia": "friuli-venezia-giulia-it",
        "lazio": "lazio-it",
        "liguria": "liguria-it",
        "lombardia": "lombardia-it",
        "marche": "marche-it",
        "molise": "molise-it",
        "piemonte": "piemonte-it",
        "puglia": "puglia-it",
        "sardegna": "sardegna-it",
        "sicilia": "sicilia-it",
        "toscana": "toscana-it",
        "trentino-alto adige": "trentino-alto-adige-it",
        "umbria": "umbria-it",
        "valle d'aosta": "valle-daosta-it",
        "veneto": "veneto-it",
    }

    SWEET_SECTORS = ["pasticceria", "dolci", "confetture", "mieli", "cioccolat", "gelat"]

    def __init__(self):
        self.source_name = "Fondazione Slow Food"
        self.base_url = "https://www.fondazioneslowfood.com"

    def _get_region_slug(self, region: str) -> str:
        r_low = region.lower().strip()
        if r_low in self.REGION_SLUGS:
            return self.REGION_SLUGS[r_low]
        slug = r_low.replace("'", "").replace("’", "").replace(" ", "-")
        return f"{slug}-it"

    def scrape(self, region: str, page=None, category_filter: str = "Tutti") -> List[Dict[str, str]]:
        slug = self._get_region_slug(region)
        leads: List[Dict[str, str]] = []

        is_only_restaurants = "ristoranti" in category_filter.lower() and "tutti" not in category_filter.lower() and "negozi" not in category_filter.lower()
        is_only_shops = "negozi" in category_filter.lower() and "tutti" not in category_filter.lower()

        # 1. Estrazione Produttori dai Presìdi Slow Food (se non è filtrato solo Ristoranti)
        if not is_only_restaurants:
            presidi_leads = self._scrape_presidi_producers(region, slug)
            leads.extend(presidi_leads)

        # 2. Estrazione Ristoranti / Osterie dall'Alleanza Slow Food dei Cuochi (se non è filtrato solo Negozi)
        if not is_only_shops:
            alleanza_leads = self._scrape_alleanza_cuochi(region, slug)
            leads.extend(alleanza_leads)

        print(f"[{self.source_name}] Totale estratti per {region}: {len(leads)} lead.")
        return leads

    def _scrape_presidi_producers(self, region: str, slug: str) -> List[Dict[str, str]]:
        leads: List[Dict[str, str]] = []
        presidi_urls = []
        seen_urls = set()

        # Raccogli i link dei Presìdi della regione (fino a 5 pagine)
        for page_num in range(1, 6):
            list_url = f"{self.base_url}/it/regioni-presidi/{slug}/" if page_num == 1 else f"{self.base_url}/it/regioni-presidi/{slug}/page/{page_num}/"
            try:
                r = cffi_requests.get(list_url, impersonate="chrome", timeout=12)
                if r.status_code != 200:
                    break
                soup = BeautifulSoup(r.text, "html.parser")
                found_on_page = 0
                for a in soup.find_all("a", href=True):
                    href = a["href"].strip()
                    if "/it/presidi-slow-food/" in href and href.rstrip("/") != f"{self.base_url}/it/presidi-slow-food":
                        if href not in seen_urls:
                            seen_urls.add(href)
                            presidi_urls.append(href)
                            found_on_page += 1
                if found_on_page == 0:
                    break
            except Exception as e:
                print(f"[{self.source_name}] Errore lettura pagina presidi {list_url}: {e}")
                break

        print(f"[{self.source_name}] Trovati {len(presidi_urls)} Presìdi in {region}. Estraggo le schede Produttori...")

        # Per ogni Presidio, estrai i singoli produttori dal tab #produttori
        for p_url in presidi_urls:
            try:
                p_leads = self.scrape_single_presidio(p_url, region)
                leads.extend(p_leads)
            except Exception as e:
                print(f"[{self.source_name}] Errore su presidio {p_url}: {e}")

        return leads

    def scrape_single_presidio(self, presidio_url: str, region: str = "") -> List[Dict[str, str]]:
        """
        Estrae tutti i produttori dalla scheda #produttori di una pagina Presidio Slow Food
        (es. https://www.fondazioneslowfood.com/it/presidi-slow-food/aglio-rosso-di-proceno/).
        """
        producers: List[Dict[str, str]] = []
        r = cffi_requests.get(presidio_url, impersonate="chrome", timeout=12)
        if r.status_code != 200:
            return producers

        soup = BeautifulSoup(r.text, "html.parser")

        # Titolo del Presidio
        title_el = soup.select_one("h1.entry-title, h1")
        presidio_name = title_el.get_text(" ", strip=True) if title_el else "Presidio Slow Food"

        # Settore merceologico (esclude dolci/pasticceria/mieli se richiesto)
        sector_el = soup.select_one("h3.entry-term.settore, .altre-info")
        sector_text = sector_el.get_text(" ", strip=True).lower() if sector_el else ""
        if any(sw in sector_text or sw in presidio_name.lower() for sw in self.SWEET_SECTORS):
            return producers

        # Regione dalla scheda se non passata
        if not region:
            reg_el = soup.select_one("h3.entry-term.regione")
            if reg_el:
                region = reg_el.get_text(" ", strip=True)

        # Selettori resilienti per il blocco Produttori (#produttori oppure pannello di stampa Produttori)
        prod_container = soup.select_one("div#produttori, div.tab-pane#produttori")
        if not prod_container:
            for panel in soup.select("div.panel"):
                h3 = panel.select_one("h3.print-title")
                if h3 and "produttori" in h3.get_text(strip=True).lower():
                    prod_container = panel
                    break

        if not prod_container:
            return producers

        # Separa i blocchi dei singoli produttori (divisi da <br/><br/> o <p>)
        raw_html = prod_container.decode_contents()
        # Rimuovi eventuale titolo h3 interno
        raw_html = re.sub(r'<h3[^>]*>.*?</h3>', '', raw_html, flags=re.I | re.S)

        blocks = re.split(r'(?:<br\s*/?>\s*){2,}|</p>\s*<p[^>]*>', raw_html, flags=re.I)

        for block_html in blocks:
            b_soup = BeautifulSoup(block_html, "html.parser")
            lines = [line.strip() for line in b_soup.get_text("\n").split("\n") if line.strip()]
            if not lines:
                continue

            # Ignora blocchi che sono semplici note discorsive senza contatti né indirizzi
            full_block_txt = " ".join(lines)
            if len(lines) < 2 and not re.search(r'\d', full_block_txt):
                continue

            # Nome Azienda (prima riga) + eventuale seconda riga se inizia con "di " o "Az."
            company_name = lines[0].strip().rstrip(",;-")
            start_idx = 1
            if len(lines) > 1 and (lines[1].lower().startswith("di ") or lines[1].lower().startswith("az.")):
                company_name = f"{company_name} ({lines[1].strip()})"
                start_idx = 2

            # Se la prima riga è troppo lunga (es. frase descrittiva), salta
            if len(company_name) > 95 or any(w in company_name.lower() for w in ["molti produttori", "area di produzione", "per contrastare"]):
                continue

            city = ""
            prov = ""
            address = ""
            phone = ""
            email = ""
            website = ""

            # Estrai email e sito dai tag <a> nel blocco
            for a_tag in b_soup.find_all("a", href=True):
                href = a_tag["href"].strip()
                if href.lower().startswith("mailto:"):
                    email = href[7:].strip()
                elif href.lower().startswith("tel:"):
                    phone = href[4:].strip()
                elif href.lower().startswith("http") and "fondazioneslowfood" not in href.lower():
                    website = href

            # Analizza le righe successive per Città (Provincia), Indirizzo, Telefono, Email, Sito
            for line in lines[start_idx:]:
                l_clean = line.strip()
                if not l_clean:
                    continue

                # Email testuale
                if "@" in l_clean and not email:
                    m_em = re.search(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', l_clean)
                    if m_em:
                        email = m_em.group(0)
                    continue

                # Sito web testuale
                if not website and (l_clean.lower().startswith("www.") or l_clean.lower().startswith("http")):
                    w_cand = l_clean.split()[0].strip()
                    website = w_cand if w_cand.startswith("http") else f"https://{w_cand}"
                    continue

                # Telefono (es. "Tel. 349 7848966" o "+39 0763 ...")
                if re.search(r'(?:tel|cell|ph|\+39|0\d{1,3}[\s\./\-]?\d{4,8}|3\d{2}[\s\./\-]?\d{6,7})', l_clean, re.I):
                    m_tel = re.search(r'(\+39\s*)?(?:0\d{1,4}[\s\./\-]?\d{4,8}|3\d{2}[\s\./\-]?\d{5,8})', l_clean)
                    if m_tel and not phone:
                        phone = m_tel.group(0).strip()
                        continue

                # Riga con Comune e Provincia tra parentesi es. "Proceno (Vt)"
                m_city_prov = re.search(r'^([A-Za-zÀ-ÿ\s\'\.\-]+?)\s*\(([A-Za-z]{2})\)$', l_clean)
                if m_city_prov and not city:
                    city = m_city_prov.group(1).strip()
                    prov = m_city_prov.group(2).upper()
                    continue

                # Indirizzo (Via, Corso, Piazza, Loc., Fraz., Contrada, Strada, Viale, ecc.)
                if re.search(r'\b(?:via|viale|piazza|corso|loc\.|localit|frazione|fraz\.|contrada|c\.da|strada|vicolo|largo|borgo|cascina|podere)\b', l_clean, re.I) or re.search(r',\s*\d+', l_clean):
                    if not address:
                        address = l_clean
                    else:
                        address = f"{address}, {l_clean}"
                    continue

                # Se non abbiamo ancora la città e la riga è breve senza numeri telefonici
                if not city and len(l_clean) < 40 and not re.search(r'\d{4,}', l_clean):
                    city = re.sub(r'\([A-Za-z]{2}\)', '', l_clean).strip()
                    p_cand = extract_province(l_clean, address, region)
                    if p_cand and not prov:
                        prov = p_cand

            if not prov:
                prov = extract_province(city, f"{address} {full_block_txt}", region)

            lead = {
                "Nome": company_name,
                "Tipologia": "Negozio / Gastronomia",
                "Regione": region,
                "Provincia": prov,
                "Citta": city,
                "Indirizzo": address,
                "Telefono": phone,
                "Email": email,
                "Sito Web": website if website else presidio_url,
                "Link Pagina": presidio_url,
                "Fonte": f"Slow Food ({presidio_name})",
                "Note Commerciali": f"Produttore Presidio Slow Food: {presidio_name}"
            }
            lead = PhoneEnricher.enrich(lead)
            producers.append(lead)

        return producers

    def _scrape_alleanza_cuochi(self, region: str, slug: str) -> List[Dict[str, str]]:
        """
        Estrae i Ristoranti e le Osterie dell'Alleanza Slow Food dei Cuochi della regione.
        """
        leads: List[Dict[str, str]] = []
        seen_names = set()

        for page_num in range(1, 6):
            url = f"{self.base_url}/it/regioni-alleanza/{slug}/" if page_num == 1 else f"{self.base_url}/it/regioni-alleanza/{slug}/page/{page_num}/"
            try:
                r = cffi_requests.get(url, impersonate="chrome", timeout=12)
                if r.status_code != 200:
                    break
                soup = BeautifulSoup(r.text, "html.parser")
                articles = soup.select("article.alleanza-dei-cuochi, article.panel")
                if not articles:
                    break

                for art in articles:
                    title_el = art.select_one(".entry-title .title, h2 .title")
                    if not title_el:
                        continue
                    name = title_el.get_text(" ", strip=True)
                    if not name or name.lower() in seen_names:
                        continue
                    seen_names.add(name.lower())

                    city_el = art.select_one(".entry-term.citta, p.citta")
                    city = city_el.get_text(" ", strip=True).title() if city_el else ""

                    addr_el = art.select_one("p.indirizzo")
                    address = addr_el.get_text(" ", strip=True) if addr_el else ""

                    phone = ""
                    tel_a = art.select_one("a[href^='tel:']")
                    if tel_a:
                        phone = tel_a.get("href", "").replace("tel:", "").strip()

                    email = ""
                    mail_a = art.select_one("a[href^='mailto:']")
                    if mail_a:
                        email = mail_a.get("href", "").replace("mailto:", "").strip()

                    website = ""
                    for a_tag in art.select(".panel-body a[href^='http']"):
                        href = a_tag.get("href", "").strip()
                        if "fondazioneslowfood" not in href.lower():
                            website = href
                            break

                    chef_el = art.select_one("p.cuoco")
                    chef_txt = chef_el.get_text(" ", strip=True) if chef_el else ""

                    prov = extract_province(city, address, region)

                    lead = {
                        "Nome": name,
                        "Tipologia": "Ristorante",
                        "Regione": region,
                        "Provincia": prov,
                        "Citta": city,
                        "Indirizzo": address,
                        "Telefono": phone,
                        "Email": email,
                        "Sito Web": website if website else url,
                        "Link Pagina": url,
                        "Fonte": "Slow Food (Alleanza Cuochi)",
                        "Note Commerciali": chef_txt
                    }
                    lead = PhoneEnricher.enrich(lead)
                    leads.append(lead)
            except Exception as e:
                print(f"[{self.source_name}] Errore Alleanza pagina {page_num}: {e}")
                break

        return leads
