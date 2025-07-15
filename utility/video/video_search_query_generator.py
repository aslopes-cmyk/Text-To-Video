#!/usr/bin/env python3
import os
import json
import re
import math
from datetime import datetime
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
prompt = f"""# Instruções

Dado o seguinte material de origem — seja um texto, um arquivo ou uma URL — analise-o e gere um roteiro de vídeo em Português do Brasil, destinado a fins jornalísticos. O roteiro deve obedecer a estas regras:

Estruture segmentos de tempo consecutivos, cobrindo toda a duração do vídeo, com duração aproximada de {min_segment} a {max_segment} segundos cada.

Para cada segmento, apresente:

start: tempo inicial (em segundos ou no formato “mm:ss”).
end: tempo final (em segundos ou no formato “mm:ss”).
trecho: texto do roteiro que será narrado, claro e objetivo.
keywords: três palavras ou expressões curtas, em Português, visualmente concretas, que possam ser usadas para buscar imagens ou vídeos de fundo.

Inclua:
1. Introdução (00:00–00:{intro_duration:02d}): apresentação do tema.
2. {est_segments - 2} segmentos centrais (~{central_duration // ((min_segment + max_segment)//2)} segmentos) cada um de {min_segment}-{max_segment}s com informações específicas.
3. Conclusão (últimos {outro_duration}s): recapitulação jornalística e chamada à ação.

A saída deve ser apenas um array JSON no formato:

[
  {{
    "start": "00:00",
    "end": "00:04",
    "trecho": "Texto do roteiro para este intervalo de tempo.",
    "keywords": ["palavra-chave1", "palavra-chave2", "palavra-chave3"]
  }},
  …
]

Exemplo de keywords
Legenda: “O guepardo é o animal terrestre mais rápido, alcançando até 120 km/h.”
Keywords: ["guepardo correndo", "animal veloz", "120 km/h"]

Observação:
Este roteiro será usado em produção jornalística; seja o mais preciso possível.
Total de duração alvo: {total_duration}s, segmentos de {min_segment}-{max_segment}s, total aproximado de {est_segments} segmentos.
"""

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
    out = []
    try:
        while True:
            content = call_OpenAI(script, captions_timed)
            # tenta carregar JSON
            try:
                raw = json.loads(content)
            except json.JSONDecodeError:
                cleaned = content.replace("```json", "").replace("```", "")
                cleaned = fix_json(cleaned)
                raw = json.loads(cleaned)
            # converte dicts para o formato interno
            if raw and isinstance(raw[0], dict):
                converted = []
                for item in raw:
                    try:
                        start = to_seconds(item['start'])
                        end = to_seconds(item['end'])
                        kws = item.get('keywords', [])
                        converted.append([[start, end], kws])
                    except KeyError:
                        continue
                out = converted
            else:
                out = raw
            # verifica término
            if out and to_seconds(out[-1][0][1]) == end_time:
                break
        out = normalize_segments(out)
        print(f"Gerados {len(out)} segmentos para {end_time}s (meta: {est_segments})")
        return out
    except Exception as e:
        print("Erro ao gerar queries de vídeo: ", repr(e))
        raise


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
