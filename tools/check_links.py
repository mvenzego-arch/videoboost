#!/usr/bin/env python3
"""check_links.py — проверка href/src во всех HTML-страницах корня репозитория.

Python 3.10, только стандартная библиотека.
Запуск из корня репозитория: python tools/check_links.py

Код выхода: 0 — ошибок нет, 1 — есть ошибки.
Предупреждения на код выхода не влияют.
"""

from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent

SCHEME_RE = re.compile(r"^([a-zA-Z][a-zA-Z0-9+.-]*):")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:[\\/]")


def setup_stdout() -> None:
    """Принудительно UTF-8, чтобы кириллица и «→» не роняли скрипт."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass


def squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def clip(value: str, limit: int = 120) -> str:
    value = squash(value)
    if len(value) <= limit:
        return value
    return value[: limit - 1] + "…"


def is_https(url: str) -> bool:
    return url.lower().startswith("https://")


def is_protocol_relative(url: str) -> bool:
    return url.startswith("//")


def is_http(url: str) -> bool:
    return bool(re.match(r"^https?://", url, re.IGNORECASE))


def valid_mailto(value: str) -> bool:
    body = value[len("mailto:"):]
    body = body.split("?", 1)[0].strip()
    recipients = [part.strip() for part in body.split(",") if part.strip()]
    if not recipients:
        return False
    for recipient in recipients:
        if not EMAIL_RE.fullmatch(unquote(recipient)):
            return False
    return True


class LinkCollector(HTMLParser):
    """Собирает href/src и id со страницы."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str, str | None, int]] = []
        self.ids: set[str] = set()

    def _collect(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        line = self.getpos()[0]
        for name, value in attrs:
            if name in ("href", "src"):
                self.links.append((tag, name, value, line))
            elif name == "id" and value is not None and value.strip():
                self.ids.add(value.strip())

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._collect(tag, attrs)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._collect(tag, attrs)


def resolve_local(page: Path, raw_path: str, root_absolute: bool) -> tuple[Path, bool]:
    """Возвращает (путь-кандидат, вышел_ли за корень).

    Все страницы лежат в корне репозитория, поэтому локальные цели
    отсчитываются от корня (как требует контракт проверки).
    """
    base = ROOT
    relative = raw_path.lstrip("/") if root_absolute else raw_path
    candidate = base / relative
    root_resolved = ROOT.resolve()
    try:
        resolved = candidate.resolve()
        resolved.relative_to(root_resolved)
    except ValueError:
        return candidate, True
    except OSError:
        return candidate, False
    return resolved, False


def check_local(
    page: Path,
    value: str,
) -> tuple[str | None, str | None]:
    """Вернуть (ошибка, предупреждение) для локальной ссылки."""
    split = urlsplit(value)
    raw_path = unquote(split.path).replace("\\", "/")

    if raw_path == "":
        # Ссылка на текущую страницу (например, "?page=2") — файл есть.
        return None, None

    root_absolute = raw_path.startswith("/")
    warning = None
    if root_absolute:
        warning = f"абсолютный путь от корня — лучше относительный → {value}"

    target, escaped = resolve_local(page, raw_path, root_absolute)
    if escaped:
        return f"битая ссылка → {value} (выходит за пределы репозитория)", warning

    if target.is_dir():
        target = target / "index.html"

    if target.is_file():
        return None, warning

    return f"битая ссылка → {value}", warning


def check_reference(
    page: Path,
    attr: str,
    raw_value: str | None,
    ids: set[str],
) -> tuple[str, str | None, str | None]:
    """Классифицировать одну ссылку.

    Возвращает (вид, ошибка, предупреждение), где вид:
    "external" | "placeholder" | "ok".
    """
    value = "" if raw_value is None else raw_value.strip()

    if value == "":
        return "ok", f"пустой {attr} (нет значения)", None

    if value == "#":
        if attr == "href":
            return "placeholder", None, None
        return "ok", f"фиктивный {attr}=\"#\"", None

    if WINDOWS_DRIVE_RE.match(value):
        return "ok", f"абсолютный путь к файлу — нужен относительный → {value}", None

    if value.lower().startswith("file:"):
        return "ok", f"file:-ссылка — нужен относительный путь → {value}", None

    if is_protocol_relative(value):
        return "external", None, f"нет явного HTTPS (//…) → {clip(value)}"

    if is_http(value):
        warning = None
        if not is_https(value):
            warning = f"внешняя ссылка без HTTPS → {clip(value)}"
        return "external", None, warning

    if value.lower().startswith("mailto:"):
        if valid_mailto(value):
            return "ok", None, None
        return "ok", f"некорректный mailto → {clip(value)}", None

    scheme_match = SCHEME_RE.match(value)
    if scheme_match:
        scheme = scheme_match.group(1).lower()
        warning = None
        if scheme == "javascript":
            warning = f"javascript: ссылка — избегайте → {clip(value)}"
        return "ok", None, warning

    if value.startswith("#"):
        anchor = unquote(value[1:])
        if anchor and anchor in ids:
            return "ok", None, None
        return "ok", f"якорь не найден на странице → #{clip(anchor)}", None

    error, warning = check_local(page, value)
    return "ok", error, warning


def main() -> int:
    setup_stdout()
    pages = sorted(path for path in ROOT.glob("*.html") if path.is_file())
    if not pages:
        print("html-файлов не найдено — ошибок 0")
        return 0

    print("=== check_links.py ===")
    print(f"Проверяю ссылки на страницах: {len(pages)}")
    print()

    external: list[tuple[str, int, str]] = []
    placeholders: list[tuple[str, int, str]] = []
    warnings: list[tuple[str, int, str]] = []
    errors: list[tuple[str, int, str]] = []
    total_links = 0

    for page in pages:
        name = page.name
        try:
            source = page.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            errors.append((name, 1, f"не удалось прочитать файл: {exc}"))
            continue

        collector = LinkCollector()
        try:
            collector.feed(source)
            collector.close()
        except Exception as exc:
            errors.append((name, 1, f"внутренняя ошибка разбора: {exc}"))
            continue

        for tag, attr, value, line in collector.links:
            total_links += 1
            kind, error, warning = check_reference(page, attr, value, collector.ids)
            display = clip(value) if value is not None else ""
            if error:
                errors.append((name, line, f"{error} (<{tag} {attr}>)"))
            if warning:
                warnings.append((name, line, warning))
            if kind == "external":
                external.append((name, line, f"{attr}=\"{display}\" (<{tag}>)"))
            elif kind == "placeholder":
                placeholders.append((name, line, f"{attr}=\"{display}\""))

    if total_links == 0 and not errors and not warnings:
        print("ссылок на страницах не найдено — ошибок 0")
        return 0

    if external:
        print(f"внешние: {len(external)}")
        for name, line, text in external:
            print(f"  {name}:{line} → {text}")
        print()

    if placeholders:
        print(f"placeholder: {len(placeholders)}")
        for name, line, text in placeholders:
            print(f"  {name}:{line} → {text}")
        print()

    if warnings:
        print(f"[предупреждения] {len(warnings)}")
        for name, line, text in warnings:
            print(f"  {name}:{line} → {text}")
        print()

    if errors:
        print(f"[ошибки] {len(errors)}")
        for name, line, text in sorted(errors, key=lambda item: (item[0], item[1])):
            print(f"  {name}:{line} → {text}")
        print()

    print(
        f"Итог: ссылок {total_links}, ошибок {len(errors)}, "
        f"предупреждений {len(warnings)}."
    )
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
