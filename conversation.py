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
_dynamic_silence_threshold = None  # set by calibrate_noise_floor(), if called

# Whisper occasionally hallucinates these stock phrases out of pure
# background noise with no real speech in it — reject them outright.
_KNOWN_NOISE_HALLUCINATIONS = {
    "thank you", "thank you.", "thanks for watching", "thank you for watching",
    "bye", "bye.", "you", "you.", "the", "okay", "okay.",
}


def _get_client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=config.OPENAI_API_KEY)
    return _client


def calibrate_noise_floor(duration_seconds: float = None):
    """Record a few seconds of ambient sound and set the real silence
    threshold relative to what's actually measured, instead of trusting a
    fixed guess that has no idea whether this is a quiet room or a loud
    show floor. Call this once at startup — ideally right at the actual
    venue, since a quiet house doesn't represent booth noise at a show."""
    global _dynamic_silence_threshold
    duration = duration_seconds or config.NOISE_CALIBRATION_SECONDS
    print(f"[conversation] calibrating noise floor ({duration:.0f}s)...")
    try:
        recording = sd.rec(
            int(duration * config.MIC_SAMPLE_RATE),
            samplerate=config.MIC_SAMPLE_RATE, channels=1, dtype="int16",
        )
        sd.wait()
        ambient_rms = float(np.sqrt(np.mean(recording.astype(np.float32) ** 2)))
        _dynamic_silence_threshold = max(
            config.SILENCE_RMS_THRESHOLD, ambient_rms * config.NOISE_THRESHOLD_MULTIPLIER
        )
        print(f"[conversation] ambient RMS={ambient_rms:.0f} -> silence threshold={_dynamic_silence_threshold:.0f}")
    except Exception as e:
        print(f"[conversation] noise calibration failed ({e}); using fixed threshold {config.SILENCE_RMS_THRESHOLD}")
        _dynamic_silence_threshold = config.SILENCE_RMS_THRESHOLD


def _current_threshold() -> float:
    return _dynamic_silence_threshold if _dynamic_silence_threshold is not None else config.SILENCE_RMS_THRESHOLD


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
                if rms > _current_threshold():
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


# Bias Whisper toward the vocabulary that actually matters here — without
# this it's transcribing blind, with no idea "GRUNT" and "GUNNY" are real
# product names rather than noise/mishearing candidates. Helps most exactly
# where it's needed most: marginal audio in a loud environment.
_WHISPER_VOCAB_PROMPT = (
    "rucRak, GRUNT, GUNNY, Jeep Wrangler, Ford Bronco, cargo rack, "
    "bike rack, off-road, hitch, fitment, Crew Chief, Daryl, Jason."
)


def transcribe(audio: np.ndarray):
    """Returns transcribed text, or None if this was probably just noise —
    not real speech. Uses Whisper's own no_speech_prob per segment (its
    built-in confidence signal) plus a filter for known short hallucinated
    phrases Whisper sometimes produces from pure background noise."""
    buf = io.BytesIO()
    sf.write(buf, audio, config.MIC_SAMPLE_RATE, format="WAV")
    buf.seek(0)
    buf.name = "speech.wav"

    result = _get_client().audio.transcriptions.create(
        model="whisper-1", file=buf, response_format="verbose_json",
        prompt=_WHISPER_VOCAB_PROMPT,
    )

    segments = getattr(result, "segments", None) or []
    if segments:
        no_speech_probs = [getattr(s, "no_speech_prob", 0.0) for s in segments]
        avg_no_speech = sum(no_speech_probs) / len(no_speech_probs)
        if avg_no_speech > config.MAX_NO_SPEECH_PROB:
            return None

    text = (result.text or "").strip()
    if len(text) < config.MIN_TRANSCRIPT_CHARS:
        return None
    if text.lower().strip(".! ") in _KNOWN_NOISE_HALLUCINATIONS:
        return None
    return text


def generate_reply(history: list) -> str:
    response = _get_client().chat.completions.create(
        model="gpt-4o",
        max_tokens=120,
        messages=history,
    )
    return response.choices[0].message.content.strip()
