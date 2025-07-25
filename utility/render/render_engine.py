#!/usr/bin/env python3
import os
import tempfile
import platform
import subprocess
import requests
from PIL import Image as PilImage
# Monkey-patch ANTIALIAS for Pillow ≥10
if not hasattr(PilImage, 'ANTIALIAS'):
    PilImage.ANTIALIAS = PilImage.Resampling.LANCZOS

from moviepy.editor import (
    AudioFileClip,
    CompositeVideoClip,
    CompositeAudioClip,
    ColorClip,
    TextClip,
    VideoFileClip
)
from moviepy import video as mpy_video
from moviepy.video.fx.all import loop

# Resolução alvo 16:9
target_width, target_height = 1920, 1080
# Configurações de legenda
font_size = 48
caption_width = int(target_width * 0.8)  # largura máxima para wrap


def download_file(url: str, filename: str) -> None:
    """Baixa o arquivo da URL para o caminho local."""
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    with open(filename, 'wb') as f:
        f.write(resp.content)


def find_imagemagick() -> str:
    """Procura o binário do ImageMagick no sistema."""
    cmd = "where" if platform.system() == "Windows" else "which"
    try:
        return subprocess.check_output([cmd, 'magick']).decode().strip()
    except Exception:
        return None


def get_output_media(
    audio_file_path: str,
    timed_captions: list,
    background_video_data: list,
    video_server: str
) -> str:
    """
    Gera e exporta o vídeo final com background, legendas e áudio.
    """
    # Configura ImageMagick para TextClip
    im_path = find_imagemagick()
    if im_path:
        os.environ['IMAGEMAGICK_BINARY'] = im_path

    temp_files = []
    visual_clips = []
    last_bg_clip = None

    # 1) Processa clipes de fundo
    for (t1, t2), video_url in background_video_data:
        segment_dur = t2 - t1
        bg = None

        if video_url:
            # Baixa vídeo
            tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4').name
            temp_files.append(tmp_file)
            download_file(video_url, tmp_file)
            # Tenta carregar o clip; se falhar, cai no fallback
            try:
                raw = VideoFileClip(tmp_file)
                # Cria clipe de duração exata (loop se necessário)
                if raw.duration >= segment_dur:
                    bg = raw.subclip(0, segment_dur)
                else:
                    bg = raw.subclip(0, raw.duration).fx(loop, duration=segment_dur)
                last_bg_clip = bg
            except Exception as e:
                print(f"⚠️ Falha ao carregar vídeo '{video_url}': {e}")
                bg = None
        else:
            # Fallback: usa último clipe ou nada
            if last_bg_clip:
                if last_bg_clip.duration >= segment_dur:
                    bg = last_bg_clip.subclip(0, segment_dur)
                else:
                    bg = last_bg_clip.fx(loop, duration=segment_dur)

        # Se ainda não tem bg válido, gera tela preta
        if bg is None:
            bg = ColorClip((target_width, target_height), color=(0, 0, 0), duration=segment_dur)

        # Ajusta posição e tamanho
        bg = bg.set_start(t1)
        bg = bg.resize(height=target_height)
        if bg.w < target_width:
            bg = bg.fx(
                mpy_video.crop,
                width=target_width,
                height=target_height,
                x_center=bg.w / 2,
                y_center=bg.h / 2
            )
        bg = bg.resize((target_width, target_height))
        visual_clips.append(bg)

    # 2) Processa legendas
    for (t1, t2), txt in timed_captions:
        # Escapa aspas tipográficas
        safe_txt = txt.replace('“', '"').replace('”', '"').replace('’', "'").replace('–', '-')
        text_clip = TextClip(
            safe_txt,
            fontsize=font_size,
            color="white",
            stroke_width=2,
            stroke_color="black",
            method="caption",
            size=(caption_width, None),
            align="center"
        ).set_start(t1).set_end(t2)
        text_clip = text_clip.set_position(("center", target_height - font_size * 2))
        visual_clips.append(text_clip)

    # 3) Composição final
    final = CompositeVideoClip(visual_clips, size=(target_width, target_height))

    # 4) Adiciona áudio
    audio = CompositeAudioClip([AudioFileClip(audio_file_path)])
    final = final.set_audio(audio).set_duration(audio.duration)

    # 5) Exporta
    output = "rendered_video1.mp4"
    final.write_videofile(
        output,
        codec='libx264',
        audio_codec='aac',
        fps=25,
        preset='veryfast'
    )

    # 6) Limpeza de arquivos temporários
    for fpath in temp_files:
        try:
            os.remove(fpath)
        except OSError:
            pass

    return output
