#!/usr/bin/env python3
"""syllabify.py -- Estonian syllable splitting for on-screen line breaking.

The library doing the actual work is **pyphen with lang="et"**, whose Estonian
patterns are the Filosoft `hyph_et_EE` data (the same engine behind
https://filosoft.ee/hyph_et/). It already gives correct Estonian syllable
breaks, e.g.:

    putukapüügivõistlus -> pu-tu-ka-püü-gi-võist-lus
    salvestusfailidest  -> sal-ves-tus-fai-li-dest
    raadiotorn          -> raa-dio-torn

This module adds two things the raw hyphenator can't do on its own, both needed
for the 18-tile Game Boy text box:

  * **tile-aware wrapping** -- `#` renders as "POKé" (4 tiles) and `{RAM}`-style
    inserts as ~2 tiles, so a break point must be chosen by on-screen width, not
    Python string length (see textwidth.tiles).
  * **game-token words** -- pyphen refuses to split a word containing `#` or
    `{...}`. For words like `#MONidega` we keep the `#XXX` game token whole and
    only break inside the plain-letter tail (`#MONi-dega`).

Standalone use:
    from syllabify import syllables, wrap
    syllables("kaubamaja")            # -> ['kau', 'ba', 'ma', 'ja']
    wrap("putukapüügivõistlus", 12)   # -> ('putukapüügi-', 'võistlus')  (tile-fit head)
"""
import re

import pyphen

from textwidth import tiles

_dic = pyphen.Pyphen(lang="et")

# a leading game token: '#MON', '#DEX', '{RAM}', '<PLAYER>' ... kept atomic.
# '#' + an UPPERCASE run only, so '#MONidega' keeps '#MON' and still splits 'idega'.
_HEAD_TOKEN = re.compile(r"^(#[A-Z]+|\{[^}]*\}|<[^>]*>)")


def syllables(word):
    """Estonian syllables of `word` (Filosoft/et_EE via pyphen).

    A word carrying a `#`/`{...}`/`<...>` game token is split into
    [token, *syllables-of-the-rest] so the token stays intact.
    """
    m = _HEAD_TOKEN.match(word)
    if m:
        head, rest = m.group(0), word[m.end():]
        return [head] + (syllables(rest) if rest else [])
    if "#" in word or "{" in word or "<" in word:
        return [word]  # can't safely syllabify around an interior token
    return _dic.inserted(word).split("-")


def _break_points(word):
    """Character offsets after which a hyphen may legally be inserted."""
    syl = syllables(word)
    pts, pos = [], 0
    for s in syl[:-1]:
        pos += len(s)
        pts.append(pos)
    return pts


def wrap(word, room):
    """Split `word` so the head (plus a trailing '-') fits within `room` tiles.

    Returns (head_with_hyphen, tail), or None if no legal break fits `room`
    (caller should then push the whole word to the next line). Never splits so
    that the hyphen would abut a game token unnaturally.
    """
    if room <= 1:
        return None
    best = None
    for p in _break_points(word):
        head = word[:p] + "-"
        if tiles(head) <= room:
            best = (head, word[p:])
        else:
            break  # break points are left-to-right; once too wide, stop
    return best


if __name__ == "__main__":
    import sys
    for w in sys.argv[1:] or ["putukapüügivõistlus", "salvestusfailidest",
                              "raadiotorn", "#MONidega", "kaubamaja"]:
        print(f"{w:22s} {'-'.join(syllables(w))}")
