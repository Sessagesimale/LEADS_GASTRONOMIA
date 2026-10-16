import re
from typing import List, Dict, Optional

# Mappa Ufficiale delle 20 Regioni Italiane -> Province (Nome Completo e Sigla)
REGION_PROVINCES: Dict[str, List[Dict[str, str]]] = {
    "Abruzzo": [
        {"code": "AQ", "name": "L'Aquila"},
        {"code": "CH", "name": "Chieti"},
        {"code": "PE", "name": "Pescara"},
        {"code": "TE", "name": "Teramo"},
    ],
    "Basilicata": [
        {"code": "MT", "name": "Matera"},
        {"code": "PZ", "name": "Potenza"},
    ],
    "Calabria": [
        {"code": "CS", "name": "Cosenza"},
        {"code": "CZ", "name": "Catanzaro"},
        {"code": "KR", "name": "Crotone"},
        {"code": "RC", "name": "Reggio Calabria"},
        {"code": "VV", "name": "Vibo Valentia"},
    ],
    "Campania": [
        {"code": "AV", "name": "Avellino"},
        {"code": "BN", "name": "Benevento"},
        {"code": "CE", "name": "Caserta"},
        {"code": "NA", "name": "Napoli"},
        {"code": "SA", "name": "Salerno"},
    ],
    "Emilia-Romagna": [
        {"code": "BO", "name": "Bologna"},
        {"code": "FC", "name": "Forlì-Cesena"},
        {"code": "FE", "name": "Ferrara"},
        {"code": "MO", "name": "Modena"},
        {"code": "PC", "name": "Piacenza"},
        {"code": "PR", "name": "Parma"},
        {"code": "RA", "name": "Ravenna"},
        {"code": "RE", "name": "Reggio Emilia"},
        {"code": "RN", "name": "Rimini"},
    ],
    "Friuli-Venezia Giulia": [
        {"code": "GO", "name": "Gorizia"},
        {"code": "PN", "name": "Pordenone"},
        {"code": "TS", "name": "Trieste"},
        {"code": "UD", "name": "Udine"},
    ],
    "Lazio": [
        {"code": "FR", "name": "Frosinone"},
        {"code": "LT", "name": "Latina"},
        {"code": "RI", "name": "Rieti"},
        {"code": "RM", "name": "Roma"},
        {"code": "VT", "name": "Viterbo"},
    ],
    "Liguria": [
        {"code": "GE", "name": "Genova"},
        {"code": "IM", "name": "Imperia"},
        {"code": "SP", "name": "La Spezia"},
        {"code": "SV", "name": "Savona"},
    ],
    "Lombardia": [
        {"code": "BG", "name": "Bergamo"},
        {"code": "BS", "name": "Brescia"},
        {"code": "CO", "name": "Como"},
        {"code": "CR", "name": "Cremona"},
        {"code": "LC", "name": "Lecco"},
        {"code": "LO", "name": "Lodi"},
        {"code": "MB", "name": "Monza e Brianza"},
        {"code": "MI", "name": "Milano"},
        {"code": "MN", "name": "Mantova"},
        {"code": "PV", "name": "Pavia"},
        {"code": "SO", "name": "Sondrio"},
        {"code": "VA", "name": "Varese"},
    ],
    "Marche": [
        {"code": "AN", "name": "Ancona"},
        {"code": "AP", "name": "Ascoli Piceno"},
        {"code": "FM", "name": "Fermo"},
        {"code": "MC", "name": "Macerata"},
        {"code": "PU", "name": "Pesaro e Urbino"},
    ],
    "Molise": [
        {"code": "CB", "name": "Campobasso"},
        {"code": "IS", "name": "Isernia"},
    ],
    "Piemonte": [
        {"code": "AL", "name": "Alessandria"},
        {"code": "AT", "name": "Asti"},
        {"code": "BI", "name": "Biella"},
        {"code": "CN", "name": "Cuneo"},
        {"code": "NO", "name": "Novara"},
        {"code": "TO", "name": "Torino"},
        {"code": "VB", "name": "Verbano-Cusio-Ossola"},
        {"code": "VC", "name": "Vercelli"},
    ],
    "Puglia": [
        {"code": "BA", "name": "Bari"},
        {"code": "BT", "name": "Barletta-Andria-Trani"},
        {"code": "BR", "name": "Brindisi"},
        {"code": "FG", "name": "Foggia"},
        {"code": "LE", "name": "Lecce"},
        {"code": "TA", "name": "Taranto"},
    ],
    "Sardegna": [
        {"code": "CA", "name": "Cagliari"},
        {"code": "NU", "name": "Nuoro"},
        {"code": "OR", "name": "Oristano"},
        {"code": "SS", "name": "Sassari"},
        {"code": "SU", "name": "Sud Sardegna"},
    ],
    "Sicilia": [
        {"code": "AG", "name": "Agrigento"},
        {"code": "CL", "name": "Caltanissetta"},
        {"code": "CT", "name": "Catania"},
        {"code": "EN", "name": "Enna"},
        {"code": "ME", "name": "Messina"},
        {"code": "PA", "name": "Palermo"},
        {"code": "RG", "name": "Ragusa"},
        {"code": "SR", "name": "Siracusa"},
        {"code": "TP", "name": "Trapani"},
    ],
    "Toscana": [
        {"code": "AR", "name": "Arezzo"},
        {"code": "FI", "name": "Firenze"},
        {"code": "GR", "name": "Grosseto"},
        {"code": "LI", "name": "Livorno"},
        {"code": "LU", "name": "Lucca"},
        {"code": "MS", "name": "Massa-Carrara"},
        {"code": "PI", "name": "Pisa"},
        {"code": "PO", "name": "Prato"},
        {"code": "PT", "name": "Pistoia"},
        {"code": "SI", "name": "Siena"},
    ],
    "Trentino-Alto Adige": [
        {"code": "BZ", "name": "Bolzano"},
        {"code": "TN", "name": "Trento"},
    ],
    "Umbria": [
        {"code": "PG", "name": "Perugia"},
        {"code": "TR", "name": "Terni"},
    ],
    "Valle d'Aosta": [
        {"code": "AO", "name": "Aosta"},
    ],
    "Veneto": [
        {"code": "BL", "name": "Belluno"},
        {"code": "PD", "name": "Padova"},
        {"code": "RO", "name": "Rovigo"},
        {"code": "TV", "name": "Treviso"},
        {"code": "VE", "name": "Venezia"},
        {"code": "VI", "name": "Vicenza"},
        {"code": "VR", "name": "Verona"},
    ],
}

# Costruzione tabelle di lookup veloce
VALID_PROVINCE_CODES = set()
CODE_TO_PROVINCE_NAME = {}
NAME_TO_PROVINCE_CODE = {}
PROVINCE_TO_REGION = {}

for reg, prov_list in REGION_PROVINCES.items():
    for p in prov_list:
        code = p["code"]
        name = p["name"]
        VALID_PROVINCE_CODES.add(code)
        CODE_TO_PROVINCE_NAME[code] = name
        NAME_TO_PROVINCE_CODE[name.lower()] = code
        PROVINCE_TO_REGION[code] = reg

# Alias comuni di province
NAME_TO_PROVINCE_CODE.update({
    "forli": "FC", "forlì": "FC", "cesena": "FC", "forli-cesena": "FC",
    "pesaro": "PU", "urbino": "PU", "pesaro urbino": "PU",
    "massa": "MS", "carrara": "MS", "massa carrara": "MS",
    "monza": "MB", "brianza": "MB",
    "verbania": "VB", "verbano": "VB",
    "barletta": "BT", "andria": "BT", "trani": "BT",
    "bolzano": "BZ", "bozen": "BZ", "alto adige": "BZ", "sudtirol": "BZ",
    "reggio nell'emilia": "RE", "reggio calabria": "RC", "l'aquila": "AQ", "aquila": "AQ",
    "aosta": "AO", "valle d'aosta": "AO", "vda": "AO",
})

# Mappa Prefissi CAP (prime 2 o 3 cifre del CAP italiano) -> Sigla Provincia
CAP_PREFIX_TO_PROVINCE = {
    "00": "RM", "01": "VT", "02": "RI", "03": "FR", "04": "LT",
    "05": "TR", "06": "PG",
    "07": "SS", "08": "NU", "09": "CA", "090": "SU", "091": "CA", "0901": "SU", "0902": "SU", "0907": "OR", "0917": "OR",
    "10": "TO", "11": "AO", "12": "CN", "13": "VC", "138": "BI", "139": "BI", "14": "AT", "15": "AL",
    "16": "GE", "17": "SV", "18": "IM", "19": "SP",
    "20": "MI", "208": "MB", "209": "MB", "21": "VA", "22": "CO", "23": "SO", "238": "LC", "239": "LC",
    "24": "BG", "25": "BS", "26": "CR", "268": "LO", "269": "LO", "27": "PV",
    "28": "NO", "288": "VB", "289": "VB", "29": "PC",
    "30": "VE", "31": "TV", "32": "BL", "33": "UD", "3307": "PN", "3308": "PN", "3309": "PN", "3317": "PN",
    "34": "TS", "3407": "GO", "3417": "GO", "35": "PD", "36": "VI", "37": "VR", "38": "TN", "39": "BZ",
    "40": "BO", "41": "MO", "42": "RE", "43": "PR", "44": "FE", "45": "RO", "46": "MN", "47": "FC", "478": "RN", "479": "RN", "48": "RA",
    "50": "FI", "51": "PT", "52": "AR", "53": "SI", "54": "MS", "55": "LU", "56": "PI", "57": "LI", "58": "GR", "59": "PO",
    "60": "AN", "61": "PU", "62": "MC", "63": "AP", "638": "FM", "639": "FM",
    "64": "TE", "65": "PE", "66": "CH", "67": "AQ",
    "70": "BA", "71": "FG", "72": "BR", "73": "LE", "74": "TA", "76": "BT",
    "75": "MT", "85": "PZ",
    "80": "NA", "81": "CE", "82": "BN", "83": "AV", "84": "SA",
    "86": "CB", "8607": "IS", "8608": "IS", "8609": "IS", "8617": "IS",
    "87": "CS", "88": "CZ", "888": "KR", "889": "KR", "89": "RC", "898": "VV", "899": "VV",
    "90": "PA", "91": "TP", "92": "AG", "93": "CL", "94": "EN", "95": "CT", "96": "SR", "97": "RG", "98": "ME"
}

# Comuni frequenti in ambito gastronomico per risoluzione diretta
KNOWN_MUNICIPALITIES = {
    # Valle d'Aosta
    "courmayeur": "AO", "cogne": "AO", "saint-vincent": "AO", "breuil-cervinia": "AO", "cervinia": "AO",
    "brusson": "AO", "morgex": "AO", "sarre": "AO", "arnad": "AO", "donnas": "AO", "gignod": "AO",
    "ayas": "AO", "valtournenche": "AO", "la thuile": "AO", "gressoney": "AO", "chatillon": "AO",
    # Lazio
    "proceno": "VT", "acquapendente": "VT", "bolsena": "VT", "viterbo": "VT", "civita castellana": "VT",
    "amatrice": "RI", "accumoli": "RI", "leonessa": "RI",
    "fiuggi": "FR", "anagni": "FR", "cassino": "FR", "sora": "FR",
    "gaeta": "LT", "sperlonga": "LT", "terracina": "LT", "ponza": "LT",
    "fiumicino": "RM", "frascati": "RM", "tivoli": "RM", "ariccia": "RM", "albano": "RM",
    # Emilia-Romagna
    "salsomaggiore": "PR", "busseto": "PR", "fidenza": "PR", "langhirano": "PR", "collecchio": "PR", "soragna": "PR", "polesine": "PR",
    "carpi": "MO", "sassuolo": "MO", "formigine": "MO", "vignola": "MO", "castelvetro": "MO",
    "correggio": "RE", "guastalla": "RE", "scandiano": "RE", "rubiera": "RE",
    "imola": "BO", "casalecchio": "BO", "san lazzaro": "BO",
    "cervia": "RA", "faenza": "RA", "lugo": "RA",
    "riccione": "RN", "cattolica": "RN", "santarcangelo": "RN",
    "cesenatico": "FC", "comacchio": "FE", "bobbi": "PC", "castell'arquato": "PC",
    # Piemonte
    "alba": "CN", "bra": "CN", "barolo": "CN", "la morra": "CN", "monforte": "CN", "saluzzo": "CN", "pollenzo": "CN",
    "stresa": "VB", "orta": "NO", "borgomanero": "NO", "arona": "NO",
    "casale monferrato": "AL", "acqui terme": "AL", "novi ligure": "AL", "tortona": "AL", "canelli": "AT", "nizza monferrato": "AT",
    # Lombardia
    "franciacorta": "BS", "erbusco": "BS", "desenzano": "BS", "sirmione": "BS", "gardone": "BS", "salò": "BS",
    "bellagio": "CO", "cernobbio": "CO", "menaggio": "CO",
    "bormio": "SO", "livigno": "SO", "chiavenna": "SO", "tirano": "SO",
    "crema": "CR", "vigevano": "PV", "voghera": "PV", "busto arsizio": "VA", "gallarate": "VA",
    # Veneto & Trentino & FVG
    "cortina": "BL", "cortina d'ampezzo": "BL", "jesolo": "VE", "chioggia": "VE", "murano": "VE", "burano": "VE",
    "abano terme": "PD", "cittadella": "PD", "este": "PD",
    "bassano del grappa": "VI", "asiago": "VI", "schio": "VI",
    "conegliano": "TV", "valdobbiadene": "TV", "asolo": "TV", "castelfranco": "TV",
    "bardolino": "VR", "peschiera": "VR", "valeggio": "VR", "soave": "VR",
    "merano": "BZ", "bressanone": "BZ", "brunico": "BZ", "ortisei": "BZ", "corvara": "BZ",
    "rovereto": "TN", "riva del garda": "TN", "madonna di campiglio": "TN",
    "cormons": "GO", "grado": "GO", "cividale": "UD", "san daniele": "UD", "tarvisio": "UD",
    # Toscana
    "montalcino": "SI", "montepulciano": "SI", "san gimignano": "SI", "pienza": "SI", "chianti": "SI",
    "forte dei marmi": "LU", "viareggio": "LU", "pietrasanta": "LU",
    "cortona": "AR", "bolgheri": "LI", "castagneto": "LI", "portoferraio": "LI",
    "orbetello": "GR", "montalto": "VT", "castiglione della pescaia": "GR",
    # Campania, Puglia, Sicilia, Sardegna
    "sorrento": "NA", "massa lubrense": "NA", "capri": "NA", "ischia": "NA", "pompei": "NA", "vico equense": "NA", "gragnano": "NA",
    "amalfi": "SA", "positano": "SA", "ravello": "SA", "paestum": "SA", "capaccio": "SA", "cetara": "SA",
    "ostuni": "BR", "fasano": "BR", "ceglie messapica": "BR",
    "polignano a mare": "BA", "monopoli": "BA", "alberobello": "BA", "altamura": "BA", "gravina": "BA",
    "gallipoli": "LE", "otranto": "LE", "martina franca": "TA", "vieste": "FG",
    "taormina": "ME", "lipari": "ME", "salina": "ME", "milazzo": "ME",
    "cefalu": "PA", "cefalù": "PA", "monreale": "PA",
    "noto": "SR", "ortigia": "SR", "modica": "RG", "scicli": "RG", "ragusa ibla": "RG",
    "marsala": "TP", "mazara": "TP", "san vito lo capo": "TP", "erice": "TP",
    "bronte": "CT", "acireale": "CT", "caltagirone": "CT", "riposto": "CT",
    "porto cervo": "SS", "arzachena": "SS", "olbia": "SS", "alghero": "SS", "villasimius": "CA"
}


def extract_province(city: str = "", address: str = "", region: str = "") -> str:
    """
    Estrae la sigla della provincia (es. 'PR', 'VT', 'AO', 'MI') combinando:
    1. Sigla esplicita tra parentesi o dopo trattino, es. 'Proceno (Vt)' o '41121 Modena (MO)'
    2. CAP a 5 cifre presente nell'indirizzo o nella città
    3. Match del nome del comune / capoluogo di provincia
    4. Fallback regionale se regione mono-provincia (es. Valle d'Aosta -> AO)
    """
    combined = f"{city} {address}".strip()

    # 1. Cerca sigla tra parentesi es. (VT), (Vt), (AO), (PR)
    paren_matches = re.findall(r'\(([A-Za-z]{2})\)', combined)
    for m in paren_matches:
        code = m.upper()
        if code in VALID_PROVINCE_CODES:
            return code

    # 2. Cerca CAP a 5 cifre nell'indirizzo o città
    cap_matches = re.findall(r'\b([0-9]{5})\b', combined)
    for cap in cap_matches:
        if cap[:4] in CAP_PREFIX_TO_PROVINCE:
            return CAP_PREFIX_TO_PROVINCE[cap[:4]]
        if cap[:3] in CAP_PREFIX_TO_PROVINCE:
            return CAP_PREFIX_TO_PROVINCE[cap[:3]]
        if cap[:2] in CAP_PREFIX_TO_PROVINCE:
            return CAP_PREFIX_TO_PROVINCE[cap[:2]]

    # 3. Cerca match diretto con capoluogo di provincia o comune noto
    clean_city = re.sub(r'\([A-Za-z]{2}\)', '', str(city)).strip().lower()
    clean_city = re.sub(r'^\b\d{5}\b\s*', '', clean_city).strip()
    clean_city = clean_city.replace("it-", "").replace("-", " ").strip()

    if clean_city in NAME_TO_PROVINCE_CODE:
        return NAME_TO_PROVINCE_CODE[clean_city]
    if clean_city in KNOWN_MUNICIPALITIES:
        return KNOWN_MUNICIPALITIES[clean_city]

    # Cerca sottostringa comune noto o provincia dentro city o address
    combined_lower = combined.lower()
    for muni, code in KNOWN_MUNICIPALITIES.items():
        if re.search(rf'\b{re.escape(muni)}\b', combined_lower):
            return code
    for pname, code in NAME_TO_PROVINCE_CODE.items():
        if len(pname) > 3 and re.search(rf'\b{re.escape(pname)}\b', combined_lower):
            return code

    # 4. Cerca sigla provincia isolata a fine stringa (es. "Modena MO")
    end_code = re.search(r'\b([A-Z]{2})\s*$', combined.strip())
    if end_code and end_code.group(1) in VALID_PROVINCE_CODES:
        return end_code.group(1)

    # 5. Fallback per regione mono-provincia o prima provincia se regione nota
    if region:
        provs = REGION_PROVINCES.get(region, [])
        if len(provs) == 1:
            return provs[0]["code"]

    return ""


def format_province_display(code: str) -> str:
    """Restituisce 'PR (Parma)' oppure solo il codice se non trovato."""
    code = (code or "").strip().upper()
    if code in CODE_TO_PROVINCE_NAME:
        return f"{code} ({CODE_TO_PROVINCE_NAME[code]})"
    return code


def get_provinces_for_regions(regions: List[str]) -> List[str]:
    """Restituisce la lista formattata 'Tutte le Province', 'PR - Parma', ecc. per la GUI."""
    options = ["Tutte le Province"]
    seen = set()
    for reg in regions:
        for p in REGION_PROVINCES.get(reg, []):
            item = f"{p['code']} - {p['name']}"
            if item not in seen:
                seen.add(item)
                options.append(item)
    return options


def parse_selected_province_code(gui_selection: str) -> Optional[str]:
    """Estrae la sigla a 2 lettere dalla selezione GUI (es. 'PR - Parma' -> 'PR'), o None se 'Tutte'."""
    if not gui_selection or "tutte" in gui_selection.lower():
        return None
    parts = gui_selection.split("-")
    code = parts[0].strip().upper()
    if code in VALID_PROVINCE_CODES:
        return code
    return None
