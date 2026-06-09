#!/usr/bin/env python3
"""Claude Code hook -> macropad cus panel (pad 1).

Wired into ~/.claude/settings.json for PreToolUse / UserPromptSubmit / Stop /
Notification. Reads the hook event JSON on stdin, formats a one-line activity
message, and fires a NON-BLOCKING pad update (detached subprocess) so it can
never delay or break Claude's tool flow. Always exits 0.
"""
import sys
import os
import json
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
RENDER = os.path.join(HERE, "cus_status.py")


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    ev = data.get("hook_event_name", "")
    msg, status, color = None, "", "#1E4FFF"

    if ev == "PreToolUse":
        tn = data.get("tool_name", "tool")
        ti = data.get("tool_input", {}) or {}
        if tn == "Bash":
            detail = str(ti.get("command", ""))[:90]
        elif tn in ("Edit", "Write", "Read", "NotebookEdit"):
            detail = os.path.basename(str(ti.get("file_path", "")))
        elif tn in ("Task", "Agent"):
            detail = str(ti.get("description", ""))[:70]
        elif tn in ("Grep", "Glob"):
            detail = str(ti.get("pattern", ""))[:60]
        else:
            detail = ""
        msg = (f"{tn}: {detail}" if detail else tn).rstrip(": ")
        status = "working..."
        color = "#1E4FFF"
    elif ev == "UserPromptSubmit":
        msg = "You: " + str(data.get("prompt", ""))[:140]
        status = "thinking..."
        color = "#0E7A4B"
    elif ev == "Stop":
        msg = "Done."
        status = "idle - standing by"
        color = "#333A4D"
    elif ev == "Notification":
        msg = str(data.get("message", "Claude needs you"))[:140]
        status = "notification"
        color = "#B8860B"
    else:
        return

    try:
        subprocess.Popen(
            ["python3", RENDER, msg, status, color],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


if __name__ == "__main__":
    main()
