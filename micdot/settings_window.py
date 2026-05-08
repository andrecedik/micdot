"""Run as: python -m micdot.settings_window [config_path]"""
from __future__ import annotations
import json
import shutil
import sys
import threading
from dataclasses import asdict
from pathlib import Path

from micdot.autostart import enable_autostart, disable_autostart
from micdot.config import Config, DEFAULT_CONFIG_PATH
from micdot.log import setup as setup_logging

log = setup_logging()


_HTML = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,sans-serif;font-size:13px;
  background:#f0f0f0;padding:20px;color:#222}
h1{font-size:15px;font-weight:600;margin-bottom:16px;color:#111}
.lbl{font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.8px;
  color:#888;margin-bottom:6px}
.group{background:#fff;border-radius:8px;border:1px solid #e5e5e5;
  overflow:hidden;margin-bottom:16px}
.row{display:flex;align-items:center;padding:8px 12px;
  border-bottom:1px solid #e5e5e5}
.row:last-child{border-bottom:none}
.row>label{width:110px;color:#555;flex-shrink:0}
.row input[type=text],.row input[type=password],.row input[type=number]{
  flex:1;border:none;outline:none;font-size:13px;font-family:inherit;background:transparent}
.crow{display:flex;align-items:center;gap:8px;flex:1}
input[type=color]{width:22px;height:22px;border:1px solid #ccc;border-radius:4px;
  padding:0;cursor:pointer;flex-shrink:0}
.hex{font-family:monospace;border:1px solid #ddd;border-radius:4px;
  padding:3px 6px;font-size:12px;flex:1;outline:none}
.autorow{display:flex;align-items:center;justify-content:space-between;
  padding:8px 0;margin-bottom:16px}
button{width:100%;padding:8px;border-radius:6px;background:#007aff;color:#fff;
  border:none;font-size:13px;font-weight:500;cursor:pointer}
button:disabled{opacity:.6;cursor:default}
</style>
</head>
<body>
<h1>MicDot Settings</h1>
<div class="lbl">MQTT</div>
<div class="group">
  <div class="row"><label>Host</label>
    <input type="text" id="mqtt_host"></div>
  <div class="row"><label>Port</label>
    <input type="number" id="mqtt_port" min="1" max="65535" style="width:70px;flex:none"></div>
  <div class="row"><label>Username</label>
    <input type="text" id="mqtt_username" autocomplete="off"></div>
  <div class="row"><label>Password</label>
    <input type="password" id="mqtt_password" autocomplete="off"></div>
</div>
<div class="lbl">HARDWARE &amp; BEHAVIOUR</div>
<div class="group">
  <div class="row"><label>Hotkey</label>
    <input type="text" id="hotkey"></div>
  <div class="row"><label>Brightness</label>
    <input type="number" id="led_brightness" min="0" max="255" style="width:70px;flex:none"></div>
  <div class="row"><label>Muted color</label>
    <div class="crow">
      <input type="color" id="mp">
      <input type="text" class="hex" id="mh" maxlength="7">
    </div></div>
  <div class="row"><label>Unmuted color</label>
    <div class="crow">
      <input type="color" id="up">
      <input type="text" class="hex" id="uh" maxlength="7">
    </div></div>
</div>
<div class="autorow">
  <span>Autostart on login</span>
  <input type="checkbox" id="autostart">
</div>
<button id="btn">Save</button>
<script>
var c=CONFIG_PLACEHOLDER;
document.getElementById('mqtt_host').value=c.mqtt_host;
document.getElementById('mqtt_port').value=c.mqtt_port;
document.getElementById('mqtt_username').value=c.mqtt_username;
document.getElementById('mqtt_password').value=c.mqtt_password;
document.getElementById('hotkey').value=c.hotkey;
document.getElementById('led_brightness').value=c.led_brightness;
document.getElementById('autostart').checked=c.autostart;
function toHex(o){return'#'+[o.r,o.g,o.b].map(function(v){return('0'+v.toString(16)).slice(-2)}).join('')}
function hexToRgb(h){h=h.replace('#','');return{r:parseInt(h.slice(0,2),16),g:parseInt(h.slice(2,4),16),b:parseInt(h.slice(4,6),16)}}
var mp=document.getElementById('mp'),mh=document.getElementById('mh');
var up=document.getElementById('up'),uh=document.getElementById('uh');
mp.value=mh.value=toHex(c.color_muted);
up.value=uh.value=toHex(c.color_unmuted);
mp.addEventListener('input',function(){mh.value=mp.value});
mh.addEventListener('input',function(){if(/^#[0-9a-fA-F]{6}$/.test(mh.value))mp.value=mh.value});
up.addEventListener('input',function(){uh.value=up.value});
uh.addEventListener('input',function(){if(/^#[0-9a-fA-F]{6}$/.test(uh.value))up.value=uh.value});
document.getElementById('btn').addEventListener('click',function(){
  var portVal=parseInt(document.getElementById('mqtt_port').value);
  var brightVal=parseInt(document.getElementById('led_brightness').value);
  if(isNaN(portVal)||portVal<1||portVal>65535){alert('Port must be 1–65535');return;}
  if(isNaN(brightVal)||brightVal<0||brightVal>255){alert('Brightness must be 0–255');return;}
  var mhv=/^#[0-9a-fA-F]{6}$/.test(mh.value)?mh.value:toHex(c.color_muted);
  var uhv=/^#[0-9a-fA-F]{6}$/.test(uh.value)?uh.value:toHex(c.color_unmuted);
  document.getElementById('btn').disabled=true;
  window.pywebview.api.save({
    mqtt_host:document.getElementById('mqtt_host').value,
    mqtt_port:portVal,
    mqtt_username:document.getElementById('mqtt_username').value,
    mqtt_password:document.getElementById('mqtt_password').value,
    hotkey:document.getElementById('hotkey').value,
    led_brightness:brightVal,
    color_muted:hexToRgb(mhv),
    color_unmuted:hexToRgb(uhv),
    autostart:document.getElementById('autostart').checked
  }).catch(function(){document.getElementById('btn').disabled=false;});
});
</script>
</body>
</html>"""


class Api:
    def __init__(self, config_path: Path) -> None:
        self._config_path = config_path
        self._saved = False
        self._window = None

    @property
    def saved(self) -> bool:
        return self._saved

    def set_window(self, window) -> None:
        self._window = window

    def save(self, data: dict) -> None:
        log.info("Saving settings")
        new = Config(
            mqtt_host=str(data["mqtt_host"]),
            mqtt_port=int(data["mqtt_port"]),
            mqtt_username=str(data["mqtt_username"]),
            mqtt_password=str(data["mqtt_password"]),
            hotkey=str(data["hotkey"]),
            led_brightness=int(data["led_brightness"]),
            color_muted={
                "r": int(data["color_muted"]["r"]),
                "g": int(data["color_muted"]["g"]),
                "b": int(data["color_muted"]["b"]),
            },
            color_unmuted={
                "r": int(data["color_unmuted"]["r"]),
                "g": int(data["color_unmuted"]["g"]),
                "b": int(data["color_unmuted"]["b"]),
            },
            autostart=bool(data["autostart"]),
        )
        new.save(self._config_path)
        log.info("Config saved to %s", self._config_path)
        self._saved = True
        # Autostart configuration can be slow (launchctl); run it in the background.
        threading.Thread(target=self._handle_autostart, args=(new,), daemon=True).start()
        # Close the window synchronously (waitUntilDone=True) from the main thread
        # before returning to the caller. pywebview's js_bridge_call thread calls
        # evaluate_js immediately after save() returns to resolve the JS Promise.
        # evaluate_js blocks on a semaphore waiting for a WKWebView completion
        # handler. If we close the window asynchronously (waitUntilDone=False) from
        # a separate thread, the close races with that completion handler: when close
        # wins, windowWillClose_ sets i.webview=None and calls app.stop_(), orphaning
        # the pending eval — the handler never fires and the thread deadlocks.
        # With waitUntilDone=True here, windowWillClose_ has already run and removed
        # the window from BrowserView.instances by the time save() returns, so
        # evaluate_js finds no instance and returns None immediately — no deadlock.
        if self._window is None:
            return
        native = getattr(self._window, "native", None)
        if native is not None:
            try:
                native.performSelectorOnMainThread_withObject_waitUntilDone_(
                    b"close", None, True
                )
                log.debug("Window closed via performSelectorOnMainThread (sync)")
            except Exception:
                log.exception("Sync window close failed; falling back to destroy()")
                self._window.destroy()
        else:
            self._window.destroy()

    def _handle_autostart(self, config: Config) -> None:
        if config.autostart:
            if getattr(sys, "frozen", False):
                enable_autostart(sys.executable)
            else:
                python = shutil.which("python3") or sys.executable
                enable_autostart(f"{python} -m micdot.main")
        else:
            disable_autostart()
        log.info("Autostart configured (enabled=%s)", config.autostart)


def run(config_path: Path) -> None:
    import webview  # deferred so tests never need pywebview mocked
    config = Config.load(config_path)
    api = Api(config_path)
    html = _HTML.replace("CONFIG_PLACEHOLDER", json.dumps(asdict(config)))
    window = webview.create_window(
        "MicDot Settings",
        html=html,
        js_api=api,
        width=440,
        height=580,
        resizable=False,
    )
    api.set_window(window)
    webview.start()
    sys.exit(0 if api.saved else 1)


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CONFIG_PATH
    run(path)
