"""
config.py — all tunables and secrets live here.
Copy .env.example to .env and fill in real values before running.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# --- API keys ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "")

# --- Wyze camera ---
# Requires Wyze RTSP Firmware enabled on the cam (Wyze app > Camera > Firmware
# Update > install "RTSP Firmware" beta). Without this, the cam only streams
# to Wyze's cloud and there's no local frame to grab.
WYZE_RTSP_URL = os.getenv("WYZE_RTSP_URL", "rtsp://user:pass@192.168.8.100/live")

# --- Arduino / HC-SR04 ---
ARDUINO_SERIAL_PORT = os.getenv("ARDUINO_SERIAL_PORT", "/dev/ttyUSB0")  # COM3 etc on Windows
ARDUINO_BAUD_RATE = int(os.getenv("ARDUINO_BAUD_RATE", "9600"))

# --- Trigger tuning ---
TRIGGER_DISTANCE_CM = float(os.getenv("TRIGGER_DISTANCE_CM", "150"))   # someone's "here"
DWELL_SECONDS = float(os.getenv("DWELL_SECONDS", "1.5"))               # must hold inside range this long
COOLDOWN_SECONDS = float(os.getenv("COOLDOWN_SECONDS", "75"))          # silence after a greeting
WALKAWAY_DELTA_CM = float(os.getenv("WALKAWAY_DELTA_CM", "60"))        # distance increase that reads as "leaving"

# --- BLE Bossman tag ---
BOSSMAN_BEACON_UUID = os.getenv("BOSSMAN_BEACON_UUID", "").lower()     # Blue Charm BC011 UUID
BLE_RSSI_THRESHOLD = int(os.getenv("BLE_RSSI_THRESHOLD", "-70"))       # closer = less negative
BLE_LOST_GRACE_SECONDS = float(os.getenv("BLE_LOST_GRACE_SECONDS", "5"))
BOSSMAN_LINE_MIN_INTERVAL_SECONDS = float(os.getenv("BOSSMAN_LINE_MIN_INTERVAL_SECONDS", "240"))

# --- Optional IFTTT webhook (secondary/backup trigger, logging only) ---
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "5005"))

# --- Audio ---
# Bluetooth speaker should be paired and set as the system's default output
# device — this just plays through whatever that is via ffplay.
AUDIO_TEMP_DIR = os.getenv("AUDIO_TEMP_DIR", "/tmp/daryl_audio")

# --- Simulation mode (no hardware needed) ---
# When true: distance + Bossman presence come from your keyboard instead of
# the Arduino/BLE, and vision.py reads a local photo instead of the Wyze
# RTSP stream. Everything else (GPT-4o, ElevenLabs) runs for real, so this
# is the way to test the actual pipeline before any hardware shows up.
SIMULATION_MODE = os.getenv("SIMULATION_MODE", "false").lower() == "true"
TEST_IMAGE_PATH = os.getenv("TEST_IMAGE_PATH", "test_assets/sample_person.jpg")

