#!/usr/bin/env python3
import os
import edge_tts

async def generate_audio(
    text: str,
    output_filename: str,
    voice: str = None
) -> None:
    """
    Gera arquivo de áudio com TTS usando edge_tts.
    :param text: texto a ser narrado.
    :param output_filename: caminho de saída para salvar o áudio.
    :param voice: nome da voz do Azure TTS (padrão: TTS_VOICE env ou 'pt-BR-AntonioNeural').
    """
    # Seleciona voz padrão de ENV ou fixa
    if voice is None:
        voice = os.getenv('TTS_VOICE', 'pt-BR-AntonioNeural')
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_filename)




