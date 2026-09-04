"""
recent_lines.py — tracks a rolling window of Daryl's most recently
generated lines (across ALL visitors, not just the current conversation)
so vision.py and conversation.py can tell GPT-4o what's already been said
today and push it toward something fresh instead of quietly recycling the
same handful of jokes on every third person who walks up.

This is deliberately in-memory only — resets when main.py restarts, which
lines up with "fresh material for a new show day" being a reasonable
default. Not meant to persist across days.
"""
import threading

_lock = threading.Lock()
_recent: list[str] = []

MAX_RECENT = 15  # how many past lines to actively steer away from


def record(line: str):
    if not line:
        return
    with _lock:
        _recent.append(line)
        if len(_recent) > MAX_RECENT:
            _recent.pop(0)


def get_recent() -> list[str]:
    with _lock:
        return list(_recent)


def build_avoid_block() -> str:
    """Returns a prompt-ready block listing recent lines, or '' if none yet."""
    recent = get_recent()
    if not recent:
        return ""
    listed = "\n".join(f"- {line}" for line in recent)
    return (
        "\n\nLines you've already used on other people today — don't repeat "
        "these or close variations of them, come up with something new:\n"
        f"{listed}"
    )
