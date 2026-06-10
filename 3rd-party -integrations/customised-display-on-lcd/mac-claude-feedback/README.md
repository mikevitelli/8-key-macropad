# Mac + Claude Code → MacroPad AI feedback (cus)

Live "AI tool feedback display": this drives the macropad's customised (`cus`) screen
from a **Claude Code** session on a Mac, over USB serial, with zero cloud/app dependency.
As Claude runs tools, prompts, or goes idle, the LCD shows a live activity panel; the
bottom key strip is a dedicated **AI control deck** (Profile 5).

Requires **firmware v35+** (v29 ignores `cus` frames). Python 3 + `pyserial`.

## Files
- `cus_status.py` — the renderer. Sends a clear-then-redraw `cus` panel (main message +
  status line) to the pad. **Clear-then-redraw is mandatory**: `cus` panels *stack* and are
  never replaced, so each refresh sends `clear_canvas:true` on the first panel to avoid
  pile-up/ghosting (the firmware caps at 48 panels and FIFO-evicts otherwise).
- `pad_feedback_hook.py` — a Claude Code hook handler. Reads the event JSON on stdin,
  formats a one-line message, and fires a **non-blocking** pad update (detached subprocess,
  always exits 0) so it can never delay or break Claude's tool flow.
- `cus_tail.py` — **the live mirror that needs no hooks and no restart** (recommended). A
  daemon that tails the newest transcript `.jsonl` (re-detecting the active session across
  restarts) and renders the latest message + action to the pad in plain language
  (clear-then-redraw, drains to the freshest entry). Run it once: `nohup python3 cus_tail.py &`.
  Use this instead of the hooks if you don't want to restart Claude Code to load them.
- `settings.hooks.json` — the hooks block to merge into `~/.claude/settings.json`.
- `eezbot.py` — the serial config tool (defines Profile 5, the AI deck; pushes labels/scripts).

## Setup
1. Edit `cus_status.py` `PORT` to your pad's CDC port (`ls /dev/cu.usbmodem*`).
2. Merge `settings.hooks.json` into `~/.claude/settings.json` (paths point at `~/eezbot/`;
   adjust if you keep the scripts elsewhere). **Hooks load at session start — restart Claude
   Code to activate.**
3. Push the AI deck: `python3 eezbot.py push --profile 5` (Profile 5 = Confirm/Reject/
   Scroll Up/Scroll Dn/Stop/Menu/Voice/Relay).
4. Icons: the key-icon slot is **64×64** — undersized PNGs get tiled 2×2. Drop 64×64
   `profile_5_key_*.png` into the drive's `app_icons/`.

## Notes
- The customised screen's key strip shows the **currently-active profile** (the `cus`
  protocol cannot set keys). Switch to Profile 5 to get the AI deck under the panel.
- Canvas is the top **480×200**; bottom 120px is the key strip. Keep `y+h ≤ 200`.
- Serial is exclusive — stop other feeders (e.g. the `pcs` dashboard) before pushing config.
