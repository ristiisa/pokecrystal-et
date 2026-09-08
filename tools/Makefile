.PHONY: all clean venv discover mark check spell

CC := gcc
CFLAGS := -O3 -std=c17 -Wall -Wextra -pedantic

### Estonian translation tooling (Python)
# Set up once:  make -C tools venv
# Seed/wrap:    make -C tools mark FILE=maps/ElmsLab.asm
# Validate:     make -C tools check     (line widths)
#               make -C tools spell     (et_EE spelling of ;; lines)
PY := .venv/bin/python

tools := \
	gbcpal \
	gfx \
	lzcompress \
	make_patch \
	png_dimensions \
	pokemon_animation \
	pokemon_animation_graphics \
	scan_includes \
	stadium

all: $(tools)
	@:

clean:
	$(RM) $(tools)

%: %.c common.h
	$(CC) $(CFLAGS) -o $@ $<

venv: .venv/pyvenv.cfg
.venv/pyvenv.cfg: requirements.txt
	python3 -m venv .venv
	$(PY) -m pip install --quiet --upgrade pip
	$(PY) -m pip install --quiet -r requirements.txt
	@touch .venv/pyvenv.cfg

# recipes run from the repo root so path args (maps, data/text, …) resolve there
discover: venv
	cd .. && tools/$(PY) tools/discover.py $(ARGS)

mark: venv
	cd .. && tools/$(PY) tools/mark.py $(FILE)

check: venv
	cd .. && tools/$(PY) tools/check-line-length.py $(DIR)

spell: venv
	cd .. && tools/$(PY) tools/spellcheck.py $(DIR)
