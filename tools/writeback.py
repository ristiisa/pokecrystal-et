#!/usr/bin/env python3
"""writeback.py -- render tools/et.json translations back into the .asm sources.

The inverse of pc_extract.py. For every translated label it regenerates the
text block from the Estonian in et.json, word-wrapped to the 18-tile box
(syllable hyphenation via syllabify/pyphen), and splices it in place -- leaving
all surrounding script code untouched.

How the byte model is honoured (see home/text.asm):
  * A text block is one PlaceString stream read until '@' ($50 = TX_END).
  * `line/cont/para/next` and `done/prompt` are control bytes *inside* the
    string, so a text segment before them needs NO '@'.
  * `text_ram/text_far/text_decimal/text_low/text_bcd/text_today` (and text_end)
    are top-level commands: the preceding string must end with '@', and text
    resumes afterwards with a fresh `text` (TX_START).
  * The abstract tokens in et.json ({RAM}/{FAR}/{NUM}/{DAY}) are mapped back to
    the ORIGINAL insert macros (with their operands) by order + type.

Conservative by design -- a block is rewritten only when it is "safe":
  * no exotic macros (text_pause/dots/scroll/buffer/box/move/asm, sound_*),
  * terminator in {done, prompt, text_end},
  * ET screen count == original para/page count + 1,
  * ET insert tokens match the original inserts in count and type/order.
Everything else is left as English and listed in the report, so a rerun is safe
and nothing is silently corrupted.  Dex entries (data/pokemon/dex_entries/*.asm)
use the db/next/page path: 18-tile lines grouped 3 to a page.

Usage:
  tools/.venv/bin/python tools/writeback.py            # rewrite every safe block
  tools/.venv/bin/python tools/writeback.py --dry-run  # report only, write nothing
  tools/.venv/bin/python tools/writeback.py maps/ElmsLab.asm   # limit to files
"""
import json
import os
import re
import sys

from textwidth import tiles, LINE_WIDTH
import syllabify

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEX_LINES_PER_PAGE = 3

LINE_MACROS = ("text", "text_start", "line", "cont", "para", "next", "page")
INSERT_MACROS = ("text_ram", "text_far", "text_decimal", "text_low",
                 "text_bcd", "text_today")
TOK_FOR = {"text_ram": "{RAM}", "text_far": "{FAR}", "text_decimal": "{NUM}",
           "text_low": "{NUM}", "text_bcd": "{NUM}", "text_today": "{DAY}"}
TOK_MACROS = {"{RAM}": ("text_ram",), "{FAR}": ("text_far",),
              "{NUM}": ("text_decimal", "text_low", "text_bcd"),
              "{DAY}": ("text_today",)}
TERMINATORS = ("done", "prompt", "text_end")
AT_TERMINATORS = ("text_end",)          # terminator that needs a preceding '@'
EXOTIC = ("text_pause", "text_dots", "text_scroll", "text_buffer", "text_box",
          "text_move", "text_asm", "text_start_asm", "text_waitbutton",
          "text_promptbutton", "sound_")
STRING_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')
TOKEN_SPLIT = re.compile(r"(\{RAM\}|\{FAR\}|\{NUM\}|\{DAY\})")
LABEL_RE = re.compile(r"^(\w[\w.]*)::?\s*(;.*)?$")


def norm(s):
    """Charmap-safe normalisation: en/em dashes -> hyphen."""
    return s.replace("–", "-").replace("—", "-")


# ---------------------------------------------------------------- wrapping ----
def wrap_screen(text):
    """Wrap one screen (words + inline {TOKEN}s) into <=18-tile rows."""
    rows, cur = [], ""
    for word in text.split():
        cand = (cur + " " + word).strip()
        if tiles(cand) <= LINE_WIDTH:
            cur = cand
            continue
        room = LINE_WIDTH - (tiles(cur) + 1 if cur else 0)
        piece = syllabify.wrap(word, room)
        if piece:
            rows.append((cur + " " + piece[0]).strip())
            word = piece[1]
        elif cur:
            rows.append(cur)
        cur = ""
        # a leftover word may itself still exceed the box -> hyphenate greedily
        while tiles(word) > LINE_WIDTH:
            p = syllabify.wrap(word, LINE_WIDTH)
            if not p:
                break
            rows.append(p[0])
            word = p[1]
        cur = word
    if cur:
        rows.append(cur)
    return rows or [""]


# --------------------------------------------------------------- emitters ----
def insert_token(source_line):
    """The et.json token a given insert macro source line corresponds to."""
    return TOK_FOR[source_line.strip().split(None, 1)[0]]


def emit_dialogue(et_text, inserts, term_needs_at):
    """Return the list of asm text lines (label + terminator added by caller).

    `inserts` are the ORIGINAL insert source lines, in order. Each et.json token
    pops the next original insert OF ITS OWN TYPE, so a translation may reorder
    inserts of different types (e.g. money vs item) and still bind correctly.
    """
    from collections import deque, defaultdict
    queues = defaultdict(deque)
    for line in inserts:
        queues[insert_token(line)].append(line)
    ops = []            # ('str', macro, text) | ('ins', source_line)
    screens = [s for s in et_text.split("\n")]
    for si, screen in enumerate(screens):
        rows = wrap_screen(norm(screen))
        for ri, row in enumerate(rows):
            if si and ri == 0:
                ops.append(["blank"])          # blank line before a new box
            opener = ("text" if si == 0 and ri == 0 else
                      "para" if ri == 0 else "line" if ri == 1 else "cont")
            pieces = TOKEN_SPLIT.split(row)   # [txt, tok, txt, tok, ..., txt]
            first = True
            for j in range(0, len(pieces), 2):
                txt = pieces[j]
                tok = pieces[j + 1] if j + 1 < len(pieces) else None
                macro = opener if first else "text"
                first = False
                ops.append(["str", macro, txt])
                if tok is not None:
                    ops.append(["ins", queues[tok].popleft()])
    # decide '@': a string needs it iff the next op is an insert, or it is the
    # final op and the terminator is a top-level command (text_end).
    out = []
    for i, op in enumerate(ops):
        if op[0] == "blank":
            out.append("")
            continue
        if op[0] == "ins":
            out.append(op[1])
            continue
        nxt = next((o for o in ops[i + 1:] if o[0] != "blank"), None)
        at = (nxt is not None and nxt[0] == "ins") or (nxt is None and term_needs_at)
        s = op[2] + ("@" if at else "")
        out.append(f'\t{op[1]} "{s}"')
    return out


DESC_FILES = ("data/moves/descriptions.asm", "data/items/descriptions.asm")


def emit_desc(et_text):
    """Move/item description: db + next, one 18-tile box (2 lines)."""
    rows = wrap_screen(norm(et_text.replace("\n", " ")))
    out = []
    for i, row in enumerate(rows):
        content = row + ("@" if i == len(rows) - 1 else "")
        out.append(f'\t{"db  " if i == 0 else "next"} "{content}"')
    return out


def process_desc_file(path, entries, report):
    lines = open(path, encoding="utf-8", errors="ignore").readlines()
    by_label = {e["label"]: e for e in entries}
    out, i, changed = [], 0, 0
    while i < len(lines):
        m = LABEL_RE.match(lines[i].rstrip("\n"))
        lbl = m.group(1) if m else None
        if lbl in by_label and by_label[lbl]["et"].strip():
            out.append(lines[i])                 # the label line
            j = i + 1
            while j < len(lines):
                s = lines[j].strip()
                if s.startswith("db ") or s.startswith("next "):
                    j += 1
                    mm = STRING_RE.search(lines[j - 1])
                    if mm and mm.group(1).endswith("@"):
                        break
                else:
                    break
            out.extend(l + "\n" for l in emit_desc(by_label[lbl]["et"]))
            changed += 1
            i = j
            continue
        out.append(lines[i])
        i += 1
    if changed and "--dry-run" not in sys.argv:
        with open(path, "w", encoding="utf-8", errors="ignore") as fh:
            fh.writelines(out)
    return changed


def emit_dex(et_text, dw_line):
    cat, *desc = et_text.split("\n")
    rows = wrap_screen(norm(" ".join(desc)))
    out = [f'\tdb "{norm(cat)}@" ; species name', dw_line, ""]
    for pi in range(0, len(rows), DEX_LINES_PER_PAGE):
        page = rows[pi:pi + DEX_LINES_PER_PAGE]
        for li, row in enumerate(page):
            last = pi + li == len(rows) - 1
            content = row + ("@" if last else "")
            macro = ("db  " if pi == 0 else "page") if li == 0 else "next"
            out.append(f'\t{macro} "{content}"')
        if pi + DEX_LINES_PER_PAGE < len(rows):
            out.append("")
    return out


# ------------------------------------------------------------ block parse ----
def parse_block(lines):
    """Classify a block's body lines. Returns dict or None if unparseable.

    keys: inserts (source lines), n_screens, terminator (macro), exotic (bool),
          nested (bool), end_i (index of terminator line, inclusive).
    """
    inserts, n_screens, term, exotic, nested = [], 1, None, False, False
    end_i = None
    for i, raw in enumerate(lines):
        s = raw.strip()
        if not s or s.startswith(";"):
            continue
        if LABEL_RE.match(s) and "::" in s and not s.split()[0].endswith('"'):
            # a nested label inside the block (merged pool) -> unsafe
            nested = True
            end_i = i - 1
            break
        head = s.split(None, 1)[0]
        if head in TERMINATORS:
            term = head
            end_i = i
            break
        if head in INSERT_MACROS:
            inserts.append(raw.rstrip("\n"))
        elif head in ("para", "page"):
            n_screens += 1
        elif head in ("text", "text_start", "line", "cont", "next"):
            pass
        elif any(head.startswith(e) for e in EXOTIC):
            exotic = True
        else:
            return None                     # unknown macro -> bail, leave as-is
    if term is None:
        return None
    return dict(inserts=inserts, n_screens=n_screens, terminator=term,
                exotic=exotic, nested=nested, end_i=end_i)


def et_tokens(et_text):
    return [t for t in TOKEN_SPLIT.findall(et_text)]


def safe_and_render(et_text, block_lines, term_line, report, key):
    """Return emitted lines for a dialogue block, or None (with a report entry)."""
    info = parse_block(block_lines)
    if info is None:
        report["unparseable"].append(key); return None
    if info["exotic"]:
        report["exotic"].append(key); return None
    if info["nested"]:
        report["merged_pool"].append(key); return None
    scr = et_text.count("\n") + 1
    # et > asm: the extractor folded a following (usually `; unreferenced`) label
    # into this one, so et has more screens than this block holds. Recover only
    # this block's own live text -- its FIRST n_screens screens -- and leave the
    # trailing merged labels as-is. Skip if the recovered prefix's inserts don't
    # line up with the block's (then it's not a clean head).
    if scr > info["n_screens"]:
        prefix = "\n".join(et_text.split("\n")[:info["n_screens"]])
        from collections import Counter
        if (Counter(et_tokens(prefix)) ==
                Counter(insert_token(i) for i in info["inserts"])):
            report["merged_pool_headonly"].append(key)
            et_text = prefix
        else:
            report["merged_pool"].append(f"{key} (et {scr} vs asm {info['n_screens']})")
            return None
    # compare inserts per token-type (a translation may reorder different types)
    from collections import Counter
    et_counts = Counter(et_tokens(et_text))
    asm_counts = Counter(insert_token(i) for i in info["inserts"])
    if et_counts != asm_counts:
        report["insert_mismatch"].append(
            f"{key} (et {dict(et_counts)} vs asm {dict(asm_counts)})")
        return None
    term_needs_at = info["terminator"] in AT_TERMINATORS
    body = emit_dialogue(et_text, [i.rstrip("\n") for i in info["inserts"]],
                         term_needs_at)
    return body + [term_line.rstrip("\n")]


# --------------------------------------------------------------- driver -------
def process_dialogue_file(path, entries, report):
    with open(path, encoding="utf-8", errors="ignore") as fh:
        lines = fh.readlines()
    by_label = {e["label"]: e for e in entries}
    out, i, changed = [], 0, 0
    while i < len(lines):
        m = LABEL_RE.match(lines[i].rstrip("\n"))
        lbl = m.group(1) if m else None       # matches both `Foo:` and `Foo::`
        if lbl not in by_label:
            out.append(lines[i]); i += 1; continue
        et = by_label[lbl]["et"]
        key = f"{by_label[lbl]['file']}::{lbl}"
        # gather block body from i+1 until terminator (parse_block finds end)
        body_lines = lines[i + 1:]
        info = parse_block(body_lines)
        if info is None or info["end_i"] is None:
            report["no_block"].append(key); out.append(lines[i]); i += 1; continue
        term_line = body_lines[info["end_i"]]
        if not et.strip() or not re.search(r"[A-Za-zÀ-ÿ]", et):
            # pure token/symbol block (e.g. {FAR} stubs) -> leave English as-is
            report["skipped_symbolic"].append(key); out.append(lines[i]); i += 1
            continue
        rendered = safe_and_render(et, body_lines[:info["end_i"] + 1], term_line,
                                   report, key)
        out.append(lines[i])                       # label line
        if rendered is None:                       # keep original body
            out.extend(lines[i + 1:i + 1 + info["end_i"] + 1])
        else:
            out.extend(l + "\n" for l in rendered)
            changed += 1
        i += 1 + info["end_i"] + 1
    if changed and "--dry-run" not in sys.argv:
        with open(path, "w", encoding="utf-8", errors="ignore") as fh:
            fh.writelines(out)
    return changed


def process_dex_file(path, entry, report):
    orig = open(path, encoding="utf-8", errors="ignore").read().splitlines()
    dw = next((l for l in orig if l.strip().startswith("dw ")), "\tdw 0, 0")
    if not entry["et"].strip():
        report["skipped_symbolic"].append(entry["file"]); return 0
    body = emit_dex(entry["et"], dw.rstrip("\n"))
    if "--dry-run" not in sys.argv:
        with open(path, "w", encoding="utf-8", errors="ignore") as fh:
            fh.write("\n".join(body) + "\n")
    return 1


def apply_menus(report):
    """Regenerate fixed-layout menu db-strings from tools/menus.json (committed).

    These aren't text-macro dialogue, so they live in a separate source and are
    written back as literal db-string replacements. '*' entries apply to every
    engine/ and data/ .asm; the rest are per-file. Idempotent + safe on a fresh
    (English) upstream checkout, which is the whole point of not committing .asm.
    """
    mpath = os.path.join(ROOT, "tools", "menus.json")
    if not os.path.exists(mpath):
        return 0
    menus = json.load(open(mpath, encoding="utf-8"))
    glob = menus.get("*", {})
    changed = 0

    def rewrite(path, mapping):
        nonlocal changed
        if not os.path.exists(path):
            return
        txt = open(path, encoding="utf-8", errors="ignore").read()
        orig = txt
        for en, et in mapping.items():
            txt = txt.replace(f'"{en}"', f'"{et}"')
        if txt != orig:
            if "--dry-run" not in sys.argv:
                open(path, "w", encoding="utf-8", errors="ignore").write(txt)
            changed += 1

    for f, mapping in menus.items():
        if f in ("*", "_comment"):
            continue
        rewrite(os.path.join(ROOT, f), mapping)
    if glob:
        for base in ("engine", "data", "home"):
            for dp, _, names in os.walk(os.path.join(ROOT, base)):
                for n in names:
                    if n.endswith(".asm"):
                        rewrite(os.path.join(dp, n), glob)
    if changed:
        print(f"menu files rewritten: {changed}")
    return changed


def main():
    for mod in ("apply_assets", "fix_pngs"):   # charmap, then font/logo PNGs
        try:
            __import__(mod).main()
        except Exception as e:        # never block the text writeback on assets
            print(f"  {mod} skipped: {e}")
    d = json.load(open(os.path.join(ROOT, "tools", "et.json"), encoding="utf-8"))
    only = [a for a in sys.argv[1:] if not a.startswith("-")]
    from collections import defaultdict
    by_file = defaultdict(list)
    for v in d.values():
        by_file[v["file"]].append(v)
    report = defaultdict(list)
    changed = 0
    for f, entries in sorted(by_file.items()):
        if only and not any(f.endswith(o) or o in f for o in only):
            continue
        path = os.path.join(ROOT, f)
        if not os.path.exists(path):
            report["no_file"].append(f); continue
        if "dex_entries" in f:
            changed += process_dex_file(path, entries[0], report)
        elif f in DESC_FILES:
            changed += process_desc_file(path, entries, report)
        else:
            changed += process_dialogue_file(path, entries, report)
    apply_menus(report)
    print(f"rewritten blocks: {changed}")
    if report["merged_pool_headonly"]:
        print(f"  merged pools rewritten head-only: {len(report['merged_pool_headonly'])}")
    for reason in ("no_file", "no_block", "unparseable", "exotic", "merged_pool",
                   "insert_mismatch", "skipped_symbolic"):
        n = len(report[reason])
        if n:
            print(f"  skipped [{reason}]: {n}")
            for k in report[reason][:8]:
                print(f"      {k}")
            if n > 8:
                print(f"      ... +{n - 8} more")


if __name__ == "__main__":
    main()
