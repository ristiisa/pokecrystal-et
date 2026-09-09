#!/usr/bin/env python3
"""translate.py -- draft Estonian for the extraction worksheet via TartuNLP.

Fills the empty `et` field of an {file,label,box,en,et} worksheet:
  1. exact matches from the pokered translation memory (human-reviewed) win,
  2. everything else is machine-drafted by the TartuNLP NMT API
     (https://api.tartunlp.ai/translation/v2).

Unique English strings are translated once and fanned back out to every row,
so shared phrases stay consistent and the API is called as little as possible.
Game tokens (<PLAYER>, #MON, {RAM}, ...) are preserved by the API's xml
support; each result is checked and rows whose tokens changed are flagged
"check" for review rather than trusted.

Every row gets an `et_src`: "memory", "mt", or "" (untouched). The draft is
written to a SEPARATE file and the run is resumable -- rerun to continue, and
rows you have already reviewed/edited (et_src cleared or set to "ok") are kept.

Usage:
  tools/.venv/bin/python tools/translate.py \
      [tools/et_untranslated.json] [--out tools/et_draft.json] \
      [--memory tools/pocketred_et_memory.json] [--limit N] [--batch 25]

  make -C tools translate            # whole worksheet
  make -C tools translate ARGS="--limit 50"   # a small trial
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

API = "https://api.tartunlp.ai/translation/v2"
TOKEN = re.compile(r"<[^>]+>|\{[^}]*\}")


def opt(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


# ---- glossary: mask game terms before NMT, restore after (see glossary.json) ----
class Glossary:
    def __init__(self, path):
        g = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
        self.types = g.get("types", {})
        self.terms = g.get("terms", {})
        self.caps = g.get("caps", {})
        self.keep_caps = g.get("keep_caps", False)
        self.enabled = bool(g)

    def mask(self, en):
        restore, ctr, s = {}, [0], en

        def tag(val):
            t = f"<g{ctr[0]}>"
            restore[t] = val
            ctr[0] += 1
            return t

        def typerep(m):
            w, lw = m.group(1), m.group(1).lower()
            if lw in self.types:
                v = self.types[lw]
                return tag(v.capitalize() if w[0].isupper() else v) + m.group(2)
            return m.group(0)

        s = re.sub(r"\b([A-Za-z]+)( ?#MONS?| ?#MON|-type| type| TYPE)", typerep, s)
        for term, val in sorted(self.terms.items(), key=lambda x: -len(x[0])):
            s = re.sub(rf"\b{re.escape(term)}\b", lambda m, v=val: tag(v), s)
        for cap, val in sorted(self.caps.items(), key=lambda x: -len(x[0])):
            if cap in s:
                s = s.replace(cap, tag(val))
        if self.keep_caps:
            s = re.sub(r"(?<![#<>\w])[A-Z][A-Z0-9]{1,}(?:[ '\-][A-Z0-9]+)*",
                       lambda m: tag(m.group(0)), s)
        return s, restore

    @staticmethod
    def restore(et, rmap):
        for t, v in rmap.items():
            et = et.replace(t, v)
        return et


def tokens(s):
    """Multiset of protected tokens (control tags, inserts, and '#' count)."""
    toks = sorted(TOKEN.findall(s))
    return (tuple(toks), s.count("#"))


def translate_batch(texts, retries=4):
    body = json.dumps({"text": texts, "src": "en", "tgt": "et"}).encode()
    headers = {"Content-Type": "application/json"}
    key = os.environ.get("TARTUNLP_API_KEY")
    if key:
        headers["x-api-key"] = key
    for attempt in range(retries):
        try:
            req = urllib.request.Request(API, data=body, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.load(resp)["result"]
            return result if isinstance(result, list) else [result]
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            wait = 2 ** attempt
            code = getattr(e, "code", "")
            print(f"  API error {code} ({e}); retry in {wait}s", file=sys.stderr)
            time.sleep(wait)
    raise SystemExit("TartuNLP API unreachable after retries")


def main():
    infile = next((a for a in sys.argv[1:] if not a.startswith("-")),
                  "tools/et_untranslated.json")
    outfile = opt("--out", "tools/et_draft.json")
    memfile = opt("--memory", "tools/pocketred_et_memory.json")
    limit = int(opt("--limit", "0"))
    batch = int(opt("--batch", "25"))

    rows = json.load(open(infile, encoding="utf-8"))
    # resume: carry over anything already drafted/reviewed in a prior run
    prior = {}
    if os.path.exists(outfile):
        for r in json.load(open(outfile, encoding="utf-8")):
            if r.get("et"):
                prior[(r["file"], r["label"], r["box"])] = r
    memory = json.load(open(memfile, encoding="utf-8")) if os.path.exists(memfile) else {}
    gloss = Glossary(opt("--glossary", "tools/glossary.json"))
    redo_mt = "--redo-mt" in sys.argv          # re-translate existing mt rows

    for r in rows:
        r.setdefault("et", "")
        r.setdefault("et_src", "")
        p = prior.get((r["file"], r["label"], r["box"]))
        if p:
            r["et"], r["et_src"] = p["et"], p.get("et_src", "")
            if p.get("flag"):
                r["flag"] = p["flag"]
        if redo_mt and r.get("et_src") == "mt":
            r["mt_raw"] = r["et"]               # keep pre-glossary NMT for reference
            r["et"], r["et_src"] = "", ""       # requeue (memory/pe rows untouched)

    # unique English still needing a draft
    todo = {}
    for r in rows:
        if not r["et"] and r["en"]:
            todo.setdefault(r["en"], [])
    uniques = list(todo)
    if limit:
        uniques = uniques[:limit]

    resolved = {}          # en -> (et, src)
    mt_queue = []
    for en in uniques:
        if en in memory:
            resolved[en] = (memory[en], "memory")
        else:
            mt_queue.append(en)

    print(f"{len(rows)} rows | {len(todo)} unique to fill | "
          f"{len(resolved)} from memory | {len(mt_queue)} to NMT")

    def write_back():
        by_en = {}
        for r in rows:
            if not r["et"] and r["en"] in resolved:
                et, src = resolved[r["en"]]
                r["et"], r["et_src"] = et, src
                if tokens(r["en"]) != tokens(et):
                    r["flag"] = "check"
                elif r.get("flag") == "check":
                    del r["flag"]
        json.dump(rows, open(outfile, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)

    for i in range(0, len(mt_queue), batch):
        chunk = mt_queue[i:i + batch]
        if gloss.enabled:
            masked = [gloss.mask(en) for en in chunk]
            out = translate_batch([m[0] for m in masked])
            for en, (_, rmap), et in zip(chunk, masked, out):
                resolved[en] = (gloss.restore(et, rmap), "mt")
        else:
            for en, et in zip(chunk, translate_batch(chunk)):
                resolved[en] = (et, "mt")
        write_back()
        done = min(i + batch, len(mt_queue))
        print(f"  NMT {done}/{len(mt_queue)}", end="\r", file=sys.stderr)
        time.sleep(0.2)
    write_back()

    flagged = sum(1 for r in rows if r.get("flag") == "check")
    filled = sum(1 for r in rows if r["et"])
    print(f"\n{filled}/{len(rows)} rows have a draft "
          f"({flagged} flagged for token review) -> {outfile}")


if __name__ == "__main__":
    main()
