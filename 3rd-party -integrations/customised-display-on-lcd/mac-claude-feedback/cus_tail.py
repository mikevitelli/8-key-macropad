#!/usr/bin/env python3
"""Live Claude -> macropad pad 1 (cus), WITHOUT Claude Code hooks.

Tails the newest transcript .jsonl in the Claude projects dir (re-detects the
active session across restarts) and mirrors it to the customised screen, in
plain language: the latest message on the main panel, the latest action on the
status line. Drains to the freshest entry each cycle (snappy, not flashy) and
only reads complete lines (robust to mid-write).
"""
import os
import glob
import json
import time

import serial

PROJ = os.path.expanduser("~/.claude/projects/-Users-mikevitelli")
PORT = "/dev/cu.usbmodem1234561"   # pad 1 = AI display

_ser = None


def _frame(o: dict) -> bytes:
    p = json.dumps(o, separators=(",", ":")).encode("utf-8")
    return b"cus" + len(p).to_bytes(2, "big") + p


def render(msg: str, status: str, color: str) -> None:
    global _ser
    try:
        if _ser is None:
            _ser = serial.Serial(PORT, 115200, timeout=0.4, write_timeout=1.0)
        _ser.write(_frame({"clear_canvas": True, "x": 0, "y": 0, "w": 480, "h": 120,
                           "text": msg[:180], "fg": "#FFFFFF", "bg": color, "align": "LEFT",
                           "long_mode": "WRAP", "border-radius": 10, "activate": True}))
        _ser.flush(); time.sleep(0.03)
        if status:
            _ser.write(_frame({"x": 0, "y": 128, "w": 480, "h": 56, "text": status[:72],
                               "fg": "#FFFFFF", "bg": "#9C1C9E", "align": "LEFT",
                               "long_mode": "WRAP", "border": 3, "border-color": "#C04FE0",
                               "border-radius": 12}))
            _ser.flush()
    except Exception:
        try:
            _ser.close()
        except Exception:
            pass
        _ser = None


def _newest():
    fs = glob.glob(PROJ + "/*.jsonl")
    return max(fs, key=os.path.getmtime) if fs else None


def _friendly(tn: str, ti: dict) -> str:
    base = os.path.basename
    if tn == "Bash":
        return ti.get("description") or ("Running: " + str(ti.get("command", ""))[:60])
    if tn == "Edit":
        return "Editing " + base(str(ti.get("file_path", "")))
    if tn == "Write":
        return "Writing " + base(str(ti.get("file_path", "")))
    if tn in ("Read", "NotebookEdit"):
        return "Reading " + base(str(ti.get("file_path", "")))
    if tn in ("Grep", "Glob"):
        return "Searching: " + str(ti.get("pattern", ""))[:40]
    if tn in ("Task", "Agent"):
        return "Subagent: " + str(ti.get("description", ""))[:44]
    if tn == "TodoWrite":
        return "Updating tasks"
    if tn == "WebFetch":
        return "Fetching a page"
    if tn == "WebSearch":
        return "Searching the web: " + str(ti.get("query", ""))[:40]
    return tn


def handle(d, st) -> bool:
    t = d.get("type"); m = d.get("message", {}) or {}; c = m.get("content")
    if t == "user" and isinstance(c, str) and c.strip() and not c.lstrip().startswith("<"):
        st.update(msg="You: " + " ".join(c.split()), color="#0E7A4B", status="thinking...")
        return True
    if t == "assistant" and isinstance(c, list):
        acted = False
        for b in c:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "text" and b.get("text", "").strip():
                st.update(msg="Claude: " + " ".join(b["text"].split()), color="#1E4FFF")
                acted = True
            elif b.get("type") == "tool_use":
                st["status"] = _friendly(b.get("name", "tool"), b.get("input", {}) or {})
                acted = True
        return acted
    return False


def main():
    cur, f = None, None
    st = {"msg": "Claude standing by", "status": "live", "color": "#333A4D"}
    render(st["msg"], st["status"], st["color"])
    changed = False
    while True:
        n = _newest()
        if n != cur:
            cur = n
            if f:
                f.close()
            f = open(cur, "r") if cur else None
            if f:
                f.seek(0, 2)  # only new activity from launch onward
        if not f:
            time.sleep(0.3); continue
        pos = f.tell()
        line = f.readline()
        if line.endswith("\n"):
            try:
                if handle(json.loads(line), st):
                    changed = True
            except Exception:
                pass
            continue  # keep draining complete lines
        f.seek(pos)               # incomplete/no line: caught up
        if changed:
            render(st["msg"], st["status"], st["color"])
            changed = False
        time.sleep(0.15)


if __name__ == "__main__":
    main()
