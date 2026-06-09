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

PORT = "/dev/cu.usbmodem1234561"   # pad 1 = the AI display
BAUD = 115200


def _frame(o: dict) -> bytes:
    p = json.dumps(o, separators=(",", ":")).encode("utf-8")
    return b"cus" + len(p).to_bytes(2, "big") + p


def render(msg: str, status: str = "", color: str = "#1E4FFF") -> None:
    try:
        import serial
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
    except Exception:
        pass  # display is best-effort; never break the caller


if __name__ == "__main__":
    render(
        sys.argv[1] if len(sys.argv) > 1 else "Claude",
        sys.argv[2] if len(sys.argv) > 2 else "",
        sys.argv[3] if len(sys.argv) > 3 else "#1E4FFF",
    )
