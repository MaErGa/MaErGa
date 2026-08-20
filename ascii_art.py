#!/usr/bin/env python3
"""Convert a photo into the ASCII portrait used in the left panel.

Run this once (or whenever you change the photo); it is not part of the
scheduled workflow.

    python3 ascii_art.py photo.jpg
    python3 ascii_art.py photo.jpg --cols 46 --rows 26 --contrast 2.0 --invert

Writes ascii_art.txt, which today.py reads.
"""

import argparse
import sys

try:
    from PIL import Image, ImageEnhance, ImageOps
except ImportError:
    sys.exit("Pillow is required:  pip install -r requirements.txt")

# Dense ramp, light -> dark. Reversed with --invert for dark backgrounds.
RAMP = " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"

# A monospace cell is roughly twice as tall as it is wide.
CELL_ASPECT = 0.5


def parse_crop(spec):
    """`L,T,R,B` as fractions of the image, e.g. 0.1,0.05,0.9,0.62"""
    if not spec:
        return None
    parts = [float(v) for v in spec.split(",")]
    if len(parts) != 4:
        raise ValueError("--crop needs four comma-separated fractions")
    return parts


def to_ascii(path, cols, rows, contrast, invert, autocontrast,
             equalize=False, gamma=1.0, crop=None):
    img = Image.open(path).convert("L")

    if crop:
        w, h = img.size
        l, t, r, b = crop
        img = img.crop((int(l * w), int(t * h), int(r * w), int(b * h)))

    if autocontrast:
        img = ImageOps.autocontrast(img, cutoff=2)
    if equalize:
        # Redistributes the histogram rather than stretching it: pulls detail
        # out of a narrow midtone band (a face) without clipping the
        # highlights (a white beanie) the way raw contrast does.
        img = ImageOps.equalize(img)
    if gamma != 1.0:
        img = img.point(lambda v: int(255 * (v / 255) ** (1 / gamma)))
    if contrast != 1.0:
        img = ImageEnhance.Contrast(img).enhance(contrast)

    # Crop to the target aspect ratio before resizing so the face is not
    # squashed: the grid is cols x rows cells, each cell CELL_ASPECT wide.
    target = (cols * CELL_ASPECT) / rows
    w, h = img.size
    if w / h > target:
        new_w = int(h * target)
        img = img.crop(((w - new_w) // 2, 0, (w + new_w) // 2, h))
    else:
        new_h = int(w / target)
        img = img.crop((0, (h - new_h) // 2, w, (h + new_h) // 2))

    img = img.resize((cols, rows), Image.LANCZOS)

    ramp = RAMP[::-1] if invert else RAMP
    px = img.load()
    lines = []
    for y in range(rows):
        line = "".join(ramp[px[x, y] * (len(ramp) - 1) // 255] for x in range(cols))
        lines.append(line.rstrip())
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("image")
    p.add_argument("-o", "--out", default="ascii_art.txt")
    p.add_argument("--cols", type=int, default=46)
    p.add_argument("--rows", type=int, default=26)
    p.add_argument("--contrast", type=float, default=1.0)
    p.add_argument("--gamma", type=float, default=1.0,
                   help=">1 lifts the shadows, <1 deepens them")
    p.add_argument("--equalize", action="store_true",
                   help="histogram-equalise; lifts flat midtones, but can\n                        turn fabric and background into noise")
    p.add_argument("--crop", default=None, metavar="L,T,R,B",
                   help="crop to fractions of the source before scaling, "
                        "e.g. 0.10,0.04,0.90,0.62 to frame head and shoulders")
    p.add_argument("--invert", action="store_true",
                   help="reverse the ramp (use for a dark-background portrait)")
    p.add_argument("--no-autocontrast", dest="autocontrast",
                   action="store_false", default=True)
    args = p.parse_args()

    art = to_ascii(args.image, args.cols, args.rows, args.contrast,
                   args.invert, args.autocontrast, args.equalize, args.gamma,
                   parse_crop(args.crop))
    with open(args.out, "w") as fh:
        fh.write(art + "\n")

    print(art)
    print(f"\n-> {args.out}  ({args.cols}x{args.rows})")


if __name__ == "__main__":
    main()
