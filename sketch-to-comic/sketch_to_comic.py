#!/usr/bin/env python3
"""Convert hand-drawn sketches into simple comic style images.

Usage:
    python sketch_to_comic.py input.jpg -o out.png
    python sketch_to_comic.py a.jpg b.png c.webp -o strip.png --cols 3
    python sketch_to_comic.py input.jpg -o out.png --style ink --ink 3
"""

import argparse
import os
import sys

import cv2
import numpy as np

CLASSIC_PALETTE = [
    (0xE8, 0x3A, 0x3A),
    (0xF5, 0xA6, 0x23),
    (0xFF, 0xD4, 0x4E),
    (0x6F, 0xC2, 0x6B),
    (0x2B, 0xA8, 0xE6),
    (0x7A, 0x5C, 0xC4),
    (0xE8, 0x8A, 0xC2),
    (0x8D, 0x6E, 0x63),
    (0x56, 0xCF, 0xE0),
    (0x66, 0xBF, 0xBF),
]

BACKGROUND = (0xFF, 0xFF, 0xFF)
INK = (0x28, 0x28, 0x28)


def load_image(path):
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        raise SystemExit(f"cannot read image: {path}")
    if max(img.shape[:2]) > 4096:
        scale = 4096.0 / max(img.shape[:2])
        img = cv2.resize(img, None, fx=scale, fy=scale,
                         interpolation=cv2.INTER_AREA)
    return img


def make_line_mask(img, dilate=2):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, 5)
    _, mask = cv2.threshold(gray, 0, 255,
                            cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    small = cv2.countNonZero(mask)
    if dilate and small:
        ink = cv2.getStructuringElement(
            cv2.MORPH_RECT, (dilate, dilate) if dilate > 1 else (2, 2))
        mask = cv2.dilate(mask, ink)
    return mask


def ink_style(img, dilate=2):
    mask = make_line_mask(img, dilate)
    canvas = np.full(img.shape, BACKGROUND, dtype=np.uint8)
    canvas[mask > 0] = INK
    return canvas, mask


def region_labels(line_mask):
    comp = cv2.bitwise_not(line_mask)
    num, labels, stats, _ = cv2.connectedComponentsWithStats(
        comp, connectivity=8)
    return num, labels, stats


def color_style(img, palette=CLASSIC_PALETTE, dilate=2):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, 5)
    h, w = img.shape[:2]
    line_mask = make_line_mask(img, dilate)
    num, labels, stats = region_labels(line_mask)

    canvas = np.full((h, w, 3), BACKGROUND, dtype=np.uint8)
    order = sorted(range(1, num), key=lambda i: -stats[i, cv2.CC_STAT_AREA])
    base = np.array(palette, dtype=np.float32)
    for idx, comp_id in enumerate(order):
        color = base[comp_id % len(base)]
        region = labels == comp_id
        mean_gray = float(gray[region].mean())
        value = max(60.0, mean_gray) / 255.0
        tint = np.clip(color * value, 0, 255).astype(np.uint8)
        canvas[region] = tint
    canvas[line_mask > 0] = INK
    return canvas, line_mask


def composite_grid(images, cols, gutter, bg=BACKGROUND):
    rows = (len(images) + cols - 1) // cols
    cell_w = max(img.shape[1] for img in images)
    cell_h = max(img.shape[0] for img in images)
    page_w = (cell_w + gutter) * cols + gutter
    page_h = (cell_h + gutter) * rows + gutter
    page = np.full((page_h, page_w, 3), bg, dtype=np.uint8)
    for i, img in enumerate(images):
        r, c = divmod(i, cols)
        x = gutter + (cell_w + gutter) * c
        y = gutter + (cell_h + gutter) * r
        page[y:y + img.shape[0], x:x + img.shape[1]] = img
    return page


def style_convert(img, style, dilate, palette):
    if style == "ink":
        return ink_style(img, dilate)[0]
    if style == "color":
        return color_style(img, palette, dilate)[0]
    raise SystemExit(f"unknown style: {style}")


def parse_args(argv):
    parser = argparse.ArgumentParser(
        prog="sketch_to_comic",
        description="Convert hand-drawn sketches into simple comics.")
    parser.add_argument("inputs", nargs="+", help="sketch image file(s)")
    parser.add_argument("-o", "--output", required=True,
                        help="output image file")
    parser.add_argument("--style", choices=["color", "ink"],
                        default="color",
                        help="comic style (default: color)")
    parser.add_argument("--ink", type=int, default=2, metavar="N",
                        help="ink line dilation in px (default: 2)")
    parser.add_argument("--cols", type=int, default=1,
                        help="columns when composing multiple inputs "
                             "(default: 1)")
    parser.add_argument("--gutter", type=int, default=24,
                        help="panel gutter in px (default: 24)")
    parser.add_argument("--palette", choices=["classic"], default="classic",
                        help="comic color palette (default: classic)")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv or sys.argv[1:])
    palette = CLASSIC_PALETTE
    panels = []
    for path in args.inputs:
        img = load_image(path)
        panel = style_convert(img, args.style, args.ink, palette)
        panels.append(panel)
    page = composite_grid(panels, args.cols, args.gutter)
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    ok, ext = cv2.imencode(
        os.path.splitext(args.output)[1] or ".png", page)
    if not ok:
        raise SystemExit("failed to encode output image")
    with open(args.output, "wb") as fh:
        fh.write(ext.tobytes())
    print(f"wrote {args.output} ({page.shape[1]}x{page.shape[0]})")


if __name__ == "__main__":
    main()