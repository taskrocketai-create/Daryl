"""
sim/fake_hardware.py — stands in for serial_reader.py + ble_presence.py when
config.SIMULATION_MODE is true. Lets you drive the exact same state machine
main.py uses, but by typing instead of physically walking up to a sensor.

Commands (type and press enter):
  <number>     set distance in cm, e.g. "80" — simulates being that close
  far          shortcut for "999" (out of range)
  boss on      simulate Jason's BLE tag entering range
  boss off     simulate the tag leaving range
  auto         run a scripted approach -> linger -> walk away sequence
  help         show this list
  quit         stop the simulator (Ctrl+C also works)
"""
import threading
import time

from state import state


def _run_auto_sequence():
    """Scripted walk-up -> linger -> walk-away, useful for a hands-free
    smoke test of the whole dwell/trigger/walkaway timing."""
    print("[sim] running scripted sequence: approach -> linger -> walk away")
    steps = [
        (300, 0.3), (220, 0.3), (150, 0.3), (100, 0.3), (60, 2.5),  # approach + linger
        (60, 1.0), (60, 1.0),                                        # hold near
        (150, 0.3), (250, 0.3), (400, 0.3),                          # walk away
    ]
    for distance, hold_seconds in steps:
        state.update_distance(distance)
        print(f"[sim] distance = {distance}cm")
        time.sleep(hold_seconds)
    print("[sim] scripted sequence complete")


def _input_loop():
    print("[sim] fake hardware active. Type 'help' for commands.")
    while True:
        try:
            raw = input("[sim]> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            break

        if raw == "help":
            print(__doc__)
        elif raw == "quit":
            break
        elif raw == "far":
            state.update_distance(999)
            print("[sim] distance = 999cm (out of range)")
        elif raw == "auto":
            threading.Thread(target=_run_auto_sequence, daemon=True).start()
        elif raw == "boss on":
            state.set_bossman_seen(True)
            print("[sim] Bossman tag: IN RANGE")
        elif raw == "boss off":
            # force it out of range immediately, ignoring grace period,
            # since this is a deliberate test action
            state.bossman_in_range = False
            state.bossman_last_seen_at = 0
            print("[sim] Bossman tag: OUT OF RANGE")
        else:
            try:
                cm = float(raw)
                state.update_distance(cm)
                print(f"[sim] distance = {cm}cm")
            except ValueError:
                print("[sim] unrecognized command, type 'help'")


def start_thread():
    t = threading.Thread(target=_input_loop, daemon=True, name="fake_hardware")
    t.start()
    return t
