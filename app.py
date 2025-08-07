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
    parser = argparse.ArgumentParser(
        description="Gera um vídeo jornalístico de ~60s a partir de um tópico."
    )
    parser.add_argument("topic", type=str, help="Tópico para o roteiro do vídeo")
    parser.add_argument(
        "--tts-voice", type=str,
        default=os.getenv('TTS_VOICE', 'pt-BR-AntonioNeural'),
        help="Voz TTS (ex: pt-BR-AntonioNeural)"
    )
    parser.add_argument(
        "--video-source", type=str,
        default=os.getenv('VIDEO_SOURCE', 'pexels'),
        help="Serviço de vídeo de fundo (e.g. pexels)"
    )
    args = parser.parse_args()

    # 1. Roteiro
    script = generate_script(args.topic)
    print(f"[1/5] Roteiro gerado:\n{script}\n")

    # 2. Áudio TTS
    print(f"[2/5] Gerando áudio TTS...")
    asyncio.run(generate_audio(script, "audio_tts.wav", voice=args.tts_voice))

    # 3. Legendas
    print("[3/5] Transcrevendo áudio para legendas temporizadas...")
    captions = generate_timed_captions("audio_tts.wav")
    print(f"    {len(captions)} legendas geradas")

    # 4. Queries de vídeo
    print("[4/5] Gerando queries de busca para vídeos de fundo...")
    queries = getVideoSearchQueriesTimed(script, captions)
    if not queries:
        print("Nenhuma query gerada; abortando.")
        return

    # 5. URLs de vídeo e merge
    print("[5/5] Obtendo vídeos de fundo...")
    urls = generate_video_url(queries, args.video_source)
    urls = merge_empty_intervals(urls)

    # 6. Render final
    print("Renderizando vídeo final...")
    output = get_output_media("audio_tts.wav", captions, urls, args.video_source)
    print(f"Vídeo gerado em: {output}")

if __name__ == '__main__':
    main()
