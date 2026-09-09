#!/usr/bin/env python3
"""apply_assets.py -- add the Estonian charmap entries (õ Õ š Š ž Ž).

Maps the six letters to tiles $c6-$cb in constants/charmap.asm (ä/ö/ü already
use $c0-$c5). Foundational tweak to upstream source that the Estonian text needs,
kept OUT of a committed diff so upstream pulls stay clean: this re-applies it to a
pristine checkout. Idempotent -- safe to run repeatedly and after a `git checkout`
of constants/charmap.asm.

The matching font glyphs and the custom title logo (the PNG work, which needs
Pillow) live in the separate tools/fix_pngs.py so they can be run independently.
writeback.py runs both. See also [[fix_pngs.py]].
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHARMAP = os.path.join(ROOT, "constants", "charmap.asm")

# charmap value -> letter (glyphs themselves are drawn by fix_pngs.py).
LETTERS = [(0xc6, "õ"), (0xc7, "Õ"), (0xc8, "š"),
           (0xc9, "Š"), (0xca, "ž"), (0xcb, "Ž")]


def patch_charmap():
    txt = open(CHARMAP, encoding="utf-8").read()
    if 'charmap "õ"' in txt:
        return False
    anchor = '\tcharmap "ü",         $c5\n'
    if anchor not in txt:
        raise SystemExit("charmap.asm: expected ü/$c5 anchor not found")
    add = "".join(f'\tcharmap "{c}",{" " * (10 - len(c))}${v:02x}'
                  f'{" ; Estonian" if v == 0xc6 else ""}\n'
                  for v, c in LETTERS)
    open(CHARMAP, "w", encoding="utf-8").write(txt.replace(anchor, anchor + add))
    return True


def main():
    c = patch_charmap()
    print(f"charmap {'patched' if c else 'already has õ/š/ž'}")


if __name__ == "__main__":
    main()
