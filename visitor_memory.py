"""
visitor_memory.py — notices if someone's probably already visited the
booth today. Deliberately low-stakes: this is same-day, in-memory-only
(never written to disk, wiped every time main.py restarts), and uses a
lightweight face comparison rather than anything claiming certain
identity — the "maybe" band turns uncertainty into Daryl asking the
person directly ("Weren't you just here?") instead of guessing silently.

Uses OpenCV's built-in LBPH face recognizer (opencv-contrib-python) —
avoids the notoriously painful dlib/CMake install that heavier face-
recognition libraries require, at the cost of being less precise. That
tradeoff is fine here: false positives just mean an occasional "weren't
you just here?" asked to a genuinely new person (harmless, kind of funny
even), and false negatives just mean no callback happens — never a false
claim of certainty either way.
"""
import threading
import os
import numpy as np
import cv2

import config

_lock = threading.Lock()

# Bundled directly in the repo rather than relying on cv2.data.haarcascades
# — some OpenCV builds/versions don't ship this file at all (confirmed:
# opencv-contrib-python 5.0.0 doesn't include it), so depending on the
# package to provide it is fragile across environments.
_CASCADE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "haarcascade_frontalface_default.xml")
_face_cascade = cv2.CascadeClassifier(_CASCADE_PATH)
if _face_cascade.empty():
    raise RuntimeError(
        f"Failed to load face cascade from {_CASCADE_PATH} — check the file exists and isn't corrupted."
    )

_recognizer = cv2.face.LBPHFaceRecognizer_create()

_samples: list[np.ndarray] = []   # grayscale face crops, resized to a fixed size
_labels: list[int] = []           # one int label per unique visitor seen today
_next_label = 0
_trained = False


def _extract_face(frame_bytes: bytes):
    """Returns a normalized grayscale face crop from a JPEG frame, or None
    if no face was found."""
    arr = np.frombuffer(frame_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return None
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = _face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
    if len(faces) == 0:
        return None
    # take the largest detected face — most likely the person Daryl's
    # actually talking to, not someone in the background
    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
    face = gray[y:y + h, x:x + w]
    return cv2.resize(face, (200, 200))


def check_and_record(frame_bytes: bytes) -> str:
    """Call this once per greeting. Returns one of:
      'confident' — strong match against someone seen earlier today
      'maybe'     — weak/ambiguous match, worth asking rather than assuming
      'new'       — no meaningful match, treated as a first-time visitor
    Always records the face (new or not) so future comparisons improve."""
    global _next_label, _trained

    if not config.ENABLE_VISITOR_MEMORY:
        return "new"

    face = _extract_face(frame_bytes)
    if face is None:
        return "new"  # couldn't get a usable face crop, don't guess

    with _lock:
        result = "new"
        if _trained and len(_samples) > 0:
            try:
                label, confidence = _recognizer.predict(face)
                # LBPH: LOWER confidence = more similar
                if confidence < config.FACE_MATCH_CONFIDENT_THRESHOLD:
                    result = "confident"
                elif confidence < config.FACE_MATCH_UNCERTAIN_THRESHOLD:
                    result = "maybe"
            except cv2.error:
                pass  # not enough training data yet, treat as new

        # record this face under a new label unless it was a confident
        # match (in which case it's the same person, no need for a new one)
        if result != "confident":
            _samples.append(face)
            _labels.append(_next_label)
            _next_label += 1
            if len(_samples) >= 2:
                _recognizer.train(_samples, np.array(_labels))
                _trained = True

        return result


def reset():
    """Wipes all same-day visitor data. Called automatically by main.py at
    startup — this exists as a named function mainly so it's testable and
    so a manual reset is possible without restarting the whole program."""
    global _samples, _labels, _next_label, _trained, _recognizer
    with _lock:
        _samples = []
        _labels = []
        _next_label = 0
        _trained = False
        _recognizer = cv2.face.LBPHFaceRecognizer_create()
