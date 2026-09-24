# /// script
# requires-python = ">=3.11"
# dependencies = ["fonttools[woff]", "pillow"]
# ///
"""Generate QuickScribe app icons: a white "Q" in Geist semibold (the font and
weight of the "QuickScribe" title in the nav rail) on the brand blue.

Writes into frontend/public/:
  favicon.svg, favicon.ico (16/32/48), favicon-16/32.png
  apple-touch-icon.png (180, full-bleed: Safari/macOS "Add to Dock" masks it)
  icon-192.png, icon-512.png            (manifest, purpose "any": rounded
                                          square with a macOS-style margin)
  icon-maskable-512.png                  (manifest, purpose "maskable")

Run from v2/frontend:  uv run scripts/make_icons.py
"""

from __future__ import annotations

import io
from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from PIL import Image, ImageChops, ImageDraw

BLUE = "#0078D4"  # nav rail background (NavigationRail.tsx)
WEIGHT = 600  # Tailwind font-semibold, as on the nav rail title
FRONTEND = Path(__file__).resolve().parent.parent
FONT = FRONTEND / "node_modules/@fontsource-variable/geist/files/geist-latin-wght-normal.woff2"
OUT = FRONTEND / "public"

MASTER = 1024  # every PNG is drawn at 4x this then downsampled
SS = 4


def q_outline():
    """Return (glyph set, Q glyph name, Q bbox in font units)."""
    font = TTFont(io.BytesIO(FONT.read_bytes()))
    font = instancer.instantiateVariableFont(font, {"wght": WEIGHT})
    glyphs = font.getGlyphSet()
    name = font.getBestCmap()[ord("Q")]
    bp = BoundsPen(glyphs)
    glyphs[name].draw(bp)
    return glyphs, name, bp.bounds


def q_path_svg(glyphs, name, bounds, box: float, cx: float, cy: float) -> str:
    """SVG path data for Q scaled so its height is `box`, centred at (cx, cy)."""
    xmin, ymin, xmax, ymax = bounds
    s = box / (ymax - ymin)
    # font units are y-up; flip, scale, and centre the glyph's bounding box
    tx = cx - (xmin + xmax) / 2 * s
    ty = cy + (ymin + ymax) / 2 * s
    pen = SVGPathPen(glyphs)
    glyphs[name].draw(TransformPen(pen, (s, 0, 0, -s, tx, ty)))
    return pen.getCommands()


def polygons(glyphs, name, bounds, box, cx, cy, steps=24):
    """Flatten the glyph into polygons (for Pillow) with the same transform."""
    from fontTools.pens.recordingPen import DecomposingRecordingPen

    xmin, ymin, xmax, ymax = bounds
    s = box / (ymax - ymin)
    tx = cx - (xmin + xmax) / 2 * s
    ty = cy + (ymin + ymax) / 2 * s
    T = lambda p: (p[0] * s + tx, -p[1] * s + ty)  # noqa: E731

    rec = DecomposingRecordingPen(glyphs)
    glyphs[name].draw(rec)
    polys, cur, last = [], [], None
    for op, args in rec.value:
        if op == "moveTo":
            cur, last = [T(args[0])], args[0]
        elif op == "lineTo":
            cur.append(T(args[0]))
            last = args[0]
        elif op == "qCurveTo":
            # TrueType implied on-curve points between consecutive off-curve points
            pts = list(args)
            offs, on = pts[:-1], pts[-1]
            seq = [last]
            for i, off in enumerate(offs):
                seq.append(off)
                nxt = offs[i + 1] if i + 1 < len(offs) else None
                seq.append(((off[0] + nxt[0]) / 2, (off[1] + nxt[1]) / 2) if nxt else on)
            for i in range(0, len(seq) - 2, 2):
                p0, p1, p2 = seq[i], seq[i + 1], seq[i + 2]
                for k in range(1, steps + 1):
                    t = k / steps
                    x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t**2 * p2[0]
                    y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t**2 * p2[1]
                    cur.append(T((x, y)))
            last = on
        elif op == "curveTo":
            p0, (p1, p2, p3) = last, args
            for k in range(1, steps + 1):
                t = k / steps
                x = ((1 - t) ** 3 * p0[0] + 3 * (1 - t) ** 2 * t * p1[0]
                     + 3 * (1 - t) * t**2 * p2[0] + t**3 * p3[0])
                y = ((1 - t) ** 3 * p0[1] + 3 * (1 - t) ** 2 * t * p1[1]
                     + 3 * (1 - t) * t**2 * p2[1] + t**3 * p3[1])
                cur.append(T((x, y)))
            last = p3
        elif op in ("closePath", "endPath"):
            if len(cur) > 2:
                polys.append(cur)
            cur = []
    return polys


def render(glyphs, name, bounds, *, inset: float, radius: float, q_height: float) -> Image.Image:
    """Master image. inset/radius/q_height are fractions of the canvas."""
    n = MASTER * SS
    bg = Image.new("L", (n, n), 0)
    d = ImageDraw.Draw(bg)
    a, b = inset * n, n - inset * n
    d.rounded_rectangle((a, a, b, b), radius=radius * n, fill=255)

    # Even-odd fill: XOR each contour so the counter (hole in the Q) stays open
    glyph = Image.new("1", (n, n), 0)
    for poly in polygons(glyphs, name, bounds, q_height * n, n / 2, n / 2):
        contour = Image.new("1", (n, n), 0)
        ImageDraw.Draw(contour).polygon(poly, fill=1)
        glyph = ImageChops.logical_xor(glyph, contour)

    img = Image.new("RGBA", (n, n), BLUE)
    img.putalpha(bg)
    white = Image.new("RGBA", (n, n), "white")
    img.paste(white, (0, 0), glyph.convert("L"))
    img.putalpha(bg)
    return img.resize((MASTER, MASTER), Image.LANCZOS)


def save_png(img: Image.Image, size: int, name: str) -> None:
    img.resize((size, size), Image.LANCZOS).save(OUT / name, optimize=True)


def main() -> None:
    glyphs, name, bounds = q_outline()

    # Full-bleed square: favicons (tiny, so a small corner radius only),
    # apple-touch-icon (OS applies its own mask), maskable.
    fav = render(glyphs, name, bounds, inset=0, radius=0.16, q_height=0.62)
    bleed = render(glyphs, name, bounds, inset=0, radius=0, q_height=0.56)
    # Maskable safe zone is the central 80% circle: keep the Q well inside.
    maskable = render(glyphs, name, bounds, inset=0, radius=0, q_height=0.46)
    # macOS app-icon grid: 824/1024 body, ~22.5% corner radius, transparent margin.
    macos = render(glyphs, name, bounds, inset=100 / 1024, radius=185 / 1024, q_height=0.46)

    for size in (16, 32):
        save_png(fav, size, f"favicon-{size}.png")
    fav.resize((256, 256), Image.LANCZOS).save(
        OUT / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)]
    )
    save_png(bleed, 180, "apple-touch-icon.png")
    save_png(macos, 192, "icon-192.png")
    save_png(macos, 512, "icon-512.png")
    save_png(maskable, 512, "icon-maskable-512.png")

    # Vector favicon with the glyph as a path (no font dependency)
    d = q_path_svg(glyphs, name, bounds, 0.62 * 512, 256, 256)
    (OUT / "favicon.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">\n'
        f'  <rect width="512" height="512" rx="82" fill="{BLUE}"/>\n'
        f'  <path fill="#fff" fill-rule="evenodd" d="{d}"/>\n'
        "</svg>\n"
    )
    print("wrote", sorted(p.name for p in OUT.iterdir()))


if __name__ == "__main__":
    main()
