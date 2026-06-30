"""Run as: python -m micdot.settings_window [config_path]"""
from __future__ import annotations
import json
import shutil
import sys
import threading
import webbrowser
from dataclasses import asdict
from pathlib import Path

from micdot.autostart import enable_autostart, disable_autostart
from micdot.config import Config, DEFAULT_CONFIG_PATH
from micdot.hotkey import to_pynput_format
from micdot.log import setup as setup_logging
from micdot.version import get_version
from pynput import keyboard as _pynput_keyboard

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
h1{font-size:15px;font-weight:600;margin-bottom:12px;color:#111}
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
nav.tabs{display:flex;gap:2px;background:#e0e0e0;border-radius:8px;padding:2px;margin-bottom:16px}
.tab-btn{flex:1;padding:5px;border:none;background:transparent;font-size:12px;font-weight:500;
  color:#555;border-radius:6px;cursor:pointer}
.tab-btn.active{background:#fff;color:#111;box-shadow:0 1px 3px rgba(0,0,0,.12)}
.pane.hidden{display:none}
.link-row{display:flex;align-items:center;padding:10px 12px;border-bottom:1px solid #e5e5e5;
  text-decoration:none;color:#007aff;font-size:13px;cursor:pointer}
.link-row:last-child{border-bottom:none}
.about-app{padding:16px 12px 4px;font-size:15px;font-weight:600;color:#111}
.about-ver{padding:2px 12px 14px;font-size:12px;color:#888}
#hotkey{cursor:pointer;font-family:monospace}
</style>
</head>
<body>
<h1>MicDot</h1>
<nav class="tabs">
  <button class="tab-btn" data-tab="settings">Settings</button>
  <button class="tab-btn" data-tab="about">About</button>
</nav>
<section class="pane" id="pane-settings">
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
    <input type="text" id="hotkey" readonly placeholder="click, then press hotkey…"></div>
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
</section>
<section class="pane" id="pane-about">
<div class="group">
  <div class="about-app">MicDot</div>
  <div class="about-ver" id="about-version"></div>
</div>
<div class="lbl">LINKS</div>
<div class="group">
  <a class="link-row" href="#" data-url="https://github.com/andrecedik/micdot">GitHub Repository ↗</a>
  <a class="link-row" href="#" data-url="https://donatr.ee/andrecedik">Support me ↗</a>
</div>
</section>
<script>
var c=__MICDOT_CONFIG__;
var initialTab=__MICDOT_TAB__;
var appVersion=__MICDOT_VER__;
document.getElementById('about-version').textContent='Version '+appVersion;
var panes=document.querySelectorAll('.pane');
var tabBtns=document.querySelectorAll('.tab-btn');
function showTab(name){
  panes.forEach(function(p){p.classList.toggle('hidden',p.id!=='pane-'+name)});
  tabBtns.forEach(function(b){b.classList.toggle('active',b.dataset.tab===name)});
}
tabBtns.forEach(function(b){b.addEventListener('click',function(){showTab(b.dataset.tab)})});
showTab(initialTab);
document.querySelectorAll('[data-url]').forEach(function(el){
  el.addEventListener('click',function(e){
    e.preventDefault();
    window.pywebview.api.open_url(el.dataset.url);
  });
});
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
var hotkeyInput=document.getElementById('hotkey');
hotkeyInput.addEventListener('focus',function(){
  if(hotkeyInput.value)hotkeyInput.placeholder='press new hotkey…';
});
hotkeyInput.addEventListener('blur',function(){
  hotkeyInput.placeholder='click, then press hotkey…';
});
hotkeyInput.addEventListener('keydown',function(e){
  e.preventDefault();
  var k=e.key;
  if(k==='Control'||k==='Shift'||k==='Alt'||k==='Meta')return;
  var parts=[];
  if(e.ctrlKey)parts.push('ctrl');
  if(e.shiftKey)parts.push('shift');
  if(e.altKey)parts.push('alt');
  if(e.metaKey)parts.push('cmd');
  if(!parts.length)return;
  var name;
  if(k===' ')name='space';
  else if(k==='Enter')name='enter';
  else if(k==='Tab')name='tab';
  else if(k==='Backspace')name='backspace';
  else if(/^F\\d{1,2}$/.test(k))name=k.toLowerCase();
  else if(k.length===1)name=k.toLowerCase();
  else return;
  parts.push(name);
  hotkeyInput.value=parts.join('+');
});
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


def _build_html(config: Config, initial_tab: str, version: str) -> str:
    html = _HTML.replace("__MICDOT_CONFIG__", json.dumps(asdict(config)))
    html = html.replace("__MICDOT_TAB__", json.dumps(initial_tab))
    html = html.replace("__MICDOT_VER__", json.dumps(version))
    return html


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
        hotkey_str = str(data["hotkey"])
        _parts = hotkey_str.split("+")
        if len(_parts) < 2 or not any(p.lower() in {"ctrl", "shift", "alt", "cmd"} for p in _parts[:-1]):
            raise ValueError(f"Hotkey must include at least one modifier: {hotkey_str!r}")
        try:
            _pynput_keyboard.HotKey.parse(to_pynput_format(hotkey_str))
        except Exception as exc:
            raise ValueError(f"Invalid hotkey: {hotkey_str!r}") from exc
        new = Config(
            mqtt_host=str(data["mqtt_host"]),
            mqtt_port=int(data["mqtt_port"]),
            mqtt_username=str(data["mqtt_username"]),
            mqtt_password=str(data["mqtt_password"]),
            hotkey=hotkey_str,
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

    def open_url(self, url: str) -> None:
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            log.warning("Refusing to open non-http(s) URL: %r", url)
            return
        log.info("Opening external URL %s", url)
        webbrowser.open(url)


def run(config_path: Path, initial_tab: str = "settings") -> None:
    import webview  # deferred so tests never need pywebview mocked
    if initial_tab not in {"settings", "about"}:
        initial_tab = "settings"
    config = Config.load(config_path)
    api = Api(config_path)
    html = _build_html(config, initial_tab, get_version())
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
    argv = sys.argv[1:]
    tab = "settings"
    if "--tab" in argv:
        i = argv.index("--tab")
        if i + 1 < len(argv):
            tab = argv[i + 1]
            del argv[i:i + 2]
    path = Path(argv[0]) if argv else DEFAULT_CONFIG_PATH
    run(path, initial_tab=tab)
