"""
ble_presence.py — background thread that continuously scans for Jason's
iBeacon tag (e.g. Blue Charm BC011) and updates shared state with
in-range/out-of-range status.

iBeacon isn't natively parsed by bleak, so we pull it out of Apple's
manufacturer_data (company ID 0x004C) ourselves.
"""
import asyncio
import threading

from bleak import BleakScanner

import config
from state import state


def _parse_ibeacon_uuid(manufacturer_data: dict):
    """Return the iBeacon UUID string (lowercase, dashed) if this advertisement
    is an iBeacon frame, else None."""
    apple_data = manufacturer_data.get(0x004C)
    if not apple_data or len(apple_data) < 23:
        return None
    # Apple iBeacon frame: 2 bytes type/length (0x02, 0x15) + 16 byte UUID + major + minor + tx power
    if apple_data[0] != 0x02 or apple_data[1] != 0x15:
        return None
    uuid_bytes = apple_data[2:18]
    uuid_str = uuid_bytes.hex()
    return f"{uuid_str[0:8]}-{uuid_str[8:12]}-{uuid_str[12:16]}-{uuid_str[16:20]}-{uuid_str[20:32]}"


def _detection_callback(device, advertisement_data):
    if not config.BOSSMAN_BEACON_UUID:
        return
    uuid = _parse_ibeacon_uuid(advertisement_data.manufacturer_data)
    if uuid != config.BOSSMAN_BEACON_UUID:
        return
    rssi = advertisement_data.rssi
    rssi_ok = rssi is not None and rssi >= config.BLE_RSSI_THRESHOLD
    if rssi_ok:
        state.set_bossman_seen(True)


async def _scan_loop():
    scanner = BleakScanner(detection_callback=_detection_callback)
    await scanner.start()
    print("[ble] scanning for Bossman tag...")
    try:
        while True:
            await asyncio.sleep(1)
            # if we haven't seen the tag within the grace window, clear range flag
            # (mute logic itself uses the grace period separately — this just
            # keeps bossman_in_range honest for anything else that reads it)
            if not state.bossman_should_still_be_muted(config.BLE_LOST_GRACE_SECONDS):
                state.clear_bossman_range()
    finally:
        await scanner.stop()


def _run_in_new_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(_scan_loop())


def start_thread():
    t = threading.Thread(target=_run_in_new_loop, daemon=True, name="ble_presence")
    t.start()
    return t
