#!/usr/bin/env python3
import os
import json
import re
from textwrap import dedent
from dotenv import load_dotenv
from openai import OpenAI
from utility.utils import log_response, LOG_TYPE_GPT, LOG_TYPE_STORYBOARD

load_dotenv()

# --- CARREGAMENTO DE PROMPT EXTERNO ---

def load_prompt_from_file(file_path: str, fallback_prompt: str) -> str:
    """Lê um prompt de um arquivo, com um texto de fallback em caso de erro."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"⚠️ Arquivo de prompt não encontrado em '{file_path}'. Usando prompt padrão.")
        return fallback_prompt

visual_plan_prompt_path = "prompts/visual_plan_prompt.txt"
fallback_visual_plan_prompt = dedent("""
# Instruções para Gerar um Plano Visual (Storyboard)

Você é um diretor de arte de IA. Seu objetivo é criar um plano visual para um vídeo a partir de um roteiro e legendas temporizadas.

Para cada segmento do roteiro, decida o melhor formato visual seguindo estas prioridades:
1.  `"video"`: **Use este tipo para a maior parte da narrativa.** Deve ser a sua escolha padrão para ilustrar o roteiro.
2.  `"slide"`: **Use este tipo APENAS** para apresentar dados específicos, listas, nomes próprios, ou conceitos-chave que precisam de destaque visual com texto. Não use para narrativa geral.
3.  `"title"`: **Use este tipo UMA VEZ** para a introdução do vídeo, se aplicável.

**Formato de Saída Obrigatório**: um array JSON de "cenas". Cada cena DEVE ser um objeto com os seguintes campos:
- `"start"`: Início do segmento em segundos (float).
- `"end"`: Fim do segmento em segundos (float).
- `"type"`: O tipo de cena (`"video"`, `"title"`, ou `"slide"`).
- `"data"`: Um objeto contendo os dados para aquele tipo de cena:
    - Para `"type": "video"`, a data deve ser: `{"keywords": ["query para vídeo de fundo"]}`
    - Para `"type": "title"`, a data deve ser: `{"main_text": "TÍTULO PRINCIPAL E CHAMATIVO", "background_keywords": ["query para vídeo de fundo"]}`
    - Para `"type": "slide"`, a data deve ser: `{"slide_text": "Texto do slide", "background_keywords": ["query para VÍDEO de fundo"]}`
""")
prompt_base = load_prompt_from_file(visual_plan_prompt_path, fallback_visual_plan_prompt)


# --- INICIALIZAÇÃO DO CLIENTE LLM E FUNÇÕES ---

groq_key = os.environ.get("GROQ_API_KEY", "")
if len(groq_key) > 30:
    from groq import Groq
    model = "llama3-70b-8192"
    client = Groq(api_key=groq_key)
else:
    model = "gpt-4o"
    openai_key = os.getenv('OPENAI_API_KEY')
    if not openai_key:
        raise ValueError('A chave da API da OpenAI não foi definida.')
    client = OpenAI(api_key=openai_key)


def fix_json(json_str: str) -> str:
    """Função auxiliar para corrigir erros comuns em JSONs gerados por LLMs."""
    return json_str.replace("’", "'").replace("“", '"').replace("”", '"')

def generate_visual_plan(script: str, captions_timed: list, video_source: str, user_keywords: str = None) -> list:
    """Gera um plano visual completo (storyboard) a partir do roteiro e legendas."""
    final_prompt = prompt_base
    if user_keywords:
        user_guideline = f"**Diretriz de Conteúdo Fornecida pelo Usuário:** Dê preferência a visuais que se relacionem com estas palavras-chave: {user_keywords}.\n\n"
        final_prompt = user_guideline + final_prompt
    if video_source.lower() == 'pexels':
        insertion_point = final_prompt.find("**Formato de Saída Obrigatório**")
        if insertion_point != -1:
            instruction = "**Instrução Crítica de Idioma: Todas as queries de busca (`keywords` e `background_keywords`) DEVEM ser geradas em INGLÊS.**\n\n"
            final_prompt = final_prompt[:insertion_point] + instruction + final_prompt[insertion_point:]
    
    user_content = f"Roteiro: {script}\n\nLegendas Temporizadas: {captions_timed}"
    response = client.chat.completions.create(
        model=model,
        temperature=0.7,
        messages=[
            {"role": "system", "content": final_prompt},
            {"role": "user", "content": user_content}
        ],
        response_format={"type": "json_object"}
    )
    content = response.choices[0].message.content.strip()
    log_response(LOG_TYPE_GPT, script, content)
    
    try:
        data = json.loads(content)
        visual_plan_list = []
        if isinstance(data, list):
            visual_plan_list = data
        elif isinstance(data, dict):
            for key in data:
                if isinstance(data[key], list):
                    visual_plan_list = data[key]
                    break
        if not visual_plan_list:
            print("⚠️ O plano visual retornado pela IA está vazio ou em formato inesperado.")
        
        log_response(LOG_TYPE_STORYBOARD, script, visual_plan_list)
        return visual_plan_list
    except (json.JSONDecodeError, AttributeError):
        print("⚠️ Falha ao decodificar JSON da IA, tentando extração manual.")
        match = re.search(r'\[.*\]', content, re.DOTALL)
        if match:
            json_str = match.group(0)
            parsed_json = json.loads(fix_json(json_str))
            log_response(LOG_TYPE_STORYBOARD, script, parsed_json)
            return parsed_json
        else:
            raise ValueError("Não foi possível extrair um array JSON válido da resposta da IA.")

def create_slideshow_plan(slideshow_script: list, duration_per_slide: int = 7) -> list:
    """Converte um roteiro de slideshow em um plano visual."""
    visual_plan = []
    current_time = 0
    for i, slide in enumerate(slideshow_script):
        start_time = current_time
        end_time = start_time + duration_per_slide
        slide_text_content = f"{slide.get('title', '')}\n\n{slide.get('text', '')}"
        search_keywords = slide.get('search_keywords', [slide.get('title', '')])
        scene = {
            "start": start_time,
            "end": end_time,
            "type": "slide",
            "data": {
                "slide_text": slide_text_content,
                "background_keywords": search_keywords
            }
        }
        visual_plan.append(scene)
        current_time = end_time
    return visual_plan