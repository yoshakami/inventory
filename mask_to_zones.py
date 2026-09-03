"""Turn a color-mask image into bounding boxes. No AI.

In GIMP / Photoshop:
  1. Open the furniture photo.
  2. Add an empty layer (transparent background).
  3. Fill each compartment with a unique hex color:
       Case 1  = #000001
       Case 2  = #000002
       ...
       Case 54 = #000036
  4. Hide the photo layer, export the color layer as PNG.

Transparent pixels and #000000 are ignored.

Usage:
  python mask_to_zones.py mask.png
  python mask_to_zones.py mask.png -o zones.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict

from PIL import Image

MIN_PIXELS = 20


def hex_color(r: int, g: int, b: int) -> str:
    return f"#{r:02X}{g:02X}{b:02X}"


def color_to_slot(r: int, g: int, b: int) -> int:
    return (r << 16) + (g << 8) + b


def mask_to_zones(path: str, min_pixels: int = MIN_PIXELS) -> dict:
    img = Image.open(path).convert("RGBA")
    width, height = img.size
    data = img.getdata()

    stats = defaultdict(lambda: {
        "minx": width, "miny": height, "maxx": 0, "maxy": 0,
        "count": 0, "sumx": 0, "sumy": 0,
    })

    for i, pixel in enumerate(data):
        r, g, b, a = pixel
        if a < 128:
            continue
        if r == 0 and g == 0 and b == 0:
            continue
        x = i % width
        y = i // width
        s = stats[(r, g, b)]
        if x < s["minx"]:
            s["minx"] = x
        if y < s["miny"]:
            s["miny"] = y
        if x > s["maxx"]:
            s["maxx"] = x
        if y > s["maxy"]:
            s["maxy"] = y
        s["count"] += 1
        s["sumx"] += x
        s["sumy"] += y

    zones = []
    for (r, g, b), s in stats.items():
        if s["count"] < min_pixels:
            continue
        x1, y1, x2, y2 = s["minx"], s["miny"], s["maxx"], s["maxy"]
        bw = max(1, x2 - x1 + 1)
        bh = max(1, y2 - y1 + 1)
        zones.append({
            "color": hex_color(r, g, b),
            "slot": color_to_slot(r, g, b),
            "pixel_count": s["count"],
            "bbox_px": [x1, y1, x2, y2],
            "x": 100.0 * x1 / width,
            "y": 100.0 * y1 / height,
            "w": 100.0 * bw / width,
            "h": 100.0 * bh / height,
            "cx": 100.0 * (s["sumx"] / s["count"]) / width,
            "cy": 100.0 * (s["sumy"] / s["count"]) / height,
        })

    zones.sort(key=lambda z: z["slot"])
    return {
        "width": width,
        "height": height,
        "zones": zones,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Color mask → JSON bounding boxes")
    parser.add_argument("mask", help="PNG color mask (one unique hex per compartment)")
    parser.add_argument("-o", "--output", help="Write JSON here (default: stdout)")
    parser.add_argument("--min-pixels", type=int, default=MIN_PIXELS)
    args = parser.parse_args(argv)

    result = mask_to_zones(args.mask, min_pixels=args.min_pixels)
    text = json.dumps(result, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text)
            f.write("\n")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
