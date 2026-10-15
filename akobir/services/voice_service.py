import os
import uuid
import asyncio
import subprocess
from typing import Optional
from pathlib import Path
import speech_recognition as sr

from config import FFMPEG_PATH, TEMP_DIR

async def convert_to_wav(input_path: str) -> str:
    """
    Converts any audio/voice format to 16kHz mono WAV using ffmpeg.
    """
    output_wav = str(TEMP_DIR / f"voice_{uuid.uuid4().hex[:8]}.wav")
    
    cmd = [
        FFMPEG_PATH,
        "-y",
        "-i", input_path,
        "-ac", "1",
        "-ar", "16000",
        output_wav
    ]

    def _run():
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return res.returncode == 0

    success = await asyncio.to_thread(_run)
    if success and os.path.exists(output_wav):
        return output_wav
    return ""

async def recognize_voice_query(audio_file_path: str) -> Optional[str]:
    """
    Recognizes spoken words from voice message / audio note using SpeechRecognition.
    Tries Uzbek, Russian, English in order.
    """
    wav_path = await convert_to_wav(audio_file_path)
    if not wav_path or not os.path.exists(wav_path):
        return None

    def _sync_recognize():
        recognizer = sr.Recognizer()
        recognizer.energy_threshold = 300
        recognizer.dynamic_energy_threshold = True
        with sr.AudioFile(wav_path) as source:
            try:
                recognizer.adjust_for_ambient_noise(source, duration=0.2)
            except Exception:
                pass
            audio_data = recognizer.record(source)

        # Try languages
        languages = ["uz-UZ", "ru-RU", "en-US"]
        for lang in languages:
            try:
                text = recognizer.recognize_google(audio_data, language=lang)
                if text and len(text.strip()) > 1:
                    return text.strip()
            except sr.UnknownValueError:
                continue
            except Exception as e:
                print(f"[SpeechRecog {lang} error] {e}")
                continue
        return None

    try:
        result = await asyncio.to_thread(_sync_recognize)
        return result
    finally:
        # Cleanup temp wav
        if wav_path and os.path.exists(wav_path):
            try:
                os.remove(wav_path)
            except Exception:
                pass
