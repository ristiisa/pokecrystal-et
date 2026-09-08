#!/usr/bin/env python3
"""spellcheck.py -- Estonian spell-check of ';;' translation lines.

Ported from pokered. Runs the et_EE Hunspell dictionary over the words on
';;' lines (the pending-translation markers) and prints unknown words in
context, so you can catch typos before mark.py bakes them into the ROM.

An allowlist covers game proper nouns (POKéMON place/character names) that
Hunspell will never know. Extend ALLOW as the translation grows; keeping it
in sync with cspell.json is convenient but not required.

Usage:  tools/.venv/bin/python tools/spellcheck.py [maps data ...]
"""
import os
import re
import sys

import phunspell
from termcolor import colored

pspell = phunspell.Phunspell("et_EE")

# Proper nouns / tokens Hunspell can't know. Lowercased.
ALLOW = {
    "player", "rival", "pokemon", "pokedex", "pk", "mn",
}

STRIP = re.compile(r"[.,!?;:\"'()…\n]")
TOKEN = re.compile(r"<[^>]+>|\{[^}]*\}")     # control tokens -> ignore


def words_of(line):
    line = line.lstrip()[2:]                 # drop ';;'
    line = TOKEN.sub(" ", line)
    line = line.replace("#", " ")            # POKé prefix marker
    line = STRIP.sub(" ", line).lower()
    return [w for w in line.split() if w and not w.isdigit()]


def check_file(path):
    hits = 0
    for i, line in enumerate(open(path, encoding="utf-8", errors="ignore"), 1):
        if not line.lstrip().startswith(";;"):
            continue
        words = words_of(line)
        bad = [w for w in pspell.lookup_list(words) if w not in ALLOW]
        if bad:
            print(colored(f"{path}:{i}", "dark_grey"))
            print(colored(", ".join(bad), "yellow"))
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
            if name.endswith(".asm"):
                hits += check_file(os.path.join(dp, name))
    return hits


def main():
    dirs = [a for a in sys.argv[1:] if not a.startswith("-")] or ["maps", "data", "engine"]
    total = sum(check(d) for d in dirs if os.path.exists(d))
    print(f"\n{total} ';;' line(s) with unknown words.", file=sys.stderr)


if __name__ == "__main__":
    main()
