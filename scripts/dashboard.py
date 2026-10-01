#!/usr/bin/env python3
"""Tiny dependency-free local XBot control dashboard.

Run:
  python scripts/dashboard.py

Then open http://127.0.0.1:8787 in the same machine.
The dashboard can inspect and approve/reject drafts. It does not publish posts.
"""
from __future__ import annotations

import html
import json
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import settings

ROOT = Path(__file__).resolve().parent.parent
PLANS = ROOT / "drafts"
STATE = ROOT / "state.json"
HOST = "127.0.0.1"
PORT = 8787


def read_json(path: Path, fallback):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def today_plan() -> dict:
    date = __import__("datetime").datetime.now(settings.tzinfo()).strftime("%Y-%m-%d")
    return read_json(PLANS / f"{date}.json", {"date": date, "slots": []})


def state() -> dict:
    return read_json(STATE, {"posts": []})


def mutate_slot(slot_name: str, approved: bool) -> bool:
    plan = today_plan()
    changed = False
    for slot in plan.get("slots", []):
        if slot.get("slot") == slot_name:
            if approved and not (slot.get("text") or "").strip():
                return False
            slot["approved"] = approved
            slot["reviewed_at"] = __import__("datetime").datetime.now().astimezone().isoformat()
            slot["review_reason"] = None
            changed = True
            break
    if changed:
        PLANS.mkdir(parents=True, exist_ok=True)
        (PLANS / f"{plan['date']}.json").write_text(
            json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    return changed


def page() -> str:
    plan = today_plan()
    st = state()
    handle = html.escape(str(plan.get("handle") or settings.load().get("handle") or "").lstrip("@"))
    rows = []
    for slot in plan.get("slots", []):
        text = html.escape(slot.get("text") or "")
        if slot.get("posted"):
            status = "POSTED"
        elif slot.get("skipped"):
            status = "SKIPPED"
        elif not (slot.get("text") or "").strip():
            status = "EMPTY"
        elif slot.get("approved"):
            status = "APPROVED"
        else:
            status = "PENDING REVIEW"
        actions = ""
        if not slot.get("posted") and slot.get("text"):
            actions = (
                f'<form method="post" style="display:inline"><input type="hidden" name="slot" value="{html.escape(slot.get("slot",""))}">'
                f'<button name="action" value="approve">Approve</button></form> '
                f'<form method="post" style="display:inline"><input type="hidden" name="slot" value="{html.escape(slot.get("slot",""))}">'
                f'<button name="action" value="reject">Reject</button></form>'
            )
        rows.append(
            f"<tr><td>{html.escape(slot.get('slot',''))}</td>"
            f"<td>{html.escape(slot.get('kind','value'))}</td>"
            f"<td>{html.escape(str(slot.get('due_at',''))[11:16])}</td>"
            f"<td>{status}</td><td><pre>{text}</pre>{actions}</td></tr>"
        )
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>XBot Dashboard</title>
<style>
body{{font-family:system-ui,-apple-system,sans-serif;margin:24px;background:#f7f7f8;color:#171717}}
main{{max-width:1100px;margin:auto}} table{{width:100%;border-collapse:collapse;background:#fff}}
th,td{{padding:12px;border-bottom:1px solid #ddd;vertical-align:top;text-align:left}}
pre{{white-space:pre-wrap;word-break:break-word;margin:0 0 12px;font-family:inherit}}
button{{padding:7px 12px;border:1px solid #aaa;border-radius:8px;background:#fff;cursor:pointer}}
.card{{display:inline-block;background:#fff;padding:14px 18px;border:1px solid #ddd;border-radius:10px;margin:0 8px 12px 0}}
small{{color:#666}}
</style></head><body><main>
<h1>XBot</h1><p>Account: <strong>@{handle or 'not configured'}</strong> · date: {html.escape(plan.get('date',''))}</p>
<div class="card"><strong>{len(plan.get('slots',[]))}</strong><br><small>slots</small></div>
<div class="card"><strong>{sum(1 for s in plan.get('slots',[]) if s.get('approved'))}</strong><br><small>approved</small></div>
<div class="card"><strong>{len(st.get('posts',[]))}</strong><br><small>recorded posts</small></div>
<table><thead><tr><th>Slot</th><th>Type</th><th>Due</th><th>Status</th><th>Draft / Review</th></tr></thead>
<tbody>{''.join(rows) or '<tr><td colspan="5">No plan for today.</td></tr>'}</tbody></table>
<p><small>This dashboard manages review state only. Publishing remains a separate, explicit action.</small></p>
</main></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def _send(self, body: str, status: int = 200):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.split("?", 1)[0] == "/":
            self._send(page())
        else:
            self._send("Not found", 404)

    def do_POST(self):
        if self.path != "/":
            self._send("Not found", 404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        form = urllib.parse.parse_qs(body)
        slot = (form.get("slot") or [""])[0]
        action = (form.get("action") or [""])[0]
        ok = mutate_slot(slot, action == "approve")
        self.send_response(303 if ok else 400)
        self.send_header("Location", "/")
        self.end_headers()


if __name__ == "__main__":
    print(f"XBot dashboard: http://{HOST}:{PORT}")
    print("Review state only; no publishing endpoint is exposed.")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
