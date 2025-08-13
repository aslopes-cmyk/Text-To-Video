# utility/audio/audio_generator.py
import os
import asyncio
from dotenv import load_dotenv

# Carrega as variáveis de ambiente, incluindo a nova chave da ElevenLabs
load_dotenv()
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

# --- Lógica da ElevenLabs ---
def generate_audio_elevenlabs(script: str, output_path: str, voice_id: str) -> bool:
    """Gera áudio usando a API da ElevenLabs."""
    try:
        from elevenlabs.client import ElevenLabs
        from elevenlabs import save

        # Inicializa o cliente da API
        client = ElevenLabs(api_key=ELEVENLABS_API_KEY)

        # Gera o áudio a partir do texto
        print(f"    - Gerando áudio com a voz '{voice_id}' da ElevenLabs...")
        audio = client.generate(
            text=script,
            voice=voice_id,
            model="eleven_multilingual_v2" # Modelo recomendado para múltiplos idiomas
        )
        
        # Salva o áudio no arquivo de saída
        save(audio, output_path)
        print(f"    - Áudio da ElevenLabs salvo em: {output_path}")
        return True

    except ImportError:
        print("⚠️ Biblioteca 'elevenlabs' não instalada. Execute 'pip install elevenlabs'.")
        return False
    except Exception as e:
        print(f"⚠️ Erro ao gerar áudio com ElevenLabs: {e}")
        return False

# --- Lógica do Edge-TTS (Fallback) ---
async def generate_audio_edge_tts(script: str, output_path: str, voice: str) -> bool:
    """Gera áudio usando a biblioteca edge-tts."""
    try:
        import edge_tts
        communicate = edge_tts.Communicate(script, voice)
        await communicate.save(output_path)
        print(f"    - Áudio do Edge-TTS salvo em: {output_path}")
        return True
    except ImportError:
        print("⚠️ Biblioteca 'edge-tts' não instalada. Execute 'pip install edge-tts'.")
        return False
    except Exception as e:
        print(f"⚠️ Erro ao gerar áudio com Edge-TTS: {e}")
        return False

# --- Função Principal de Orquestração ---
async def generate_audio(script: str, output_path: str, tts_provider: str = "edge", voice: str = "pt-BR-AntonioNeural"):
    """
    Orquestra a geração de áudio, escolhendo o provedor (ElevenLabs ou Edge-TTS).
    """
    if tts_provider.lower() == 'elevenlabs':
        if not ELEVENLABS_API_KEY:
            print("⚠️ ELEVENLABS_API_KEY não configurada. Usando Edge-TTS como fallback.")
            await generate_audio_edge_tts(script, output_path, voice)
        else:
            # A biblioteca da ElevenLabs não é assíncrona, então chamamos a função síncrona
            success = generate_audio_elevenlabs(script, output_path, voice_id=voice)
            if not success:
                print("⚠️ Falha na ElevenLabs. Tentando Edge-TTS como fallback.")
                await generate_audio_edge_tts(script, output_path, "pt-BR-AntonioNeural") # Fallback para uma voz padrão
    else:
        # Padrão é usar Edge-TTS
        await generate_audio_edge_tts(script, output_path, voice)