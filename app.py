#!/usr/bin/env python3
import os
import argparse
import asyncio

from utility.script.script_generator import generate_script
from utility.audio.audio_generator import generate_audio
from utility.captions.timed_captions_generator import generate_timed_captions
from utility.video.video_search_query_generator import getVideoSearchQueriesTimed, merge_empty_intervals
from utility.video.background_video_generator import generate_video_url
from utility.render.render_engine import get_output_media


def main():
    parser = argparse.ArgumentParser(description="Gera um vídeo jornalístico de ~60s a partir de um tópico.")
    parser.add_argument("topic", type=str, help="Tópico para o roteiro do vídeo")
    parser.add_argument("--tts-voice", type=str, default=os.getenv('TTS_VOICE', 'pt-BR-AntonioNeural'),
                        help="Voz TTS para narração (ex: pt-BR-AntonioNeural)")
    parser.add_argument("--video-source", type=str, default=os.getenv('VIDEO_SOURCE', 'pexels'),
                        help="Serviço de vídeo de fundo (e.g. pexels)")
    args = parser.parse_args()
    topic = args.topic
    audio_file = "audio_tts.wav"

    # 1. Gera roteiro explicativo em Português (16:9, ~60s)
    script = generate_script(topic)
    print(f"[1/5] Roteiro gerado:\n{script}\n")

    # 2. Converte texto em áudio com TTS em Português
    print(f"[2/5] Gerando áudio TTS com voz {args.tts_voice}...")
    asyncio.run(generate_audio(script, audio_file, voice=args.tts_voice))

    # 3. Gera legendas temporizadas em Português
    print("[3/5] Transcrevendo áudio para legendas temporizadas...")
    captions = generate_timed_captions(audio_file)
    print(f"    {len(captions)} legendas geradas")

    # 4. Cria termos de busca de vídeo para cada segmento
    print("[4/5] Gerando queries de busca para vídeos de fundo...")
    queries = getVideoSearchQueriesTimed(script, captions)
    if not queries:
        print("Nenhuma query gerada, abortando vídeo de fundo.")
        return
    print(f"    {len(queries)} segmentos para busca de vídeo")

    # 5. Busca URLs de vídeo de fundo e normaliza intervalos
    print(f"[5/5] Obtendo vídeos do serviço '{args.video_source}'...")
    urls = generate_video_url(queries, args.video_source)
    urls = merge_empty_intervals(urls)
    print(f"    {len(urls)} intervalos de vídeo prontos")

    # 6. Renderiza o vídeo final com áudio, legendas e fundo
    print("Renderizando vídeo final...")
    output_path = get_output_media(audio_file, captions, urls, args.video_source)
    print(f"Vídeo gerado em: {output_path}")


if __name__ == '__main__':
    main()
