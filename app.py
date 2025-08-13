#!/usr/bin/env python3
import os
import argparse
from datetime import datetime
import asyncio

from utility.script.script_generator import generate_script, generate_slideshow_script
from utility.video.video_search_query_generator import generate_visual_plan, create_slideshow_plan
from utility.audio.audio_generator import generate_audio
from utility.captions.timed_captions_generator import generate_timed_captions
from utility.video.background_video_generator import fetch_media_for_plan
from utility.render.render_engine import get_output_media
from utility.scraper.scraper import extract_text_from_url
from utility.utils import slugify

OUTPUT_DIR = "output"

def main():
    # --- PASSO 0: Argumentos ---
    parser = argparse.ArgumentParser(description="Gera vídeos a partir de texto.")
    parser.add_argument("topic", nargs='?', type=str, help="Tópico para o vídeo.")
    parser.add_argument(
        "--mode", type=str, default="video", choices=['video', 'slideshow'],
        help="Modo de operação: 'video' (completo) ou 'slideshow' (visual)."
    )
    parser.add_argument("-u", "--url", type=str, help="URL de uma reportagem para usar como base.")
    parser.add_argument("-k", "--keywords", type=str, help="Palavras-chave para guiar a busca de mídia.")
    parser.add_argument(
        "--strict-keywords", action='store_true',
        help="Força a busca de mídia a usar apenas as keywords fornecidas via -k."
    )
    # NOVOS ARGUMENTOS PARA CONTROLE DE VOZ
    parser.add_argument(
        "--tts-provider", type=str, default="edge", choices=['edge', 'elevenlabs'],
        help="Provedor de Text-to-Speech a ser usado."
    )
    parser.add_argument(
        "--voice", type=str,
        help="Voz a ser usada. Para 'edge', nome (ex: pt-BR-AntonioNeural). Para 'elevenlabs', a Voice ID."
    )
    parser.add_argument("--video-source", type=str, default=os.getenv('VIDEO_SOURCE', 'pexels'), choices=['pexels', 'pixabay', 'jwplayer', 'local'], help="Fonte da mídia.")
    parser.add_argument(
        "--slide-duration", type=int, default=7,
        help="Duração de cada slide no modo slideshow."
    )
    args = parser.parse_args()

    if not args.topic and not args.url:
        parser.error("Você deve fornecer um 'topic' ou uma '--url'.")

    # Define a voz padrão se não for especificada pelo usuário
    if not args.voice:
        if args.tts_provider == 'elevenlabs':
            # Use uma Voice ID padrão da sua conta ou uma que você goste
            args.voice = os.getenv('ELEVENLABS_VOICE_ID', 'JBFqnCBsd6RMkjVDRZzb') 
        else:
            args.voice = os.getenv('EDGE_TTS_VOICE', 'pt-BR-AntonioNeural')

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # --- LÓGICA PRINCIPAL BASEADA NO MODO ---
    
    if args.mode == 'slideshow':
        # ... (fluxo do slideshow continua o mesmo)
        print("🚀 Iniciando modo SLIDESHOW...")
        base_name = slugify(args.topic)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{base_name}_{timestamp}.mp4"
        output_filepath = os.path.join(OUTPUT_DIR, filename)
        print(f"[INFO] Nome do arquivo de saída será: {output_filepath}")
        
        print("[1/4] Gerando roteiro de slides...")
        slideshow_script = generate_slideshow_script(args.topic)
        
        print("[2/4] Criando plano visual do slideshow...")
        visual_plan = create_slideshow_plan(slideshow_script, duration_per_slide=args.slide_duration)
        
        print("[3/4] Buscando mídias para o plano visual...")
        visual_plan_com_midia = fetch_media_for_plan(
            visual_plan, 
            args.video_source, 
            user_keywords=args.keywords, 
            strict_mode=args.strict_keywords
        )
        
        print("\n[4/4] Renderizando vídeo final...")
        output_file_path = get_output_media(visual_plan_com_midia, output_filepath)
        print(f"\n✅ Vídeo de slideshow gerado com sucesso em: {output_file_path}")

    elif args.mode == 'video':
        print("🚀 Iniciando modo VÍDEO...")
        script_input = ""
        if args.url:
            print(f"[1/7] Extraindo conteúdo da URL: {args.url}")
            article_text = extract_text_from_url(args.url)
            if not article_text: return
            script_input = f"Crie um roteiro jornalístico para um vídeo curto baseado no seguinte artigo:\n\n---\n\n{article_text}"
        else:
            script_input = args.topic
            print("[1/7] Gerando roteiro a partir do tópico...")
        
        script = generate_script(script_input)
        print(f"    Roteiro gerado:\n{script}\n")
        
        base_name = slugify(script[:60])
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{base_name}_{timestamp}.mp4"
        output_filepath = os.path.join(OUTPUT_DIR, filename)
        print(f"[INFO] Nome do arquivo de saída será: {output_filepath}")
        
        print(f"[2/7] Gerando áudio TTS usando '{args.tts_provider}'...")
        # ATUALIZADO: Chamada da função de áudio agora passa os novos parâmetros
        asyncio.run(generate_audio(
            script, 
            "audio_tts.wav", 
            tts_provider=args.tts_provider,
            voice=args.voice
        ))
        
        print("[3/7] Gerando legendas temporizadas...")
        captions = generate_timed_captions("audio_tts.wav")
        print(f"    {len(captions)} segmentos de legenda gerados.\n")
        
        print("[4/7] Gerando plano visual (storyboard)...")
        visual_plan = generate_visual_plan(script, captions, args.video_source, args.keywords)
        
        print("[5/7] Buscando mídias para o plano visual...")
        visual_plan_com_midia = fetch_media_for_plan(
            visual_plan, 
            args.video_source,
            user_keywords=args.keywords,
            strict_mode=args.strict_keywords
        )
        
        print(f"\n[6/7] Renderizando vídeo final para {output_filepath}...")
        output_file_path = get_output_media(visual_plan_com_midia, output_filepath, "audio_tts.wav", captions)
        print(f"\n✅ Vídeo gerado com sucesso em: {output_file_path}")

if __name__ == '__main__':
    main()
