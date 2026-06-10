# Pad config backups

Drive-content backup of the two EezBotFun pads. **Both pads are verified-identical
clones** (same profiles/keys/icons), so this single backup represents both. If they
ever diverge into different states, split into `pad1/` and `pad2/`.

## Contents
- `app_icons/` — the 64×64 key icons (profiles 1/2/3/5, 8 keys each, + the `clock/cpu/gpu/profile` UI glyphs). Not easily regenerable, so this is the important artifact.
- `scripts/` — the per-key Ducky scripts (the key *functions*), one `profile_P_key_K.txt` per key.

## Deliberately excluded (do not commit)
- `ssid.txt` / `pw.txt` — WiFi credentials (this is a public fork).
- `configs/<deviceid>` — device-specific.
- `bg_dark.bin` — off-limits (custom backgrounds have hung the firmware).

## Restore to a pad
1. **Connect ONE pad only** — both pads share USB serial `1234561`, so with both plugged in the serial port that is "pad 1" vs "pad 2" is a coin flip. One at a time = unambiguous.
2. Labels + scripts (device side): `python3 ../eezbot.py push` (pushes aliases + scripts; labels live in the device config, the drive's `display_names/` is empty on these pads).
3. Icons: enable the pad's USB drive (double-click the dial) and copy `app_icons/*.png` onto it, then eject.
4. Power-cycle the pad so the LCD re-reads config + icons.

Firmware: v35 (icons must be 64×64 or they tile 2×2; `cus` customised-display works).
