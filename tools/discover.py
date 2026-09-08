#!/usr/bin/env python3
"""discover.py -- inventory translatable text and report progress.

Two views:

  (default) string inventory -- every string behind a text macro, classified
      english    : has a lowercase word, no Estonian diacritic -> to translate
      translated : contains an Estonian diacritic (heuristic)
      trivial    : symbols / <PLAYER> / TM01 / numbers -> nothing to do

  --remaining BASE   files still identical to git ref BASE (untouched work).
      This is the robust "what's left" signal once translation is underway;
      the diacritic heuristic above undercounts (many Estonian words have no
      diacritic), so use it only for the initial scope estimate.

All-caps NAMES (pokemon/move/item/type/class) stay English by project
convention, so they classify as 'trivial' and are out of scope.

Usage:  tools/.venv/bin/python tools/discover.py [--remaining <git-ref>]
"""
import os
import re
import subprocess
import sys

DIACRITIC = re.compile(r"[õäöüšžÕÄÖÜŠŽ]")
ENGLISH = re.compile(r"[a-z]{3,}")
STRING = re.compile(r'"([^"]*)"')

DIALOGUE = ("text", "line", "cont", "para", "next", "page")
NAMEISH = ("dname", "li")
INLINE_NAME = ("bt_trainer", "npctrade")


def category(path):
    p = path.replace(os.sep, "/")
    if "/dex_entries/" in p:
        return "dex"
    if p.startswith("maps/"):
        return "maps"
    if p.startswith("data/text/"):
        return "text"
    if "/names.asm" in p or "class_names" in p:
        return "names"
    if p.startswith("data/"):
        return "data"
    if p.startswith("engine/"):
        return "engine"
    return "other"


def classify(s):
    core = re.sub(r"<[^>]+>", "", s).replace("@", "").strip()
    if DIACRITIC.search(s):
        return "translated"
    if ENGLISH.search(core):
        return "english"
    return "trivial"


def strings_of(line, cat):
    stripped = line.lstrip()
    head = stripped.split(None, 1)[0] if stripped else ""
    if head in DIALOGUE or head in NAMEISH:
        return STRING.findall(stripped)
    if head in INLINE_NAME:
        m = STRING.findall(stripped)
        return m[-1:] if m else []
    if head == "db" and cat == "dex":
        return STRING.findall(stripped)
    return []


def bar(done, total, w=20):
    if total == 0:
        return " " * w
    f = int(w * done / total)
    return "#" * f + "-" * (w - f)


def inventory():
    cats, files = {}, {}
    for dp, _, names in os.walk("."):
        if "/.git" in dp:
            continue
        for name in names:
            if not name.endswith(".asm"):
                continue
            path = os.path.relpath(os.path.join(dp, name), ".")
            cat = category(path)
            for line in open(os.path.join(dp, name), encoding="utf-8", errors="ignore"):
                for s in strings_of(line, cat):
                    idx = {"english": 0, "translated": 1, "trivial": 2}[classify(s)]
                    cats.setdefault(cat, [0, 0, 0])[idx] += 1
                    files.setdefault(path, [0, 0, 0])[idx] += 1

    print(f"{'category':10}{'english':>9}{'translated':>12}{'trivial':>9}   progress")
    tot = [0, 0, 0]
    for c in sorted(cats, key=lambda c: -cats[c][0]):
        e, t, r = cats[c]
        tot = [tot[i] + cats[c][i] for i in range(3)]
        pct = 100 * t / (e + t) if e + t else 100
        print(f"{c:10}{e:9}{t:12}{r:9}   [{bar(t, e + t)}] {pct:5.1f}%")
    e, t, r = tot
    print("-" * 62)
    pct = 100 * t / (e + t) if e + t else 100
    print(f"{'TOTAL':10}{e:9}{t:12}{r:9}   [{bar(t, e + t)}] {pct:5.1f}%")

    print("\nTop 15 files by untranslated strings:")
    for path in sorted(files, key=lambda p: -files[p][0])[:15]:
        print(f"  {files[path][0]:4}  {path}")


def remaining(base):
    dirs = ["maps", "data/text", "engine", "data/pokemon/dex_entries"]
    files = subprocess.run(
        ["git", "ls-files", *[f"{d}/*.asm" for d in dirs]],
        capture_output=True, text=True).stdout.split()
    touched = [f for f in files
               if subprocess.run(["git", "diff", "--quiet", base, "--", f]).returncode]
    print(f"baseline {base}: {len(touched)}/{len(files)} files touched "
          f"[{bar(len(touched), len(files))}] "
          f"{100 * len(touched) / len(files) if files else 0:.1f}%")
    print("\nUntouched files (sample):")
    for f in sorted(set(files) - set(touched))[:20]:
        print(f"  {f}")


def main():
    # anchor to the repo root so it works from any CWD (e.g. make -C tools)
    root = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                          capture_output=True, text=True).stdout.strip()
    if root:
        os.chdir(root)
    if "--remaining" in sys.argv:
        i = sys.argv.index("--remaining")
        base = sys.argv[i + 1] if i + 1 < len(sys.argv) else "HEAD"
        remaining(base)
    else:
        inventory()


if __name__ == "__main__":
    main()
