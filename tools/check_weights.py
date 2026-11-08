#!/usr/bin/env python3
"""check_weights.py — контроль весов HTML, css/js и файлов assets/.

Python 3.10, только стандартная библиотека.
Запуск из корня репозитория: python tools/check_weights.py

Код выхода: 0 — ошибок нет, 1 — есть ошибки.
Предупреждения (в том числе мягкий лимит 1.5 МБ) на код выхода не влияют.
"""

from __future__ import annotations

import os
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {"tools", "logs", ".git", ".opencode"}

PAGE_LIMIT = 400 * 1024          # 400 КБ на HTML-файл
ASSET_LIMIT = 200 * 1024         # 200 КБ на файл в assets/
TOTAL_LIMIT = int(1.5 * 1024 * 1024)  # мягкая планка 1.5 МБ

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".avif", ".svg", ".ico", ".gif"}


def setup_stdout() -> None:
    """Принудительно UTF-8, чтобы кириллица и «→» не роняли скрипт."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass


def human(size: int) -> str:
    return f"{size / 1024:.1f} КБ"


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def iter_files(base: Path):
    """Все файлы внутри base, кроме служебных каталогов."""
    if not base.is_dir():
        return
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = sorted(
            name for name in dirnames if name.lower() not in SKIP_DIRS
        )
        for filename in sorted(filenames):
            yield Path(dirpath) / filename


def is_remote(ref: str) -> bool:
    return ref.startswith("//") or bool(
        re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", ref)
    )


class ResourceCollector(HTMLParser):
    """Собирает локальные ресурсы, участвующие в загрузке страницы."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.urls: list[str] = []

    def _collect(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        amap = {key: ("" if value is None else value) for key, value in attrs}

        if tag in ("img", "source"):
            if amap.get("src"):
                self.urls.append(amap["src"])
            srcset = amap.get("srcset", "").strip()
            if srcset:
                first = srcset.split(",", 1)[0].strip()
                if first:
                    self.urls.append(first.split()[0])

        if tag == "video" and amap.get("poster"):
            self.urls.append(amap["poster"])

        if tag == "script" and amap.get("src"):
            self.urls.append(amap["src"])

        if tag == "link":
            rels = set(amap.get("rel", "").lower().split())
            if "stylesheet" in rels and amap.get("href"):
                self.urls.append(amap["href"])

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._collect(tag, attrs)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._collect(tag, attrs)


def resolve_resource(page: Path, ref: str) -> Path | None:
    """Локальный существующий файл или None (внешнее/битое/вне корня)."""
    ref = ref.strip()
    if not ref or ref.startswith("#") or is_remote(ref):
        return None

    split = urlsplit(ref)
    raw_path = unquote(split.path).replace("\\", "/")
    if not raw_path:
        return None

    if raw_path.startswith("/"):
        candidate = ROOT / raw_path.lstrip("/")
    else:
        candidate = page.parent / raw_path

    try:
        resolved = candidate.resolve()
        resolved.relative_to(ROOT.resolve())
    except (ValueError, OSError):
        return None
    return resolved if resolved.is_file() else None


def page_resources(page: Path) -> tuple[int, int, list[str]]:
    """Вес страницы с локальными ресурсами, число картинок и битые src."""
    try:
        source = page.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0, 0, []

    collector = ResourceCollector()
    try:
        collector.feed(source)
        collector.close()
    except Exception:
        return 0, 0, []

    try:
        total = page.stat().st_size
    except OSError:
        return 0, 0, []

    seen: set[Path] = set()
    image_count = 0
    missing: list[str] = []

    for ref in collector.urls:
        resolved = resolve_resource(page, ref)
        if resolved is None:
            if not is_remote(ref) and not ref.strip().startswith("#"):
                missing.append(ref)
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        try:
            total += resolved.stat().st_size
        except OSError:
            continue
        if resolved.suffix.lower() in IMAGE_EXTENSIONS:
            image_count += 1

    return total, image_count, missing


def main() -> int:
    setup_stdout()

    pages = sorted(path for path in ROOT.glob("*.html") if path.is_file())
    assets = list(iter_files(ROOT / "assets")) if (ROOT / "assets").is_dir() else []

    css_js: list[Path] = []
    for folder, suffixes in (("css", {".css"}), ("js", {".js"})):
        base = ROOT / folder
        if base.is_dir():
            css_js.extend(
                path for path in iter_files(base)
                if path.suffix.lower() in suffixes
            )

    if not pages and not assets and not css_js:
        print("html-файлов не найдено — ошибок 0")
        return 0

    print("=== check_weights.py ===")
    print()

    errors: list[str] = []
    warnings: list[str] = []

    if pages:
        print(f"[страницы] {len(pages)}")
        for page in pages:
            name = rel(page)
            try:
                size = page.stat().st_size
            except OSError as exc:
                errors.append(f"{name} → не удалось прочитать размер: {exc}")
                print(f"  {name} → не удалось прочитать размер: {exc}")
                continue

            if size > PAGE_LIMIT:
                errors.append(
                    f"{name} → вес {human(size)} > лимита {human(PAGE_LIMIT)}"
                )
                print(
                    f"  {name} → вес {human(size)} > лимита {human(PAGE_LIMIT)}"
                )
            else:
                print(f"  {name} → HTML {human(size)} / {human(PAGE_LIMIT)} — ок")

            full_size, image_count, missing = page_resources(page)
            print(
                f"  {name} → полный вес с ресурсами (html+css+js+картинки): "
                f"{human(full_size)}, картинок {image_count}"
            )
            for ref in missing:
                warnings.append(f"{name} → ресурс не найден, не учтён → {ref}")
                print(f"  {name} → предупреждение: ресурс не найден → {ref}")
        print()
    else:
        print("html-страниц не найдено")
        print()

    if assets:
        print(f"[assets] {len(assets)}")
        violations = 0
        for asset in assets:
            name = rel(asset)
            try:
                size = asset.stat().st_size
            except OSError as exc:
                errors.append(f"{name} → не удалось прочитать размер: {exc}")
                print(f"  {name} → не удалось прочитать размер: {exc}")
                violations += 1
                continue
            if size <= ASSET_LIMIT:
                continue

            violations += 1
            if asset.suffix.lower() in IMAGE_EXTENSIONS:
                errors.append(
                    f"{name} → вес {human(size)} > лимита {human(ASSET_LIMIT)}"
                )
                print(
                    f"  {name} → вес {human(size)} > лимита {human(ASSET_LIMIT)}"
                )
            else:
                warnings.append(
                    f"{name} → вес {human(size)} > лимита {human(ASSET_LIMIT)} "
                    f"(не картинка — предупреждение)"
                )
                print(
                    f"  {name} → вес {human(size)} > лимита {human(ASSET_LIMIT)} "
                    f"(не картинка — предупреждение)"
                )
        if violations == 0:
            print(f"  проверено файлов: {len(assets)} — превышений нет")
        print()

    total = 0
    for path in pages + css_js:
        try:
            total += path.stat().st_size
        except OSError:
            continue

    print("[общий вес]")
    print(
        f"  сумма html+css+js → {human(total)} / {human(TOTAL_LIMIT)} — "
        f"{'ок' if total <= TOTAL_LIMIT else 'мягкий лимит превышен'}"
    )
    if total > TOTAL_LIMIT:
        warnings.append(
            f"сумма html+css+js → {human(total)} > лимита {human(TOTAL_LIMIT)} "
            f"(мягкая планка, предупреждение)"
        )
    print()

    print(f"Итог: ошибок {len(errors)}, предупреждений {len(warnings)}.")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
