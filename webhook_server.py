"""
webhook_server.py — optional secondary trigger path.

The HC-SR04 (via serial_reader.py) is the primary, low-latency trigger.
This just gives IFTTT/Wyze motion events somewhere to land for logging and
future use (e.g. content-capture timestamps), without gating any of the
actual greeting logic. Safe to ignore/leave running in the background.
"""
import threading
from flask import Flask, request

import config

app = Flask(__name__)


@app.route("/wyze-motion", methods=["POST"])
def wyze_motion():
    print("[webhook] Wyze motion event received (logging only, not gating triggers)")
    return {"status": "ok"}, 200


def start_thread():
    def _run():
        app.run(host="0.0.0.0", port=config.WEBHOOK_PORT, debug=False, use_reloader=False)

    t = threading.Thread(target=_run, daemon=True, name="webhook_server")
    t.start()
    return t
