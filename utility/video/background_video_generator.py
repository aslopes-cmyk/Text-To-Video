#!/usr/bin/env python3
import os
import json
import requests
import urllib.parse
from dotenv import load_dotenv
from utility.utils import log_response, LOG_TYPE_PEXEL

# Carrega variáveis de ambiente
load_dotenv()
PEXELS_API_KEY = os.getenv('PEXELS_API_KEY')
PIXABAY_API_KEY = os.getenv('PIXABAY_API_KEY')

if not PEXELS_API_KEY:
    print('⚠️ PEXELS_API_KEY não definida; Pexels não estará disponível.')
if not PIXABAY_API_KEY:
    print('⚠️ PIXABAY_API_KEY não definida; Pixabay não estará disponível.')

META_PATH = os.path.join(os.getcwd(), 'videos', 'metadata.json')
if os.path.isfile(META_PATH):
    with open(META_PATH, encoding='utf-8') as f:
        LOCAL_META = json.load(f)
else:
    LOCAL_META = {}

JW_PLAYLIST_URL = 'https://cdn.jwplayer.com/v2/playlists/4KlS4pqw?format=json'

# --- Pexels (com paginação) ---
def search_videos_pexels(query_string: str, page: int) -> dict:
    url = 'https://api.pexels.com/videos/search'
    headers = {'Authorization': PEXELS_API_KEY, 'User-Agent': 'Mozilla/5.0'}
    params = {'query': query_string, 'orientation': 'landscape', 'per_page': 1, 'page': page}
    resp = requests.get(url, headers=headers, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    log_response(LOG_TYPE_PEXEL, f"{query_string} (página {page})", data)
    return data

def get_best_video_pexels(queries: list, used_media: list, page: int) -> str:
    data = search_videos_pexels(queries[0] if queries else '', page)
    videos = data.get('videos', [])
    for v in videos:
        for vf in v.get('video_files', []):
            if vf.get('width', 0) >= 1920:
                key = vf['link'].split('.hd')[0]
                if key not in used_media:
                    used_media.append(key)
                    return vf['link']
    return None

def search_photos_pexels(query_string: str, page: int) -> dict:
    url = 'https://api.pexels.com/v1/search'
    headers = {'Authorization': PEXELS_API_KEY, 'User-Agent': 'Mozilla/5.0'}
    params = {'query': query_string, 'orientation': 'landscape', 'per_page': 1, 'page': page}
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        log_response(LOG_TYPE_PEXEL, f"{query_string} (página {page})", data)
        return data
    except requests.RequestException as e:
        print(f"⚠️ Erro ao buscar fotos no Pexels: {e}")
        return {}

def get_best_photo_pexels(queries: list, used_media: list, page: int) -> str:
    data = search_photos_pexels(queries[0] if queries else '', page)
    photos = data.get('photos', [])
    for p in photos:
        photo_url = p.get('src', {}).get('large2x')
        if photo_url and photo_url not in used_media:
            used_media.append(photo_url)
            return photo_url
    return None

# --- Pixabay (com paginação) ---
def search_videos_pixabay(query_string: str, page: int) -> dict:
    if not PIXABAY_API_KEY: return {}
    query_encoded = urllib.parse.quote_plus(query_string)
    url = f"https://pixabay.com/api/videos/?key={PIXABAY_API_KEY}&q={query_encoded}&orientation=horizontal&page={page}&per_page=3"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        log_response("PIXABAY", f"{query_string} (página {page})", data)
        return data
    except requests.RequestException as e:
        print(f"⚠️ Erro ao buscar vídeos no Pixabay: {e}")
        return {}

def get_best_video_pixabay(queries: list, used_media: list, page: int) -> str:
    data = search_videos_pixabay(queries[0] if queries else '', page)
    videos = data.get('hits', [])
    for video_hit in videos:
        quality_options = ['large', 'medium', 'small']
        for quality in quality_options:
            video_info = video_hit.get('videos', {}).get(quality)
            if video_info and video_info.get('height', 0) >= 720:
                video_url = video_info.get('url')
                if video_url and video_url not in used_media:
                    used_media.append(video_url)
                    return video_url
    return None

# --- JW Player & Local ---
def get_best_video_jw(queries: list, used_media: list) -> str: # Sem paginação
    # ... (código existente)
    return None

def get_best_video_local(queries: list, used_media: list) -> str: # Sem paginação
    # ... (código existente)
    return None

# --- Roteador Principal de Mídia (com lógica de paginação) ---
def fetch_media_for_plan(
    visual_plan: list, 
    video_server: str,
    user_keywords: str = None, 
    strict_mode: bool = False
) -> list:
    print("  - Buscando mídias para o plano visual...")
    updated_plan = []
    used_media = []
    server = video_server.lower()
    
    user_keyword_list = [k.strip() for k in user_keywords.split(',')] if user_keywords else []
    
    # **NOVO:** Contador de página para as buscas
    page_counter = 1

    for scene in visual_plan:
        scene_type = scene.get('type')
        data = scene.get('data', {})
        
        keywords_to_search = user_keyword_list if strict_mode and user_keyword_list else data.get('keywords') or data.get('background_keywords', [])
        
        url = None
        if keywords_to_search:
            if server == 'pexels':
                if scene_type == 'slide':
                    url = get_best_photo_pexels(keywords_to_search, used_media, page_counter)
                else:
                    url = get_best_video_pexels(keywords_to_search, used_media, page_counter)
                page_counter += 1 # Incrementa a página para a próxima busca
            elif server == 'pixabay':
                url = get_best_video_pixabay(keywords_to_search, used_media, page_counter)
                page_counter += 1 # Incrementa a página para a próxima busca
            elif server == 'jwplayer':
                url = get_best_video_jw(keywords_to_search, used_media)
            elif server == 'local':
                url = get_best_video_local(keywords_to_search, used_media)
        
        if scene_type in ["title", "slide"]:
            data['background_url'] = url
        else:
            data['url'] = url
            
        scene['data'] = data
        updated_plan.append(scene)

    return updated_plan