#!/usr/bin/env python3
"""check_contrast.py — WCAG-контраст цветовых токенов из css/style.css.

Python 3.10, только стандартная библиотека.
Запуск из корня репозитория: python tools/check_contrast.py

Код выхода: 0 — ошибок нет (или проверять нечего), 1 — контраст ниже 4.5:1.
Предупреждения на код выхода не влияют.
"""

from __future__ import annotations

import colorsys
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS_PATH = ROOT / "css" / "style.css"
MIN_CONTRAST = 4.5

COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
ROOT_BLOCK_RE = re.compile(r":root\b[^{}]*\{", re.IGNORECASE)
TOKEN_RE = re.compile(r"(--[A-Za-z0-9_-]+)\s*:\s*([^;]+)")
VAR_RE = re.compile(
    r"var\(\s*(--[A-Za-z0-9_-]+)\s*(?:,\s*([^()]*))?\)"
)

BASE_PAIRS = [
    ("--text", "--bg"),
    ("--text", "--bg-elev"),
    ("--text-muted", "--bg"),
    ("--accent", "--bg"),
]


def setup_stdout() -> None:
    """Принудительно UTF-8, чтобы кириллица и «→» не роняли скрипт."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass


@dataclass
class Token:
    raw: str
    line: int


def strip_comments(css: str) -> str:
    """Заменить комментарии пробелами, сохранив номера строк."""
    def blank(match: re.Match) -> str:
        return re.sub(r"[^\n]", " ", match.group(0))

    return COMMENT_RE.sub(blank, css)


def extract_tokens(css: str) -> tuple[dict[str, Token], str]:
    """Достать объявления из всех блоков :root. Возвращает токены и CSS без комментариев."""
    clean = strip_comments(css)
    tokens: dict[str, Token] = {}

    for block in ROOT_BLOCK_RE.finditer(clean):
        start = block.end()
        end = clean.find("}", start)
        if end == -1:
            end = len(clean)
        body = clean[start:end]
        base_line = clean.count("\n", 0, start) + 1

        for declaration in TOKEN_RE.finditer(body):
            name = declaration.group(1)
            raw = declaration.group(2).strip()
            line = base_line + body.count("\n", 0, declaration.start())
            tokens[name] = Token(raw=raw, line=line)

    return tokens, clean


def expand_vars(
    value: str,
    tokens: dict[str, Token],
    seen: set[str] | None = None,
) -> str:
    """Подставить var(--x), чтобы токены могли ссылаться друг на друга."""
    if seen is None:
        seen = set()

    def replace(match: re.Match) -> str:
        name = match.group(1)
        fallback = match.group(2)
        resolved = resolve_token(name, tokens, seen)
        if resolved is not None:
            return resolved
        if fallback is not None:
            return expand_vars(fallback.strip(), tokens, seen)
        return match.group(0)

    return VAR_RE.sub(replace, value)


def resolve_token(
    name: str,
    tokens: dict[str, Token],
    seen: set[str] | None = None,
) -> str | None:
    if seen is None:
        seen = set()
    if name in seen:
        return None
    token = tokens.get(name)
    if token is None:
        return None
    return expand_vars(token.raw, tokens, seen | {name})


def clamp_channel(value: float) -> int:
    return int(round(max(0.0, min(255.0, value))))


def parse_channel(part: str) -> int:
    part = part.strip()
    if part.endswith("%"):
        return clamp_channel(float(part[:-1]) * 255.0 / 100.0)
    return clamp_channel(float(part))


def parse_hue(part: str) -> float:
    part = part.strip().lower()
    if part.endswith("deg"):
        return float(part[:-3])
    if part.endswith("rad"):
        return math.degrees(float(part[:-3]))
    if part.endswith("turn"):
        return float(part[:-4]) * 360.0
    if part.endswith("grad"):
        return float(part[:-4]) * 0.9
    return float(part)


def parse_percent(part: str) -> float:
    part = part.strip()
    if part.endswith("%"):
        return float(part[:-1]) / 100.0
    value = float(part)
    return value / 100.0 if value > 1.0 else value


def parse_color(raw: str) -> tuple[int, int, int] | None:
    """#RGB/#RGBA/#RRGGBB/#RRGGBBAA, rgb()/rgba(), hsl()/hsla().

    Альфа игнорируется: сравниваем rgb-часть, как требует контракт проверки.
    """
    value = re.sub(r"\s*!important\s*$", "", raw.strip(), flags=re.IGNORECASE)
    value = value.strip().lower()
    if not value:
        return None

    if value.startswith("#"):
        digits = value[1:]
        if not re.fullmatch(r"[0-9a-f]+", digits):
            return None
        if len(digits) in (3, 4):
            digits = "".join(char * 2 for char in digits[:3])
        elif len(digits) in (6, 8):
            digits = digits[:6]
        else:
            return None
        return tuple(
            int(digits[index:index + 2], 16) for index in (0, 2, 4)
        )

    rgb_match = re.fullmatch(r"rgba?\((.*)\)", value, re.DOTALL)
    if rgb_match:
        body = rgb_match.group(1).replace("/", " ")
        parts = [part for part in re.split(r"[,\s]+", body.strip()) if part]
        if len(parts) < 3:
            return None
        try:
            return (
                parse_channel(parts[0]),
                parse_channel(parts[1]),
                parse_channel(parts[2]),
            )
        except ValueError:
            return None

    hsl_match = re.fullmatch(r"hsla?\((.*)\)", value, re.DOTALL)
    if hsl_match:
        body = hsl_match.group(1).replace("/", " ")
        parts = [part for part in re.split(r"[,\s]+", body.strip()) if part]
        if len(parts) < 3:
            return None
        try:
            hue = parse_hue(parts[0]) % 360.0
            saturation = parse_percent(parts[1])
            lightness = parse_percent(parts[2])
        except ValueError:
            return None
        red, green, blue = colorsys.hls_to_rgb(
            hue / 360.0,
            max(0.0, min(1.0, lightness)),
            max(0.0, min(1.0, saturation)),
        )
        return (
            clamp_channel(red * 255.0),
            clamp_channel(green * 255.0),
            clamp_channel(blue * 255.0),
        )

    return None


def relative_luminance(rgb: tuple[int, int, int]) -> float:
    def linear(channel: int) -> float:
        value = channel / 255.0
        if value <= 0.03928:
            return value / 12.92
        return ((value + 0.055) / 1.055) ** 2.4

    red, green, blue = (linear(channel) for channel in rgb)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(first: tuple[int, int, int], second: tuple[int, int, int]) -> float:
    lum_first = relative_luminance(first)
    lum_second = relative_luminance(second)
    lighter, darker = max(lum_first, lum_second), min(lum_first, lum_second)
    return (lighter + 0.05) / (darker + 0.05)


def main() -> int:
    setup_stdout()

    if not CSS_PATH.is_file():
        print("style.css не найден — контраст не проверен, ошибок 0")
        return 0

    try:
        source = CSS_PATH.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        print(f"css/style.css → не удалось прочитать файл: {exc}")
        return 1

    tokens, _clean_css = extract_tokens(source)
    if not tokens:
        print("css/style.css: токены :root не найдены — контраст не проверен")
        return 0

    pairs = list(BASE_PAIRS)

    print("=== check_contrast.py ===")
    print()

    errors = 0
    warnings = 0
    checked = 0

    for foreground, background in pairs:
        if foreground not in tokens or background not in tokens:
            continue

        fg_raw = resolve_token(foreground, tokens)
        bg_raw = resolve_token(background, tokens)
        if fg_raw is None or bg_raw is None:
            continue

        fg_rgb = parse_color(fg_raw)
        bg_rgb = parse_color(bg_raw)

        if fg_rgb is None or bg_rgb is None:
            warnings += 1
            line = tokens[foreground].line
            bad_name = foreground if fg_rgb is None else background
            bad_raw = fg_raw if fg_rgb is None else bg_raw
            print(
                f"css/style.css:{line} → предупреждение: {bad_name} — "
                f"не удалось разобрать цвет «{bad_raw[:60]}»"
            )
            continue

        checked += 1
        ratio = contrast_ratio(fg_rgb, bg_rgb)
        line = tokens[foreground].line
        if ratio < MIN_CONTRAST:
            errors += 1
            print(
                f"css/style.css:{line} → {foreground} vs {background} = "
                f"{ratio:.2f}:1 < {MIN_CONTRAST}"
            )
        else:
            print(
                f"css/style.css:{line} → {foreground} vs {background} = "
                f"{ratio:.2f}:1 — ок"
            )

    if checked == 0 and warnings == 0:
        print("css/style.css: цветовых пар для проверки не найдено — ошибок 0")
        return 0

    print()
    print(f"Итог: пар {checked}, ошибок {errors}, предупреждений {warnings}.")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
