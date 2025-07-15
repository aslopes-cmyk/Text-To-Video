#!/usr/bin/env python3
import os
import json
import re
from dotenv import load_dotenv  # Carrega variáveis de ambiente de um arquivo .env
from openai import OpenAI

load_dotenv()

# Configurações de parâmetros
target_duration = 60     # duração alvo em segundos
approx_words = 180       # contagem aproximada de palavras
orientation = "horizontal 16:9"
template_path = os.path.join(
    os.path.dirname(__file__),
    'templates',
    'explanatory_prompt_pt_BR.txt'
)

# Carrega template de prompt externo, se disponível
try:
    with open(template_path, 'r', encoding='utf-8') as f:
        prompt_template = f.read()
except FileNotFoundError:
    prompt_template = (
        "Você é um redator experiente para vídeos jornalísticos em formato {orientation}, "
        "especializado em conteúdos explicativos. Cada vídeo deve durar aproximadamente {duration} "
        "segundos (aproximadamente {words} palavras). Foque em clareza, precisão jornalística e na "
        "capacidade de ajudar o público a compreender o tema solicitado.\n\n"
        "Quando o usuário solicitar um tópico, gere um roteiro em Português do Brasil estruturado "
        "em parágrafos claros e objetivos.\n\n"
        "A saída deve ser apenas um objeto JSON com a chave \"script\" contendo o roteiro completo:\n"
        "{{\"script\":\"Aqui vai o roteiro completo do vídeo...\"}}\n"
    )

# Formata prompt com parâmetros
template = prompt_template.format(
    orientation=orientation,
    duration=target_duration,
    words=approx_words
)

# Inicialização do cliente LLM
groq_key = os.environ.get('GROQ_API_KEY', '')
if len(groq_key) > 30:
    from groq import Groq
    model = 'mixtral-8x7b-32768'
    client = Groq(api_key=groq_key)
else:
    model = 'gpt-4o'
    # Usa OPENAI_API_KEY carregada do .env ou variáveis de ambiente de sistema
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    if not OPENAI_API_KEY:
        raise ValueError('A variável de ambiente OPENAI_API_KEY não está definida.')
    client = OpenAI(api_key=OPENAI_API_KEY)


def fix_json(json_str: str) -> str:
    """
    Ajusta aspas tipográficas para padrão JSON.
    """
    replacements = {'“': '"', '”': '"', '‘': "'", '’': "'"}
    for old, new in replacements.items():
        json_str = json_str.replace(old, new)
    return json_str


def generate_script(topic: str) -> str:
    """
    Gera o roteiro explicativo para vídeo jornalístico em 16:9.
    Retorna apenas a string do script.
    """
    response = client.chat.completions.create(
        model=model,
        temperature=0.7,
        messages=[
            {'role': 'system', 'content': template},
            {'role': 'user', 'content': topic}
        ]
    )

    content = response.choices[0].message.content.strip()
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        # Extrai JSON bruto e ajusta aspas
        start = content.find('{')
        end = content.rfind('}') + 1
        snippet = content[start:end]
        snippet = fix_json(snippet)
        data = json.loads(snippet)
    return data.get('script', '')


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print('Uso: python script_generator.py "Tópico do vídeo explicativo"')
        sys.exit(1)
    topic = sys.argv[1]
    script = generate_script(topic)
    print(script)
