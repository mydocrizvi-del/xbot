"""Shared settings for tweetytweets.

Everything install-specific lives in config.json (git-ignored). Scripts never
hardcode a handle, a path, or a character limit: they read it from here, or fall
back to a sane default that works on a fresh machine.

`config.example.json` is the template that ships with the repo; the onboarding
step copies it to config.json and fills in the answers from the interview.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent          # repo root
CONFIG_PATH = ROOT / "config.json"
EXAMPLE_PATH = ROOT / "config.example.json"

DEFAULTS: dict[str, Any] = {
    "handle": "",                       # set during onboarding
    "premium": False,                   # False => the 280-character ceiling applies
    "max_chars": 280,
    "timezone": "local",                # e.g. "Asia/Kolkata"; "local" = machine tz
    "slots": ["13:00", "16:00", "20:00", "00:00"],
    "jitter_minutes": 45,
    "min_gap_hours": 3,
    "ai_update_slot": "16:00",
    "ai_update_header": "Daily AI updates | Day {day}",
    "ai_update_enabled": True,
    "research_hour": 11,
    "window_hours": 36,
    "subreddits": ["LocalLLaMA", "artificial", "singularity", "ChatGPTCoding",
                   "n8n", "SideProject"],
    "x_queries": ["AI agents", "AI coding", "open source LLM", "developer tools"],
    "feeds": {
        "techcrunch-ai": "https://techcrunch.com/category/artificial-intelligence/feed/",
        "arxiv-cs-ai": "https://export.arxiv.org/rss/cs.AI",
    },
    "require_verified_source": True,    # refuse to write claims it hasn't read
    "browser": {
        "port": 9222,
        "profile_dir": "",              # empty => <home>/.tweetytweets/chrome-profile
        "chrome_path": "",              # empty => auto-detect
        "headless": False,
    },
}


def _merged(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merged(out[k], v)
        else:
            out[k] = v
    return out


def load(required: bool = False) -> dict:
    """Merged config. With required=True, exits with guidance if missing."""
    if not CONFIG_PATH.exists():
        if required:
            print(json.dumps({
                "error": "config.json not found",
                "fix": f"cp {EXAMPLE_PATH.name} config.json  — then run the onboarding interview",
                "docs": "see README.md > Setup",
            }, indent=2), file=sys.stderr)
            raise SystemExit(2)
        return dict(DEFAULTS)
    try:
        user = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as err:
        raise SystemExit(f"config.json is not valid JSON: {err}")
    return _merged(DEFAULTS, user)


def home() -> Path:
    return Path(os.path.expanduser("~"))


def profile_dir(cfg: dict | None = None) -> Path:
    cfg = cfg or load()
    raw = (cfg.get("browser") or {}).get("profile_dir") or ""
    p = Path(os.path.expanduser(raw)) if raw else home() / ".tweetytweets" / "chrome-profile"
    p.mkdir(parents=True, exist_ok=True)
    return p


def find_chrome(explicit: str = "") -> Path | None:
    """Locate a Chrome/Chromium binary on the three desktop platforms."""
    import shutil

    if explicit:
        p = Path(os.path.expanduser(explicit))
        return p if p.exists() else None

    candidates: list[str] = []
    if sys.platform.startswith("win"):
        for base in (os.environ.get("PROGRAMFILES", r"C:\Program Files"),
                     os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
                     os.environ.get("LOCALAPPDATA", "")):
            if base:
                candidates.append(os.path.join(base, "Google", "Chrome", "Application", "chrome.exe"))
                candidates.append(os.path.join(base, "Chromium", "Application", "chrome.exe"))
        candidates += [
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        ]
    elif sys.platform == "darwin":
        candidates += [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        ]
    else:
        for name in ("google-chrome", "google-chrome-stable", "chromium",
                     "chromium-browser", "microsoft-edge"):
            found = shutil.which(name)
            if found:
                candidates.append(found)

    for c in candidates:
        if c and Path(c).exists():
            return Path(c)
    return None


def state_path() -> Path:
    return ROOT / "state.json"


def data_dir(name: str) -> Path:
    p = ROOT / name
    p.mkdir(parents=True, exist_ok=True)
    return p


def tzinfo():
    """The timezone slots are interpreted in."""
    from datetime import datetime, timedelta, timezone
    name = (load().get("timezone") or "local")
    if name and name.lower() != "local":
        try:
            from zoneinfo import ZoneInfo
            return ZoneInfo(name)
        except Exception:
            pass
    return datetime.now().astimezone().tzinfo or timezone(timedelta(0))
