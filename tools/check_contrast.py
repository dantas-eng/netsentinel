#!/usr/bin/env python3
"""Razão de contraste WCAG 2.1. Uso: check_contrast.py FRONT BACK MIN."""
from math import isfinite
import sys


def channel(value):
    value = value / 255
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def luminance(hex_color):
    raw = hex_color.removeprefix("#")
    if len(raw) != 6:
        raise SystemExit("cor deve ser #RRGGBB")
    r, g, b = (int(raw[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def ratio(front, back):
    lighter, darker = sorted((luminance(front), luminance(back)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def main():
    if len(sys.argv) != 4:
        raise SystemExit("uso: check_contrast.py FRONT BACK MIN")
    front, back, minimum = sys.argv[1], sys.argv[2], float(sys.argv[3])
    if not isfinite(minimum) or minimum <= 0:
        raise SystemExit("MIN deve ser finito e positivo")
    value = ratio(front, back)
    print(f"{value:.2f}:1")
    if value < minimum:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
