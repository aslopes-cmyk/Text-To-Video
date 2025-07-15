#!/usr/bin/env python3
import os
import re
from whisper_timestamped import load_model, transcribe_timestamped

# Parâmetros de configuração
default_model_size = os.getenv('WHISPER_MODEL_SIZE', 'small')
default_language = 'pt'
MAX_CAPTION_SIZE = 40          # máximo de caracteres por legenda
CONSIDER_PUNCTUATION = True    # quebrar por pontuação
MIN_CAPTION_DURATION = 4       # duração mínima de cada legenda (s)
MAX_CAPTION_DURATION = 6       # duração máxima de cada legenda (s)


def generate_timed_captions(
    audio_filename: str,
    model_size: str = default_model_size,
    language: str = default_language
):
    """
    Transcreve o áudio e gera legendas temporizadas em Português.
    Retorna lista de tuplas [((start, end), texto), ...].
    """
    whisper_model = load_model(model_size)
    # Inclui parâmetro de idioma se suportado
    gen = transcribe_timestamped(
        whisper_model,
        audio_filename,
        verbose=False,
        fp16=False,
        language=language
    )
    captions = get_captions_with_time(
        whisper_analysis=gen,
        max_caption_size=MAX_CAPTION_SIZE,
        consider_punctuation=CONSIDER_PUNCTUATION
    )
    # Normaliza duração das legendas para o intervalo desejado
    return normalize_captions(captions)


def split_words_by_size(words, max_caption_size: int):
    half_size = max_caption_size / 2
    captions = []
    while words:
        caption = words.pop(0)
        while words and len(caption + ' ' + words[0]) <= max_caption_size:
            caption += ' ' + words.pop(0)
            if len(caption) >= half_size and words:
                break
        captions.append(caption)
    return captions


def get_timestamp_mapping(whisper_analysis: dict):
    index = 0
    mapping = {}
    for segment in whisper_analysis.get('segments', []):
        for word in segment.get('words', []):
            start_idx = index
            end_idx = start_idx + len(word['text']) + 1
            mapping[(start_idx, end_idx)] = word.get('end')
            index = end_idx
    return mapping


def clean_word(word: str) -> str:
    # preserva caracteres de palavras em PT (acentos) e hífens
    return re.sub(r"[^\wÀ-ÿ\s\-_'\"]", "", word)



def interpolate_time(position: int, mapping: dict):
    for (start, end), ts in mapping.items():
        if start <= position <= end:
            return ts
    return None


def get_captions_with_time(
    whisper_analysis: dict,
    max_caption_size: int,
    consider_punctuation: bool
):
    word_map = get_timestamp_mapping(whisper_analysis)
    position = 0
    start_time = 0
    captions = []
    text = whisper_analysis.get('text', '')

    # Quebra em palavras agrupadas
    if consider_punctuation:
        sentences = re.split(r'(?<=[.!?]) +', text)
        chunks = []
        for sentence in sentences:
            words = sentence.split()
            cleaned = [clean_word(w) for w in words]
            chunks.extend(split_words_by_size(cleaned, max_caption_size))
    else:
        words = text.split()
        cleaned = [clean_word(w) for w in words]
        chunks = split_words_by_size(cleaned, max_caption_size)

    # Atribui timestamps a cada chunk
    for chunk in chunks:
        position += len(chunk) + 1
        end_time = interpolate_time(position, word_map)
        if end_time is not None and chunk:
            captions.append(((start_time, end_time), chunk))
            start_time = end_time
    return captions


def normalize_captions(captions):
    """
    Ajusta legendas para que cada segmento tenha entre MIN_CAPTION_DURATION e MAX_CAPTION_DURATION.
    Combina segmentos muito curtos e divide muito longos.
    """
    normalized = []
    buffer_text = ''
    buffer_start = None

    for (start, end), text in captions:
        duration = end - start
        if buffer_text:
            # mescla buffer e segmento atual
            buffer_text += ' ' + text
            buffer_end = end
            total_dur = buffer_end - buffer_start
            if total_dur >= MIN_CAPTION_DURATION:
                normalized.append(((buffer_start, buffer_end), buffer_text))
                buffer_text = ''
                buffer_start = None
            # se ainda curto, continua acumulando
        elif duration < MIN_CAPTION_DURATION:
            # inicia buffer
            buffer_text = text
            buffer_start = start
        elif duration > MAX_CAPTION_DURATION:
            # divide segment longo em 2 partes aproximadas
            midpoint = (start + end) / 2
            # primeira metade
            normalized.append(((start, midpoint), text))
            normalized.append(((midpoint, end), text))
        else:
            normalized.append(((start, end), text))

    # se sobra buffer ao final
    if buffer_text:
        last_end = captions[-1][0][1]
        normalized.append(((buffer_start, last_end), buffer_text))

    return normalized


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print('Uso: python generate_timed_captions.py audio.mp3')
        sys.exit(1)
    audio_file = sys.argv[1]
    legendas = generate_timed_captions(audio_file)
    for (start, end), txt in legendas:
        print(f"{start:.2f}-{end:.2f}: {txt}")
