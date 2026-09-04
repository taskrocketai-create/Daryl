"""
serial_reader.py — background thread that reads distance readings off the
Arduino Nano over USB serial and updates shared state.

Expects the Arduino to be running arduino/hcsr04_distance.ino, which prints
one line per reading like:  DIST:123.4
"""
import time
import serial

import config
from state import state


def run():
    while True:
        try:
            ser = serial.Serial(config.ARDUINO_SERIAL_PORT, config.ARDUINO_BAUD_RATE, timeout=2)
            print(f"[serial] connected on {config.ARDUINO_SERIAL_PORT}")
            time.sleep(2)  # let the Nano finish its reset-on-connect

            while True:
                raw = ser.readline().decode("utf-8", errors="ignore").strip()
                if not raw.startswith("DIST:"):
                    continue
                try:
                    cm = float(raw.split(":", 1)[1])
                except ValueError:
                    continue
                state.update_distance(cm)

        except serial.SerialException as e:
            print(f"[serial] lost connection ({e}), retrying in 3s...")
            time.sleep(3)
        except Exception as e:
            print(f"[serial] unexpected error: {e}, retrying in 3s...")
            time.sleep(3)


def start_thread():
    import threading
    t = threading.Thread(target=run, daemon=True, name="serial_reader")
    t.start()
    return t
