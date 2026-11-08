#!/usr/bin/env python3
"""check_html.py — статическая проверка HTML-страниц в корне репозитория.

Python 3.10, только стандартная библиотека.
Запуск из корня репозитория: python tools/check_html.py

Код выхода: 0 — ошибок нет, 1 — есть ошибки.
Предупреждения на код выхода не влияют.
"""

from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

VOID_ELEMENTS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}

# Теги, закрывающий тег которых в HTML5 можно опустить.
OPTIONAL_CLOSE = {
    "html", "head", "body", "p", "li", "dt", "dd", "option", "optgroup",
    "rt", "rp", "tr", "td", "th", "thead", "tbody", "tfoot", "colgroup",
    "caption",
}


def setup_stdout() -> None:
    """Принудительно UTF-8, чтобы кириллица и «→» не роняли скрипт."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass


def is_external(url: str) -> bool:
    return url.startswith("//") or bool(re.match(r"^https?://", url, re.IGNORECASE))


def is_absolute_local(url: str) -> bool:
    if url.startswith(("/", "\\")):
        return True
    if re.match(r"^[A-Za-z]:[\\/]", url):
        return True
    return url.lower().startswith("file:")


def squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


class HtmlChecker(HTMLParser):
    """Собирает находки по одной HTML-странице."""

    def __init__(self, name: str) -> None:
        super().__init__(convert_charrefs=True)
        self.name = name
        self.errors: list[tuple[int, str]] = []
        self.warnings: list[tuple[int, str]] = []

        self.doctypes: list[tuple[int, str]] = []
        self.html_line: int | None = None
        self.html_lang: str | None = None
        self.charsets: list[tuple[int, str]] = []
        self.viewports: list[tuple[int, str]] = []
        self.descriptions: list[tuple[int, str]] = []
        self.title_lines: list[int] = []
        self.title_parts: list[str] = []
        self.in_title = False

        self.h1_lines: list[int] = []
        self.headings: list[tuple[int, int]] = []
        self.main_lines: list[int] = []
        self.ids: dict[str, list[int]] = {}

        self.stack: list[tuple[str, int]] = []
        self.link_stack: list[dict] = []

    # --- служебное ---------------------------------------------------------

    def add_error(self, line: int, message: str) -> None:
        self.errors.append((line, message))

    def add_warning(self, line: int, message: str) -> None:
        self.warnings.append((line, message))

    def _attrs_map(self, tag: str, attrs: list[tuple[str, str | None]], line: int) -> dict[str, str]:
        result: dict[str, str] = {}
        for key, value in attrs:
            if key in result:
                self.add_warning(line, f"атрибут {key} повторяется у <{tag}>")
            result[key] = "" if value is None else value
        return result

    # --- разбор тегов ------------------------------------------------------

    def handle_decl(self, decl: str) -> None:
        line = self.getpos()[0]
        text = decl.strip()
        if text.lower().startswith("doctype"):
            self.doctypes.append((line, text))
        else:
            self.add_warning(line, f"неизвестная декларация <!{text}>")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._handle_start(tag, attrs, self_closing=False)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._handle_start(tag, attrs, self_closing=True)

    def _handle_start(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
        self_closing: bool,
    ) -> None:
        line = self.getpos()[0]
        amap = self._attrs_map(tag, attrs, line)

        if "style" in amap:
            self.add_error(line, "инлайновый style= запрещён — стили только в css/")

        if tag == "html":
            if self.html_line is None:
                self.html_line = line
            self.html_lang = amap.get("lang", self.html_lang)

        if tag == "meta":
            charset = amap.get("charset")
            if charset is not None:
                self.charsets.append((line, charset.strip().lower()))
            name = squash(amap.get("name", "")).lower()
            content = amap.get("content", "").strip()
            if name == "viewport":
                self.viewports.append((line, content))
            elif name == "description":
                self.descriptions.append((line, content))

        if tag == "title" and not any(open_tag == "svg" for open_tag, _ in self.stack):
            self.title_lines.append(line)
            self.in_title = True

        if re.fullmatch(r"h[1-6]", tag):
            level = int(tag[1])
            self.headings.append((level, line))
            if level == 1:
                self.h1_lines.append(line)

        if tag == "main":
            self.main_lines.append(line)

        elem_id = amap.get("id")
        if elem_id is not None:
            elem_id = elem_id.strip()
            if not elem_id:
                self.add_warning(line, "пустой атрибут id")
            else:
                self.ids.setdefault(elem_id, []).append(line)

        if tag == "img":
            if "alt" not in amap:
                self.add_error(line, "у <img> нет атрибута alt")
            elif self.link_stack and amap.get("alt", "").strip():
                self._mark_link_label()

        if tag == "link":
            rels = set(squash(amap.get("rel", "")).lower().split())
            href = amap.get("href", "").strip()
            if href:
                if "stylesheet" in rels and is_external(href):
                    self.add_error(
                        line,
                        f'внешние ресурсы запрещены → <link rel="stylesheet" href="{href}">',
                    )
                elif "stylesheet" in rels and is_absolute_local(href):
                    self.add_error(
                        line,
                        f"путь таблицы стилей должен быть относительным → {href}",
                    )
                elif is_external(href):
                    self.add_warning(
                        line,
                        f"внешний <link> ({' '.join(sorted(rels)) or 'без rel'}) — "
                        f"проверьте, что это не CDN/шрифт → {href}",
                    )

        if tag == "script":
            src = amap.get("src")
            if src is not None:
                src = src.strip()
                if src == "":
                    self.add_error(line, "пустой src у <script>")
                elif is_external(src):
                    self.add_error(
                        line,
                        f'внешние ресурсы запрещены → <script src="{src}">',
                    )
                elif is_absolute_local(src):
                    self.add_error(
                        line,
                        f"путь скрипта должен быть относительным → {src}",
                    )

        if tag in ("a", "button") and not self_closing:
            self.link_stack.append(
                {
                    "tag": tag,
                    "line": line,
                    "text": [],
                    "label": bool(
                        amap.get("aria-label", "").strip()
                        or amap.get("aria-labelledby", "").strip()
                        or amap.get("title", "").strip()
                    ),
                    "img_alt": False,
                }
            )
        elif self.link_stack:
            # aria-label/title на вложенной иконке тоже даёт ссылке имя.
            if amap.get("aria-label", "").strip() or amap.get("title", "").strip():
                self._mark_link_label()

        if tag not in VOID_ELEMENTS and not self_closing:
            self.stack.append((tag, line))

    def _mark_link_label(self) -> None:
        if self.link_stack:
            self.link_stack[-1]["label"] = True

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)
        if self.link_stack:
            self.link_stack[-1]["text"].append(data)

    def handle_endtag(self, tag: str) -> None:
        line = self.getpos()[0]

        if tag == "title":
            self.in_title = False

        if tag in VOID_ELEMENTS:
            self.add_error(line, f"закрывающий </{tag}> у void-элемента")
            return

        if tag in ("a", "button"):
            self._close_link_context(tag)

        self._close_stack_tag(tag, line)

    def _close_link_context(self, tag: str) -> None:
        for index in range(len(self.link_stack) - 1, -1, -1):
            context = self.link_stack[index]
            if context["tag"] != tag:
                continue
            closing = self.link_stack[index:]
            del self.link_stack[index:]
            for item in reversed(closing):
                self._evaluate_link(item)
            return
        # Нет открытого <a>/<button> — об этом сообщит проверка стека тегов.

    def _evaluate_link(self, context: dict) -> None:
        text = squash("".join(context["text"]))
        if not text and not context["label"] and not context["img_alt"]:
            tag = context["tag"]
            self.add_error(
                context["line"],
                f"пустой <{tag}> — нет текста и доступного имени "
                f"(добавьте текст, aria-label или alt у картинки)",
            )

    def _close_stack_tag(self, tag: str, line: int) -> None:
        for index in range(len(self.stack) - 1, -1, -1):
            open_tag, open_line = self.stack[index]
            if open_tag != tag:
                continue
            for above_tag, above_line in self.stack[index + 1:]:
                if above_tag not in OPTIONAL_CLOSE:
                    self.add_error(
                        above_line,
                        f"<{above_tag}> не закрыт (встретился </{tag}> на строке {line})",
                    )
            del self.stack[index:]
            return
        self.add_error(line, f"закрывающий </{tag}> без открывающего тега")

    # --- итоги по документу ------------------------------------------------

    def finish(self) -> None:
        for context in self.link_stack:
            self._evaluate_link(context)
        self.link_stack.clear()

        for tag, line in self.stack:
            if tag not in OPTIONAL_CLOSE and tag not in VOID_ELEMENTS:
                self.add_error(line, f"<{tag}> не закрыт до конца документа")

        self._check_doctype()
        self._check_html_lang()
        self._check_head_meta()
        self._check_headings()
        self._check_main()
        self._check_ids()

    def _check_doctype(self) -> None:
        if not self.doctypes:
            self.add_error(1, "нет <!DOCTYPE html>")
            return
        line, text = self.doctypes[0]
        if not re.fullmatch(r"doctype\s+html", text.strip(), re.IGNORECASE):
            self.add_error(line, f"ожидался <!DOCTYPE html>, найдено <!{text}>")
        for extra_line, _ in self.doctypes[1:]:
            self.add_error(extra_line, "повторный <!DOCTYPE>")

    def _check_html_lang(self) -> None:
        if self.html_line is None:
            self.add_error(1, 'нет тега <html lang="ru">')
            return
        if self.html_lang is None:
            self.add_error(self.html_line, 'у <html> нет lang="ru"')
        elif self.html_lang.strip().lower() != "ru":
            self.add_error(
                self.html_line,
                f'lang="{self.html_lang}" — нужен lang="ru"',
            )

    def _check_head_meta(self) -> None:
        if not self.charsets:
            self.add_error(1, 'нет <meta charset="utf-8">')
        else:
            for line, value in self.charsets:
                if value != "utf-8":
                    self.add_error(line, f'charset="{value}" — нужен utf-8')

        if not self.viewports:
            self.add_error(
                1,
                'нет <meta name="viewport" content="width=device-width, initial-scale=1">',
            )
        else:
            for line, content in self.viewports:
                normalized = re.sub(r"\s+", "", content.lower())
                has_width = "width=device-width" in normalized
                has_scale = bool(
                    re.search(r"initial-scale=1(?:\.0)?(?:,|$)", normalized)
                )
                if not has_width:
                    self.add_error(
                        line,
                        "viewport должен содержать width=device-width",
                    )
                elif not has_scale:
                    self.add_warning(
                        line,
                        "viewport без initial-scale=1 — масштаб на мобильных может отличаться",
                    )
                if "user-scalable=no" in normalized or "maximum-scale=1" in normalized:
                    self.add_warning(
                        line,
                        "viewport запрещает масштабирование (проблема доступности)",
                    )

        if not self.descriptions:
            self.add_error(1, 'нет <meta name="description" content="...">')
        else:
            for line, content in self.descriptions:
                if not content:
                    self.add_error(line, "пустой meta description")
            if len(self.descriptions) > 1:
                for line, _ in self.descriptions[1:]:
                    self.add_warning(line, "повторный meta description")

        if not self.title_lines:
            self.add_error(1, "нет <title>")
        else:
            title = squash("".join(self.title_parts))
            if not title:
                self.add_error(self.title_lines[0], "пустой <title>")
            for line in self.title_lines[1:]:
                self.add_warning(line, "повторный <title>")

    def _check_headings(self) -> None:
        if not self.h1_lines:
            self.add_error(1, "нет <h1>")
        elif len(self.h1_lines) > 1:
            for line in self.h1_lines[1:]:
                self.add_error(
                    line,
                    f"второй <h1> — на странице должен быть ровно один "
                    f"(всего {len(self.h1_lines)})",
                )

        # Первый подзаголовок после h1 обязан быть h2.
        h1_index = None
        for index, (level, _line) in enumerate(self.headings):
            if level == 1:
                h1_index = index
                break
        first_after_h1 = None
        if h1_index is not None:
            for index in range(h1_index + 1, len(self.headings)):
                if self.headings[index][0] != 1:
                    first_after_h1 = index
                    break
        if first_after_h1 is not None:
            level, line = self.headings[first_after_h1]
            if level != 2:
                self.add_error(
                    line,
                    f"первый подзаголовок после h1 — h{level}, ожидался h2",
                )

        seen_h2 = False
        previous_level: int | None = None
        for index, (level, line) in enumerate(self.headings):
            if index == first_after_h1:
                previous_level = level
                if level == 2:
                    seen_h2 = True
                continue
            if previous_level is not None and level > previous_level + 1:
                self.add_error(
                    line,
                    f"прыжок в заголовках: после h{previous_level} сразу h{level} — "
                    f"пропущен h{previous_level + 1}",
                )
            if level == 2:
                seen_h2 = True
            elif level == 3 and not seen_h2:
                self.add_error(line, "h3 идёт раньше первого h2")
            previous_level = level

    def _check_main(self) -> None:
        if not self.main_lines:
            self.add_error(1, "нет <main> — не выделена основная область страницы")

    def _check_ids(self) -> None:
        for value, lines in self.ids.items():
            if len(lines) <= 1:
                continue
            first = lines[0]
            for extra in lines[1:]:
                self.add_error(
                    extra,
                    f'id="{value}" уже использован на строке {first}',
                )


def main() -> int:
    setup_stdout()
    pages = sorted(
        path for path in ROOT.glob("*.html") if path.is_file()
    )
    if not pages:
        print("html-файлов не найдено — ошибок 0")
        return 0

    print("=== check_html.py ===")
    print(f"Проверяю HTML-страниц: {len(pages)}")
    print()

    total_errors = 0
    total_warnings = 0

    for page in pages:
        name = page.name
        try:
            source = page.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            print(f"{name} → не удалось прочитать файл: {exc}")
            total_errors += 1
            continue

        checker = HtmlChecker(name)
        try:
            checker.feed(source)
            checker.close()
            checker.finish()
        except Exception as exc:  # HTMLParser не должен падать, но не рискуем
            print(f"{name} → внутренняя ошибка разбора: {exc}")
            total_errors += 1
            continue

        for line, message in sorted(checker.errors, key=lambda item: item[0]):
            print(f"{name}:{line} → {message}")
        for line, message in sorted(checker.warnings, key=lambda item: item[0]):
            print(f"{name}:{line} → предупреждение: {message}")

        total_errors += len(checker.errors)
        total_warnings += len(checker.warnings)

    print()
    if total_errors == 0:
        print(f"Итог: ошибок нет, предупреждений {total_warnings}.")
    else:
        print(f"Итог: ошибок {total_errors}, предупреждений {total_warnings}.")
    return 0 if total_errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
