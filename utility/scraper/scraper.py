# utility/scraper/scraper.py
import requests
from bs4 import BeautifulSoup

def extract_text_from_url(url: str) -> str:
    """Extrai o texto principal de uma URL de notícia."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Tenta encontrar o conteúdo principal (isto pode precisar de ajuste por site)
        article_body = soup.find('article') or soup.find('main')
        if not article_body:
            print("⚠️ Tag <article> ou <main> não encontrada. Extraindo todo o texto da página.")
            return soup.get_text(separator=' ', strip=True)

        # Remove lixo (scripts, estilos, etc.) antes de extrair o texto
        for element in (article_body.find_all("script") + article_body.find_all("style")):
            element.decompose()
            
        return article_body.get_text(separator=' ', strip=True)
    except Exception as e:
        print(f"Erro ao extrair texto da URL {url}: {e}")
        return None