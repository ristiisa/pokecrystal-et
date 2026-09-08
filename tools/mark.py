#!/usr/bin/env python3
"""mark.py -- seed/replace pokecrystal dialogue from ';;' translation lines.

Adapted from pokered's extract-and-mark.py, with two changes for pokecrystal:

  * One ';;' line == one textbox. Consecutive ';;' lines become successive
    'para' boxes, so paragraph breaks are PRESERVED (pokered's version
    collapsed a multi-paragraph block into one run of text/line/cont).
  * Dialogue lives inline in maps/*.asm next to script code, so the rewrite
    is bounded: it only ever replaces the span between the ';;' lines and the
    block terminator, and bails out the moment it meets a label or non-text
    macro. Surrounding map-script code is never touched.

Workflow:
  1. Above an English block, write the Estonian, one ';;' line per textbox:

        ;;Tere <PLAYER>! Mina olen professor ELM.
        ;;Palun aita mul uurida #MONE!
        ProfElmText:
                text "Hi, <PLAYER>! ..."     <- English, gets replaced
                ...
                done

  2. Run:  make -C tools mark FILE=maps/ElmsLab.asm
     or:   tools/.venv/bin/python tools/mark.py maps/ElmsLab.asm  (dir also ok)

  3. Each ';;' box is word-wrapped to 18 tiles and written back in place.

Re-running is safe: blocks with no ';;' above them are left untouched.
Pass --stdout to preview without writing.
"""
import os
import re
import sys

import pyphen

from textwidth import LINE_WIDTH, tiles

et = pyphen.Pyphen(lang="et")

TERMINATORS = ("done", "prompt", "text_end", "text_promptbutton",
               "text_ram", "text_far")
BLOCK_MACROS = ("text", "line", "cont", "para", "next", "page")


def wrap_box(estonian):
    """Wrap one Estonian textbox string into a list of <=18-tile lines."""
    dialog, cur = [], ""
    for word in estonian.split(" "):
        if not word:
            continue
        candidate = (cur + " " + word).strip()
        if tiles(candidate) <= LINE_WIDTH:
            cur = candidate
            continue
        # word overflows: try to hyphenate it (never split a "#" POKé word)
        room = LINE_WIDTH - tiles(cur) - (1 if cur else 0) - 1  # -1 for the "-"
        piece = et.wrap(word, room) if "#" not in word and room > 1 else None
        if piece:
            dialog.append((cur + " " + piece[0]).strip())
            cur = piece[1]
        else:
            if cur:
                dialog.append(cur)
            cur = word
    if cur:
        dialog.append(cur)
    return dialog


def render(boxes):
    """boxes: list of wrapped-line lists -> emitted macro lines."""
    out = []
    for bi, box in enumerate(boxes):
        for li, text in enumerate(box):
            if bi == 0 and li == 0:
                macro = "text"
            elif li == 0:
                out.append("\n")               # blank line before a new box
                macro = "para"
            elif li == 1:
                macro = "line"
            else:
                macro = "cont"
            out.append(f'\t{macro} "{text}"\n')
    return out


def process(path):
    with open(path, encoding="utf-8", errors="ignore") as fh:
        lines = fh.readlines()

    out, i, changed = [], 0, False
    while i < len(lines):
        if not lines[i].lstrip().startswith(";;"):
            out.append(lines[i])
            i += 1
            continue

        # 1. collect consecutive ';;' boxes
        boxes_src = []
        while i < len(lines) and lines[i].lstrip().startswith(";;"):
            boxes_src.append(lines[i].lstrip()[2:].strip())
            i += 1

        # keep a label line (e.g. "ProfElmText:") that sits above the text
        if (i < len(lines) and re.match(r"^\w[\w.]*:?\s*$", lines[i])
                and not lines[i].lstrip().startswith(BLOCK_MACROS)):
            out.append(lines[i])
            i += 1

        # 2. emit the translated block
        out.extend(render([wrap_box(b) for b in boxes_src if b]))
        changed = True

        # 3. delete the old English up to (not including) the terminator
        while i < len(lines):
            stripped = lines[i].strip()
            head = stripped.split(None, 1)[0] if stripped else ""
            if head in TERMINATORS:
                break
            if stripped and head not in BLOCK_MACROS:
                break                          # label/code -> safety stop
            i += 1
        # terminator / stop line is copied verbatim by the outer loop

    if changed:
        if "--stdout" in sys.argv:
            sys.stdout.writelines(out)
        else:
            with open(path, "w", encoding="utf-8", errors="ignore") as fh:
                fh.writelines(out)
    return changed


def main():
    targets = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not targets:
        sys.exit(__doc__)
    for target in targets:
        if os.path.isdir(target):
            for dp, _, names in os.walk(target):
                for name in names:
                    if name.endswith(".asm"):
                        process(os.path.join(dp, name))
        else:
            process(target)


if __name__ == "__main__":
    main()
