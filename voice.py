"""
voice.py — turns text into speech via ElevenLabs and plays it back.
Plays through whatever the system's default audio output device is, so
just make sure the Bluetooth speaker is paired and set as default before
the show starts.

Requires ffmpeg installed and on PATH (for ffplay).
"""
import os
import time
import subprocess
import requests

import config

os.makedirs(config.AUDIO_TEMP_DIR, exist_ok=True)


def _tts_to_file(text: str) -> str:
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{config.ELEVENLABS_VOICE_ID}"
    headers = {
        "xi-api-key": config.ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    payload = {
        "text": text,
        "model_id": "eleven_turbo_v2_5",  # low-latency model, good fit for real-time playback
        "voice_settings": {"stability": 0.45, "similarity_boost": 0.8},
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=20)
    resp.raise_for_status()

    out_path = os.path.join(config.AUDIO_TEMP_DIR, f"daryl_{int(time.time()*1000)}.mp3")
    with open(out_path, "wb") as f:
        f.write(resp.content)
    return out_path


def speak(text: str, blocking: bool = True):
    """Generate and play a line. Set blocking=False to fire-and-forget
    (useful for the stall line, which doesn't need us to wait)."""
    print(f"[daryl says] {text}")
    try:
        path = _tts_to_file(text)
    except Exception as e:
        print(f"[voice] ElevenLabs TTS failed: {e}")
        return

    cmd = ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path]
    if blocking:
        subprocess.run(cmd)
    else:
        subprocess.Popen(cmd)
