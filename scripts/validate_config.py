#!/usr/bin/env python3
"""Validate XBot configuration before a deployment.

No network calls are made. The goal is to catch dangerous or confusing
configuration before the scheduler is started.
"""
from __future__ import annotations

import json
from pathlib import Path

import settings


def fail(msg: str) -> None:
    raise SystemExit(json.dumps({"ok": False, "error": msg}, indent=2))


def main() -> None:
    cfg = settings.load(required=True)
    errors: list[str] = []

    handle = str(cfg.get("handle") or "").strip().lstrip("@")
    if not handle or handle == "yourhandle_without_the_at":
        errors.append("set a real X handle in config.json")
    elif not all(ch.isalnum() or ch == "_" for ch in handle) or len(handle) > 20:
        errors.append("handle must be 1-20 characters using letters, digits, or underscore")

    limit = int(cfg.get("max_chars") or 280)
    if limit < 1 or limit > 10000:
        errors.append("max_chars must be between 1 and 10000")

    mode = str(cfg.get("approval_mode") or "manual").lower()
    if mode not in {"manual", "auto"}:
        errors.append("approval_mode must be 'manual' or 'auto'")

    slots = cfg.get("slots") or []
    if not slots:
        errors.append("slots must contain at least one HH:MM anchor")
    for slot in slots:
        try:
            hh, mm = map(int, str(slot).split(":"))
            if not (0 <= hh <= 23 and 0 <= mm <= 59):
                raise ValueError
        except Exception:
            errors.append(f"invalid slot: {slot!r}")

    if float(cfg.get("min_gap_hours", 0)) < 0:
        errors.append("min_gap_hours cannot be negative")
    if int(cfg.get("jitter_minutes", 0)) < 0:
        errors.append("jitter_minutes cannot be negative")

    feeds = cfg.get("feeds") or {}
    for name, url in feeds.items():
        if not str(url).startswith(("https://", "http://")):
            errors.append(f"feed {name!r} must be an http(s) URL")

    browser_cfg = cfg.get("browser") or {}
    port = int(browser_cfg.get("port", 9222))
    if not (1 <= port <= 65535):
        errors.append("browser.port must be between 1 and 65535")

    if errors:
        print(json.dumps({"ok": False, "errors": errors}, indent=2))
        raise SystemExit(2)

    print(json.dumps({
        "ok": True,
        "handle": f"@{handle}",
        "approval_mode": mode,
        "max_chars": limit,
        "slots": slots,
        "timezone": cfg.get("timezone"),
        "browser_port": port,
    }, indent=2))


if __name__ == "__main__":
    main()
