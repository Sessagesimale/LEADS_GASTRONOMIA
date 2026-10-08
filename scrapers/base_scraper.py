import abc
from typing import List, Dict

class BaseScraper(abc.ABC):
    def __init__(self):
        self.source_name = "Base"

    @abc.abstractmethod
    def scrape(self, region: str, page: 'playwright.sync_api.Page') -> List[Dict[str, str]]:
        """
        Esegue lo scraping per una determinata regione e restituisce una lista di dizionari.
        Ogni dizionario rappresenta un lead e deve contenere (se possibile):
        - Nome
        - Indirizzo
        - Citta
        - Telefono
        - Email
        - Sito Web
        - Fonte
        - Qualita/Score
        """
        pass
