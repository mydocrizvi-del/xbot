#!/usr/bin/env python3
"""Single entry point for the XBot control plane.

Examples:
  python xbot.py validate
  python xbot.py plan
  python xbot.py review
  python xbot.py dashboard
  python xbot.py status
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRIPTS = ROOT / "scripts"


def run(script: str, *args: str) -> int:
    cmd = [sys.executable, str(SCRIPTS / script), *args]
    return subprocess.call(cmd, cwd=ROOT)


def status() -> None:
    state = ROOT / "state.json"
    plans = ROOT / "drafts"
    posts = 0
    if state.exists():
        try:
            posts = len(json.loads(state.read_text(encoding="utf-8")).get("posts", []))
        except Exception:
            posts = -1
    plan_count = len(list(plans.glob("*.json"))) if plans.exists() else 0
    print(json.dumps({
        "repo": "xbot",
        "posts_recorded": posts,
        "plans_on_disk": plan_count,
        "root": str(ROOT),
    }, indent=2))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "command",
        choices=["validate", "plan", "review", "dashboard", "status"],
        help="control-plane command",
    )
    ap.add_argument("--date", default=None)
    ns = ap.parse_args()

    if ns.command == "validate":
        raise SystemExit(run("validate_config.py"))
    if ns.command == "plan":
        args = ["make-plan"]
        if ns.date:
            args += ["--date", ns.date]
        raise SystemExit(run("due.py", *args))
    if ns.command == "review":
        raise SystemExit(run("review.py", "list", *([ "--date", ns.date] if ns.date else [])))
    if ns.command == "dashboard":
        raise SystemExit(run("dashboard.py"))
    status()


if __name__ == "__main__":
    main()
