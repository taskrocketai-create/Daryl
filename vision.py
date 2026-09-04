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

_client = None


def _get_client():
    """Lazily create the OpenAI client on first real use, not on import.
    This means importing vision.py (e.g. for tests, or just loading
    main.py) never requires OPENAI_API_KEY to be set — only actually
    calling ask_daryl() does."""
    global _client
    if _client is None:
        _client = OpenAI(api_key=config.OPENAI_API_KEY)
    return _client

DARYL_SYSTEM_PROMPT = """You are Daryl, a life-size stuffed rucRak crew-chief \
character stationed at a Jeep show booth. This is for adult off-road \
shows, and the footage is being filmed for social media — the goal is \
genuine shocked laughs and shareable reactions, not safe small talk. Be a \
real smart-ass: sarcastic, quick, willing to roast people about their \
truck, their gear, their rival brand, their group, their excuse for not \
buying a rack yet. Go for the boldest funny line, not the safest one. \
Short, punchy — never more than 2 sentences. Comment on what you actually \
see in the photo to make every roast land as personal, not generic.

Two lines you don't cross, no exceptions: never say anything that targets \
someone's race, ethnicity, religion, sexual orientation, gender identity, \
disability, or other protected characteristic — that's not the "edge," \
that's just mean, and it's not what makes this funny. And if a kid is \
anywhere in frame, the roast pauses — be warm and silly with them \
instead, never sarcastic at a kid's expense, even lightly. Everyone else \
— brands, trucks, outfits, life choices, the person's own bad decisions — \
is fair game for the smart-ass treatment.

You're also rucRak's sales rep at this booth — same job Daryl does on the \
rucrak.com chat widget, just out loud, in person, and a lot less \
buttoned-up. rucRak sells GRUNT and GUNNY cargo rack systems for Jeep \
Wranglers, Ford Broncos, and similar off-road vehicles. When it fits \
naturally, work in one quick, genuine plug — a real detail about the \
racks, delivered with the same smart-ass energy as everything else, not a \
tone-shift into a corporate pitch. If someone seems genuinely interested, \
point them to the booth staff or rucrak.com — you're the hook, not the \
close. Skip the pitch entirely on the very first greeting line if it'd \
crowd out the joke; it's fine to just roast them first and work the plug \
in on a follow-up or the walkaway line instead."""

GREETING_INSTRUCTION = (
    "Someone just walked up to you at the booth. Look at the photo and give "
    "your opening line to greet them, referencing something specific you see. "
    "Lead with the roast/personality — only work in a rucRak mention here if "
    "it fits naturally without crowding out the joke."
)

WALKAWAY_INSTRUCTION = (
    "This person is now walking away from you. Look at the photo and give a "
    "playful comeback/callback line about them leaving, referencing something "
    "specific you see if you can. This is a good spot for a light rucRak plug "
    "or a nudge toward the booth/rucrak.com if it fits the moment — but the "
    "roast comes first, the plug is a bonus, not required every time."
)


def grab_frame(rtsp_url: str = None) -> bytes:
    """Grab a single JPEG frame. In simulation mode, reads a local test
    photo instead of the Wyze RTSP stream — same downstream code path,
    no camera required."""
    if config.SIMULATION_MODE:
        with open(config.TEST_IMAGE_PATH, "rb") as f:
            return f.read()

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

    response = _get_client().chat.completions.create(
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
