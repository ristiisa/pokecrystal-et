"""Shared helper: measure a pokecrystal text string in on-screen tiles.

The Gen 2 text box is a uniform 18 tiles wide for every line macro
(text / line / cont / para / next / page). Control tokens do not occupy
their source width:
  * '#'                 -> "POKé", 4 tiles
  * "'d 'l 'm 'r 's 't 'v" combined-apostrophe glyphs -> 1 tile each
  * <PLAYER> / <RIVAL>  -> a name, worst case 7 tiles
  * <...> other control -> ~1 tile
  * {d:VAR} / {s:VAR}   -> a printed value, approximated as 2 tiles
  * '@'                 -> string terminator, 0 tiles
"""
import re

LINE_WIDTH = 18
APOSTROPHE = ("'d", "'l", "'m", "'r", "'s", "'t", "'v")


def tiles(s):
    """Return the on-screen tile width of a source text string."""
    s = s.replace("@", "")
    for a in APOSTROPHE:
        s = s.replace(a, "\x01")                 # 1 tile
    s = s.replace("#", "\x01\x01\x01\x01")       # POKé = 4 tiles
    s = re.sub(r"<PLAYER>|<RIVAL>", "\x01" * 7, s)
    s = re.sub(r"\{[^}]*\}", "\x01\x01", s)      # printed number/string ~2
    s = re.sub(r"<[^>]+>", "\x01", s)            # other control token ~1
    return len(s)
