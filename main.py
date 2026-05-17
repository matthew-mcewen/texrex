"""
main.py
-------
Unified service for OBS TX and RX indicator image sources.

  TX indicator: shown while set PTT is held
  RX indicator: shown while TrackAudio is receiving on a frequency with TX+RX both selected

Requirements:
    pip install websockets obsws-python pynput
"""

import asyncio
import json
import logging
import pathlib
import threading

import obsws_python as obs
import websockets
from pynput import keyboard

# ── Load config.json ──────────────────────────────────────────────────────────
_cfg_path = pathlib.Path(__file__).with_name("config.json")
if not _cfg_path.exists():
    raise FileNotFoundError(
        f"config.json not found at {_cfg_path}\n"
        "Edit config.json directly or run configure.py to set your options."
    )
_cfg: dict = json.loads(_cfg_path.read_text(encoding="utf-8"))

TRACKAUDIO_WS          = _cfg["trackaudio_ws"]
OBS_HOST               = _cfg["obs_host"]
OBS_PORT               = _cfg["obs_port"]
OBS_PASSWORD           = _cfg["obs_password"]
OBS_SCENE_NAME         = _cfg["obs_scene_name"]
OBS_TX_SOURCE          = _cfg["obs_tx_source"]
OBS_RX_SOURCE          = _cfg["obs_rx_source"]
OBS_RECONNECT_INTERVAL = _cfg["obs_reconnect_interval"]


def _parse_ptt_key(s: str):
    try:
        return keyboard.Key[s]
    except KeyError:
        return keyboard.KeyCode.from_char(s)

PTT_KEY = _parse_ptt_key(_cfg["ptt_key"])

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ── OBS connection ────────────────────────────

class OBSController:
    def __init__(self):
        self._lock = threading.Lock()
        self._cl: obs.ReqClient | None = None
        self._item_ids: dict[str, int] = {}
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    def try_connect(self, scene: str, sources: list[str]) -> bool:
        """Attempt to connect to OBS; returns True on success."""
        try:
            log.info("Connecting to OBS WebSocket...")
            cl = obs.ReqClient(host=OBS_HOST, port=OBS_PORT, password=OBS_PASSWORD)
            items = cl.get_scene_item_list(scene).scene_items
            item_ids: dict[str, int] = {}
            for source in sources:
                match = next((i for i in items if i["sourceName"] == source), None)
                if match is None:
                    raise RuntimeError(f"Source '{source}' not found in scene '{scene}'")
                item_ids[source] = match["sceneItemId"]
                log.info(f"  '{source}' → scene item ID {match['sceneItemId']}")
            with self._lock:
                self._cl = cl
                self._item_ids = item_ids
                self._connected = True
            for source in sources:
                self._do_set(cl, item_ids[source], False)
            log.info("OBS ready.")
            return True
        except Exception as e:
            log.warning(f"OBS connection failed: {e}")
            return False

    def _do_set(self, cl: obs.ReqClient, item_id: int, visible: bool):
        """Low-level scene-item visibility call; marks disconnected on failure."""
        try:
            cl.set_scene_item_enabled(OBS_SCENE_NAME, item_id, visible)
        except Exception as e:
            log.warning(f"OBS call failed: {e}")
            with self._lock:
                if self._cl is cl:
                    self._connected = False
                    self._cl = None

    def _send(self, source: str, visible: bool):
        with self._lock:
            if not self._connected or self._cl is None:
                return
            cl = self._cl
            item_id = self._item_ids.get(source)
        if item_id is None:
            return
        log.info(f"OBS {'▶' if visible else '■'}  {'show' if visible else 'hide'} '{source}'")
        self._do_set(cl, item_id, visible)

    def show(self, source: str):
        self._send(source, True)

    def hide(self, source: str):
        self._send(source, False)


obs_ctrl = OBSController()


# ── TX: pynput keyboard listener (runs in its own thread) ────────────────────

def start_ptt_listener():
    """
    Spawns a pynput Listener in a daemon thread.
    pynput passes the key through to all other applications automatically.
    """
    def _on_press(key):
        if key == PTT_KEY:
            obs_ctrl.show(OBS_TX_SOURCE)

    def _on_release(key):
        if key == PTT_KEY:
            obs_ctrl.hide(OBS_TX_SOURCE)

    t = keyboard.Listener(on_press=_on_press, on_release=_on_release)
    t.daemon = True
    t.start()
    log.info(f"PTT listener active on {PTT_KEY}.")
    return t


# ── OBS reconnect loop ────────────────────────────────────────────────────────

async def obs_reconnect_loop():
    """Keeps attempting to connect (or reconnect) to OBS in the background."""
    loop = asyncio.get_running_loop()
    sources = [OBS_TX_SOURCE, OBS_RX_SOURCE]
    while True:
        if not obs_ctrl.connected:
            await loop.run_in_executor(
                None,
                lambda: obs_ctrl.try_connect(OBS_SCENE_NAME, sources),
            )
        await asyncio.sleep(OBS_RECONNECT_INTERVAL)


# ── RX: TrackAudio WebSocket listener (runs in asyncio) ──────────────────────

async def trackaudio_loop():
    # { freq_hz: {"callsign": str, "tx": bool, "rx": bool} }
    station_states: dict[int, dict] = {}
    primary_freq: int | None = None

    def find_primary() -> int | None:
        for freq, s in station_states.items():
            if s["tx"] and s["rx"]:
                return freq
        return None

    log.info(f"Connecting to TrackAudio at {TRACKAUDIO_WS} ...")

    async for ws in websockets.connect(TRACKAUDIO_WS):
        try:
            log.info("TrackAudio connected.")

            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                msg_type = msg.get("type")
                value    = msg.get("value", {})

                # Station added, removed, or toggled
                if msg_type == "kStationStateUpdate":
                    freq     = value.get("frequency")
                    is_avail = value.get("isAvailable", False)
                    callsign = value.get("callsign", "")

                    if not is_avail or freq is None:
                        station_states.pop(freq, None)
                    else:
                        station_states[freq] = {
                            "callsign": callsign,
                            "tx": value.get("tx", False),
                            "rx": value.get("rx", False),
                        }

                    new_primary = find_primary()
                    if new_primary != primary_freq:
                        primary_freq = new_primary
                        if primary_freq:
                            cs = station_states[primary_freq]["callsign"]
                            log.info(f"Primary frequency: {cs} @ {primary_freq / 1e6:.3f} MHz")
                        else:
                            log.info("No primary frequency (no station is TX+RX)")

                # Incoming transmission started
                elif msg_type == "kRxBegin":
                    freq     = value.get("pFrequencyHz")
                    callsign = value.get("callsign", "?")
                    if primary_freq and freq == primary_freq:
                        log.info(f"RX begin: {callsign} on {freq / 1e6:.3f} MHz")
                        obs_ctrl.show(OBS_RX_SOURCE)
                    else:
                        log.debug(f"RX begin: {callsign} on {freq} (not primary, ignored)")

                # Incoming transmission ended
                elif msg_type == "kRxEnd":
                    freq     = value.get("pFrequencyHz")
                    callsign = value.get("callsign", "?")
                    if primary_freq and freq == primary_freq:
                        log.info(f"RX end:   {callsign} on {freq / 1e6:.3f} MHz")
                        obs_ctrl.hide(OBS_RX_SOURCE)

        except websockets.ConnectionClosed:
            log.warning("TrackAudio disconnected — hiding RX indicator, reconnecting in 3 s...")
            obs_ctrl.hide(OBS_RX_SOURCE)
            await asyncio.sleep(3)


# ── Entry point ───────────────────────────────

async def main():
    start_ptt_listener()
    await asyncio.gather(
        trackaudio_loop(),
        obs_reconnect_loop(),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Stopped.")
