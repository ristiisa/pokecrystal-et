#!/usr/bin/env python3
"""wrap.py -- turn editable per-message prose (et.json) into wrapped game text.

et.json holds one entry per text label:
    "maps/Foo.asm::BarText": {"file","label","en","et","status"}
where `et` is the full Estonian, paragraphs separated by newlines. A newline
starts a new textbox screen (para); within a paragraph the text flows freely --
NO manual line-breaking. This wrapper does the line-breaking to the 18-tile box,
hyphenating over-long words with pyphen, so nothing has to be pre-wrapped by hand.

  tools/.venv/bin/python tools/wrap.py            # validate every message fits
  tools/.venv/bin/python tools/wrap.py --show maps/Foo.asm::BarText   # preview one

The emitted block (text/line/cont + para for new screens) is what gets written
into the .asm; use --show to eyeball it. Validation flags only real problems --
a single word that even hyphenation can't fit (rare).
"""
import json
import re
import sys

import pyphen

from textwidth import tiles, LINE_WIDTH

et = pyphen.Pyphen(lang="et")


def wrap_paragraph(text):
    """Greedy-wrap one paragraph into <=18-tile display lines (pyphen hyphenation)."""
    lines, cur = [], ""
    for word in text.split():
        cand = (cur + " " + word).strip()
        if tiles(cand) <= LINE_WIDTH:
            cur = cand
            continue
        # word (or cur+word) overflows -> try to hyphenate the word onto this line
        room = LINE_WIDTH - (tiles(cur) + 1 if cur else 0) - 1  # -1 for the hyphen
        piece = et.wrap(word, room) if room > 1 and "#" not in word else None
        if piece:
            lines.append((cur + " " + piece[0]).strip())
            cur = piece[1]
        else:
            if cur:
                lines.append(cur)
            # word alone may still exceed the box; hyphenate greedily
            while tiles(word) > LINE_WIDTH:
                p = et.wrap(word, LINE_WIDTH - 1)
                if not p:
                    break
                lines.append(p[0])
                word = p[1]
            cur = word
    if cur:
        lines.append(cur)
    return lines


def wrap_message(et_text):
    """Full message (newline-separated paragraphs) -> list of macro lines."""
    out = []
    for pi, para in enumerate(p for p in et_text.split("\n")):
        if not para.strip():
            continue
        lines = wrap_paragraph(para.strip())
        for li, ln in enumerate(lines):
            if pi == 0 and li == 0:
                macro = "text"
            elif li == 0:
                out.append("")
                macro = "para"
            elif li == 1:
                macro = "line"
            else:
                macro = "cont"
            out.append(f'\t{macro} "{ln}"')
    return out


def main():
    data = json.load(open("tools/et.json", encoding="utf-8"))
    if "--show" in sys.argv:
        key = sys.argv[sys.argv.index("--show") + 1]
        print("\n".join(wrap_message(data[key]["et"])))
        return
    problems = 0
    for key, m in data.items():
        if not m.get("et"):
            continue
        for ln in wrap_message(m["et"]):
            text = re.search(r'"([^"]*)"', ln)
            if text and tiles(text.group(1)) > LINE_WIDTH:
                print(f"{key}: cannot fit -> {text.group(1)!r} ({tiles(text.group(1))} tiles)")
                problems += 1
    print(f"\n{problems} unfittable line(s).", file=sys.stderr)


if __name__ == "__main__":
    main()
