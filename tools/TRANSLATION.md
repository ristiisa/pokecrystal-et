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
