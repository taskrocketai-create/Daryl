"""
conversation.py — the actual back-and-forth. After Daryl's opening line,
this listens for a spoken reply, transcribes it with Whisper, and generates
a contextual response with GPT-4o — repeating until the person walks away
(which interrupts this via a threading.Event, not a graceful "goodbye").

Requires a working microphone on whatever machine runs main.py. Silence
detection is amplitude-based and WILL need tuning against your real mic/
booth noise floor — SILENCE_RMS_THRESHOLD in config.py is a starting guess,
not a calibrated value.
"""
import io
import time

import numpy as np
import sounddevice as sd
import soundfile as sf
from openai import OpenAI

import config

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=config.OPENAI_API_KEY)
    return _client


def listen_for_speech(stop_event):
    """Record from the default mic until the person stops talking, until
    MAX_LISTEN_SECONDS elapses, or until stop_event is set (walkaway
    triggered mid-listen). Returns int16 numpy audio, or None if nothing
    was said / got interrupted before any speech was heard."""
    chunk_samples = int(config.MIC_SAMPLE_RATE * config.MIC_CHUNK_MS / 1000)
    silence_chunks_needed = max(1, int(config.SILENCE_DURATION_SECONDS * 1000 / config.MIC_CHUNK_MS))

    frames = []
    silent_run = 0
    heard_speech = False
    started = time.time()

    try:
        with sd.InputStream(samplerate=config.MIC_SAMPLE_RATE, channels=1, dtype="int16") as stream:
            while time.time() - started < config.MAX_LISTEN_SECONDS:
                if stop_event.is_set():
                    return None
                data, _ = stream.read(chunk_samples)
                frames.append(data.copy())
                rms = float(np.sqrt(np.mean(data.astype(np.float32) ** 2)))
                if rms > config.SILENCE_RMS_THRESHOLD:
                    heard_speech = True
                    silent_run = 0
                else:
                    silent_run += 1
                    if heard_speech and silent_run >= silence_chunks_needed:
                        break
    except Exception as e:
        print(f"[conversation] mic error: {e}")
        return None

    if not heard_speech or not frames:
        return None
    return np.concatenate(frames, axis=0)


def transcribe(audio: np.ndarray) -> str:
    buf = io.BytesIO()
    sf.write(buf, audio, config.MIC_SAMPLE_RATE, format="WAV")
    buf.seek(0)
    buf.name = "speech.wav"
    result = _get_client().audio.transcriptions.create(model="whisper-1", file=buf)
    return result.text.strip()


def generate_reply(history: list) -> str:
    response = _get_client().chat.completions.create(
        model="gpt-4o",
        max_tokens=120,
        messages=history,
    )
    return response.choices[0].message.content.strip()
