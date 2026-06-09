#!/usr/bin/env python3
"""
eezbot.py - configure the EezBotFun 8-key MacroPad directly over its USB serial
port, no browser / no WebSerial pairing.

Protocol (reverse-engineered from the vendor web-config, webserial.js):
  Frame on the wire: b"ebf" + <1 byte: len(COMMAND)> + COMMAND
  COMMAND first char = type:
    '0'  keyboard config   : 0<prof>.<key>:<flag><payload>   flag 0=plain 1=mod 2=consumer
    '2'  set key alias/label: 2<prof>.<key>:<utf8 label>
    '3'  delete key alias  : 3<prof>.<key>:
    '6'  set key script    : 6<prof>.<key>:<ducky-script text>
    '7'  delete key script : 7<prof>.<key>:
    '4'  wifi              : 4<ssid>.<password>
    'a'  enable HID mode   : a<prof>.<key>     (makes the key fire without companion app)
    '5'  query version     : 5
    '8'  query key config  : 8<prof>.<key>     (device replies a=/c= lines)
    'l'/'m' profile count
  COMMAND length is one byte, so each frame's COMMAND must be <= 255 bytes.

On-device script language (runs as HID, works on macOS, max 20 lines):
  DELAY n | STRING text | ENTER SPACE TAB ESC BACKSPACE | F1..F12
  CONTROL SHIFT ALT COMMAND OPTION WINDOWS  (combine on one line: COMMAND SHIFT a)
  Media: PP VOLUP VOLDOWN MUTE NEXT PREV STOP
  GOTO_PROFILE id | NEXT_PROFILE | PREV_PROFILE | DEFAULTDURATION n
"""

import argparse
import os
import sys
import time

import serial

# Two pads now: original = usbmodem1234561, new (AI/cus display) = usbmodem2.
# Override per-invocation:  EEZBOT_PORT=/dev/cu.usbmodem2 python3 eezbot.py push --profile 5
PORT = os.environ.get("EEZBOT_PORT", "/dev/cu.usbmodem1234561")
BAUD = 115200

# ---------------------------------------------------------------------------
# Key layout reference (physical):   1 2 3 4
#                                    5 6 7 8
# 5 profiles available (1..5).
# Each entry: key number -> {"label": <LCD text>, "script": <ducky script>}
# Edit freely, then re-run:  python3 eezbot.py push
# ---------------------------------------------------------------------------


def type_cmd(cmd: str) -> str:
    """Type a command into the ALREADY-FOCUSED terminal + Enter. Assumes a ready
    terminal is frontmost. No Spotlight, no new window."""
    return f"STRING {cmd}\nENTER"


def open_app(name: str) -> str:
    """Spotlight-launch/focus an app by name (no command typed after)."""
    return "\n".join(["COMMAND SPACE", "DELAY 350", f"STRING {name}", "DELAY 200", "ENTER"])


def lr_key(k: str) -> str:
    """Send one bare Lightroom shortcut key (no Enter, no modifier) to the focused app.
    Bare keystrokes can't strand a modifier; Lightroom must be frontmost."""
    return f"STRING {k}"


PROFILES = {
    # Profile 1 - Terminals & SSH (daily driver).
    # type_cmd types the command into the already-focused terminal + Enter.
    # K5 monitor: ~/.local/bin/livemon on the device; TERM override avoids Ghostty's
    # xterm-ghostty being unknown to the uConsole terminfo (breaks curses).
    1: {
        1: {"label": "Claude", "script": type_cmd("yolo")},
        2: {"label": "uConsole", "script": type_cmd("ssh uconsole")},
        3: {"label": "pi-top", "script": type_cmd("ssh pi-top")},
        4: {"label": "server", "script": type_cmd("ssh server")},
        5: {"label": "monitor", "script": type_cmd("ssh -t uconsole 'TERM=xterm-256color ~/.local/bin/livemon'")},
        6: {"label": "Ghostty", "script": "COMMAND n"},
        7: {"label": "Shot", "script": "COMMAND SHIFT 4"},
        8: {"label": "Hermes", "script": type_cmd("hermes")},
    },
    # Profile 2 - Spotify. Transport/volume are consumer-control HID (global, no focus
    # needed); K8 opens Spotify via Spotlight.
    2: {
        1: {"label": "Prev", "script": "PREV"},
        2: {"label": "Play", "script": "PP"},
        3: {"label": "Next", "script": "NEXT"},
        4: {"label": "Stop", "script": "STOP"},
        5: {"label": "Vol-", "script": "VOLDOWN"},
        6: {"label": "Vol+", "script": "VOLUP"},
        7: {"label": "Mute", "script": "MUTE"},
        8: {"label": "Spotify", "script": open_app("Spotify")},
    },
    # Profile 3 - Adobe Lightroom Classic. The finger-twister chords + a macro, the stuff
    # that's annoying by hand (single-key shortcuts are easy on the keyboard already).
    # Lightroom must be the focused app. NOTE: these hold modifiers -> if the pad ever drops
    # a key-up, unplug it to clear a stuck modifier.
    3: {
        1: {"label": "Copy",   "script": "COMMAND SHIFT c"},   # copy develop settings
        2: {"label": "Paste",  "script": "COMMAND SHIFT v"},   # paste develop settings
        3: {"label": "Match",  "script": "COMMAND OPTION v"},  # paste settings from previous photo
        4: {"label": "Reset",  "script": "COMMAND SHIFT r"},   # reset all develop sliders
        5: {"label": "Auto",   "script": "COMMAND u"},         # auto tone
        6: {"label": "PS",     "script": "COMMAND e"},         # edit in Photoshop (round-trip)
        7: {"label": "Export", "script": "COMMAND SHIFT e"},   # export dialog
        # Keeper macro: 3-star rating + green color label in one press
        8: {"label": "Keeper", "script": "STRING 3\nDELAY 80\nSTRING 8"},
    },
    # Profile 5 - "AI" control deck for the customised (cus / AI-feedback) screen.
    # The customised screen shows whichever profile is ACTIVE (cus can't set the key strip),
    # so switch to P5 when driving the LCD feedback panel. Distinct icons + functions, not the menus.
    5: {
        1: {"label": "Confirm",   "script": "ENTER"},        # approve a Claude prompt
        2: {"label": "Reject",    "script": "ESC"},          # cancel / dismiss
        3: {"label": "Scroll Up", "script": "PAGEUP"},       # scroll output up (verify token on v35)
        4: {"label": "Scroll Dn", "script": "PAGEDOWN"},     # scroll output down
        5: {"label": "Stop",      "script": "CONTROL c"},    # interrupt a run
        6: {"label": "Menu",      "script": "NEXT_PROFILE"}, # back to the macro profiles
        7: {"label": "Voice",     "script": "F5"},           # macOS dictation (remap in System Settings if needed)
        8: {"label": "Relay",     "script": "STRING relay"}, # placeholder - define the real relay action
    },
}

# ---------------------------------------------------------------------------
# Wire protocol
# ---------------------------------------------------------------------------


def frame(command: bytes) -> bytes:
    if not 0 <= len(command) <= 255:
        raise ValueError(
            f"COMMAND too long ({len(command)} > 255): {command[:40]!r}..."
        )
    return b"ebf" + bytes([len(command)]) + command


def f_keyboard_empty(prof: int, key: int) -> bytes:
    # type 0, flag 0, empty payload  ->  placeholder so the script takes over
    return frame(f"0{prof}.{key}:0".encode("latin-1"))


def f_alias(prof: int, key: int, label: str) -> bytes:
    return frame(f"2{prof}.{key}:".encode("latin-1") + label.encode("utf-8"))


def f_alias_clear(prof: int, key: int) -> bytes:
    return frame(f"3{prof}.{key}:".encode("latin-1"))


def f_script(prof: int, key: int, script: str) -> bytes:
    return frame(f"6{prof}.{key}:".encode("latin-1") + script.encode("latin-1"))


def f_script_clear(prof: int, key: int) -> bytes:
    return frame(f"7{prof}.{key}:".encode("latin-1"))


def f_enable_hid(prof: int, key: int) -> bytes:
    return frame(f"a{prof}.{key}".encode("latin-1"))


def f_query_version() -> bytes:
    return frame(b"5")


def f_query_key(prof: int, key: int) -> bytes:
    return frame(f"8{prof}.{key}".encode("latin-1"))


# ---------------------------------------------------------------------------
# IO
# ---------------------------------------------------------------------------


def send(ser, data: bytes, settle: float = 0.12):
    ser.write(data)
    ser.flush()
    time.sleep(settle)


def drain(ser, wait: float = 0.4) -> str:
    time.sleep(wait)
    out = ser.read(ser.in_waiting or 1)
    try:
        return out.decode("utf-8", "replace")
    except Exception:
        return repr(out)


def push_key(ser, prof: int, key: int, label: str, script: str, verbose=True):
    if verbose:
        print(
            f"  P{prof} K{key}  {label!r:14}  {script.splitlines()[0]!r}"
            + ("  ..." if "\n" in script else "")
        )
    # mirror the exact order the vendor web app uses on Save:
    send(ser, f_keyboard_empty(prof, key))  # type 0 (empty placeholder)
    if label:
        send(ser, f_alias(prof, key, label))  # type 2
    else:
        send(ser, f_alias_clear(prof, key))  # type 3
    send(ser, f_script(prof, key, script))  # type 6
    send(ser, f_enable_hid(prof, key))  # type a


def cmd_push(args):
    with serial.Serial(PORT, BAUD, timeout=0.3) as ser:
        time.sleep(0.3)
        send(ser, f_query_version())
        print("device version reply:", repr(drain(ser)))
        profs = [args.profile] if args.profile else sorted(PROFILES)
        for p in profs:
            if p not in PROFILES:
                print(f"profile {p} not defined, skipping")
                continue
            print(f"profile {p}:")
            for k in sorted(PROFILES[p]):
                if args.key and k != args.key:
                    continue
                e = PROFILES[p][k]
                push_key(ser, p, k, e["label"], e["script"])
        print("done.")


def cmd_query(args):
    with serial.Serial(PORT, BAUD, timeout=0.3) as ser:
        time.sleep(0.3)
        send(ser, f_query_version())
        print("version:", repr(drain(ser)))
        for p in ([args.profile] if args.profile else sorted(PROFILES)):
            for k in sorted(PROFILES.get(p, {})):
                if args.key and k != args.key:
                    continue
                ser.reset_input_buffer()
                send(ser, f_query_key(p, k))
                print(f"P{p} K{k} ->", repr(drain(ser, 0.5)))


def main():
    ap = argparse.ArgumentParser(description="Configure EezBotFun MacroPad over serial")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pp = sub.add_parser("push", help="write profiles/keys to the device")
    pp.add_argument("--profile", type=int, help="only this profile")
    pp.add_argument("--key", type=int, help="only this key number")
    pp.set_defaults(func=cmd_push)
    pq = sub.add_parser("query", help="read back stored config for keys")
    pq.add_argument("--profile", type=int)
    pq.add_argument("--key", type=int)
    pq.set_defaults(func=cmd_query)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
