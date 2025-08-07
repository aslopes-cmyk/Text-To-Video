#!/usr/bin/env python3
import os
import json
import requests
from dotenv import load_dotenv
from utility.utils import log_response, LOG_TYPE_PEXEL

# Carrega variáveis de ambiente
load_dotenv()
PEXELS_API_KEY = os.getenv('PEXELS_API_KEY')
if not PEXELS_API_KEY:
    print('⚠️ PEXELS_API_KEY não definida; Pexels não estará disponível.')

# Carrega metadata local (se existir)
META_PATH = os.path.join(os.getcwd(), 'videos', 'metadata.json')
if os.path.isfile(META_PATH):
    with open(META_PATH, encoding='utf-8') as f:
        LOCAL_META = json.load(f)
else:
    LOCAL_META = {}

# URL JW Player (exemplo turismo)
JW_PLAYLIST_URL = 'https://cdn.jwplayer.com/v2/playlists/x0jVjEsD?format=json'

# --- Pexels ---
def search_videos_pexels(query_string: str, orientation_landscape: bool = True) -> dict:
    """Busca vídeos no Pexels."""
    url = 'https://api.pexels.com/videos/search'
    headers = {'Authorization': PEXELS_API_KEY, 'User-Agent': 'Mozilla/5.0'}
    params = {'query': query_string, 'orientation': 'landscape' if orientation_landscape else 'portrait', 'per_page': 15}
    resp = requests.get(url, headers=headers, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    log_response(LOG_TYPE_PEXEL, query_string, data)
    return data


def get_best_video_pexels(queries: list, used_vids: list) -> str:
    data = search_videos_pexels(queries[0] if queries else '')
    videos = data.get('videos', [])
    filtered = [v for v in videos if v['width'] >= 1920 and v['height'] >= 1080]
    filtered.sort(key=lambda v: abs(v.get('duration', 0) - 15))
    for v in filtered:
        for vf in v.get('video_files', []):
            if vf['width'] == 1920 and vf['height'] == 1080:
                key = vf['link'].split('.hd')[0]
                if key not in used_vids:
                    used_vids.append(key)
                    return vf['link']
    return None

# --- JW Player ---
def fetch_jwplaylist() -> list:
    """Busca playlist do JW Player e retorna itens com metadata e fontes MP4."""
    resp = requests.get(JW_PLAYLIST_URL, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    items = []
    for entry in data.get('playlist', []):
        title = entry.get('title', '')
        description = entry.get('description', '')
        raw_tags = entry.get('tags') or entry.get('keywords') or []
        # normaliza tags para lista de strings
        if isinstance(raw_tags, str):
            tags = [t.strip() for t in raw_tags.split(',') if t.strip()]
        elif isinstance(raw_tags, list):
            tags = raw_tags
        else:
            tags = []
        sources = []
        for s in entry.get('sources', []):
            file = s.get('file')
            if file and file.endswith('.mp4'):
                sources.append({'file': file, 'width': s.get('width'), 'height': s.get('height')})
        if sources:
            items.append({'title': title, 'description': description, 'tags': tags, 'sources': sources})
    return items


def get_best_video_jw(queries: list, used_vids: list) -> str:
    items = fetch_jwplaylist()
    # primeiro tenta match por title, description ou tags
    for q in queries:
        ql = q.lower()
        for item in items:
            text = ' '.join([item['title'], item['description']] + item['tags']).lower()
            if ql in text:
                # seleciona fonte MP4 1280x720
                for src in item['sources']:
                    if src['width'] == 1280 and src['height'] == 720:
                        link = src['file']
                        if link not in used_vids:
                            used_vids.append(link)
                            return link
    # fallback: primeiro MP4 1280x720 não usado
    for item in items:
        for src in item['sources']:
            if src['width'] == 1280 and src['height'] == 720:
                link = src['file']
                if link not in used_vids:
                    used_vids.append(link)
                    return link
    return None

# --- Local ---
def get_best_video_local(queries: list, used_vids: list) -> str:
    for q in queries:
        ql = q.lower()
        for key, info in LOCAL_META.items():
            if ql in key:
                for path in info.get('paths', []):
                    if path not in used_vids:
                        used_vids.append(path)
                        return path
    for info in LOCAL_META.values():
        for path in info.get('paths', []):
            if path not in used_vids:
                used_vids.append(path)
                return path
    return None

# --- Gerador de URLs ---
def generate_video_url(timed_searches: list, video_server: str) -> list:
    """Retorna [[t1,t2], url] para cada segmento."""
    results, used = [], []
    server = video_server.lower()
    for (t1, t2), queries in timed_searches:
        url = None
        if server == 'pexels':
            url = get_best_video_pexels(queries, used)
        elif server == 'jwplayer':
            url = get_best_video_jw(queries, used)
        elif server == 'local':
            url = get_best_video_local(queries, used)
        else:
            raise ValueError(f"Serviço de vídeo desconhecido: {video_server}")
        results.append([[t1, t2], url])
    return results
