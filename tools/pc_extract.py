#!/usr/bin/env python3
"""Extract pokecrystal English dialogue needing translation, as {file,label,box,en,et}.

Same JSON structure as the pokered extraction (et_translations.json), but et
is left empty (a translation worksheet). Boxes are parsed like the pokered
extractor: text/para/page start a box, line/cont/next continue it, terminators
end it, wrapped lines are de-hyphenated into whole sentences. Labels with no
text macros (map scripts, object data) produce no boxes and drop out.
'db' counts as dialogue only inside data/pokemon/dex_entries/.
"""
import json
import os
import re
import sys

ROOT = os.path.expanduser("~/projects/pokecrystal-et")
OUT = sys.argv[1] if len(sys.argv) > 1 else "."
MEMORY = os.path.join(ROOT, "tools", "pocketred_et_memory.json")

DIRS = ["maps", "data/text", "engine", "data/pokemon/dex_entries",
        "data/phone/text", "data/battle_tower"]
# db/next description tables (like dex, but real per-label): parse with db-boxes
DESC_FILES = ("data/moves/descriptions.asm", "data/items/descriptions.asm")
BOX_CONT = ("line", "cont", "next")
TERMINATORS = ("done", "prompt", "text_end", "text_promptbutton",
               "text_waitbutton", "text_scroll", "text_ram", "text_far",
               "text_asm", "para_ram")
STRING = re.compile(r'"((?:[^"\\]|\\.)*)"')
LABEL = re.compile(r"^(\w[\w.]*)::?\s*$")

# these files are full-width special screens, not the 18-tile text box
EXCLUDE = {"mail_input_chars.asm", "name_input_chars.asm"}


# macros that print at the current cursor (concatenate with the previous text)
CONCAT = ("text", "text_start")
# runtime inserts with no string operand -> inline placeholder
INSERT = {"text_ram": "{RAM}", "text_far": "{FAR}", "text_decimal": "{NUM}",
          "text_low": "{NUM}", "text_bcd": "{NUM}", "text_today": "{DAY}"}
# macros that move to a new display line (space-joined, de-hyphenated)
NEWLINE = ("line", "cont", "next")


def build(segs):
    """segs: list of (kind, text); kind 'c'=concat, 'n'=newline."""
    out = ""
    for kind, txt in segs:
        txt = txt.replace("@", "")
        if not out:
            out = txt
        elif kind == "c":
            out += txt
        elif out.endswith("-"):
            out = out[:-1] + txt           # hyphenation break
        else:
            out += " " + txt
    return re.sub(r"\s+", " ", out).strip()


def parse(text, dex, default_label=None):
    newbox = ("para", "page") + (("db",) if dex else ())
    result, label, boxes, cur = {}, default_label, [], None

    def flush():
        nonlocal cur
        if cur:
            boxes.append(build(cur))
        cur = None

    for raw in text.splitlines():
        s = raw.strip()
        m = LABEL.match(s)
        if m:
            flush()
            if label is not None and boxes:
                result[label] = boxes
            label, boxes = m.group(1), []
            continue
        head = s.split(None, 1)[0] if s else ""
        if head in newbox:
            q = STRING.findall(s)
            if not q:                      # e.g. "db 0, 0" -> not dialogue
                continue
            flush()
            cur = [("c", q[0])]
        elif head in CONCAT:
            # text_start opens a box even with no string operand, so a label
            # beginning "text_start / line ..." keeps its first line.
            q = STRING.findall(s)
            if head == "text_start" or q:
                cur = (cur or []) + [("c", q[0])] if q else (cur or [])
        elif head in INSERT:
            cur = (cur or []) + [("c", INSERT[head])]
        elif head in NEWLINE:
            q = STRING.findall(s)
            if q:
                cur = cur or []          # a line/cont with no opener starts a box
                cur.append(("n", q[0]))
        elif head in TERMINATORS:
            flush()
    flush()
    if label is not None and boxes:
        result[label] = boxes
    return result


def main():
    memory = {}
    if os.path.exists(MEMORY):
        memory = json.load(open(MEMORY, encoding="utf-8"))

    rows, matched = [], 0

    def emit(rel, text, dex, dl):
        nonlocal matched
        for label, boxes in parse(text, dex, dl).items():
            for i, en in enumerate(boxes):
                if not en:
                    continue
                if en in memory:
                    matched += 1
                rows.append({"file": rel, "label": label,
                             "box": i, "en": en, "et": ""})

    for d in DIRS:
        base = os.path.join(ROOT, d)
        if not os.path.exists(base):
            continue
        dex = "dex_entries" in d
        for dp, _, names in os.walk(base):
            for name in sorted(names):
                if not name.endswith(".asm") or name in EXCLUDE:
                    continue
                path = os.path.join(dp, name)
                rel = os.path.relpath(path, ROOT)
                text = open(path, encoding="utf-8", errors="ignore").read()
                dl = os.path.splitext(name)[0] if dex else None
                emit(rel, text, dex, dl)

    # move/item description tables: db/next boxes, but keep the real labels
    for rel in DESC_FILES:
        path = os.path.join(ROOT, rel)
        if os.path.exists(path):
            emit(rel, open(path, encoding="utf-8", errors="ignore").read(),
                 True, None)

    out_path = os.path.join(OUT, "et_untranslated.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    print(f"{len(rows)} boxes need translation -> {out_path}")
    print(f"{matched} of them have an exact match in et_memory.json "
          f"({100*matched/len(rows):.1f}%)")


if __name__ == "__main__":
    main()
