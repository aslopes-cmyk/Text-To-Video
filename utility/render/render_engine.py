#!/usr/bin/env python3
import os
import tempfile
import platform
import subprocess
import requests
from PIL import Image as PilImage
# Monkey-patch ANTIALIAS para Pillow ≥10
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
TARGET_WIDTH, TARGET_HEIGHT = 1920, 1080
# Configurações de legenda
FONT_SIZE = 48
CAPTION_WIDTH = int(TARGET_WIDTH * 0.8)  # largura máxima para wrap


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

    # 1) Processa clipes de fundo
    for (t1, t2), video_url in background_video_data:
        segment_dur = t2 - t1
        bg = None

        if video_url:
            try:
                # Abre vídeo local ou remoto
                if os.path.isfile(video_url):
                    raw = VideoFileClip(video_url)
                else:
                    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4').name
                    download_file(video_url, tmp_file)
                    raw = VideoFileClip(tmp_file)
                    temp_files.append(tmp_file)
                # Cria clipe de duração exata (loop se necessário)
                if raw.duration >= segment_dur:
                    bg = raw.subclip(0, segment_dur)
                else:
                    bg = raw.subclip(0, raw.duration).fx(loop, duration=segment_dur)
            except Exception as e:
                print(f"⚠️ Falha ao abrir clipe '{video_url}': {e}")
                bg = None
        # fallback: clipe preto
        if bg is None:
            bg = ColorClip((TARGET_WIDTH, TARGET_HEIGHT), color=(0, 0, 0), duration=segment_dur)

        # posiciona e redimensiona
        bg = bg.set_start(t1)
        bg = bg.resize(height=TARGET_HEIGHT)
        if bg.w < TARGET_WIDTH:
            bg = bg.fx(
                mpy_video.crop,
                width=TARGET_WIDTH,
                height=TARGET_HEIGHT,
                x_center=bg.w / 2,
                y_center=bg.h / 2
            )
        bg = bg.resize((TARGET_WIDTH, TARGET_HEIGHT))
        visual_clips.append(bg)

    # 2) Processa legendas
    for (t1, t2), txt in timed_captions:
        safe_txt = txt.replace('“', '"').replace('”', '"').replace('’', "'").replace('–', '-')
        text_clip = TextClip(
            safe_txt,
            font='Helvetica-Bold',
            fontsize=FONT_SIZE,
            color="white",
            stroke_width=2,
            stroke_color="black",
            method="caption",
            size=(CAPTION_WIDTH, None),
            align="center"
        ).set_start(t1).set_end(t2)
        text_clip = text_clip.set_position(("center", TARGET_HEIGHT - FONT_SIZE * 2))
        visual_clips.append(text_clip)

    # 3) Composição final
    final = CompositeVideoClip(visual_clips, size=(TARGET_WIDTH, TARGET_HEIGHT))

    # 4) Adiciona áudio
    audio = CompositeAudioClip([AudioFileClip(audio_file_path)])
    final = final.set_audio(audio).set_duration(audio.duration)

    # 5) Exporta
    output = "rendered_video.mp4"
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
