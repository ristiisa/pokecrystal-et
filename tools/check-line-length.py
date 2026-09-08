#!/usr/bin/env python3
"""check-line-length.py -- flag text lines wider than the 18-tile box.

Ported from pokered. Scans dialogue macros (text/line/cont/para/next/page)
and dex 'db' strings, measures each in on-screen tiles (see textwidth.py),
and prints any that overflow. Run it after mark.py / hand edits to catch
lines that won't fit the text box.

Usage:  tools/.venv/bin/python tools/check-line-length.py [maps data engine ...]
        (defaults to maps data/text engine data/pokemon/dex_entries)
"""
import os
import re
import sys

from textwidth import LINE_WIDTH, tiles

MACROS = ("text", "line", "cont", "para", "next", "page", "db")
LINE_RE = re.compile(r'^\s+(text|line|cont|para|next|page|db)\s+"([^"]*)"\s*(;.*)?$')

DEFAULT_DIRS = ["maps", "data/text", "data/pokemon/dex_entries"]

# Full-width special screens (on-screen keyboards, stats tables) that are laid
# out by hand and legitimately exceed the 18-tile dialogue box. Skip by basename.
EXCLUDE = {"mail_input_chars.asm", "name_input_chars.asm"}


def check_file(path):
    hits = 0
    for i, line in enumerate(open(path, encoding="utf-8", errors="ignore"), 1):
        m = LINE_RE.match(line)
        if not m:
            continue
        text = m.group(2)
        # skip untranslated Japanese leftovers
        if any(ord(c) > 0x2e00 for c in text):
            continue
        w = tiles(text)
        if w > LINE_WIDTH:
            print(f"{path}:{i}: {w} tiles (>{LINE_WIDTH})  {text!r}")
            hits += 1
    return hits


def check(root):
    if os.path.isfile(root):
        return check_file(root) if root.endswith(".asm") else 0
    hits = 0
    for dp, _, names in os.walk(root):
        if "/.git" in dp:
            continue
        for name in names:
            if name.endswith(".asm") and name not in EXCLUDE:
                hits += check_file(os.path.join(dp, name))
    return hits


def main():
    dirs = [a for a in sys.argv[1:] if not a.startswith("-")] or DEFAULT_DIRS
    total = sum(check(d) for d in dirs if os.path.exists(d))
    print(f"\n{total} line(s) over {LINE_WIDTH} tiles.", file=sys.stderr)
    sys.exit(1 if total else 0)


if __name__ == "__main__":
    main()
