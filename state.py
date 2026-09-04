"""
state.py — single shared, thread-safe state object.
serial_reader, ble_presence, and main all read/write through this instead
of passing values around directly.
"""
import threading
import time


class DarylState:
    def __init__(self):
        self._lock = threading.Lock()

        # Distance / dwell tracking (fed by serial_reader.py)
        self.last_distance_cm = None
        self.last_distance_at = 0.0
        self.dwell_start = None          # timestamp when person first entered trigger range
        self.closest_distance_cm = None  # tightest distance seen during an active conversation

        # Trigger / cooldown
        self.cooldown_until = 0.0
        self.conversation_active = False

        # BLE Bossman
        self.bossman_in_range = False
        self.bossman_last_seen_at = 0.0
        self.bossman_mute_active = False
        self.bossman_last_line_at = 0.0

    # --- distance ---
    def update_distance(self, cm: float):
        with self._lock:
            self.last_distance_cm = cm
            self.last_distance_at = time.time()

    def get_distance(self):
        with self._lock:
            return self.last_distance_cm, self.last_distance_at

    # --- dwell ---
    def start_dwell_if_needed(self):
        with self._lock:
            if self.dwell_start is None:
                self.dwell_start = time.time()
            return self.dwell_start

    def clear_dwell(self):
        with self._lock:
            self.dwell_start = None

    # --- conversation lifecycle ---
    def begin_conversation(self, distance_cm: float):
        with self._lock:
            self.conversation_active = True
            self.closest_distance_cm = distance_cm
            self.dwell_start = None

    def update_closest(self, distance_cm: float):
        with self._lock:
            if self.closest_distance_cm is None or distance_cm < self.closest_distance_cm:
                self.closest_distance_cm = distance_cm

    def end_conversation(self, cooldown_seconds: float):
        with self._lock:
            self.conversation_active = False
            self.closest_distance_cm = None
            self.cooldown_until = time.time() + cooldown_seconds

    def in_cooldown(self):
        with self._lock:
            return time.time() < self.cooldown_until

    # --- Bossman / BLE ---
    def set_bossman_seen(self, rssi_ok: bool):
        with self._lock:
            now = time.time()
            if rssi_ok:
                self.bossman_in_range = True
                self.bossman_last_seen_at = now
            return self.bossman_in_range, self.bossman_last_seen_at

    def bossman_should_still_be_muted(self, grace_seconds: float):
        with self._lock:
            if self.bossman_in_range:
                return True
            # grace period after the tag drops out, so brief signal loss
            # doesn't immediately un-mute mid-conversation
            return (time.time() - self.bossman_last_seen_at) < grace_seconds

    def clear_bossman_range(self):
        with self._lock:
            self.bossman_in_range = False

    def set_mute(self, muted: bool):
        with self._lock:
            self.bossman_mute_active = muted

    def is_muted(self):
        with self._lock:
            return self.bossman_mute_active

    def can_play_bossman_line(self, min_interval: float):
        with self._lock:
            return (time.time() - self.bossman_last_line_at) >= min_interval

    def mark_bossman_line_played(self):
        with self._lock:
            self.bossman_last_line_at = time.time()


# Single shared instance imported everywhere
state = DarylState()
