#!/usr/bin/env python3
"""Render a Claude-activity panel to macropad pad 1 via the cus protocol.

Clear-then-redraw (clear_canvas on the first panel) so panels never stack/ghost.
Layout: a main message panel (top) + a status line (below). Bottom 120px is the
AI key strip (Profile 5). Exception-safe: never raises, so it can't break a caller.

Usage: cus_status.py "<message>" ["<status>"] ["#RRGGBB main-bg"]
"""
import sys
import json
import time
import fcntl
import os

PORT = "/dev/cu.usbmodem1234561"   # pad 1 = the AI display
BAUD = 115200
LOCK = "/tmp/cus_status.lock"      # one writer at a time; see render()


def _frame(o: dict) -> bytes:
    p = json.dumps(o, separators=(",", ":")).encode("utf-8")
    return b"cus" + len(p).to_bytes(2, "big") + p


def render(msg: str, status: str = "", color: str = "#1E4FFF") -> None:
    lock = None
    try:
        import serial
        # Claude fires this per tool call and tool calls run in parallel, so
        # several detached copies race for one CDC port. Take an exclusive lock
        # first; if another render is mid-write, drop this frame rather than
        # queue (the pad only ever shows the latest state anyway).
        lock = open(LOCK, "w")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return
        s = serial.Serial(PORT, BAUD, timeout=0.4, write_timeout=1.0)
        time.sleep(0.05)
        s.write(_frame({
            "clear_canvas": True, "x": 0, "y": 0, "w": 480, "h": 118,
            "text": msg[:200], "fg": "#FFFFFF", "bg": color, "align": "LEFT",
            "long_mode": "WRAP", "border-radius": 10, "activate": True,
        }))
        s.flush(); time.sleep(0.05)
        if status:
            s.write(_frame({
                "x": 0, "y": 126, "w": 480, "h": 58, "text": status[:80],
                "fg": "#FFFFFF", "bg": "#9C1C9E", "align": "LEFT", "long_mode": "WRAP",
                "border": 3, "border-color": "#C04FE0", "border-radius": 12,
            }))
            s.flush()
        s.close()
    except Exception as e:
        # display is best-effort; never break the caller, but leave a trace
        try:
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "cus_status.log"), "a") as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {type(e).__name__}: {e}\n")
        except Exception:
            pass
    finally:
        if lock is not None:
            try:
                fcntl.flock(lock, fcntl.LOCK_UN)
                lock.close()
            except Exception:
                pass


if __name__ == "__main__":
    render(
        sys.argv[1] if len(sys.argv) > 1 else "Claude",
        sys.argv[2] if len(sys.argv) > 2 else "",
        sys.argv[3] if len(sys.argv) > 3 else "#1E4FFF",
    )
