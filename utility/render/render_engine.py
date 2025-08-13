#!/usr/bin/env python3
import os
import tempfile
import requests
from PIL import Image as PilImage

# Garante compatibilidade com versões recentes do Pillow
if not hasattr(PilImage, 'ANTIALIAS'):
    PilImage.ANTIALIAS = PilImage.Resampling.LANCZOS

from moviepy.editor import (
    AudioFileClip,
    CompositeVideoClip,
    VideoFileClip,
    ImageClip,
    ColorClip,
    TextClip,
    concatenate_videoclips,
    CompositeAudioClip
)
from moviepy.video.fx.all import loop, resize

# --- Configurações Globais ---
TARGET_WIDTH, TARGET_HEIGHT = 1920, 1080
CAPTION_FONT_SIZE = 48
CAPTION_FONT = 'Helvetica-Bold'
CAPTION_WIDTH = int(TARGET_WIDTH * 0.8)

# --- ARQUIVOS DE MÍDIA ---
LOGO_FILE_PATH = "assets/BASE LOGO HORIZONTAL.png"
VINHETA_FILE_PATH = "assets/AGVinhetaAudio04.mp4"


# --- Funções Auxiliares ---
def download_file(url: str, filename: str) -> bool:
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        with open(filename, 'wb') as f: f.write(resp.content)
        return True
    except requests.RequestException as e:
        print(f"⚠️ Falha no download de '{url}': {e}")
        return False

def _apply_ken_burns(clip: ImageClip, duration: float):
    resized_clip = clip.fx(resize, 1.15)
    moved_clip = resized_clip.set_position(lambda t: ('center', 10 * t))
    return CompositeVideoClip([moved_clip], size=(TARGET_WIDTH, TARGET_HEIGHT)).set_duration(duration)

def _create_base_clip(url: str, duration: float, temp_files: list, is_video: bool = True):
    if url is None:
        return ColorClip((TARGET_WIDTH, TARGET_HEIGHT), color=(0, 0, 0), duration=duration)
    clip = None
    try:
        if os.path.isfile(url):
            clip = VideoFileClip(url) if is_video else ImageClip(url)
        else:
            suffix = '.mp4' if is_video else '.jpg'
            tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix).name
            if download_file(url, tmp_file):
                clip = VideoFileClip(tmp_file) if is_video else ImageClip(tmp_file)
                temp_files.append(tmp_file)
        if clip:
            if is_video:
                if clip.duration < duration:
                    clip = clip.fx(loop, duration=duration)
                else:
                    clip = clip.subclip(0, duration)
            else:
                clip = clip.set_duration(duration)
            clip = clip.resize(height=TARGET_HEIGHT)
            if clip.w < TARGET_WIDTH:
                clip = clip.crop(x_center=clip.w / 2, width=TARGET_WIDTH)
            clip = clip.resize((TARGET_WIDTH, TARGET_HEIGHT))
            return clip
    except Exception as e:
        print(f"⚠️ Falha ao criar clipe para '{url}': {e}")
    return ColorClip((TARGET_WIDTH, TARGET_HEIGHT), color=(0, 0, 0), duration=duration)

def _create_styled_text_clip(text: str, duration: float, is_title: bool = False):
    font_size = 110 if is_title else 80
    font_style = 'Impact' if is_title else 'Helvetica-Bold'
    text_align = 'West' if is_title else 'center'
    text_clip = TextClip(
        text.upper(), font=font_style, fontsize=font_size, color='white',
        method='caption', size=(int(TARGET_WIDTH * 0.85), None), align=text_align
    ).set_duration(duration)
    margin = 30
    text_bg_size = (text_clip.w + margin * 2, text_clip.h + margin * 2)
    text_bg_clip = ColorClip(size=text_bg_size, color=(0, 0, 0, 0.6)).set_duration(duration)
    return CompositeVideoClip([text_bg_clip, text_clip.set_position('center')])


def get_output_media(
    visual_plan: list,
    output_filename: str,
    audio_file_path: str = None,
    timed_captions: list = None
) -> str:
    visual_clips = []
    temp_files = []

    print("  - Processando plano visual...")
    for scene in visual_plan:
        t1, t2 = scene['start'], scene['end']
        scene_type = scene['type']
        data = scene['data']
        segment_dur = t2 - t1
        if scene_type == "video":
            bg_clip = _create_base_clip(data.get('url'), segment_dur, temp_files, is_video=True)
            visual_clips.append(bg_clip.set_start(t1))
        elif scene_type == "slide":
            background_url = data.get('background_url')
            is_video_bg = isinstance(background_url, str) and background_url.endswith('.mp4')
            bg_clip = _create_base_clip(background_url, segment_dur, temp_files, is_video=is_video_bg)
            if not is_video_bg and isinstance(bg_clip, ImageClip):
                bg_clip = _apply_ken_burns(bg_clip, segment_dur)
            styled_text_group = _create_styled_text_clip(data['slide_text'], segment_dur, is_title=False)
            final_slide = CompositeVideoClip([bg_clip, styled_text_group.set_position("center")])
            visual_clips.append(final_slide.set_start(t1))
        elif scene_type == "title":
            bg_clip = _create_base_clip(data.get('background_url'), segment_dur, temp_files, is_video=True)
            styled_text_group = _create_styled_text_clip(data['main_text'], segment_dur, is_title=True)
            final_title_group = styled_text_group.set_position((100, TARGET_HEIGHT - styled_text_group.h - 100))
            final_title_scene = CompositeVideoClip([bg_clip, final_title_group])
            visual_clips.append(final_title_scene.set_start(t1))
    
    if timed_captions:
        print("  - Adicionando legendas...")
        for (t1, t2), txt in timed_captions:
            caption_clip = TextClip(
                txt, font=CAPTION_FONT, fontsize=CAPTION_FONT_SIZE, color="white",
                stroke_width=2, stroke_color="black", method="caption",
                size=(CAPTION_WIDTH, None), align="center"
            ).set_start(t1).set_duration(t2 - t1)
            caption_clip = caption_clip.set_position(("center", TARGET_HEIGHT - (CAPTION_FONT_SIZE * 2.5)))
            visual_clips.append(caption_clip)

    print("  - Compondo vídeo principal...")
    main_content_duration = visual_plan[-1]['end'] if visual_plan else 0
    main_content_clip = CompositeVideoClip(visual_clips, size=(TARGET_WIDTH, TARGET_HEIGHT)).set_duration(main_content_duration)

    vinheta_clip = VideoFileClip(VINHETA_FILE_PATH).resize(height=TARGET_HEIGHT)
    vinheta_clip = vinheta_clip.set_start(main_content_duration)
    
    total_duration = main_content_duration + vinheta_clip.duration

    # --- LOGOMARCA ---
    print("  - Adicionando logomarca...")
    logo_clip = (ImageClip(LOGO_FILE_PATH)
                 .set_duration(total_duration)
                 .resize(height=int(TARGET_HEIGHT * 0.50)) # Reduzido para 8% da altura
                 .set_opacity(0.9))

    # Coordenadas logomarca
    margin = 25 # Margem de 25 pixels da borda
    logo_position = (TARGET_WIDTH - logo_clip.w - margin, margin)
    logo_clip = logo_clip.set_position(logo_position)
    

    final_audio = None
    audio_clips = []
    if audio_file_path and os.path.exists(audio_file_path):
        narration_audio = AudioFileClip(audio_file_path)
        audio_clips.append(narration_audio)
    
    if vinheta_clip.audio:
        vinheta_audio = vinheta_clip.audio.set_start(main_content_duration)
        audio_clips.append(vinheta_audio)
        
    if audio_clips:
        final_audio = CompositeAudioClip(audio_clips)

    final_video = CompositeVideoClip([main_content_clip, vinheta_clip, logo_clip], size=(TARGET_WIDTH, TARGET_HEIGHT))
    final_video.duration = total_duration
    if final_audio:
        final_video = final_video.set_audio(final_audio)

    print(f"  - Exportando vídeo para {output_filename}...")
    final_video.write_videofile(
        output_filename, codec='libx264', audio_codec='aac',
        fps=25, preset='veryfast'
    )

    print("  - Limpando arquivos temporários...")
    for fpath in temp_files:
        try:
            os.remove(fpath)
        except OSError as e:
            print(f"  - Erro ao remover arquivo temporário {fpath}: {e}")

    return output_filename