#!/usr/bin/env python3
import os
import json
import re
from dotenv import load_dotenv
from openai import OpenAI
from textwrap import dedent

load_dotenv()

# --- LÓGICA PARA O MODO DE VÍDEO COMPLETO ---

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
    
    # Prompt para geracao do script 
    prompt_template = (
        "Você é um redator experiente para vídeos jornalísticos em formato horizontal 16:9, "
        "especializado em conteúdos explicativos para o portal de notícias A Gazeta.\n\n"
        "**Regras para a criação do roteiro:**\n"
        "1.  **Gancho Inicial:** Comece com o dado mais impactante ou uma pergunta provocativa para "
        "prender a atenção (máximo 2 frases curtas). Não revele a informação completa na introdução.\n"
        "2.  **Contexto:** Explique em até 2 frases sobre o que é o vídeo e por que o tema é importante.\n"
        "3.  **Desenvolvimento:** Apresente as informações principais em ordem lógica. Use uma linguagem "
        "simples e texto direto.\n"
        "4.  **Estilo:** O vídeo é atemporal. Evite datas e nomes de pessoas, a menos que seja essencial "
        "para o tema.\n"
        "5.  **Conclusão:** Resuma a ideia central do vídeo, sem repetições.\n"
        "6.  **Duração:** O roteiro completo deve ter aproximadamente 180 palavras (cerca de 60 segundos "
        "de narração).\n\n"
        "**Formato de Saída:**\n"
        "A saída deve ser apenas um objeto JSON com a chave \"script\" contendo o roteiro completo, "
        "seguindo todas as regras acima.\n"
        "{\"script\":\"Aqui vai o roteiro completo do vídeo...\"}"
    )


template = prompt_template

# Inicialização do cliente LLM
groq_key = os.environ.get('GROQ_API_KEY', '')
if len(groq_key) > 30:
    from groq import Groq
    model = 'mixtral-8x7b-32768'
    client = Groq(api_key=groq_key)
else:
    model = 'gpt-4o'
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    if not OPENAI_API_KEY:
        raise ValueError('A variável de ambiente OPENAI_API_KEY não está definida.')
    client = OpenAI(api_key=OPENAI_API_KEY)


def fix_json(json_str: str) -> str:
    """Ajusta aspas tipográficas para padrão JSON."""
    replacements = {'“': '"', '”': '"', '‘': "'", '’': "'"}
    for old, new in replacements.items():
        json_str = json_str.replace(old, new)
    return json_str


def generate_script(topic: str) -> str:
    """Gera o roteiro explicativo para o modo de vídeo completo."""
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
        start = content.find('{')
        end = content.rfind('}') + 1
        snippet = content[start:end]
        snippet = fix_json(snippet)
        data = json.loads(snippet)
    return data.get('script', '')

# --- LÓGICA PARA O MODO SLIDESHOW ---

slideshow_prompt_template = dedent("""
Você é um roteirista especializado em vídeos curtos em formato de lista (listicles) para redes sociais.
Sua tarefa é criar um roteiro para um slideshow sobre o tema fornecido, contendo entre 5 e 7 slides.

O resultado deve ser um objeto JSON contendo uma chave "slides", que é uma lista de objetos.
Cada objeto da lista representa um slide e deve conter:
1. "title": Um título curto e impactante para o slide (máximo 5 palavras).
2. "text": Um texto de apoio curto (máximo 15 palavras).
3. "search_keywords": Uma lista de 2 a 3 palavras-chave de busca em INGLÊS que descrevam visualmente o conteúdo do slide.

Exemplo de saída para o tema "5 dicas para acordar cedo":
{{
  "slides": [
    {{
      "title": "1. Defina um Alarme Consistente",
      "text": "Tente acordar no mesmo horário todos os dias, inclusive nos fins de semana."
    }},
    {{
      "title": "2. Evite Telas Antes de Dormir",
      "text": "A luz azul de celulares e TVs pode atrapalhar a qualidade do seu sono."
    }}
  ]
}}
""")

def generate_slideshow_script(topic: str) -> list:
    """Gera um roteiro estruturado para um vídeo de slideshow."""
    response = client.chat.completions.create(
        model=model,
        temperature=0.8,
        messages=[
            {'role': 'system', 'content': slideshow_prompt_template},
            {'role': 'user', 'content': topic}
        ],
        response_format={"type": "json_object"}
    )
    content = response.choices[0].message.content.strip()
    try:
        data = json.loads(content)
        return data.get('slides', [])
    except (json.JSONDecodeError, AttributeError):
        print("⚠️ Falha ao decodificar JSON do roteiro de slideshow.")
        return []


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print('Uso: python script_generator.py "Tópico do vídeo explicativo"')
        sys.exit(1)
    topic = sys.argv[1]
    
    print("--- Testando Roteiro de Vídeo Padrão ---")
    script = generate_script(topic)
    print(script)
    
    print("\n--- Testando Roteiro de Slideshow ---")
    slides = generate_slideshow_script(topic)
    print(json.dumps(slides, indent=2, ensure_ascii=False))