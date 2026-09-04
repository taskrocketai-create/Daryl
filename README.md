# Daryl Booth Backend

Life-size interactive Daryl for Jeep shows. HC-SR04 is the primary trigger
(fast, no cloud round-trip); Wyze cams supply the vision frame and content
capture; GPT-4o writes the line; ElevenLabs speaks it.

## Network / internet uplink

`vision.py` and `voice.py` both call out to the internet (OpenAI, ElevenLabs)
on every single trigger, so the booth needs *some* reliable WAN connection —
the GL.iNet router alone only creates a private local bubble for the cams
and laptop, it doesn't generate its own internet.

**Options, not yet decided:**

- **Starlink (not yet purchased)** — if Jason picks this up, it becomes the
  WAN uplink and travels with him to every show:
  ```
  Starlink dish/router → GL.iNet (WAN-in) → private WiFi bubble → 2x Wyze cams + laptop
  ```
  Biggest upside: not dependent on venue WiFi or phone hotspot quality,
  which is the actual failure point at most outdoor/fairground shows. Also
  means the `WYZE_RTSP_URL` IP can be pinned with a DHCP reservation on the
  GL.iNet router and stay stable show to show, since it's the same router
  every time rather than a different venue network each time.
  One caveat: consumer Starlink plans typically sit behind CGNAT (no public
  static IP) unless he's on the static-IP add-on — so the optional IFTTT
  webhook path (`webhook_server.py`) would still need an ngrok/Cloudflare
  Tunnel to be externally reachable. Since that path is logging-only and
  not on the critical trigger path (HC-SR04 handles that), this isn't
  urgent either way.
- **Phone hotspot / venue WiFi (fallback, no purchase needed)** — works,
  but quality varies a lot show to show, and the Wyze cam's local IP isn't
  guaranteed to stay the same between different networks — re-check
  `WYZE_RTSP_URL` at every setup if going this route.

Until Starlink is purchased, assume hotspot/venue WiFi and re-verify
`WYZE_RTSP_URL` each show per the checklist below.

## Testing before the hardware arrives

You don't need the Arduino, HC-SR04, Wyze cams, or the BLE tag in hand to
test almost all of this. Three layers, in order of how much they cover:

### 1. Logic tests — free, instant, no API keys needed
```
pip install -r requirements.txt
pytest tests/ -v
```
Drives the dwell timer, cooldown, walkaway-distance, and Bossman-mute state
machine directly, with `vision.py`/`voice.py` mocked out. Runs in under two
seconds. This is what you run after every change to `main.py` or `state.py`
to make sure the timing logic still behaves — no hardware, no cost, no
waiting around.

### 2. Simulation mode — tests the real GPT-4o + ElevenLabs pipeline
Needs real `OPENAI_API_KEY` and `ELEVENLABS_API_KEY` in `.env`, but no
Arduino/BLE/Wyze cam. Drop any photo of a person into `test_assets/` (see
`test_assets/README.txt`), then:
```
# in .env:
SIMULATION_MODE=true
TEST_IMAGE_PATH=test_assets/sample_person.jpg

python main.py
```
A `[sim]>` prompt takes over for the Arduino and BLE tag — type a number to
simulate standing that many cm away, `boss on`/`boss off` for the BLE tag,
or `auto` to run a scripted approach → linger → walk-away sequence
hands-free. Everything downstream is real: real GPT-4o call on your test
photo, real ElevenLabs voice, real audio played through your speakers. This
is the actual way to sanity-check Daryl's generated lines and tune the
persona prompt in `vision.py` before there's anything to point a camera at.

### 3. What genuinely needs the physical hardware
- Whether the HC-SR04's real-world distance readings behave the way the
  simulated numbers assumed (noise, false reflections, effective range).
- Wyze RTSP frame grab actually working end-to-end (needs RTSP Firmware
  enabled — see setup steps above).
- The Blue Charm BLE tag's actual RSSI values at your chosen distances —
  `BLE_RSSI_THRESHOLD` in `.env` is a guess until tested against the real
  tag and real interference at a show floor.
- Bluetooth speaker audio routing/latency on the actual laptop being used.

Layers 1 and 2 should catch the vast majority of logic and persona issues
well before any of that — hardware time is best spent confirming physical
behavior, not debugging code that could've been caught for free.

## One-time setup

1. **Wyze cam**: enable RTSP Firmware (Wyze app → camera → Firmware Update →
   RTSP Firmware beta). Without this the cam only talks to Wyze's cloud and
   there's no local frame to grab. Note the RTSP URL it gives you.
2. **Arduino**: install the CH340 driver if this is the Nano's first time
   plugging into this laptop. Flash `arduino/hcsr04_distance.ino` via the
   Arduino IDE. Wire per the comments at the top of that file.
3. **Blue Charm (or similar) iBeacon tag**: configure it with its companion
   app, note the UUID it broadcasts, put that in `.env`.
4. **Bluetooth speaker**: pair it and set it as the system's default audio
   output device *before* running the script.
5. **ffmpeg**: needs to be installed and on PATH (provides `ffplay` for
   audio playback).
6. Copy `.env.example` → `.env`, fill in every value.
7. `pip install -r requirements.txt`
   - **Windows:** the `sounddevice` package bundles PortAudio automatically
     — nothing extra to install.
   - **Linux:** if you hit `OSError: PortAudio library not found`, run
     `sudo apt-get install libportaudio2` first, then reinstall.

## Running it

```
python main.py
```

Leave it running. It boots three background threads (serial reader, BLE
scanner, optional webhook listener) and then loops watching distance/mute
state in `main.py`'s `tick()`.

## Testing before the show

- **Distance/dwell**: walk up to the sensor and watch the console — you
  should see `[trigger] greeting pipeline firing` after holding still for
  `DWELL_SECONDS`. Tune `TRIGGER_DISTANCE_CM` and `DWELL_SECONDS` in `.env`
  to match your actual booth layout.
- **Walkaway**: after a greeting fires, back away steadily and confirm
  `[trigger] walkaway pipeline firing` shows up once you clear
  `WALKAWAY_DELTA_CM` past your closest approach.
- **Cooldown**: immediately re-approach after a walkaway — Daryl should
  stay silent until `COOLDOWN_SECONDS` has passed.
- **Bossman tag**: carry the BLE tag toward Daryl and confirm a joke line
  fires once, then everything else goes silent until you step away past
  `BLE_LOST_GRACE_SECONDS`. Walk it in and out repeatedly and confirm the
  joke line doesn't repeat back-to-back and respects
  `BOSSMAN_LINE_MIN_INTERVAL_SECONDS`.

## Two-way conversation

Daryl doesn't just say one line and go quiet — after the greeting, he opens
the mic and actually listens. The flow per interaction:

1. Greeting line fires (as before)
2. `conversation.py` starts listening on the default microphone
3. When the person stops talking (silence detected), their speech gets
   transcribed via Whisper and fed to GPT-4o along with the conversation
   history so far, generating a contextual reply
4. Daryl speaks the reply, then listens again — repeat
5. This keeps going until the HC-SR04 detects the person actually walking
   away, which **interrupts the conversation immediately** (even mid-reply-
   generation) and hands off to the walkaway line instead

**Tuning note:** `SILENCE_RMS_THRESHOLD` in `.env` is only a fallback. On
every real startup, `main.py` runs `conversation.calibrate_noise_floor()` —
records a few seconds of actual ambient sound and sets the real threshold
relative to that measurement, rather than trusting a fixed guess. This
matters a lot more than it sounds: a flat threshold has no idea whether
it's sitting in a quiet room or next to a generator and a PA system, so
**always let this calibration run at the actual show floor**, not just at
home — a quiet house isn't representative of Jeep-show background noise.

**Noise/hallucination filtering:** Whisper has a known tendency to produce
short phantom transcriptions (like "Thank you.") from pure background
noise with no real speech in it. `transcribe()` filters these two ways:
Whisper's own `no_speech_prob` confidence signal per segment (rejects if
Whisper itself thinks a clip was mostly non-speech), plus a small blocklist
of known hallucinated stock phrases. Tune `MAX_NO_SPEECH_PROB` in `.env` if
real speech is getting rejected as noise (raise the value, more permissive)
or noise is still getting through as fake "replies" (lower it, stricter).

**Biggest lever that's outside this code entirely: microphone choice.** An
omnidirectional USB mic will pick up the whole booth's ambient noise
indiscriminately, no amount of software filtering fully compensates for
that. A **directional/cardioid mic** (or a small shotgun mic) mounted to
pick up specifically the zone where someone stands to talk to Daryl, aimed
away from the main crowd/music/engine noise, is the single highest-leverage
fix here — worth prioritizing over further silence-detection tuning.

**One thing that's already handled, not a new concern:** since `voice.speak()`
runs blocking during Daryl's own lines, the mic never records while he's
mid-sentence — so there's no risk of him hearing and reacting to his own
voice through the booth speaker. Listening only starts after he's done
talking, by construction.

**Since automatic listening was chosen over push-to-talk,** the noise-floor
calibration and mic hardware choice above aren't optional nice-to-haves —
there's no button acting as a fallback if noise handling falls short, so
get both right before relying on this at a real show.

**Whisper vocabulary priming:** `transcribe()` passes a short prompt
biasing Whisper toward rucRak-specific vocabulary (GRUNT, GUNNY, Bronco,
Wrangler, fitment, etc.) — helps most in marginal/noisy audio, where a
mumbled or noise-obscured word could otherwise go either way. Update
`_WHISPER_VOCAB_PROMPT` in `conversation.py` if new product terms come up
that Daryl keeps mishearing.

**Known limitation:** if walkaway triggers at the exact moment Daryl is
mid-way through generating or speaking a reply, there's a small chance of
audio overlap between the interrupted reply and the walkaway line. Rare in
practice, but worth knowing it's not fully guarded against.

## Known gaps / things to nail down with Jason

**Keeping material fresh across the whole day:** `recent_lines.py` tracks a
rolling list of Daryl's last 15 generated lines — across *every* visitor,
not just the current conversation — and feeds them back into every future
generation as a "don't repeat these" list. Without this, each person's
interaction has no idea what's already been said to someone else five
minutes earlier, so the same handful of jokes would otherwise recycle
constantly over a full show day. This resets when `main.py` restarts,
which lines up with "fresh material each show" as the reasonable default.

- Line wording in `lines.py` (stall + Bossman lines) is placeholder —
  swap in Jason's actual voice before the first show.
- `vision.py`'s `DARYL_SYSTEM_PROMPT` sets tone/persona — worth a pass once
  you've heard a few real generated lines.
- No disclosure/signage logic here — handle that physically at the booth
  if capturing identifiable faces for social content.
- `ARDUINO_SERIAL_PORT` and `WYZE_RTSP_URL` are laptop/network specific —
  confirm both fresh at every show, they can change.

## One-click startup at the show (Windows)

Once everything's physically set up and powered — Arduino connected, Wyze
cams on the network, Bluetooth speaker paired, mic plugged in — Jason
shouldn't need Command Prompt at all. Set this up **once**, ahead of time:

1. Right-click **`start_daryl.bat`** in the `Daryl` folder → **Send to** →
   **Desktop (create shortcut)**
2. On the Desktop, rename the new shortcut to something obvious like
   **"Start Daryl"**
3. (Optional) Right-click the shortcut → **Properties** → **Change Icon** to
   make it easier to spot at a glance

**At the show, starting Daryl is then just:** double-click that desktop
shortcut. It will:
- Check `.env` exists and give a plain-English message (not a Python
  error) if it's missing
- Run the noise-floor calibration and boot everything automatically
- **Auto-restart itself if it crashes** (bad frame grab, API hiccup, mic
  error) after a 5-second pause — no need to notice and manually restart
  mid-show
- Stay stopped for good only if the window itself is closed

Worth testing this shortcut once before the actual show, not for the
first time on-site — confirm it launches cleanly and finds `.env` from
wherever the shortcut actually lives.
