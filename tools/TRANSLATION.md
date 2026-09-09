# Estonian translation tooling

Helpers for translating pokecrystal's text into Estonian, adapted from the
`pocketrgb-en` (pokered → Estonian) workflow. All of them are Python and run
from a project virtualenv.

## Setup (once)

```bash
make -C tools venv          # creates tools/.venv and installs requirements.txt
```

Homebrew's system Python is PEP 668 "externally managed", so the deps
(`pyphen`, `phunspell`, `termcolor`) live in `tools/.venv`, which is
git-ignored.

## The loop: discover → seed → wrap → validate

### 1. discover — what needs translating

```bash
tools/.venv/bin/python tools/discover.py               # string inventory by category
tools/.venv/bin/python tools/discover.py --remaining HEAD   # files untouched vs a baseline
```

Use the inventory to scope the job; once translation is underway, pin a
baseline commit (the pristine English tree) and use `--remaining <ref>` as the
robust "what's left" meter. All-caps names (pokémon/move/item/type) stay
English by convention and show up as `trivial`.

### 1b. draft — machine-translate the worksheet (optional first pass)

Extract the English into a worksheet, then draft Estonian for it:

```bash
tools/.venv/bin/python tools/pc_extract.py tools/   # -> tools/et_untranslated.json (et="")
make -C tools translate                             # -> tools/et_draft.json
make -C tools translate ARGS="--limit 50"           # small trial run
```

`translate.py` fills each row's `et`: exact matches from the pokered memory
(`pocketred_et_memory.json`, human-reviewed) win, everything else is drafted by
the TartuNLP NMT API (https://api.tartunlp.ai). Each row carries an `et_src`
(`memory` / `mt`) so you know what to trust; rows whose game tokens
(`<PLAYER>`, `#MON`, `{RAM}`) changed in translation are flagged `check`. Unique
strings are translated once, and the run is resumable (rerun to continue; edited
rows are kept). Set `TARTUNLP_API_KEY` for higher rate limits.

The NMT output is a **draft** — e.g. it rendered "groom" as "peigmeheks"
(bridegroom) — so review every `mt` row before seeding it.

**Glossary** (`tools/glossary.json`): before each NMT call, game terms are
masked and restored so the model can't mangle them — lowercase type words get
their Estonian root (`bug #MON` → `putuk #MON`), proper nouns are protected
(kept English: `MAY:` stays `MAY:`), and caps overrides map to the pokered
Estonian (`TOWN MAP` → `LINNA KAART`). Extend it as terminology decisions are
made. Re-run the machine rows through an updated glossary with:

```bash
make -C tools translate ARGS="tools/et_draft.json --out tools/et_draft.json --redo-mt"
```

`--redo-mt` re-translates only `et_src:"mt"` rows (memory and hand-edited `pe`
rows are kept) and stashes the previous machine output in `mt_raw`.

### 1c. post-edit — correct the draft (Claude / human)

The glossary fixes terminology, not idiom or word-sense. A reviewer (or Claude)
corrects the drafted `et`, sets `et_src:"pe"`, and the row is then trusted and
kept across re-runs. This is the bulk of the quality work; NMT is scaffolding.

### 2. seed — write Estonian as `;;` lines

Above an English text block, write the translation, **one `;;` line per
textbox**. Consecutive `;;` lines become successive `para` boxes, so paragraph
breaks are preserved. Use the same control tokens as the source
(`<PLAYER>`, `<RIVAL>`, `#` for POKé, `{d:VAR}` prints, …):

```
;;Tere <PLAYER>! Mina olen professor ELM.
;;Palun aita mul uurida #MONE!
ProfElmText:
	text "Hi, <PLAYER>! I'm"
	line "PROF. ELM."
	...
	done
```

### 3. wrap — bake the `;;` lines into the block

```bash
make -C tools mark FILE=maps/ElmsLab.asm      # a file
tools/.venv/bin/python tools/mark.py maps      # or a whole directory
```

`mark.py` word-wraps each `;;` box to the 18-tile line width (Estonian
hyphenation via `pyphen`), emits `text`/`line`/`cont`/`para`, and replaces the
old English up to the block terminator (`done`/`prompt`/`text_end`/…). It only
rewrites the span between the `;;` lines and the terminator and stops at any
label or non-text macro, so surrounding map-script code is never touched.
Blocks with no `;;` above them are left alone, so it is safe to re-run.
Add `--stdout` to preview without writing.

### 4. validate

```bash
make -C tools check DIR=maps      # flag any line wider than 18 tiles
make -C tools spell DIR=maps      # et_EE spell-check of ;; lines
```

`check-line-length.py` measures on-screen tiles (see `textwidth.py`): `#`→4,
combined apostrophes (`'t`, `'s`, …)→1, `<PLAYER>`/`<RIVAL>`→7, `{…}`→~2. It
reports zero false positives on the shipped English tree. `spellcheck.py` runs
the `et_EE` Hunspell dictionary over `;;` lines; extend its `ALLOW` set (and
`cspell.json` for the editor) with game proper nouns.

## Files

| file | purpose |
|---|---|
| `discover.py` | inventory / progress of translatable text |
| `mark.py` | seed & word-wrap `;;` lines into text blocks |
| `check-line-length.py` | flag over-wide lines |
| `spellcheck.py` | Estonian spell-check of `;;` lines |
| `textwidth.py` | shared on-screen tile-width measurement |
| `requirements.txt` | Python deps for the venv |

Dex entries (`data/pokemon/dex_entries/`) use `db`/`next`/`page` rather than
`text`, so they are out of scope for `mark.py`; translate those from a flat
description list as in pokered's `generate-pokemon-descriptions.py`.
