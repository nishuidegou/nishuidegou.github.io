#!/usr/bin/env python3
"""Convert hand-drawn sketch lines into laser engraver vector files.

Supports DXF (R12 DOT polyline), SVG, and G-code output.

Usage:
    python sketch_to_laser.py input.jpg -o out.dxf
    python sketch_to_laser.py input.jpg -o out.svg --scale 0.1 --simplify 0.5
    python sketch_to_laser.py input.jpg -o out.gcode --power 800 --feed 3000
"""

import argparse
import os
import sys

import cv2
import numpy as np


def load_image(path):
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        raise SystemExit(f"cannot read image: {path}")
    return img


def make_line_mask(img, denoise=2, min_area=0):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, 5)
    _, mask = cv2.threshold(gray, 0, 255,
                            cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    if min_area > 0:
        num, labels, stats, _ = cv2.connectedComponentsWithStats(
            mask, connectivity=8)
        for comp_id in range(1, num):
            if stats[comp_id, cv2.CC_STAT_AREA] < min_area:
                mask[labels == comp_id] = 0
    return mask


def vectorize(mask, simplify=0.0):
    h, w = mask.shape
    contours, _ = cv2.findContours(mask, cv2.RETR_LIST,
                                   cv2.CHAIN_APPROX_SIMPLE)
    paths = []
    for c in contours:
        if len(c) < 3:
            continue
        if simplify > 0:
            c = cv2.approxPolyDP(c, simplify, True)
        pts = c.reshape(-1, 2).astype(np.float32)
        pts[:, 1] = h - pts[:, 1]
        paths.append(pts)
    return paths


def write_dxf(paths, fh):
    fh.write("0\nSECTION\n2\nHEADER\n0\nENDSEC\n")
    fh.write("0\nSECTION\n2\nENTITIES\n")
    for pts in paths:
        fh.write("0\nPOLYLINE\n8\n0\n66\n1\n70\n1\n")
        for x, y in pts:
            fh.write("0\nVERTEX\n8\n0\n10\n%.4f\n20\n%.4f\n" % (x, y))
        fh.write("0\nSEQEND\n8\n0\n")
    fh.write("0\nENDSEC\n0\nEOF\n")


def write_svg(paths, size, fh):
    w, h = size
    fh.write('<?xml version="1.0" encoding="UTF-8"?>\n')
    fh.write(
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'width="%d" height="%d" viewBox="0 0 %d %d">\n' % (w, h, w, h))
    fh.write('<g fill="none" stroke="#000000" stroke-width="1">\n')
    for pts in paths:
        d = "M %.1f %.1f" % (pts[0, 0], pts[0, 1])
        for x, y in pts[1:]:
            d += " L %.1f %.1f" % (x, y)
        fh.write('  <path d="%s Z"/>\n' % d)
    fh.write("</g>\n</svg>\n")


def write_gcode(paths, fh, power, feed, max_pt=100):
    fh.write("(laser engrave gcode)\n")
    fh.write("G17 G21 G90 G94\n")
    fh.write("M5\n")
    cur = None
    for pts in paths:
        if cur is not None:
            fh.write("G0 X%.3f Y%.3f\n" % (cur[0], cur[1]))
        fh.write("M3 S%d\n" % power)
        for x, y in pts:
            fh.write("G1 X%.3f Y%.3f S%d F%d\n" % (x, y, power, feed))
        cur = pts[-1]
        fh.write("M5\n")
    fh.write("G0 X0 Y0\nM5\n")


def parse_args(argv):
    parser = argparse.ArgumentParser(
        prog="sketch_to_laser",
        description="Convert sketch lines into laser engraver vector files.")
    parser.add_argument("input", help="sketch image file")
    parser.add_argument("-o", "--output", required=True,
                        help="output file (.dxf / .svg / .gcode)")
    parser.add_argument("--scale", type=float, default=1.0,
                        help="multiply coordinates by this factor "
                             "(default: 1)")
    parser.add_argument("--denoise", type=int, default=2,
                        help="median blur kernel size (default: 2)")
    parser.add_argument("--min-area", type=int, default=0,
                        help="drop speckles smaller than N px "
                             "(default: 0 = keep all)")
    parser.add_argument("--simplify", type=float, default=0.0,
                        help="polyline simplification tolerance in px "
                             "(default: 0 = keep all points)")
    parser.add_argument("--power", type=int, default=600,
                        help="laser power, gcode only (default: 600)")
    parser.add_argument("--feed", type=int, default=3000,
                        help="laser feed mm/min, gcode only (default: 3000)")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv or sys.argv[1:])
    img = load_image(args.input)
    mask = make_line_mask(img, args.denoise, args.min_area)
    paths = vectorize(mask, args.simplify)
    if args.scale != 1.0:
        paths = [p * args.scale for p in paths]

    ext = os.path.splitext(args.output)[1].lower()
    h, w = img.shape[:2]
    size = (int(w * args.scale), int(h * args.scale))
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as fh:
        if ext == ".dxf":
            write_dxf(paths, fh)
        elif ext == ".svg":
            write_svg(paths, size, fh)
        elif ext in (".gcode", ".gco", ".nc"):
            write_gcode(paths, fh, args.power, args.feed)
        else:
            raise SystemExit(
                f"unsupported format '{ext}'; use .dxf, .svg, or .gcode")
    npts = sum(len(p) for p in paths)
    print(f"wrote {args.output}: {len(paths)} paths, {npts} points")


if __name__ == "__main__":
    main()