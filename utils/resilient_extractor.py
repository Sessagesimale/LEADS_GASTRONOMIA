import json
import re
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup


class ResilientExtractor:
    """
    Motore di estrazione resiliente a 3 livelli (Self-Healing):
    1. Dati strutturati JSON-LD (Schema.org) / Microdata
    2. Cascata di selettori CSS multipli
    3. Estrazione semantica tramite Regex (Telefono, Email, P.IVA con checksum Luhn, Indirizzo, Social)
    """

    @staticmethod
    def is_valid_italian_piva(piva: str) -> bool:
        """Verifica matematica ufficiale di validità di una Partita IVA italiana (11 cifre)."""
        if not piva or len(piva) != 11 or not piva.isdigit():
            return False
        if piva == "00000000000":
            return False
        # Le prime 7 cifre sono la matricola, le cifre 8-10 sono il codice ufficio provinciale (001-100, o 120, 121, 888, 999)
        prov_code = int(piva[7:10])
        if not (1 <= prov_code <= 105 or prov_code in (120, 121, 888, 999)):
            return False
        s = 0
        for i in range(10):
            c = int(piva[i])
            if i % 2 == 0:
                s += c
            else:
                c *= 2
                if c > 9:
                    c -= 9
                s += c
        check_digit = (10 - (s % 10)) % 10
        return check_digit == int(piva[10])

    @staticmethod
    def extract_json_ld(html_content: str) -> Dict[str, str]:
        """
        Livello 1: Estrae informazioni standardizzate Schema.org da blocchi <script type="application/ld+json">
        (Immune ai cambi di grafica/CSS dei siti web).
        """
        result = {
            "Nome": "",
            "Indirizzo": "",
            "Citta": "",
            "Provincia": "",
            "CAP": "",
            "Telefono": "",
            "Email": "",
            "Sito Web": "",
            "Social": "",
        }
        if not html_content:
            return result

        try:
            soup = BeautifulSoup(html_content, "html.parser")
            scripts = soup.find_all("script", type="application/ld+json")
            for script in scripts:
                raw_text = script.string or script.get_text()
                if not raw_text:
                    continue
                try:
                    data = json.loads(raw_text.strip())
                except Exception:
                    continue

                items = []
                if isinstance(data, list):
                    items.extend(data)
                elif isinstance(data, dict):
                    if "@graph" in data and isinstance(data["@graph"], list):
                        items.extend(data["@graph"])
                    else:
                        items.append(data)

                for obj in items:
                    if not isinstance(obj, dict):
                        continue
                    obj_type = str(obj.get("@type", "")).lower()
                    if any(t in obj_type for t in ["restaurant", "foodestablishment", "localbusiness", "store", "organization", "place"]):
                        if not result["Nome"] and obj.get("name"):
                            result["Nome"] = str(obj["name"]).strip()
                        if not result["Telefono"] and obj.get("telephone"):
                            result["Telefono"] = str(obj["telephone"]).strip()
                        if not result["Email"] and obj.get("email"):
                            result["Email"] = str(obj["email"]).replace("mailto:", "").strip()
                        if not result["Sito Web"] and obj.get("url"):
                            url_val = str(obj["url"]).strip()
                            if url_val.startswith("http"):
                                result["Sito Web"] = url_val

                        # Indirizzo strutturato
                        addr = obj.get("address")
                        if isinstance(addr, dict):
                            street = str(addr.get("streetAddress", "")).strip()
                            locality = str(addr.get("addressLocality", "")).strip()
                            region_code = str(addr.get("addressRegion", "")).strip()
                            postal = str(addr.get("postalCode", "")).strip()
                            if locality and not result["Citta"]:
                                result["Citta"] = locality
                            if postal and not result["CAP"]:
                                result["CAP"] = postal
                            if len(region_code) == 2 and not result["Provincia"]:
                                result["Provincia"] = region_code.upper()
                            parts = [p for p in [street, postal, locality] if p]
                            if parts and not result["Indirizzo"]:
                                result["Indirizzo"] = ", ".join(parts)
                        elif isinstance(addr, str) and not result["Indirizzo"]:
                            result["Indirizzo"] = addr.strip()

                        # Social in sameAs
                        same_as = obj.get("sameAs")
                        if same_as:
                            if isinstance(same_as, str):
                                same_as = [same_as]
                            if isinstance(same_as, list):
                                socials = [s for s in same_as if isinstance(s, str) and any(d in s.lower() for d in ["instagram.com", "facebook.com"])]
                                if socials and not result["Social"]:
                                    result["Social"] = " | ".join(socials[:2])
        except Exception:
            pass

        return result

    @staticmethod
    def first_text_from_selectors(page, selectors: List[str]) -> str:
        """
        Livello 2: Prova una lista ordinata di selettori CSS in Playwright e restituisce il primo testo valido.
        """
        for sel in selectors:
            try:
                loc = page.locator(sel)
                if loc.count() > 0:
                    txt = loc.first.inner_text().strip()
                    if txt:
                        return txt
            except Exception:
                continue
        return ""

    @staticmethod
    def first_attr_from_selectors(page, selectors: List[str], attr: str = "href") -> str:
        """
        Livello 2: Prova una lista ordinata di selettori CSS in Playwright e restituisce il primo attributo valido.
        """
        for sel in selectors:
            try:
                loc = page.locator(sel)
                if loc.count() > 0:
                    val = loc.first.get_attribute(attr)
                    if val and val.strip():
                        return val.strip()
            except Exception:
                continue
        return ""

    @staticmethod
    def extract_semantic_patterns(html_content: str, plain_text: str = "") -> Dict[str, str]:
        """
        Livello 3: Estrazione semantica tramite pattern Regex su HTML e testo puro.
        """
        res = {
            "Telefono": "",
            "Email": "",
            "Partita IVA": "",
            "Social": "",
            "Indirizzo": ""
        }
        if not html_content and not plain_text:
            return res

        text = plain_text or BeautifulSoup(html_content, "html.parser").get_text(" ", strip=True)

        # 1. Telefono (da href="tel:..." o pattern numerico italiano)
        tel_href = re.search(r'href=["\']tel:([^"\']+)["\']', html_content, re.I)
        if tel_href:
            candidate = tel_href.group(1).strip()
            if len(re.sub(r'\D', '', candidate)) >= 6:
                res["Telefono"] = candidate

        if not res["Telefono"]:
            phone_match = re.search(
                r'(?:Tel\.?|Telefono|Cell\.?|Ph\.?|\+39)\s*[:\.]?\s*(\+?39\s*)?(0\d{1,3}[\s\.\-/]?\d{4,8}|3\d{2}[\s\.\-/]?\d{6,7})',
                text,
                re.I
            )
            if phone_match:
                prefix = phone_match.group(1) or ""
                num = phone_match.group(2) or ""
                res["Telefono"] = f"{prefix}{num}".strip()

        # 2. Email (da mailto: o pattern email)
        mailto_match = re.search(r'href=["\']mailto:([^"\'?]+)', html_content, re.I)
        if mailto_match:
            email_cand = mailto_match.group(1).strip()
            if "@" in email_cand and not any(x in email_cand.lower() for x in ["example", "sentry", "wordpress", "slowfood.it", "gamberorosso.it", "michelin.com"]):
                res["Email"] = email_cand

        if not res["Email"]:
            emails = re.findall(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', text)
            for em in emails:
                em_low = em.lower()
                if not any(bad in em_low for bad in ["example", "sentry", "wix", "wordpress", "slowfood", "gamberorosso", "michelin", "ilgolosario", "pec.it", "legalmail"]):
                    res["Email"] = em
                    break

        # 3. Partita IVA (11 cifre verificate col checksum ufficiale)
        piva_candidates = re.findall(r'\b([0-9]{11})\b', text)
        for cand in piva_candidates:
            if ResilientExtractor.is_valid_italian_piva(cand):
                res["Partita IVA"] = cand
                break

        # 4. Social Links (Instagram & Facebook)
        social_urls = []
        raw_socials = re.findall(
            r'https?://(?:www\.)?(?:instagram\.com|facebook\.com)/[a-zA-Z0-9_.\-/]+',
            html_content,
            re.I
        )
        ignored_handles = [
            "slow_food", "slowfood", "italiaslowfood", "gamberorosso", "michelinguide",
            "ilgolosario", "guideespresso", "sharer", "share", "intent", "plugins", "tr?", "p/"
        ]
        for s_url in raw_socials:
            s_clean = s_url.rstrip("/\"'\\")
            if not any(ig in s_clean.lower() for ig in ignored_handles):
                if s_clean not in social_urls:
                    social_urls.append(s_clean)
        if social_urls:
            res["Social"] = " | ".join(social_urls[:2])

        # 5. Indirizzo (Via / Piazza / Corso / Località / Frazione ...)
        addr_match = re.search(
            r'\b((?:Via|Viale|Piazza|Piazzale|Corso|Vicolo|Largo|Strada|Localit[àa]|Loc\.|Frazione|Fraz\.|Contrada|C\.da)\s+[A-Za-zÀ-ÿ0-9\s\'\.,\-]{3,45}?\d+[a-zA-Z/\-]*)',
            text,
            re.I
        )
        if addr_match:
            res["Indirizzo"] = addr_match.group(1).strip()

        return res
