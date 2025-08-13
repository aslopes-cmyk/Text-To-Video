import os
from datetime import datetime
import json
import re
import unicodedata

# Log types
LOG_TYPE_GPT = "GPT"
LOG_TYPE_PEXEL = "PEXEL"
LOG_TYPE_STORYBOARD = "STORYBOARD"

# log directory paths
DIRECTORY_LOG_GPT = ".logs/gpt_logs"
DIRECTORY_LOG_PEXEL = ".logs/pexel_logs"
DIRECTORY_LOG_STORYBOARD = ".logs/storyboard_logs"

# method to log response from pexel and openai
def log_response(log_type, query,response):
    log_entry = {
        "query": query,
        "response": response,
        "timestamp": datetime.now().isoformat()
    }
    if log_type == LOG_TYPE_GPT:
        if not os.path.exists(DIRECTORY_LOG_GPT):
            os.makedirs(DIRECTORY_LOG_GPT)
        filename = '{}_gpt3.txt'.format(datetime.now().strftime("%Y%m%d_%H%M%S"))
        filepath = os.path.join(DIRECTORY_LOG_GPT, filename)
        with open(filepath, "w") as outfile:
            outfile.write(json.dumps(log_entry) + '\n')

    if log_type == LOG_TYPE_PEXEL:
        if not os.path.exists(DIRECTORY_LOG_PEXEL):
            os.makedirs(DIRECTORY_LOG_PEXEL)
        filename = '{}_pexel.txt'.format(datetime.now().strftime("%Y%m%d_%H%M%S"))
        filepath = os.path.join(DIRECTORY_LOG_PEXEL, filename)
        with open(filepath, "w") as outfile:
            outfile.write(json.dumps(log_entry) + '\n')
            
    if log_type == LOG_TYPE_STORYBOARD:
        if not os.path.exists(DIRECTORY_LOG_STORYBOARD):
            os.makedirs(DIRECTORY_LOG_STORYBOARD)
        filename = '{}_storyboard.txt'.format(datetime.now().strftime("%Y%m%d_%H%M%S"))
        filepath = os.path.join(DIRECTORY_LOG_STORYBOARD, filename)
        with open(filepath, "w", encoding='utf-8') as outfile:
            # Salva o JSON formatado para fácil leitura
            json.dump(log_entry, outfile, indent=2, ensure_ascii=False)
            outfile.write('\n')

def slugify(text: str) -> str:
    """
    Converte uma string em um "slug" seguro para nomes de arquivo.
    Ex: "Os Benefícios do Café!" -> "os-beneficios-do-cafe"
    """
    # Normaliza para decompor acentos
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
    # Converte para minúsculas e remove caracteres inválidos
    text = re.sub(r'[^\w\s-]', '', text).strip().lower()
    # Substitui espaços e múltiplos hífens por um único hífen
    text = re.sub(r'[-\s]+', '-', text)
    # Limita o comprimento para manter o nome curto
    return text[:50]