#!/usr/bin/env python3
"""Human approval queue for XBot drafts.

This module adds a safety/control plane around the existing scheduler:
  python scripts/review.py list
  python scripts/review.py approve --slot 16:00
  python scripts/review.py reject --slot 20:00 --reason "Needs a source"
  python scripts/review.py inspect --slot 16:00
  python scripts/review.py check-duplicates --text-file draft.txt

Approval is deliberately separate from publishing. In manual mode, the scheduler
will not consider a filled slot due until it has been approved.
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
from datetime import datetime
from pathlib import Path

import settings

ROOT = Path(__file__).resolve().parent.parent
PLANS = ROOT / "drafts"
STATE = ROOT / "state.json"


def now() -> str:
    return datetime.now().astimezone().isoformat()


def load_plan(date: str | None = None) -> tuple[Path, dict]:
    if date:
        path = PLANS / f"{date}.json"
        if not path.exists():
            raise SystemExit(f"no plan for {date}")
        return path, json.loads(path.read_text(encoding="utf-8"))

    today = datetime.now(settings.tzinfo()).strftime("%Y-%m-%d")
    path = PLANS / f"{today}.json"
    if not path.exists():
        raise SystemExit(f"no plan for {today}; run due.py make-plan first")
    return path, json.loads(path.read_text(encoding="utf-8"))


def find_slot(plan: dict, slot_name: str) -> dict:
    for slot in plan.get("slots", []):
        if slot.get("slot") == slot_name:
            return slot
    raise SystemExit(f"slot {slot_name} not found in plan")


def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"posts": []}


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip()).lower()


def recent_texts(limit: int = 50) -> list[str]:
    state = load_state()
    out = []
    for post in reversed(state.get("posts", [])):
        text = post.get("text")
        if text:
            out.append(normalize(text))
        if len(out) >= limit:
            break
    return out


def similarity_report(text: str, threshold: float = 0.90) -> list[dict]:
    candidate = normalize(text)
    matches = []
    for idx, old in enumerate(recent_texts(), 1):
        ratio = difflib.SequenceMatcher(None, candidate, old).ratio()
        if ratio >= threshold:
            matches.append({"recent_rank": idx, "similarity": round(ratio, 3)})
    return matches


def save(path: Path, plan: dict) -> None:
    path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")


def list_queue(date: str | None) -> None:
    path, plan = load_plan(date)
    print(f"# {path.name}  handle=@{str(plan.get('handle') or '').lstrip('@')}")
    for slot in plan.get("slots", []):
        if slot.get("posted"):
            status = "POSTED"
        elif slot.get("skipped"):
            status = "SKIPPED"
        elif not (slot.get("text") or "").strip():
            status = "EMPTY"
        elif slot.get("approved"):
            status = "APPROVED"
        else:
            status = "PENDING"
        print(
            f"{slot.get('slot','?'):>5}  {slot.get('kind','value'):<9} "
            f"{status:<9} due={str(slot.get('due_at',''))[11:16]}"
        )


def inspect(date: str | None, slot_name: str) -> None:
    _, plan = load_plan(date)
    slot = find_slot(plan, slot_name)
    print(json.dumps(slot, indent=2, ensure_ascii=False))


def mutate(date: str | None, slot_name: str, approved: bool, reason: str = "") -> None:
    path, plan = load_plan(date)
    slot = find_slot(plan, slot_name)
    text = (slot.get("text") or "").strip()
    if not text and approved:
        raise SystemExit("cannot approve an empty draft")

    matches = similarity_report(text) if approved else []
    if approved and matches:
        print(json.dumps({
            "warning": "draft is highly similar to a recent published post",
            "matches": matches,
            "action": "approval continues; review the draft before publishing",
        }, indent=2))

    slot["approved"] = approved
    slot["reviewed_at"] = now()
    slot["review_reason"] = reason.strip() or None
    save(path, plan)
    print(json.dumps({
        "date": plan.get("date"),
        "slot": slot_name,
        "approved": approved,
        "reviewed_at": slot["reviewed_at"],
        "reason": slot["review_reason"],
        "similarity_matches": matches,
    }, indent=2, ensure_ascii=False))


def check_duplicates(text: str) -> None:
    matches = similarity_report(text)
    print(json.dumps({
        "matches": matches,
        "safe_to_review": not bool(matches),
        "threshold": 0.90,
    }, indent=2))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cmd", choices=["list", "inspect", "approve", "reject", "check-duplicates"])
    ap.add_argument("--date", default=None)
    ap.add_argument("--slot", default=None)
    ap.add_argument("--text", default=None)
    ap.add_argument("--text-file", default=None)
    ap.add_argument("--reason", default="")
    a = ap.parse_args()

    if a.cmd == "list":
        list_queue(a.date)
        return
    if a.cmd == "inspect":
        if not a.slot:
            raise SystemExit("--slot required")
        inspect(a.date, a.slot)
        return
    if a.cmd in ("approve", "reject"):
        if not a.slot:
            raise SystemExit("--slot required")
        mutate(a.date, a.slot, approved=a.cmd == "approve", reason=a.reason)
        return
    text = a.text
    if a.text_file:
        text = Path(a.text_file).read_text(encoding="utf-8")
    if not text:
        raise SystemExit("--text or --text-file required")
    check_duplicates(text)


if __name__ == "__main__":
    main()
