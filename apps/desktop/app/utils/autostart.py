"""Start-at-login via a macOS LaunchAgent (best-effort; intended for the packaged app)."""

from __future__ import annotations

import sys
from pathlib import Path

from app.utils.resources import resource_path

_LABEL = "com.sway.Sway"
_PLIST = Path("~/Library/LaunchAgents").expanduser() / f"{_LABEL}.plist"


def is_supported() -> bool:
    return sys.platform == "darwin"


def _program_arguments() -> list[str]:
    if getattr(sys, "frozen", False):
        # Packaged: relaunch the .app bundle that contains this executable.
        exe = Path(sys.executable)
        app_bundle = next((p for p in exe.parents if p.suffix == ".app"), None)
        if app_bundle is not None:
            return ["/usr/bin/open", str(app_bundle)]
        return [str(exe)]
    # Dev: run `python main.py` from the desktop app root.
    main_py = resource_path("main.py")
    return [sys.executable, str(main_py)]


def is_enabled() -> bool:
    return _PLIST.exists()


def set_enabled(enabled: bool) -> None:
    if not is_supported():
        return
    if enabled:
        _PLIST.parent.mkdir(parents=True, exist_ok=True)
        args = "".join(f"        <string>{a}</string>\n" for a in _program_arguments())
        _PLIST.write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
            '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
            '<plist version="1.0">\n'
            "<dict>\n"
            f"    <key>Label</key>\n    <string>{_LABEL}</string>\n"
            "    <key>ProgramArguments</key>\n"
            f"    <array>\n{args}    </array>\n"
            "    <key>RunAtLoad</key>\n    <true/>\n"
            "</dict>\n"
            "</plist>\n"
        )
    elif _PLIST.exists():
        _PLIST.unlink()
