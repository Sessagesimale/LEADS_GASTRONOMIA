import urllib.parse
import re

class PhoneEnricher:
    @staticmethod
    def enrich(lead: dict, page) -> dict:
        name = lead.get("Nome", "").strip()
        city = lead.get("Citta", "").strip()
        
        # Default tipologia se non presente
        if not lead.get("Tipologia"):
            source = lead.get("Fonte", "")
            if "Golosario" in source:
                lead["Tipologia"] = "Negozio / Gastronomia"
            else:
                lead["Tipologia"] = "Ristorante"
                
        # Se ha già il telefono, non serve cercare
        if lead.get("Telefono") and len(str(lead["Telefono"]).strip()) > 5:
            return lead
            
        if not name or name == "Sconosciuto":
            return lead
            
        # Ricerca su PagineGialle per reperire telefono e categoria
        try:
            q_name = urllib.parse.quote(name)
            # Se la città è 'Italia' o vuota, cerchiamo solo per nome
            q_city = urllib.parse.quote(city) if city and city.lower() != "italia" else ""
            url = f"https://www.paginegialle.it/ricerca/{q_name}/{q_city}" if q_city else f"https://www.paginegialle.it/ricerca/{q_name}"
            
            page.goto(url, timeout=12000, wait_until="domcontentloaded")
            page.wait_for_timeout(800)
            
            card = page.locator('.vcard, .search-itm').first
            if card.count() > 0:
                # Estrazione telefono
                phone_els = card.locator('.search-itm__phone-item, [class*="phone"]').all()
                for p in phone_els:
                    txt = p.inner_text().strip()
                    match = re.search(r'(\+39\s*)?(?:0\d{1,4}[-\s\./]?\d{4,8}|3\d{2}[-\s\./]?\d{6,7})', txt)
                    if match:
                        lead["Telefono"] = match.group(0).strip()
                        break
                        
                # Estrazione categoria / tipologia
                cat_els = card.locator('.search-itm__category, .category, [class*="category"]').all()
                if cat_els:
                    cat_txt = cat_els[0].inner_text().strip().lower()
                    if any(w in cat_txt for w in ['gastronomia', 'negozio', 'alimentari', 'salumeria', 'bottega', 'enoteca', 'formagg', 'panificio']):
                        lead["Tipologia"] = "Negozio / Gastronomia"
                    elif any(w in cat_txt for w in ['ristorante', 'trattoria', 'osteria', 'pizzeria', 'bistrot']):
                        lead["Tipologia"] = "Ristorante"
        except Exception as e:
            # Continua senza bloccare il flusso
            pass
            
        return lead
