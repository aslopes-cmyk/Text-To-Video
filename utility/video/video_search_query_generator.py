#!/usr/bin/env python3
import os
import json
import re
import math
from datetime import datetime
from textwrap import dedent
from dotenv import load_dotenv
from openai import OpenAI
from utility.utils import log_response, LOG_TYPE_GPT

# Carrega variáveis de ambiente de .env
load_dotenv()

# Configuração de parâmetros de duração
total_duration = 60      # duração alvo em segundos
min_segment = 4           # duração mínima de cada bloco (s)
max_segment = 6           # duração máxima de cada bloco (s)
est_segments = int(total_duration / ((min_segment + max_segment) / 2))
intro_duration = 6
outro_duration = 6
central_duration = total_duration - intro_duration - outro_duration

# Inicializa cliente de LLM
groq_key = os.environ.get("GROQ_API_KEY", "")
if len(groq_key) > 30:
    from groq import Groq
    model = "llama3-70b-8192"
    client = Groq(api_key=groq_key)
else:
    model = "gpt-4o"
    openai_key = os.getenv('OPENAI_API_KEY')
    if not openai_key:
        raise ValueError('A variável OPENAI_API_KEY não está definida para vídeo_search_query_generator.')
    client = OpenAI(api_key=openai_key)

# Monta prompt dinamicamente
prompt = dedent(f"""# 
                
Instruções para gerar queries de busca de vídeo

Você tem um roteiro jornalístico (vídeo de ~{total_duration}s) dividido em segmentos de {min_segment}–{max_segment}s.
Para cada segmento, há início (`start`), fim (`end`) e um breve texto narrado (`trecho`).

**Objetivo**: criar **três** strings de busca em **português**, **visualmente concretas**, que tragam cenas diretamente relacionadas ao conteúdo do segmento:
- Use **substantivos** e **adjetivos** que descrevam o objeto ou ação principal (ex.: “vista do Morro do Moreno, Vila Velha” em vez de “vista de montanha”).
- Adicione **cenário** ou **contexto** se ajudar (ex.: “biblloteca antiga cheia de livros”).
- Evite termos genéricos ou abstratos (não use “momento feliz”; use “criança sorrindo”, “rua ensolarada”).
- Cada query deve ser de 1 a 10 palavras.

**Formato de saída**: um array JSON com itens:
```json
[
{{"start": "00:00", "end": "00:04", "keywords": ["gato cheirando flor em uma mesa", "páginas de um livro antigo", "escritório vintage"]}},
…
]
```

+**Importante**: as queries precisam ser diretas, curtas e em inglês.
+\"\"\")
""")

log_directory = ".logs/gpt_logs"

def fix_json(json_str: str) -> str:
    json_str = json_str.replace("’", "'")
    json_str = json_str.replace("“", '"').replace("”", '"').replace("‘", '"').replace("’", '"')
    json_str = json_str.replace('"you didn"t"', '"you didn\'t"')
    return json_str


def to_seconds(time_val):
    # Converte formatos "mm:ss" ou valor numérico para segundos (float)
    if isinstance(time_val, (int, float)):
        return float(time_val)
    if isinstance(time_val, str) and ':' in time_val:
        m, s = time_val.split(':')
        return int(m) * 60 + float(s)
    try:
        return float(time_val)
    except:
        return 0.0


def normalize_segments(segments):
    normalized = []
    for (start, end), kws in segments:
        dur = end - start
        if dur > max_segment:
            num = math.ceil(dur / max_segment)
            step = dur / num
            for i in range(num):
                s = start + i * step
                e = min(end, start + (i + 1) * step)
                normalized.append(((round(s, 2), round(e, 2)), kws))
        else:
            normalized.append(((start, end), kws))
    return normalized


def getVideoSearchQueriesTimed(script, captions_timed):
    end_time = captions_timed[-1][0][1]
    # 1) chama uma única vez
    content = call_OpenAI(script, captions_timed)
    try:
        raw = json.loads(content)
    except json.JSONDecodeError:
        cleaned = content.replace("```json", "").replace("```", "")
        raw = json.loads(fix_json(cleaned))

    # 2) converte dicionários em [[start,end], keywords]
    out = []
    for item in raw:
        s = to_seconds(item.get('start', 0))
        e = to_seconds(item.get('end',   0))
        kws = item.get('keywords', [])
        out.append([[s, e], kws])

    # 3) normaliza segmentos maiores/menores que o esperado
    out = normalize_segments(out)
    print(f"Gerados {len(out)} segmentos para {end_time}s (meta: {est_segments})")
    return out


def call_OpenAI(script, captions_timed):
    user_content = f"Script: {script}\nTimed Captions: {captions_timed}"
    response = client.chat.completions.create(
        model=model,
        temperature=0.7,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_content}
        ]
    )
    text = response.choices[0].message.content.strip()
    text = re.sub(r'\s+', ' ', text)
    log_response(LOG_TYPE_GPT, script, text)
    return text


def merge_empty_intervals(segments):
    merged = []
    i = 0
    while i < len(segments):
        interval, url = segments[i]
        if url is None:
            j = i + 1
            while j < len(segments) and segments[j][1] is None:
                j += 1
            if i > 0:
                prev_interval, prev_url = merged[-1]
                if prev_url is not None and prev_interval[1] == interval[0]:
                    merged[-1] = [[prev_interval[0], segments[j-1][0][1]], prev_url]
                else:
                    merged.append([interval, prev_url])
            else:
                merged.append([interval, None])
            i = j
        else:
            merged.append([interval, url])
            i += 1
    return merged
