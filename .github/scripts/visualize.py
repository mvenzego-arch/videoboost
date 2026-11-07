# -*- coding: utf-8 -*-
"""Визуализатор репозитория VideoBoost: SVG-карта файлов по размерам.

Запуск: python .github/scripts/visualize.py > output/repository.svg
Только стандартная библиотека. Исключает мусорные и приватные каталоги.
"""
from __future__ import annotations

import html
import math
import sys
from pathlib import Path

SKIP_DIRS = {
    ".git", ".github", ".opencode", "__pycache__", "temp", "tools",
    "logs", "_baseline", "node_modules", "build", "dist", "output",
    "bin", "obj", "publish",
}
SKIP_FILES = {".gitignore", "ui_settings.json"}
PALETTE = ["#4f8cff", "#7c5cff", "#22d3ee", "#34d399", "#fbbf24", "#f472b6"]


def collect(root: Path) -> list[tuple[str, int]]:
    rows: list[tuple[str, int]] = []
    for p in sorted(root.iterdir()):
        if p.is_dir():
            if p.name in SKIP_DIRS:
                continue
            total = 0
            for f in p.rglob("*"):
                if f.is_file() and not any(part in SKIP_DIRS for part in f.parts):
                    try:
                        total += len(f.read_text(encoding="utf-8", errors="ignore").splitlines())
                    except OSError:
                        continue
            if total > 0:
                rows.append((p.name + "/", total))
    for p in sorted(root.iterdir()):
        if p.is_file():
            if p.name in SKIP_FILES or p.suffix in {".exe", ".ico"}:
                continue
            try:
                lines = len(p.read_text(encoding="utf-8", errors="ignore").splitlines())
            except OSError:
                lines = 0
            if lines > 0:
                rows.append((p.name, lines))
    rows.sort(key=lambda r: -r[1])
    return rows


def render(rows: list[tuple[str, int]], out: list[str]) -> None:
    W, H, G = 1080, 320, 10
    total = sum(n for _, n in rows) or 1
    out.append('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" font-family="Segoe UI, sans-serif">' % (W, H))
    out.append(f'<rect width="{W}" height="{H}" fill="#0b0f17"/>')
    title = "Карта репозитория VideoBoost — %d строк кода" % total
    out.append(f'<text x="16" y="30" fill="#e8eef8" font-size="18" font-weight="600">{html.escape(title)}</text>')
    x, y, row_h, max_w = 16, 52, 44, W - 32
    for i, (name, n) in enumerate(rows):
        frac = n / total
        w = max(90, int(max_w * math.sqrt(frac) / math.sqrt(1.0) * 1.0))
        w = min(w, max_w - (x - 16))
        if w < 100 and i > 0:
            continue
        label = f"{html.escape(name)} — {n} стр."
        color = PALETTE[i % len(PALETTE)]
        out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{row_h}" rx="8" fill="{color}" opacity="0.22" stroke="{color}"/>')
        text_w = int(w) - 16
        out.append(f'<text x="{x+8}" y="{y+row_h/2+5:.0f}" fill="#cfe0ff" font-size="13">{html.escape(label)}</text>')
        y += row_h + G
        if y + row_h > H - 12:
            break
    out.append("</svg>")


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    rows = collect(root)
    out: list[str] = []
    render(rows, out)
    sys.stdout.write("\n".join(out) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
