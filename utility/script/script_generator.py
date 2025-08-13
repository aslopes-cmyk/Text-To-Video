#!/usr/bin/env python3
import os
import json
import re
from textwrap import dedent
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# --- LÓGICA DE CARREGAMENTO DE PROMPTS EXTERNOS ---

def load_prompt_from_file(file_path: str, fallback_prompt: str) -> str:
    """Lê um prompt de um arquivo, com um texto de fallback em caso de erro."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"⚠️ Arquivo de prompt não encontrado em '{file_path}'. Usando prompt padrão.")
        return fallback_prompt

# Caminhos para os arquivos de prompt
video_prompt_path = "prompts/video_script_prompt.txt"
slideshow_prompt_path = "prompts/slideshow_script_prompt.txt"

# Prompts de fallback (caso os arquivos .txt não sejam encontrados)
fallback_video_prompt = dedent("""
Você é um redator experiente para vídeos jornalísticos em formato horizontal 16:9, especializado em conteúdos explicativos para o portal de notícias A Gazeta.

**Regras para a criação do roteiro:**
1.  **Gancho Inicial:** Comece com o dado mais impactante ou uma pergunta provocativa para prender a atenção (máximo 2 frases curtas). Não revele a informação completa na introdução.
2.  **Contexto:** Explique em até 2 frases sobre o que é o vídeo e por que o tema é importante.
3.  **Desenvolvimento:** Apresente as informações principais em ordem lógica. Use uma linguagem simples e texto direto.
4.  **Estilo:** O vídeo é atemporal. Evite datas e nomes de pessoas, a menos que seja essencial para o tema.
5.  **Conclusão:** Resuma a ideia central do vídeo, sem repetições.
6.  **Chamada para Ação (CTA):** Ao final, convide o espectador para acessar o site de A Gazeta para mais informações.
7.  **Duração:** O roteiro completo deve ter aproximadamente 180 palavras (cerca de 60 segundos de narração).

**Formato de Saída:**
A saída deve ser apenas um objeto JSON com a chave "script" contendo o roteiro completo, seguindo todas as regras acima.
{"script":"Aqui vai o roteiro completo do vídeo..."}
""")

fallback_slideshow_prompt = dedent("""
Você é um roteirista especializado em vídeos curtos em formato de lista (listicles) para redes sociais.
Sua tarefa é criar um roteiro para um slideshow sobre o tema fornecido, contendo entre 5 e 7 slides.

O resultado deve ser um objeto JSON contendo uma chave "slides", que é uma lista de objetos.
Cada objeto da lista representa um slide e deve conter:
1. "title": Um título curto e impactante para o slide (máximo 5 palavras).
2. "text": Um texto de apoio curto (máximo 15 palavras).
3. "search_keywords": Uma lista de 2 a 3 palavras-chave de busca em INGLÊS que descrevam visualmente o conteúdo do slide.
""")

# Carrega os prompts para uso nas funções
template = load_prompt_from_file(video_prompt_path, fallback_video_prompt)
slideshow_prompt_template = load_prompt_from_file(slideshow_prompt_path, fallback_slideshow_prompt)


# --- INICIALIZAÇÃO DO CLIENTE LLM E FUNÇÕES ---

groq_key = os.environ.get('GROQ_API_KEY', '')
if len(groq_key) > 30:
    from groq import Groq
    model = "llama3-70b-8192"
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