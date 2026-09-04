"""
main.py — Daryl's brain. Run this.

Flow per tick:
  1. Bossman check — if Jason's BLE tag is in range, play (throttled) joke
     line once on entry, then stay muted for as long as he's near. This
     overrides everything else.
  2. If not muted and no conversation active: watch the HC-SR04 distance.
     Once someone holds inside TRIGGER_DISTANCE_CM for DWELL_SECONDS, and
     we're not in cooldown, fire the greeting pipeline.
  3. If a conversation is active: watch for the walkaway threshold
     (distance grows WALKAWAY_DELTA_CM past the closest point reached),
     fire the walkaway pipeline, then enter cooldown.
"""
import time

import config
from state import state
import serial_reader
import ble_presence
import webhook_server
import vision
import voice
from lines import STALL_LINES, BOSSMAN_LINES, WALKAWAY_FALLBACK_LINES, get_random_no_repeat


def handle_bossman():
    """Returns True if Bossman logic is currently suppressing everything else."""
    still_muted = state.bossman_should_still_be_muted(config.BLE_LOST_GRACE_SECONDS)

    if still_muted and not state.is_muted():
        # just entered range this tick — play the joke line once, throttled
        state.set_mute(True)
        if state.can_play_bossman_line(config.BOSSMAN_LINE_MIN_INTERVAL_SECONDS):
            line = get_random_no_repeat("bossman", BOSSMAN_LINES)
            voice.speak(line, blocking=False)
            state.mark_bossman_line_played()

    elif not still_muted and state.is_muted():
        # tag has been gone past the grace window — resume normal operation
        state.set_mute(False)
        state.clear_dwell()

    return state.is_muted()


def run_greeting_pipeline(distance_cm: float):
    print("[trigger] greeting pipeline firing")
    state.begin_conversation(distance_cm)

    # immediate stall line while vision + TTS generate in the background
    voice.speak(get_random_no_repeat("stall", STALL_LINES), blocking=False)

    try:
        frame = vision.grab_frame()
        line = vision.ask_daryl(frame, mode="greeting")
    except Exception as e:
        print(f"[vision] greeting generation failed: {e}")
        line = "Well hey there. Come on over."

    voice.speak(line, blocking=True)


def run_walkaway_pipeline():
    print("[trigger] walkaway pipeline firing")
    try:
        frame = vision.grab_frame()
        line = vision.ask_daryl(frame, mode="walkaway")
    except Exception as e:
        print(f"[vision] walkaway generation failed: {e}")
        line = get_random_no_repeat("walkaway_fallback", WALKAWAY_FALLBACK_LINES)

    voice.speak(line, blocking=True)
    state.end_conversation(config.COOLDOWN_SECONDS)


def tick():
    if handle_bossman():
        return  # Bossman override — skip everything else this tick

    distance_cm, updated_at = state.get_distance()
    if distance_cm is None or (time.time() - updated_at) > 3:
        return  # no fresh sensor data yet / serial dropped

    if state.conversation_active:
        state.update_closest(distance_cm)
        closest = state.closest_distance_cm or distance_cm
        if distance_cm - closest >= config.WALKAWAY_DELTA_CM:
            run_walkaway_pipeline()
        return

    if state.in_cooldown():
        state.clear_dwell()
        return

    if distance_cm <= config.TRIGGER_DISTANCE_CM:
        dwell_start = state.start_dwell_if_needed()
        if time.time() - dwell_start >= config.DWELL_SECONDS:
            run_greeting_pipeline(distance_cm)
    else:
        state.clear_dwell()


def main():
    print("[daryl] booting up...")

    if config.SIMULATION_MODE:
        print("[daryl] SIMULATION MODE — no Arduino/BLE/Wyze required.")
        import sim.fake_hardware as fake_hardware
        fake_hardware.start_thread()
    else:
        serial_reader.start_thread()
        ble_presence.start_thread()

    webhook_server.start_thread()
    print("[daryl] all systems running. Waiting for someone to walk up...")

    try:
        while True:
            tick()
            time.sleep(0.15)
    except KeyboardInterrupt:
        print("\n[daryl] shutting down.")


if __name__ == "__main__":
    main()
