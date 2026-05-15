from __future__ import annotations
import json
import logging
import threading
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlencode

from micdot.conferencing.base import ConferencingPlugin

log = logging.getLogger("micdot")

_WS_HOST = "ws://localhost:8124"
_TOKEN_PATH = Path.home() / ".config" / "micdot" / "teams_token"


class TeamsPlugin(ConferencingPlugin):
    bundle_id = "com.microsoft.teams2"
    name = "Microsoft Teams"

    def __init__(self) -> None:
        self._muted: bool | None = None
        self._in_meeting: bool = False
        self._on_change: Callable[[bool], None] | None = None
        self._ws = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._request_id = 0

    # ------------------------------------------------------------------ #
    # ConferencingPlugin interface
    # ------------------------------------------------------------------ #

    def is_running(self) -> bool:
        try:
            from AppKit import NSRunningApplication
            apps = NSRunningApplication.runningApplicationsWithBundleIdentifier_(self.bundle_id)
            return len(apps) > 0
        except Exception:
            return False

    def is_in_meeting(self) -> bool:
        return self._in_meeting

    def get_mute(self) -> bool | None:
        return self._muted if self._in_meeting else None

    def set_mute(self, muted: bool) -> None:
        if not self._in_meeting or self._muted == muted:
            return
        self._send({"action": "toggle-mute"})

    def start_observing(self, on_change: Callable[[bool], None]) -> None:
        self._on_change = on_change
        self._stop_event.clear()
        threading.Thread(target=self._ws_loop, daemon=True, name="teams-ws").start()

    def stop_observing(self) -> None:
        self._stop_event.set()
        with self._lock:
            ws = self._ws
        if ws:
            try:
                ws.close()
            except Exception:
                pass

    # ------------------------------------------------------------------ #
    # WebSocket loop
    # ------------------------------------------------------------------ #

    def _ws_loop(self) -> None:
        import websocket
        while not self._stop_event.is_set():
            if not self.is_running():
                self._stop_event.wait(3.0)
                continue
            token = self._load_token()
            url = self._build_url(token)
            ws = websocket.WebSocketApp(
                url,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=lambda ws, e: log.debug("TeamsPlugin: WS error: %s", e),
                on_close=lambda ws, c, m: log.debug("TeamsPlugin: WS closed"),
            )
            with self._lock:
                self._ws = ws
            ws.run_forever()
            with self._lock:
                self._ws = None
            self._in_meeting = False
            self._muted = None
            if not self._stop_event.is_set():
                self._stop_event.wait(3.0)

    def _on_open(self, ws) -> None:
        log.debug("TeamsPlugin: connected to Teams local API")

    def _on_message(self, ws, raw: str) -> None:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return

        if "tokenRefresh" in data:
            self._save_token(data["tokenRefresh"])
            log.debug("TeamsPlugin: token saved")
            return

        meeting_update = data.get("meetingUpdate") or {}

        # Trigger pairing when not yet authenticated
        permissions = meeting_update.get("meetingPermissions") or {}
        if permissions.get("canPair") and not self._load_token():
            log.debug("TeamsPlugin: sending pair request")
            self._send({"service": "pair", "action": "pair"})

        state = meeting_update.get("meetingState")
        if state is None:
            return

        in_meeting = bool(state.get("isInMeeting"))
        muted = state.get("isMuted")

        self._in_meeting = in_meeting
        if not in_meeting:
            self._muted = None
            return

        if muted is not None and muted != self._muted:
            self._muted = muted
            cb = self._on_change
            if cb:
                cb(muted)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _send(self, payload: dict) -> None:
        with self._lock:
            ws = self._ws
            self._request_id += 1
            req_id = self._request_id
        if ws is None:
            return
        try:
            ws.send(json.dumps({"requestId": req_id, "apiVersion": "2.0.0", **payload}))
        except Exception:
            log.warning("TeamsPlugin: send failed", exc_info=True)

    def _build_url(self, token: str) -> str:
        params = urlencode({
            "token": token,
            "protocol-version": "2.0.0",
            "manufacturer": "MicDot",
            "device": "MicDot",
            "app": "com.micdot.app",
            "app-version": "1.0.0",
        })
        return f"{_WS_HOST}?{params}"

    def _load_token(self) -> str:
        try:
            return _TOKEN_PATH.read_text().strip()
        except FileNotFoundError:
            return ""

    def _save_token(self, token: str) -> None:
        _TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        _TOKEN_PATH.write_text(token)
