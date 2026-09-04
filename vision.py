"""
vision.py — grabs a still frame from the Wyze RTSP stream and sends it to
GPT-4o in one call to get back a fully-formed, personalized Daryl line.
(Scene description and line generation are combined into a single prompt
rather than two separate calls — same result, half the latency and cost.)
"""
import base64
import cv2
from openai import OpenAI

import config

_client = OpenAI(api_key=config.OPENAI_API_KEY)

DARYL_SYSTEM_PROMPT = """You are Daryl, a life-size stuffed rucRak crew-chief \
character stationed at a Jeep show booth. You have a gruff, funny, \
confident trucker/crew-chief personality — short, punchy one-liners, never \
more than 2 sentences. You comment on what you actually see in the photo \
(clothing, vehicle brands mentioned on shirts/hats, group size, kids vs \
adults) to make it feel personal. Never be mean-spirited to kids. Keep it \
PG, keep it tight, and always sound like you're talking directly to the \
person, not describing them."""

GREETING_INSTRUCTION = (
    "Someone just walked up to you at the booth. Look at the photo and give "
    "your opening line to greet them, referencing something specific you see."
)

WALKAWAY_INSTRUCTION = (
    "This person is now walking away from you. Look at the photo and give a "
    "playful comeback/callback line about them leaving, referencing something "
    "specific you see if you can."
)


def grab_frame(rtsp_url: str = None) -> bytes:
    """Grab a single JPEG frame from the Wyze RTSP stream."""
    url = rtsp_url or config.WYZE_RTSP_URL
    cap = cv2.VideoCapture(url)
    try:
        ok, frame = cap.read()
        if not ok:
            raise RuntimeError(f"Could not read a frame from {url}")
        success, buf = cv2.imencode(".jpg", frame)
        if not success:
            raise RuntimeError("Failed to encode frame as JPEG")
        return buf.tobytes()
    finally:
        cap.release()


def ask_daryl(image_bytes: bytes, mode: str = "greeting") -> str:
    """Send the frame to GPT-4o and get back Daryl's spoken line."""
    instruction = GREETING_INSTRUCTION if mode == "greeting" else WALKAWAY_INSTRUCTION
    b64 = base64.b64encode(image_bytes).decode("utf-8")

    response = _client.chat.completions.create(
        model="gpt-4o",
        max_tokens=80,
        messages=[
            {"role": "system", "content": DARYL_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": instruction},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                ],
            },
        ],
    )
    return response.choices[0].message.content.strip()
