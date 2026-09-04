"""
tests/test_trigger_logic.py — exercises the dwell/cooldown/walkaway/Bossman
state machine directly, with vision + voice calls mocked out. No hardware,
no API keys, no network, runs in well under a second.

Run with:  pytest tests/ -v
"""
import time
import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
config.DWELL_SECONDS = 0.05
config.COOLDOWN_SECONDS = 0.1
config.WALKAWAY_DELTA_CM = 50
config.TRIGGER_DISTANCE_CM = 150
config.BLE_LOST_GRACE_SECONDS = 0.05
config.BOSSMAN_LINE_MIN_INTERVAL_SECONDS = 0

from state import DarylState
import state as state_module
import main


@pytest.fixture(autouse=True)
def fresh_state(monkeypatch):
    """Give every test a clean state object and no-op vision/voice/mic calls."""
    new_state = DarylState()
    monkeypatch.setattr(state_module, "state", new_state)
    monkeypatch.setattr(main, "state", new_state)

    spoken = []
    monkeypatch.setattr(main.voice, "speak", lambda text, blocking=True: spoken.append(text))
    monkeypatch.setattr(main.vision, "grab_frame", lambda: b"fake-jpeg-bytes")
    monkeypatch.setattr(main.vision, "ask_daryl", lambda frame, mode: f"[{mode} line]")
    # never actually touch a real microphone in tests — always report silence
    monkeypatch.setattr(main.conversation, "listen_for_speech", lambda stop_event: None)

    return new_state, spoken


def test_no_trigger_when_far_away(fresh_state):
    state, spoken = fresh_state
    state.update_distance(500)
    main.tick()
    assert spoken == []
    assert state.conversation_active is False


def test_greeting_requires_dwell_time(fresh_state):
    state, spoken = fresh_state
    state.update_distance(80)
    main.tick()  # first tick starts the dwell timer, shouldn't fire yet
    assert spoken == []
    time.sleep(config.DWELL_SECONDS + 0.02)
    main.tick()
    assert any("greeting" in s for s in spoken)
    assert state.conversation_active is True


def test_cooldown_blocks_immediate_retrigger(fresh_state):
    state, spoken = fresh_state
    state.update_distance(80)
    main.tick()  # starts the dwell timer
    time.sleep(config.DWELL_SECONDS + 0.02)
    main.tick()  # greeting fires, conversation active
    assert state.conversation_active is True

    # walk away far enough to trigger walkaway and enter cooldown
    state.update_distance(80 + config.WALKAWAY_DELTA_CM + 10)
    main.tick()
    assert state.conversation_active is False
    assert state.in_cooldown() is True

    spoken.clear()
    # immediately come back into range — should NOT retrigger during cooldown
    state.update_distance(80)
    main.tick()
    assert spoken == []


def test_walkaway_fires_after_closest_approach(fresh_state):
    state, spoken = fresh_state
    state.update_distance(100)
    main.tick()  # starts the dwell timer
    time.sleep(config.DWELL_SECONDS + 0.02)
    main.tick()  # greeting fires
    spoken.clear()

    state.update_distance(60)  # gets closer — updates closest_distance_cm
    main.tick()
    assert spoken == []
    assert state.closest_distance_cm == 60

    state.update_distance(60 + config.WALKAWAY_DELTA_CM + 5)  # steps back past threshold
    main.tick()
    assert any("walkaway" in s for s in spoken)
    assert state.conversation_active is False


def test_bossman_override_suppresses_greeting(fresh_state):
    state, spoken = fresh_state
    state.set_bossman_seen(True)
    main.tick()
    assert len(spoken) == 1  # bossman line fired exactly once
    boss_line_count = len(spoken)

    # even with someone in trigger range, greeting should NOT fire while muted
    state.update_distance(50)
    time.sleep(config.DWELL_SECONDS + 0.02)
    main.tick()
    assert len(spoken) == boss_line_count  # nothing new spoken
    assert state.conversation_active is False


def test_bossman_release_resumes_normal_operation(fresh_state):
    state, spoken = fresh_state
    state.set_bossman_seen(True)
    main.tick()
    spoken.clear()

    time.sleep(config.BLE_LOST_GRACE_SECONDS + 0.05)  # let the tag "leave"
    state.bossman_in_range = False
    main.tick()  # this tick should un-mute

    state.update_distance(80)
    main.tick()  # starts the dwell timer
    time.sleep(config.DWELL_SECONDS + 0.02)
    main.tick()
    assert any("greeting" in s for s in spoken)


def test_greeting_starts_conversation_thread(fresh_state):
    state, spoken = fresh_state
    state.update_distance(80)
    main.tick()
    time.sleep(config.DWELL_SECONDS + 0.02)
    main.tick()

    assert state.conversation_stop_event is not None
    assert state.conversation_thread is not None
    assert state.conversation_history[0]["role"] == "system"
    assert state.conversation_history[-1]["role"] == "assistant"


def test_walkaway_interrupts_conversation_thread(fresh_state):
    state, spoken = fresh_state
    state.update_distance(100)
    main.tick()
    time.sleep(config.DWELL_SECONDS + 0.02)
    main.tick()  # greeting fires, conversation thread starts

    stop_event = state.conversation_stop_event
    assert stop_event.is_set() is False

    state.update_distance(100 + config.WALKAWAY_DELTA_CM + 5)
    main.tick()  # walkaway fires

    assert stop_event.is_set() is True
