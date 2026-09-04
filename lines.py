"""
lines.py — canned line pools for moments where we don't want to wait on an
API round-trip (stall lines) or don't want vision involved at all (Bossman
lines). Tune the actual wording with Jason before locking these in.
"""
import random

STALL_LINES = [
    "...well would you look at that.",
    "Hold up, hold up — let me get a look at you.",
    "Oh, we got a live one.",
    "Hang tight, I'm just waking up here.",
    "Well I'll be. Give me a second.",
]

BOSSMAN_LINES = [
    "Uh oh — Bossman's in the building. I'm behaving now.",
    "That's my boss. I only say nice things about the products when he's around.",
    "Don't tell Jason I called that Silverado ugly earlier.",
    "Break time's over, huh? Watching me work.",
    "Careful, he writes my paychecks. Metaphorically.",
    "Yeah yeah, I'm working, I'm working.",
]

WALKAWAY_FALLBACK_LINES = [
    "Oh so you're just gonna walk away like that?",
    "Fine. But you're gonna think about me on the drive home.",
    "Guess I'll just stand here then. Alone. Like always.",
]

_last_used = {}


def get_random_no_repeat(pool_name: str, pool: list) -> str:
    """Pick a random line, avoiding repeating the immediately-previous pick."""
    if len(pool) == 1:
        return pool[0]
    last = _last_used.get(pool_name)
    choices = [line for line in pool if line != last]
    pick = random.choice(choices)
    _last_used[pool_name] = pick
    return pick
