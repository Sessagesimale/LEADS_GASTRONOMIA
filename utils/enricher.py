import urllib.parse
import re
from typing import Dict, Optional
from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests
from utils.geo_utils import extract_province, VALID_PROVINCE_CODES
from utils.resilient_extractor import ResilientExtractor


class PhoneEnricher:
    """
    Arricchitore rapido ed esteso V2:
    1. Recupera Telefono, Indirizzo completo, CAP, Provincia, Sito Web Ufficiale e Tipologia da PagineGialle via HTTP veloce.
    2. Scansiona il sito web ufficiale del lead per Email, Partita IVA, Social (IG/FB) e citazioni di Parmigiano Reggiano.
    3. Interroga UfficioCamerale / motori di ricerca per l'Ultimo Bilancio Depositato (Fatturato, Utile/Perdita, Addetti, Anno).
    4. Valuta l'Affinità Parmigiano Reggiano sui canali Social e Menu online.
    """

    GUIDE_DOMAINS = [
        "michelin.com", "ilgolosario.it", "gamberorosso.it",
        "guideespresso.it", "fondazioneslowfood.com", "slowfood.it",
        "paginegialle.it"
    ]

    @staticmethod
    def _is_guide_url(url: str) -> bool:
        if not url:
            return True
        u_low = url.lower()
        return any(d in u_low for d in PhoneEnricher.GUIDE_DOMAINS)

    @staticmethod
    def enrich(lead: dict, page=None) -> dict:
        """
        Arricchimento base veloce (Telefono, Indirizzo, Provincia, Sito Web Ufficiale, Tipologia).
        Usa HTTP diretto (curl_cffi) senza rallentare o spostare la pagina Playwright.
        """
        name = str(lead.get("Nome", "")).strip()
        city = str(lead.get("Citta", "")).strip()
        region = str(lead.get("Regione", "")).strip()
        address = str(lead.get("Indirizzo", "")).strip()

        # Default tipologia se non presente
        if not lead.get("Tipologia"):
            source = str(lead.get("Fonte", ""))
            if any(k in source for k in ["Golosario", "Produttori", "Botteghe"]):
                lead["Tipologia"] = "Negozio / Gastronomia"
            else:
                lead["Tipologia"] = "Ristorante"

        # Estrai subito la provincia se già deducibile da città/indirizzo
        if not lead.get("Provincia"):
            prov = extract_province(city, address, region)
            if prov:
                lead["Provincia"] = prov

        if not name or name == "Sconosciuto":
            return lead

        has_phone = bool(lead.get("Telefono") and len(re.sub(r'\D', '', str(lead["Telefono"]))) >= 6)
        has_external_site = bool(lead.get("Sito Web") and not PhoneEnricher._is_guide_url(str(lead.get("Sito Web", ""))))
        has_prov = bool(lead.get("Provincia"))

        # Se manca telefono, sito web esterno o provincia, interroga PagineGialle via HTTP rapido
        if not (has_phone and has_external_site and has_prov):
            try:
                clean_name = re.sub(r'\s*\([^)]*\)', '', name).strip()
                q_name = urllib.parse.quote(clean_name)
                clean_city = re.sub(r'\s*\([^)]*\)', '', city).strip()
                q_city = urllib.parse.quote(clean_city) if clean_city and clean_city.lower() != "italia" else ""
                url = f"https://www.paginegialle.it/ricerca/{q_name}/{q_city}" if q_city else f"https://www.paginegialle.it/ricerca/{q_name}"

                r = cffi_requests.get(url, impersonate="chrome", timeout=6)
                if r.status_code == 200:
                    soup = BeautifulSoup(r.text, "html.parser")
                    card = soup.select_one(".search-itm, .vcard")
                    if card:
                        # 1. Telefono
                        if not has_phone:
                            phone_el = card.select_one(".search-itm__phone-item, [class*='phone']")
                            if phone_el:
                                txt = phone_el.get_text(" ", strip=True)
                                m = re.search(r'(\+39\s*)?(?:0\d{1,4}[\-\s\./]?\d{4,8}|3\d{2}[\-\s\./]?\d{6,7})', txt)
                                if m:
                                    lead["Telefono"] = m.group(0).strip()

                        # 2. Indirizzo e Provincia da PagineGialle (es. "Via Tourneuve, 4 - 11100 Aosta (AO)")
                        adr_el = card.select_one(".search-itm__adr")
                        if adr_el:
                            adr_txt = adr_el.get_text(" ", strip=True)
                            if adr_txt:
                                if not lead.get("Indirizzo") or len(lead.get("Indirizzo", "")) < 6:
                                    lead["Indirizzo"] = adr_txt
                                if not lead.get("Provincia"):
                                    prov_pg = extract_province(city, adr_txt, region)
                                    if prov_pg:
                                        lead["Provincia"] = prov_pg
                                if not city or city.lower() == "italia":
                                    m_city = re.search(r'\b\d{5}\s+([A-Za-zÀ-ÿ\s\'\-]+?)(?:\s*\([A-Z]{2}\))?$', adr_txt)
                                    if m_city:
                                        lead["Citta"] = m_city.group(1).strip()

                        # 3. Sito Web Ufficiale
                        if not has_external_site:
                            web_el = card.select_one("a[data-pag='www'], a[title*='sito web']")
                            if web_el and web_el.get("href", "").startswith("http"):
                                ext_url = web_el["href"].strip()
                                if not PhoneEnricher._is_guide_url(ext_url):
                                    lead["Sito Web"] = ext_url

                        # 4. Affinamento Tipologia
                        cat_el = card.select_one(".search-itm__category")
                        if cat_el:
                            cat_txt = cat_el.get_text(" ", strip=True).lower()
                            if any(w in cat_txt for w in ["gastronomia", "negozio", "alimentari", "salumeria", "bottega", "enoteca", "formagg", "caseificio", "ingrosso"]):
                                if "Produttore" not in lead.get("Tipologia", ""):
                                    lead["Tipologia"] = "Negozio / Gastronomia"
                            elif any(w in cat_txt for w in ["ristorante", "trattoria", "osteria", "pizzeria", "bistrot", "locanda"]):
                                lead["Tipologia"] = "Ristorante"
            except Exception:
                pass

        # Fallback finale per la provincia
        if not lead.get("Provincia"):
            lead["Provincia"] = extract_province(lead.get("Citta", ""), lead.get("Indirizzo", ""), region)

        return lead

    @staticmethod
    def enrich_v2_deep(lead: dict, enable_financial: bool = True, enable_social: bool = True) -> dict:
        """
        Arricchimento profondo V2:
        - Scansione sito web ufficiale (Email, Partita IVA, Social, menzioni Parmigiano)
        - Estrazione Ultimo Bilancio Depositato da UfficioCamerale (Fatturato, Utile/Perdita, Addetti, Anno)
        - Analisi Social & Affinità Parmigiano Reggiano
        """
        name = str(lead.get("Nome", "")).strip()
        city = str(lead.get("Citta", "")).strip()
        prov = str(lead.get("Provincia", "")).strip()
        website = str(lead.get("Sito Web", "")).strip()

        if not name or name == "Sconosciuto":
            return lead

        site_html = ""
        site_text = ""

        # 1. Se abbiamo un sito web ufficiale esterno, scarichiamo la homepage per estrarre P.IVA, Email, Social e keyword
        if website and website.startswith("http") and not PhoneEnricher._is_guide_url(website):
            try:
                r_site = cffi_requests.get(website, impersonate="chrome", timeout=5)
                if r_site.status_code == 200:
                    site_html = r_site.text
                    site_text = BeautifulSoup(site_html, "html.parser").get_text(" ", strip=True)
                    sem = ResilientExtractor.extract_semantic_patterns(site_html, site_text)
                    if not lead.get("Email") and sem["Email"]:
                        lead["Email"] = sem["Email"]
                    if not lead.get("Partita IVA") and sem["Partita IVA"]:
                        lead["Partita IVA"] = sem["Partita IVA"]
                    if not lead.get("Social") and sem["Social"]:
                        lead["Social"] = sem["Social"]
                    if not lead.get("Telefono") and sem["Telefono"]:
                        lead["Telefono"] = sem["Telefono"]
            except Exception:
                pass

        # 2. Arricchimento Bilancio (Partita IVA, Fatturato, Utile/Perdita, Addetti, Anno)
        if enable_financial:
            PhoneEnricher._enrich_financial_data(lead, name, city, prov)

        # 3. Arricchimento Social & Affinità Parmigiano Reggiano
        if enable_social:
            PhoneEnricher._enrich_social_parmigiano_affinity(lead, name, city, site_text)

        return lead

    @staticmethod
    def _enrich_financial_data(lead: dict, name: str, city: str, prov: str):
        """
        Recupera Partita IVA e dati dell'ultimo bilancio depositato tramite ricerca combinata e UfficioCamerale.
        """
        piva = str(lead.get("Partita IVA", "")).strip()
        uc_url = ""

        clean_name = re.sub(r'\s*\([^)]*\)', '', name).strip()
        clean_city = re.sub(r'\s*\([^)]*\)', '', city).strip()

        # Stop words comuni nelle ragioni sociali per calcolare l'affinità nominale
        stop_words = {
            'srl', 'spa', 'snc', 'sas', 'srls', 'di', 'e', 'il', 'la', 'le', 'lo', 'i', 'gli',
            'del', 'della', 'dei', 'delle', 'ristorante', 'osteria', 'trattoria', 'bar', 'da',
            'societa', 'cooperativa', 'agricola', 'azienda', 'supermercato', 'market', 'sapori'
        }
        lead_tokens = [w for w in re.findall(r'[a-zA-Z]{3,}', clean_name.lower()) if w not in stop_words]

        try:
            # Passo A: Se non abbiamo già la P.IVA, cerchiamo su Yahoo con query mirata
            if not piva:
                q1 = urllib.parse.quote(f"ufficiocamerale \"{clean_name}\" {clean_city}")
                r1 = cffi_requests.get(f"https://it.search.yahoo.com/search?p={q1}", impersonate="chrome", timeout=6)
                if r1.status_code == 200:
                    unquoted = urllib.parse.unquote(r1.text)
                    uc_matches = re.findall(r'https?://www\.ufficiocamerale\.it/\d+/[a-z0-9\-]+', unquoted)
                    if uc_matches:
                        uc_url = uc_matches[0]

            # Passo B: Se ancora non abbiamo uc_url, cerchiamo per Nome + Città + Partita IVA
            if not uc_url:
                search_terms = []
                if piva:
                    search_terms.append(f"{piva} ufficiocamerale")
                else:
                    search_terms.append(f"site:ufficiocamerale.it {clean_name} {clean_city}")

                for st in search_terms:
                    q2 = urllib.parse.quote(st)
                    r2 = cffi_requests.get(f"https://it.search.yahoo.com/search?p={q2}", impersonate="chrome", timeout=6)
                    if r2.status_code == 200:
                        unquoted2 = urllib.parse.unquote(r2.text)
                        uc_matches2 = re.findall(r'https?://www\.ufficiocamerale\.it/\d+/[a-z0-9\-]+', unquoted2)
                        if uc_matches2:
                            uc_url = uc_matches2[0]
                            break

            # Passo C: Se abbiamo un URL UfficioCamerale, verifichiamo rigorosamente pertinenza geografica e nominale
            if uc_url:
                r_uc = cffi_requests.get(uc_url, impersonate="chrome", timeout=6)
                if r_uc.status_code == 200:
                    uc_text = BeautifulSoup(r_uc.text, "html.parser").get_text(" ", strip=True)

                    cam_match = re.search(r'Camera di commercio:\s*([A-Z]{2})\b', uc_text)
                    uc_prov = cam_match.group(1).strip() if cam_match else ""

                    rag_match = re.search(r'Rag\.\s*Sociale:\s*(.+?)(?:Indirizzo:|Partita|Rea:|PEC:|$)', uc_text)
                    rag_sociale = rag_match.group(1).strip() if rag_match else ""
                    rag_tokens = [w for w in re.findall(r'[a-zA-Z]{3,}', rag_sociale.lower()) if w not in stop_words]

                    # 1. Verifica Coerenza Geografica:
                    # Se il lead ha una provincia nota (es. MT) e UfficioCamerale indica una CCIAA diversa (es. BO o TO),
                    # scartiamo immediatamente per evitare di associare multinazionali o omonimi distanti.
                    is_geo_ok = True
                    if prov and uc_prov:
                        if prov.upper() != uc_prov.upper():
                            is_geo_ok = False
                    elif clean_city:
                        # Se una delle due province manca, verifichiamo che la città compaia nell'indirizzo
                        if clean_city.lower() not in uc_text.lower():
                            is_geo_ok = False

                    # 2. Verifica Coerenza Nominale:
                    # La ragione sociale deve condividere almeno un termine distintivo col nome dell'attività
                    is_name_ok = True
                    if lead_tokens and rag_tokens:
                        common_words = set(lead_tokens) & set(rag_tokens)
                        if not common_words:
                            is_name_ok = False

                    if is_geo_ok and is_name_ok:
                        # Partita IVA da UfficioCamerale
                        m_piva = re.search(r'Partita IVA:\s*([0-9]{11})', uc_text)
                        if m_piva:
                            lead["Partita IVA"] = m_piva.group(1)

                        # Provincia da UfficioCamerale se mancante
                        if uc_prov and not lead.get("Provincia") and uc_prov in VALID_PROVINCE_CODES:
                            lead["Provincia"] = uc_prov

                        # Indirizzo da UfficioCamerale se mancante
                        addr_uc_match = re.search(r'Indirizzo:\s*(.+?)(?:Rea:|PEC:|Fatturato:|Dipendenti|Forma giuridica:)', uc_text)
                        if addr_uc_match and not lead.get("Indirizzo"):
                            lead["Indirizzo"] = addr_uc_match.group(1).strip()

                        # Fatturato e Anno
                        m_fatt = re.search(r'Fatturato:\s*(€?\s*[\d\.,]+)\s*\((\d{4})\)', uc_text, re.I)
                        if m_fatt:
                            lead["Fatturato"] = m_fatt.group(1).strip()
                            lead["Anno Bilancio"] = m_fatt.group(2).strip()

                        # Utile / Perdita e Anno
                        m_utile = re.search(r'Utile:\s*(€?\s*[\-\+]?[\d\.,]+)\s*\((\d{4})\)', uc_text, re.I)
                        if m_utile:
                            lead["Utile/Perdita"] = m_utile.group(1).strip()
                            if not lead.get("Anno Bilancio"):
                                lead["Anno Bilancio"] = m_utile.group(2).strip()

                        # Addetti / Dipendenti
                        m_dip = re.search(r'Dipendenti\s*:\s*(\d+)\s*\((\d{4})\)', uc_text, re.I)
                        if m_dip:
                            lead["Addetti"] = m_dip.group(1).strip()
                            if not lead.get("Anno Bilancio"):
                                lead["Anno Bilancio"] = m_dip.group(2).strip()

                        # Forma Giuridica (per spiegare eventuale assenza di bilancio depositato)
                        m_forma = re.search(r'Forma giuridica:\s*([A-ZÀ-Ÿ\'\s]+?)(?:Data Iscrizione|Ateco|Procedure)', uc_text)
                        if m_forma and not lead.get("Fatturato"):
                            forma = m_forma.group(1).strip()
                            if any(k in forma.upper() for k in ["NOME COLLETTIVO", "ACCOMANDITA SEMPLICE", "INDIVIDUALE", "SEMPLICE"]):
                                lead["Fatturato"] = f"Esente ({forma.title()})"
                                lead["Utile/Perdita"] = "Esente deposito"
        except Exception:
            pass

    @staticmethod
    def _enrich_social_parmigiano_affinity(lead: dict, name: str, city: str, site_text: str = ""):
        """
        Individua i canali Social (Instagram/Facebook) e rileva se l'attività acquista/promuove
        attivamente Parmigiano Reggiano nei post social o nel menu online.
        """
        clean_name = re.sub(r'\s*\([^)]*\)', '', name).strip()
        clean_city = re.sub(r'\s*\([^)]*\)', '', city).strip()

        high_intent_patterns = [
            r'parmigiano\s+reggiano\s+(?:dop\s+)?(?:\d{2}\s*mesi|vacche\s+rosse|bruna\s+alpina|montagna|biologico|30\s*mesi|36\s*mesi|24\s*mesi|40\s*mesi|48\s*mesi)',
            r'(?:24|30|36|40|48|60)\s*mesi\s+di\s+stagionatura',
            r'vacche\s+rosse',
            r'fonduta\s+di\s+parmigiano\s+reggiano',
            r'spuma\s+di\s+parmigiano\s+reggiano',
            r'apertura\s+(?:della\s+)?forma\s+di\s+parmigiano',
            r'taglio\s+(?:della\s+)?forma',
            r'caseificio\s+[a-z0-9\s]{2,25}parmigiano',
        ]
        medium_intent_pattern = r'parmigiano\s+reggiano'

        combined_corpus = site_text or ""
        found_socials = []
        if lead.get("Social"):
            found_socials.append(lead["Social"])

        try:
            # Ricerca mirata su Yahoo per Social + Parmigiano Reggiano
            q_soc = urllib.parse.quote(f"{clean_name} {clean_city} Parmigiano Reggiano instagram OR facebook OR menu")
            r_soc = cffi_requests.get(f"https://it.search.yahoo.com/search?p={q_soc}", impersonate="chrome", timeout=6)
            if r_soc.status_code == 200:
                soup = BeautifulSoup(r_soc.text, "html.parser")

                # Estrai profili Instagram / Facebook pertinenti
                if not found_socials:
                    for a in soup.find_all("a"):
                        href = urllib.parse.unquote(a.get("href", ""))
                        m_soc = re.search(r'RU=(https?://(?:www\.)?(?:instagram\.com|facebook\.com)/[A-Za-z0-9_.\-]+)', href)
                        if m_soc:
                            s_url = m_soc.group(1).rstrip("/")
                            if not any(x in s_url.lower() for x in ["parmigianoreggiano", "slowfood", "gamberorosso", "michelin", "login", "explore"]):
                                if s_url not in found_socials:
                                    found_socials.append(s_url)
                    if found_socials:
                        lead["Social"] = " | ".join(found_socials[:2])

                # Rimuovi annunci/header per analizzare solo gli snippet organici relativi al locale
                for bad in soup.select("head, script, style, .ads, .dd.Sponsored"):
                    bad.decompose()

                organic_snippets = []
                name_tokens = [t.lower() for t in re.findall(r'[A-Za-zÀ-ÿ]{3,}', clean_name) if t.lower() not in ("ristorante", "osteria", "trattoria", "bottega", "gastronomia", "salumeria", "alimentari", "del", "della", "dei", "alle", "allo")]
                for block in soup.find_all(["div", "li", "p"]):
                    b_txt = block.get_text(" ", strip=True)
                    if 40 < len(b_txt) < 600 and "parmigiano" in b_txt.lower():
                        # Verifica che lo snippet menzioni effettivamente il nome del locale o la città
                        if not name_tokens or any(tok in b_txt.lower() for tok in name_tokens):
                            if "yahoo italia" not in b_txt.lower() and "annuncio relativo" not in b_txt.lower():
                                organic_snippets.append(b_txt)

                if organic_snippets:
                    combined_corpus += " " + " | ".join(organic_snippets[:3])
        except Exception:
            pass

        # Valutazione del livello di Affinità Parmigiano Reggiano
        if combined_corpus:
            for pat in high_intent_patterns:
                m_high = re.search(pat, combined_corpus, re.I)
                if m_high:
                    # Estrai un breve estratto contestuale
                    start = max(0, m_high.start() - 35)
                    end = min(len(combined_corpus), m_high.end() + 45)
                    excerpt = re.sub(r'\s+', ' ', combined_corpus[start:end]).strip()
                    lead["Affinita Parmigiano"] = "🔥 ALTA - Usa/Promuove Parmigiano DOP"
                    if not lead.get("Note Commerciali"):
                        lead["Note Commerciali"] = f"Rilevato online: «...{excerpt}...»"
                    return

            m_med = re.search(medium_intent_pattern, combined_corpus, re.I)
            if m_med:
                start = max(0, m_med.start() - 30)
                end = min(len(combined_corpus), m_med.end() + 40)
                excerpt = re.sub(r'\s+', ' ', combined_corpus[start:end]).strip()
                lead["Affinita Parmigiano"] = "⚡ MEDIA - Presente a Menu / Social"
                if not lead.get("Note Commerciali"):
                    lead["Note Commerciali"] = f"Citazione Parmigiano: «...{excerpt}...»"
                return

        if not lead.get("Affinita Parmigiano"):
            lead["Affinita Parmigiano"] = "⚪ Target Potenziale"
