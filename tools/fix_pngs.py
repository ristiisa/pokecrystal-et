#!/usr/bin/env python3
"""fix_pngs.py -- regenerate the Estonian graphics assets (PNG tiles).

Split out from apply_assets.py so the PNG work (which needs Pillow) can be run
on its own -- e.g. after re-exporting a title logo from Photoshop -- without
running the text writeback. Idempotent; safe to run repeatedly and after a
`git checkout` of the target PNGs. Kept OUT of a committed gfx/ diff so upstream
pokecrystal pulls stay clean.

  * gfx/font/font.png  : draw the six õ/š/ž glyphs into tiles $c6-$cb.
  * gfx/title/logo.png : install a custom title logo from tools/assets/logo.png,
    snapped to the 4 DMG shades (optional -- no-op if that file is absent).

Run standalone (`python tools/fix_pngs.py`) or via writeback.py (which calls it).
Needs Pillow.
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT = os.path.join(ROOT, "gfx", "font", "font.png")
LOGO = os.path.join(ROOT, "gfx", "title", "logo.png")
# optional custom title logo: any PNG the user exports (e.g. from Photoshop).
# It is snapped to the 4 DMG shades and installed as LOGO.
LOGO_SRC = os.path.join(ROOT, "tools", "assets", "logo.png")

# charmap value -> (letter, 8x8 glyph). '#'=ink. Caps: 1-row diacritic on row0,
# body rows1-6, row7 empty (matches Ä/Ö/Ü). Lowercase: body rows2-6.
GLYPHS = {
    0xc6: ("õ", ["........", ".##.##..", "..####..", ".#....#.",
                 ".#....#.", ".#....#.", "..####..", "........"]),
    0xc7: ("Õ", [".##.##..", "..###...", ".#...#..", "#.....#.",
                 "#.....#.", ".#...#..", "..###...", "........"]),
    0xc8: ("š", [".#...#..", "..#.#...", "..####..", ".#......",
                 "..####..", "......#.", ".#####..", "........"]),
    0xc9: ("Š", [".#...#..", ".####...", "#....#..", "#.......",
                 ".#####..", "......#.", ".#####..", "........"]),
    0xca: ("ž", [".#...#..", "..#.#...", ".######.", ".....#..",
                 "...##...", "..#.....", ".######.", "........"]),
    0xcb: ("Ž", [".#...#..", "#######.", ".....#..", "....#...",
                 "...#....", "..#.....", "#######.", "........"]),
}


def patch_font():
    try:
        from PIL import Image
    except ImportError:
        print("  (Pillow not installed -- skipping font glyphs; run "
              "`pip install pillow` and rerun to draw õ/š/ž)")
        return False
    im = Image.open(FONT)
    px = im.load()
    cols = im.size[0] // 8
    # sample ink/paper from an existing glyph ('o' = charmap $ae -> tile 46)
    ot = 46
    vals = [px[(ot % cols) * 8 + a, (ot // cols) * 8 + b]
            for a in range(8) for b in range(8)]
    key = (lambda v: v) if isinstance(vals[0], int) else sum
    ink, paper = min(vals, key=key), max(vals, key=key)
    # already drawn?  (tile for $c6 non-blank)
    t = 0xc6 - 0x80
    if any(px[(t % cols) * 8 + a, (t // cols) * 8 + b] == ink
           for a in range(8) for b in range(8)):
        return False
    for v, (_, rows) in GLYPHS.items():
        t = v - 0x80
        tx, ty = (t % cols) * 8, (t // cols) * 8
        for b, row in enumerate(rows):
            for a, ch in enumerate(row):
                px[tx + a, ty + b] = ink if ch == "#" else paper
    im.save(FONT)
    return True


def patch_logo():
    """Install a custom title logo from LOGO_SRC, forced to the 4 DMG shades.

    gfx/title/logo.2bpp is built with `rgbgfx --colors dmg` -> a 2bpp tile
    image accepts only the four greys 0/85/170/255. Photoshop (and most editors)
    export anti-aliased RGB PNGs with dozens of near-colours, which rgbgfx
    rejects. So the user exports however is convenient to tools/assets/logo.png
    and this snaps every pixel to the nearest DMG grey (by luminance -- the
    colour itself is irrelevant, the title screen recolours these greys via a
    GBC palette at runtime) and writes gfx/title/logo.png. No-op if absent."""
    if not os.path.exists(LOGO_SRC):
        return False
    try:
        from PIL import Image
    except ImportError:
        print("  (Pillow not installed -- skipping custom logo)")
        return False
    im = Image.open(LOGO_SRC).convert("L")
    if im.size != (160, 64):
        print(f"  (logo source is {im.size}, resizing to 160x64)")
        im = im.resize((160, 64), Image.LANCZOS)
    levels = (0, 85, 170, 255)
    px = im.load()
    for y in range(64):
        for x in range(160):
            v = px[x, y]
            px[x, y] = min(levels, key=lambda L: abs(L - v))
    im.save(LOGO)
    return True


def main():
    f = patch_font()
    lg = patch_logo()
    print(f"font {'glyphs drawn' if f else 'already has glyphs'}; "
          f"logo {'installed from tools/assets' if lg else 'stock (no tools/assets/logo.png)'}")


if __name__ == "__main__":
    main()
