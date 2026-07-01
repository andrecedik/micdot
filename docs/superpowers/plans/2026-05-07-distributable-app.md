# Distributable .app Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Package MicDot as a standalone macOS `.app` built via PyInstaller, with a GitHub Actions CI that publishes `.app.zip` files for Apple Silicon and Intel on version tags.

**Architecture:** PyInstaller bundles `micdot/main.py` into a single `.app` bundle. Since the settings window is launched as a subprocess — and in the frozen app there's no standalone `python` — `main.py` gains a `--settings` flag that the bundled executable uses to dispatch into `settings_window.run()`. GitHub Actions builds both architectures in parallel and uploads both zips to a GitHub Release.

**Tech Stack:** PyInstaller 6.x, GitHub Actions (macos-14 for arm64, macos-13 for x86_64), `softprops/action-gh-release@v2`, `actions/upload-artifact@v4` / `actions/download-artifact@v4`.

---

### Task 1: Extract `_settings_cmd()` helper and add frozen dispatch to `main.py`

**Files:**
- Modify: `micdot/main.py`
- Test: `tests/test_main_frozen.py` (create)

The settings subprocess is currently launched with `[sys.executable, "-m", "micdot.settings_window", ...]`. In the frozen `.app`, `sys.executable` is `MicDot.app/Contents/MacOS/MicDot` — there is no `-m` support. Instead the frozen executable must be invoked with `--settings <path>`, and `main()` must detect this flag and branch to the settings window.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_main_frozen.py`:

```python
import sys
import pytest
from pathlib import Path
from unittest.mock import patch


def test_settings_cmd_returns_module_mode_when_not_frozen():
    from micdot.main import _settings_cmd
    cmd = _settings_cmd(Path("/cfg/config.json"))
    assert cmd == [sys.executable, "-m", "micdot.settings_window", "/cfg/config.json"]


def test_settings_cmd_returns_flag_mode_when_frozen():
    from micdot.main import _settings_cmd
    with patch.object(sys, "frozen", True, create=True), \
         patch.object(sys, "executable", "/App/MicDot.app/Contents/MacOS/MicDot"):
        cmd = _settings_cmd(Path("/cfg/config.json"))
    assert cmd == ["/App/MicDot.app/Contents/MacOS/MicDot", "--settings", "/cfg/config.json"]


def test_main_dispatches_to_settings_when_frozen_with_flag(tmp_path, mocker):
    cfg_path = tmp_path / "config.json"
    mocker.patch.object(sys, "frozen", True, create=True)
    mocker.patch.object(sys, "argv", ["micdot", "--settings", str(cfg_path)])
    mock_run = mocker.patch("micdot.settings_window.run")

    from micdot.main import main
    main()

    mock_run.assert_called_once_with(cfg_path)


def test_main_uses_default_config_path_when_no_path_arg(mocker):
    from micdot.config import DEFAULT_CONFIG_PATH
    mocker.patch.object(sys, "frozen", True, create=True)
    mocker.patch.object(sys, "argv", ["micdot", "--settings"])
    mock_run = mocker.patch("micdot.settings_window.run")

    from micdot.main import main
    main()

    mock_run.assert_called_once_with(DEFAULT_CONFIG_PATH)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/andre.cedik/devel/p/repositories/espmuter
pytest tests/test_main_frozen.py -v
```

Expected: 4 failures — `_settings_cmd` not defined, frozen dispatch not implemented.

- [ ] **Step 3: Implement `_settings_cmd` and frozen dispatch in `main.py`**

Add `_settings_cmd` just above the `main()` function, and add the dispatch block at the top of `main()`:

```python
def _settings_cmd(config_path: Path) -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, "--settings", str(config_path)]
    return [sys.executable, "-m", "micdot.settings_window", str(config_path)]


def main() -> None:
    if getattr(sys, "frozen", False) and "--settings" in sys.argv:
        idx = sys.argv.index("--settings")
        path = Path(sys.argv[idx + 1]) if idx + 1 < len(sys.argv) else DEFAULT_CONFIG_PATH
        from micdot.settings_window import run as run_settings
        run_settings(path)
        return

    config = Config.load(DEFAULT_CONFIG_PATH)
    # ... rest of main unchanged
```

Also update `open_settings()` inside `main()` to use `_settings_cmd`:

```python
    def open_settings() -> None:
        if settings_proc[0] is not None and settings_proc[0].poll() is None:
            return
        settings_proc[0] = subprocess.Popen(
            _settings_cmd(DEFAULT_CONFIG_PATH)
        )
        # ... rest unchanged
```

Remove the old hardcoded `[sys.executable, "-m", "micdot.settings_window", str(DEFAULT_CONFIG_PATH)]` line.

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_main_frozen.py -v
```

Expected: 4 PASS.

- [ ] **Step 5: Run full test suite**

```bash
pytest -v
```

Expected: all 43 + 4 = 47 tests pass.

- [ ] **Step 6: Commit**

```bash
git add micdot/main.py tests/test_main_frozen.py
git commit -m "feat: add frozen-app dispatch for settings window subprocess"
```

---

### Task 2: Frozen-app autostart path in `settings_window.py`

**Files:**
- Modify: `micdot/settings_window.py:137-162` (`Api.save`)
- Test: `tests/test_settings_window.py` (add two tests)

When frozen, `sys.executable` is the `.app` binary. The LaunchAgent must point at that binary, not `python3 -m micdot.main`.

- [ ] **Step 1: Write the failing tests**

Add to the bottom of `tests/test_settings_window.py`:

```python
import sys


def test_save_enables_autostart_with_executable_when_frozen(api, mocker):
    mocker.patch.object(sys, "frozen", True, create=True)
    fake_exe = "/Applications/MicDot.app/Contents/MacOS/MicDot"
    mocker.patch.object(sys, "executable", fake_exe)
    enable = mocker.patch("micdot.settings_window.enable_autostart")
    mocker.patch("micdot.settings_window.disable_autostart")

    api.save({**_DATA, "autostart": True})

    enable.assert_called_once_with(fake_exe)


def test_save_enables_autostart_with_python_command_when_not_frozen(api, mocker):
    mocker.patch.object(sys, "frozen", False, create=True)
    mocker.patch("micdot.settings_window.shutil")
    mocker.patch("micdot.settings_window.shutil.which", return_value="/usr/bin/python3")
    enable = mocker.patch("micdot.settings_window.enable_autostart")
    mocker.patch("micdot.settings_window.disable_autostart")

    api.save({**_DATA, "autostart": True})

    args = enable.call_args[0][0]
    assert "-m" in args and "micdot.main" in args
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_settings_window.py::test_save_enables_autostart_with_executable_when_frozen tests/test_settings_window.py::test_save_enables_autostart_with_python_command_when_not_frozen -v
```

Expected: both FAIL.

- [ ] **Step 3: Update `Api.save` in `settings_window.py`**

Replace the autostart block in `Api.save()`:

```python
        if new.autostart:
            if getattr(sys, "frozen", False):
                enable_autostart(sys.executable)
            else:
                python = shutil.which("python3") or sys.executable
                enable_autostart(f"{python} -m micdot.main")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_settings_window.py -v
```

Expected: all 7 tests pass.

- [ ] **Step 5: Run full test suite**

```bash
pytest -v
```

Expected: all 49 tests pass.

- [ ] **Step 6: Commit**

```bash
git add micdot/settings_window.py tests/test_settings_window.py
git commit -m "feat: use app executable for LaunchAgent when running as frozen .app"
```

---

### Task 3: Add `build` extra to `pyproject.toml`

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add the `build` optional dependency group**

In `pyproject.toml`, add after the `dev` group:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-mock>=3.12.0",
]
build = [
    "pyinstaller>=6.0",
]
```

- [ ] **Step 2: Verify syntax**

```bash
python -c "import tomllib; tomllib.load(open('pyproject.toml','rb'))" && echo "OK"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add build extra with pyinstaller dependency"
```

---

### Task 4: Create `MicDot.spec`

**Files:**
- Create: `MicDot.spec`

PyInstaller reads this spec to bundle the app. Key requirements:
- Entry point: `micdot/main.py`
- Hidden imports for dynamically loaded backends: pystray macOS, pynput macOS, pywebview cocoa
- `LSUIElement = True` in Info.plist so the app hides from the Dock (same as the programmatic `_hide_dock_icon()` call)
- `CFBundleIdentifier = com.micdot.app`
- No data files needed — the settings HTML is embedded in Python

- [ ] **Step 1: Install PyInstaller locally**

```bash
pip install "pyinstaller>=6.0"
```

- [ ] **Step 2: Create `MicDot.spec`**

```python
# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

webview_datas, webview_binaries, webview_hiddenimports = collect_all("webview")

a = Analysis(
    ["micdot/main.py"],
    pathex=[],
    binaries=webview_binaries,
    datas=webview_datas,
    hiddenimports=[
        *webview_hiddenimports,
        "pystray._darwin",
        "pynput.keyboard._darwin",
        "pynput.mouse._darwin",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MicDot",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="MicDot",
)
app = BUNDLE(
    coll,
    name="MicDot.app",
    icon=None,
    bundle_identifier="com.micdot.app",
    info_plist={
        "CFBundleName": "MicDot",
        "CFBundleDisplayName": "MicDot",
        "CFBundleVersion": "0.1.0",
        "CFBundleShortVersionString": "0.1.0",
        "LSUIElement": True,
        "NSAccessibilityUsageDescription": (
            "MicDot listens for the global mute hotkey."
        ),
    },
)
```

- [ ] **Step 3: Run a local build to verify the spec works**

```bash
pyinstaller MicDot.spec --noconfirm
```

Expected: `dist/MicDot.app` is created without errors. It may emit warnings about missing hidden imports — add any flagged ones to `hiddenimports` in the spec.

- [ ] **Step 4: Smoke-test the built app**

```bash
open dist/MicDot.app
```

Expected: MicDot icon appears in the menu bar, tray menu shows Toggle Mute / Settings / Quit.

- [ ] **Step 5: Test the settings window via the frozen binary**

```bash
dist/MicDot.app/Contents/MacOS/MicDot --settings ~/.config/micdot/config.json
```

Expected: The settings window opens. Saving it writes the config file and the process exits 0.

- [ ] **Step 6: Commit**

```bash
git add MicDot.spec
git commit -m "feat: add PyInstaller spec for macOS .app bundle"
```

---

### Task 5: Create GitHub Actions build workflow

**Files:**
- Create: `.github/workflows/build.yml`

Triggers on `v*` tags (e.g., `v0.1.0`). Builds on both `macos-14` (Apple Silicon / arm64) and `macos-13` (Intel / x86_64). Each job produces a `MicDot-<version>-<arch>.app.zip` and uploads it to a GitHub Release.

- [ ] **Step 1: Create `.github/workflows/` directory if needed**

```bash
mkdir -p .github/workflows
```

- [ ] **Step 2: Create `.github/workflows/build.yml`**

```yaml
name: Build

on:
  push:
    tags:
      - 'v*'

permissions:
  contents: write

jobs:
  build:
    name: Build (${{ matrix.arch }})
    strategy:
      fail-fast: false
      matrix:
        include:
          - os: macos-14
            arch: arm64
          - os: macos-13
            arch: x86_64
    runs-on: ${{ matrix.os }}

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install -e ".[build]"

      - name: Build app
        run: |
          pyinstaller MicDot.spec --noconfirm

      - name: Create zip
        run: |
          VERSION="${GITHUB_REF_NAME}"
          ZIPNAME="MicDot-${VERSION}-${{ matrix.arch }}.app.zip"
          cd dist
          zip -r "../${ZIPNAME}" MicDot.app
          echo "ZIPNAME=${ZIPNAME}" >> "$GITHUB_ENV"

      - name: Upload to GitHub Release
        uses: softprops/action-gh-release@v2
        with:
          files: ${{ env.ZIPNAME }}
          draft: false
          prerelease: false
```

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/build.yml
git commit -m "ci: add GitHub Actions workflow to build and publish macOS .app on tags"
```

---

### Task 6: Update README with download & install section

**Files:**
- Modify: `README.md`

Add a "Download & Install" section near the top (right after "Features", before "Software Setup") so users who just want the app don't need to wade through Python setup instructions.

- [ ] **Step 1: Add download section to `README.md`**

Insert the following block after the "Features" section and before "## Software Setup":

```markdown
## Download & Install (no Python required)

Pre-built binaries are available on the [Releases page](https://github.com/andrecedik/micdot/releases).

1. Download `MicDot-<version>-arm64.app.zip` (Apple Silicon) or `MicDot-<version>-x86_64.app.zip` (Intel).
2. Unzip and move `MicDot.app` to `/Applications`.
3. **First launch:** right-click `MicDot.app` → **Open** → click **Open** in the dialog. This is a one-time step to bypass Gatekeeper for unsigned apps.
4. MicDot will appear in your menu bar.

> **Note:** If you move the app after enabling "Launch at Login", re-enable it in Settings so the LaunchAgent path updates.
```

- [ ] **Step 2: Verify the README renders correctly**

```bash
cat README.md | head -60
```

Check that the new section appears in the right place.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add download and install section for pre-built .app"
```

---

### Task 7: Tag and trigger a release

- [ ] **Step 1: Verify all tests pass**

```bash
pytest -v
```

Expected: all tests pass.

- [ ] **Step 2: Tag version 0.1.0**

```bash
git tag v0.1.0
git push origin main --tags
```

- [ ] **Step 3: Monitor the GitHub Actions run**

Go to `https://github.com/andrecedik/micdot/actions` and watch the "Build" workflow. Both matrix jobs (arm64, x86_64) should succeed and the release at `https://github.com/andrecedik/micdot/releases/tag/v0.1.0` should contain two `.app.zip` files.

---

## Self-Review

**Spec coverage:**
- ✅ PyInstaller spec → Task 4
- ✅ GitHub Actions CI on version tags → Task 5
- ✅ Apple Silicon (arm64) build → Task 5 matrix
- ✅ Intel (x86_64) build → Task 5 matrix
- ✅ Publish `.app.zip` on tags → Task 5
- ✅ Settings window subprocess in frozen app → Tasks 1 & 2
- ✅ Autostart LaunchAgent path when frozen → Task 2
- ✅ User-facing install docs → Task 6

**Placeholder scan:** No TBD, TODO, or incomplete steps.

**Type consistency:** `_settings_cmd` returns `list[str]` throughout. `enable_autostart` still accepts `str` — callers pass `sys.executable` (a `str`) or `f"{python} -m micdot.main"` (a `str`). Consistent.
