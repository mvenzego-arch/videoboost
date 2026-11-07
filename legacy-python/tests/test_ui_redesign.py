# -*- coding: utf-8 -*-
"""Тесты визуальной логики редизайна VideoBoost (docs/redesign-spec-v2.md).

Покрывают новую вёрстку main.py: константы ритма, пилюли D1/D3/D4,
строки настроек D2, заглушки D6/D7, слот спиннера D5, шапку и импорт.

Окно Tk всегда withdrawn — suite ничего не показывает пользователю.
Из-за этого проверки, которые в спеке описаны через winfo_ismapped(),
заменены проверкой winfo_manager()/pack_info(): спиннер не удаляется
из pack, слот остаётся на месте.
"""

from __future__ import annotations

import ast
import importlib.util
import subprocess
import sys
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import font as tkfont
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Состояние Tk фиксируем до импорта main: импорт не должен открыть окно.
_TK_ROOT_BEFORE_MAIN = tk._default_root
import main  # noqa: E402  (импорт после настройки sys.path)
_TK_ROOT_AFTER_MAIN = tk._default_root

_MAIN_SOURCE = (PROJECT_ROOT / "main.py").read_text(encoding="utf-8")


# ------------------------------------------------------------------ helpers


def _pair(value) -> tuple:
    """Нормализует padx/pady из pack_info в пару int."""
    if isinstance(value, (tuple, list)):
        return tuple(int(v) for v in value)
    return (int(value), int(value))


def _pack_slot(widget: tk.Misc) -> tuple:
    """Значимые параметры слота pack — чтобы заметить pack_forget/перепаковку."""
    info = widget.pack_info()
    return (
        str(info.get("in")),
        info.get("side"),
        info.get("anchor"),
        info.get("fill"),
        int(info.get("expand", 0)),
        _pair(info.get("padx", 0)),
        _pair(info.get("pady", 0)),
    )


def _text_items(canvas: tk.Canvas) -> list:
    """Все текстовые элементы канвы: (текст, коords, fill, anchor)."""
    items = []
    for item in canvas.find_all():
        if canvas.type(item) == "text":
            items.append((
                canvas.itemcget(item, "text"),
                canvas.coords(item),
                canvas.itemcget(item, "fill"),
                canvas.itemcget(item, "anchor"),
            ))
    return items


class _DummyFileLogger:
    """Не даёт тестам писать в logs\\ продукта."""

    def write(self, text: str) -> None:
        pass

    def close(self) -> None:
        pass


class _DummyDndHook:
    """DragDropHook поднимает WinAPI — в тестах он не нужен."""

    def __init__(self, widget, callback):
        pass


class GuiTestCase(unittest.TestCase):
    """Базовый класс: withdrawn Tk + предсказуемый scaling."""

    scaling = 1.15

    def setUp(self) -> None:
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:  # pragma: no cover - зависит от окружения
            raise unittest.SkipTest(f"Tk недоступен: {exc}")
        self.root.withdraw()
        try:
            self.root.tk.call("tk", "scaling", self.scaling)
        except tk.TclError:
            pass
        self._tmpdir = None
        self._patches: list = []

    def tearDown(self) -> None:
        try:
            self.root.destroy()
        except tk.TclError:
            pass
        for patch in reversed(self._patches):
            try:
                patch.stop()
            except RuntimeError:
                pass
        if self._tmpdir is not None:
            self._tmpdir.cleanup()


class AppGuiTestCase(GuiTestCase):
    """Строит настоящий App на withdrawn-корне, подавляя все побочки."""

    def setUp(self) -> None:
        super().setUp()
        self._tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.prefs_path = Path(self._tmpdir.name) / "ui_settings.json"
        self._patches = [
            # PREFS_FILE — только временный файл, ui_settings.json продукта цел.
            mock.patch.object(main, "PREFS_FILE", self.prefs_path),
            # Не писать в logs\ и не поднимать WinAPI drag&drop.
            mock.patch.object(main, "FileLogger", _DummyFileLogger),
            mock.patch.object(main, "DragDropHook", _DummyDndHook),
            # Не сканировать реальные tools\ и не трогать инструменты.
            mock.patch.object(main.App, "_find_tools", staticmethod(lambda: True)),
            # Никакие диалоги не должны блокировать тест.
            mock.patch.object(main.messagebox, "showinfo"),
            mock.patch.object(main.messagebox, "showerror"),
            mock.patch.object(main.messagebox, "showwarning"),
            mock.patch.object(main.messagebox, "askyesno", return_value=False),
        ]
        for patch in self._patches:
            patch.start()
        try:
            self.app = main.App(self.root)
            self.root.update_idletasks()
        except BaseException:
            for patch in reversed(self._patches):
                patch.stop()
            self._tmpdir.cleanup()
            raise


# --------------------------------------------------------- импорт и сборка


class TestImportSafety(unittest.TestCase):
    def test_import_main_does_not_create_tk_root(self):
        self.assertIsNone(
            _TK_ROOT_BEFORE_MAIN,
            "до импорта main в процессе уже был Tk-корень — тест не сможет "
            "отличить побочку импорта",
        )
        self.assertIs(
            _TK_ROOT_AFTER_MAIN,
            _TK_ROOT_BEFORE_MAIN,
            "импорт main создал Tk-корень (появилось бы окно) — импорт "
            "должен быть без побочек",
        )

    def test_main_module_starts_only_under_dunder_main_guard(self):
        code_lines = [line.strip() for line in _MAIN_SOURCE.splitlines()
                      if line.strip()]
        self.assertEqual(
            code_lines[-2:],
            ['if __name__ == "__main__":', "main()"],
            "в конце main.py должен быть guard __main__, иначе импорт "
            "запустит приложение",
        )
        self.assertTrue(callable(main.main), "main.main должен быть функцией")

    def test_reimport_via_importlib_does_not_open_a_window(self):
        """Повторная загрузка main.py через importlib не создаёт Tk-окно."""
        before = tk._default_root
        spec = importlib.util.spec_from_file_location(
            "main_import_probe", PROJECT_ROOT / "main.py")
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertIs(
            tk._default_root, before,
            "importlib-загрузка main.py создала Tk-корень — будет окно",
        )
        self.assertTrue(callable(module.main))

    def test_main_imports_only_stdlib_and_project_engine(self):
        tree = ast.parse(_MAIN_SOURCE)
        roots: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    roots.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.level:  # относительные импорты внутри проекта
                    continue
                if node.module:
                    roots.add(node.module.split(".")[0])
        allowed = {
            "__future__", "atexit", "ctypes", "json", "math", "os", "queue",
            "re", "sys", "threading", "time", "tkinter", "traceback",
            "pathlib", "typing", "engine",
        }
        self.assertLessEqual(
            roots, allowed,
            f"в main.py появились новые импорты вне stdlib: {sorted(roots - allowed)}",
        )


class TestBuildHealth(unittest.TestCase):
    def test_main_py_compiles_with_py_compile(self):
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", "main.py"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(
            result.returncode, 0,
            "py_compile main.py завершился с ошибкой:\n" + result.stderr,
        )


# ------------------------------------------------------------- константы


class TestPaddingConstants(unittest.TestCase):
    def test_padding_constants_match_spec(self):
        expected = {
            "PAD_H": 12,
            "GRID_GAP": 12,
            "ROW_GY": 4,
            "BTN_GAP": 6,
            "BLOCK_GAP": 8,
            "GAP_LBL_CTRL": 10,
            "CARD_PAD": 10,
        }
        for name, value in expected.items():
            with self.subTest(constant=name):
                self.assertTrue(hasattr(main, name), f"в main.py нет {name}")
                self.assertEqual(
                    getattr(main, name), value,
                    f"{name} должен быть {value}, иначе ритм вёрстки уедет",
                )


class TestLayoutPacks(AppGuiTestCase):
    def _assert_pack(self, title: str, widget: tk.Misc,
                     padx=None, pady=None) -> None:
        info = widget.pack_info()
        if padx is not None:
            self.assertEqual(
                _pair(info["padx"]), padx,
                f"{title}: padx={info['padx']!r}, ожидалось {padx}",
            )
        if pady is not None:
            self.assertEqual(
                _pair(info["pady"]), pady,
                f"{title}: pady={info['pady']!r}, ожидалось {pady}",
            )

    def test_padding_constants_are_applied_to_key_packs(self):
        P = main.PAD_H
        cases = [
            ("панель списка видео", self.app.file_list.master.master,
             (P, P), (0, 0)),
            ("кнопки карточки «1»", self.app.add_btn.master,
             (P, P), (main.BTN_GAP, main.ROW_GY)),
            ("счётчик файлов", self.app.files_count,
             (P, P), (main.ROW_GY, 8)),
            ("пресет-пилюли", self.app.preset_choice,
             (P, P), (0, 0)),
            ("описание пресета", self.app.preset_desc,
             (P, P), (main.ROW_GY, 2)),
            ("строка настроек", self.app.scale_choice.master,
             (P, P), (0, main.ROW_GY)),
            ("строка «Плавность»", self.app.interp_switch.master,
             (P, P), (0, main.ROW_GY)),
            ("строка «Экономить место»", self.app.space_switch.master,
             (P, P), (0, main.ROW_GY)),
            ("ряд кнопок «3»", self.app.start_btn.master,
             (P, P), (main.BTN_GAP, 0)),
            ("ряд прогресса", self.app.spinner.master,
             (P, P), (main.BLOCK_GAP, 0)),
            ("статус запуска", self.app.status_label,
             (P, P), (0, 6)),
            ("заголовок журнала", self.app.clear_log_btn.master,
             (main.CARD_PAD, main.CARD_PAD), (10, 4)),
            ("панель журнала", self.app.log_text.master.master,
             (P, P), (main.GRID_GAP, 0)),
        ]
        for title, widget, padx, pady in cases:
            with self.subTest(point=title):
                self._assert_pack(title, widget, padx=padx, pady=pady)

        self.assertEqual(
            _pair(self.app.progress.pack_info()["padx"]), (0, 8),
            "BoostBar должен стоять в постоянном слоте спиннера (0,8)",
        )
        self.assertEqual(
            _pair(self.app.spinner.pack_info()["padx"]), (0, 6),
            "спиннер: постоянный отступ (0,6)",
        )

    def test_separator_paddings_follow_rhythm(self):
        settings_body = self.app.scale_choice.master.master
        separators = [
            w for w in settings_body.pack_slaves()
            if w.winfo_class() == "Frame"
            and int(w.cget("height")) == 1
            and str(w.cget("bg")) == main.BORDER
        ]
        self.assertGreaterEqual(
            len(separators), 2,
            "в карточке настроек должны быть два разделителя",
        )
        for separator in separators:
            self.assertEqual(
                _pair(separator.pack_info()["pady"]), (6, main.ROW_GY),
                "разделитель настроек: pady=(6, ROW_GY)",
            )
            self.assertEqual(
                _pair(separator.pack_info()["padx"]), (main.PAD_H, main.PAD_H),
                "разделитель настроек: padx=PAD_H",
            )

        left_body = self.app.start_btn.master.master
        start_separators = [
            w for w in left_body.pack_slaves()
            if w.winfo_class() == "Frame"
            and int(w.cget("height")) == 1
            and str(w.cget("bg")) == main.BORDER
        ]
        self.assertEqual(
            len(start_separators), 1,
            "перед карточкой «3» должен быть ровно один разделитель",
        )
        self.assertEqual(
            _pair(start_separators[0].pack_info()["pady"]),
            (main.BLOCK_GAP, main.ROW_GY),
            "разделитель перед «3»: pady=(BLOCK_GAP, ROW_GY)",
        )

        holder = tk.Frame(self.root, bg=main.CARD)
        self.app._make_separator(holder)
        separator = holder.pack_slaves()[-1]
        self.assertEqual(int(separator.cget("height")), 1)
        self.assertEqual(
            _pair(separator.pack_info()["pady"]), (6, main.ROW_GY),
            "_make_separator по умолчанию: pady=(6, ROW_GY)",
        )

    def test_pills_stretch_only_when_three_or_more_options(self):
        # 2 варианта (FPS, Тип видео) — без fill/expand, ширина по контенту.
        for title, pill in (("FPS", self.app.fps_choice),
                            ("Тип видео", self.app.content_choice)):
            info = pill.pack_info()
            with self.subTest(pill=title):
                self.assertEqual(
                    info["fill"], "none",
                    f"{title}: 2-вариантные пилюли не должны заполнять родителя",
                )
                self.assertEqual(
                    int(info["expand"]), 0,
                    f"{title}: 2-вариантные пилюли не должны растягиваться",
                )

        # 3+ вариантов — растяжение по карточке.
        for title, pill in (
            ("Масштаб", self.app.scale_choice),
            ("Модель", self.app.model_choice),
            ("Кодировщик", self.app.encoder_choice),
            ("Качество", self.app.quality_choice),
            ("Tile", self.app.tile_choice),
        ):
            info = pill.pack_info()
            with self.subTest(pill=title):
                self.assertEqual(
                    info["fill"], "x",
                    f"{title}: 3+ вариантов должны заполнять ширину",
                )
                self.assertEqual(
                    int(info["expand"]), 1,
                    f"{title}: 3+ вариантов должны растягиваться",
                )

        self.assertEqual(
            self.app.preset_choice.pack_info()["fill"], "x",
            "пресет-пилюли должны растягиваться по карточке",
        )


# --------------------------------------------------------------- пилюли


class TestPillChoice(GuiTestCase):
    def test_two_option_pills_have_content_widths_and_no_stretch_weights(self):
        pill = main.PillChoice(self.root, main.FPS_PILLS, "60", big=False)
        self.assertEqual(pill.grid_size(), (2, 1))
        self.assertEqual(pill.h, 28, "без подписи и big=False высота 28")

        for index, (key, title, _caption) in enumerate(pill.options):
            with self.subTest(option=key):
                canvas = pill._canv[key]
                measure = pill._font_title.measure(title)
                expected = max(96, min(150, measure + 30))
                self.assertEqual(
                    int(canvas.cget("width")), expected,
                    f"{title}: ширина должна быть clamp(96,150,measure+30)",
                )
                self.assertGreaterEqual(int(canvas.cget("width")), 96)
                self.assertLessEqual(int(canvas.cget("width")), 150)
                self.assertGreaterEqual(
                    int(canvas.cget("width")), measure + 4,
                    f"{title}: текст не должен клиппиться",
                )
                self.assertEqual(
                    pill.columnconfigure(index)["weight"], 0,
                    "у 2-вариантной строки не должно быть grid-растяжения",
                )

        self.root.update_idletasks()
        self.assertLessEqual(
            pill.winfo_reqwidth(), 2 * 150 + 12,
            "2-вариантная строка не должна запрашивать ширину на весь родитель",
        )

    def test_short_title_width_is_clamped_to_96(self):
        pill = main.PillChoice(
            self.root, [("a", "x", ""), ("b", "y", "")], "a", big=False)
        self.assertEqual(
            int(pill._canv["a"].cget("width")), 96,
            "короткий заголовок: нижняя граница 96px",
        )

    def test_medium_title_width_is_measure_plus_thirty(self):
        font = tkfont.Font(family="Segoe UI", size=9, weight="bold")
        candidates = [
            "abcdefghijklmnop", "abcdefghijklmnopq", "abcdefghijklmno",
            "Название варианта", "Средний вариант",
        ]
        chosen = next(
            (text for text in candidates if 96 < font.measure(text) + 30 < 150),
            None,
        )
        if chosen is None:  # pragma: no cover - зависит от метрик шрифта
            self.skipTest("метрики Segoe UI не дают среднюю ширину для проверки")
        pill = main.PillChoice(
            self.root, [("a", chosen, ""), ("b", "b", "")], "a", big=False)
        width = int(pill._canv["a"].cget("width"))
        self.assertEqual(
            width, font.measure(chosen) + 30,
            "средний заголовок: ширина строго measure+30, без обрезки до 96",
        )
        self.assertGreater(width, 96)
        self.assertLess(width, 150)

    def test_long_title_width_is_clamped_to_150(self):
        long_title = "Очень длинное название варианта " * 4
        pill = main.PillChoice(
            self.root, [("a", long_title, ""), ("b", "b", "")], "a",
            big=False)
        self.assertEqual(
            int(pill._canv["a"].cget("width")), 150,
            "длинный заголовок: верхняя граница 150px",
        )

    def test_five_option_pills_use_grid_stretch_weights(self):
        pill = main.PillChoice(self.root, main.SCALE_PILLS, "x2", big=False)
        self.assertEqual(pill.grid_size(), (5, 1))
        self.assertEqual(
            pill.h, 28,
            "5 вариантов без подписи, big=False: высота 28",
        )
        default_width = int(tk.Canvas(self.root).cget("width"))
        for index in range(5):
            self.assertEqual(
                pill.columnconfigure(index)["weight"], 1,
                "5 вариантов: каждая колонка должна растягиваться",
            )
        for key, canvas in pill._canv.items():
            with self.subTest(option=key):
                self.assertEqual(
                    int(canvas.cget("width")), default_width,
                    "5 вариантов: ширина не фиксируется по контенту, "
                    "растяжение делает grid",
                )

    def test_no_caption_heights_are_44_and_28(self):
        for big, expected in ((True, 44), (False, 28)):
            with self.subTest(big=big):
                pill = main.PillChoice(
                    self.root, [("a", "A", ""), ("b", "B", "")], "a",
                    big=big)
                self.assertEqual(
                    pill.h, expected,
                    "без подписи действуют прежние высоты 44 (big) / 28",
                )

    def test_caption_height_follows_font_metrics(self):
        pill = main.PillChoice(self.root, main.PRESET_PILLS, "balanced",
                               big=True)
        title_ls = pill._font_big.metrics("linespace")
        caption_ls = pill._font_small.metrics("linespace")
        self.assertEqual(
            pill.h, max(44, title_ls + caption_ls + 12),
            "с подписью h=max(44, tl+cl+12) по метрикам шрифта",
        )
        self.assertGreaterEqual(pill.h, 44)
        self.assertGreaterEqual(
            pill.h, title_ls + caption_ls + 2,
            "высота должна вмещать заголовок и подпись без наезда",
        )

    def test_title_and_caption_are_centered_by_metrics(self):
        pill = main.PillChoice(self.root, main.PRESET_PILLS, "balanced",
                               big=True)
        canvas = pill._canv["balanced"]
        title, caption = "Баланс", "x2 · до 4K · 60 FPS"
        items = _text_items(canvas)
        title_items = [item for item in items if item[0] == title]
        caption_items = [item for item in items if item[0] == caption]
        self.assertEqual(len(title_items), 2,
                         "у заголовка должны быть тень и основной текст")
        self.assertEqual(len(caption_items), 1, "подпись должна быть одна")

        width = canvas.winfo_width()
        if width <= 2:
            width = int(canvas.cget("width"))
        title_ls = pill._font_title.metrics("linespace")
        caption_ls = pill._font_small.metrics("linespace")
        block = title_ls + caption_ls + 2
        top = max(2, (pill.h - block) // 2)

        face = min(title_items, key=lambda item: item[1][1])
        shadow = max(title_items, key=lambda item: item[1][1])
        caption_item = caption_items[0]

        self.assertAlmostEqual(face[1][0], width / 2, msg="заголовок по центру")
        self.assertAlmostEqual(caption_item[1][0], width / 2,
                               msg="подпись по центру")
        self.assertAlmostEqual(face[1][1], top,
                               msg="заголовок начинается с top")
        self.assertAlmostEqual(
            shadow[1][1], top + 1.5,
            msg="тень заголовка смещена на 1.5px вниз",
        )
        self.assertAlmostEqual(
            caption_item[1][1], top + title_ls + 2,
            msg="подпись идёт сразу под заголовком",
        )
        self.assertLessEqual(
            caption_item[1][1] + caption_ls, pill.h,
            "подпись не должна вылезать за нижнюю кромку",
        )
        for _text, _coords, _fill, anchor in (face, shadow, caption_item):
            self.assertEqual(anchor, "n", "текст пилюли рисуется сверху вниз")

    def test_single_line_text_is_vertically_centered(self):
        pill = main.PillChoice(self.root, main.FPS_PILLS, "60", big=False)
        canvas = pill._canv["60"]
        items = [item for item in _text_items(canvas)
                 if item[0] == "60 FPS"]
        self.assertEqual(len(items), 2, "тень + основной текст")
        title_ls = pill._font_title.metrics("linespace")
        top = max(2, (pill.h - title_ls) // 2)
        face = min(items, key=lambda item: item[1][1])
        self.assertAlmostEqual(face[1][1], top)
        self.assertLessEqual(top + title_ls, pill.h)

    def test_glass_palette_matches_state_table(self):
        pill = main.PillChoice(self.root, main.FPS_PILLS, "60", big=False)

        top, bottom, gloss, shade, ring = pill._glass_colors("60")
        selected_top = main._mix(main.ACCENT, "#ffffff", 0.16)
        self.assertEqual((top, bottom), (selected_top, main.ACCENT),
                         "выбранная пилюля: lift ACCENT 0.16 + ACCENT")
        self.assertAlmostEqual(gloss, 0.34)
        self.assertAlmostEqual(shade, 0.14)
        self.assertEqual(ring, main._mix(selected_top, "#ffffff", 0.35))

        self.assertEqual(
            pill._glass_colors("120"),
            ("#1d2534", "#12161f", 0.08, 0.08, main.BORDER_SOFT),
            "обычная пилюля должна быть плоской: gloss/shade 0.08",
        )

        pill._hover_change("120", True)
        self.assertEqual(
            pill._glass_colors("120"),
            ("#26304a", "#171d2b", 0.14, 0.10, "#41527a"),
            "ховер невыбранной: только лёгкий объём",
        )
        pill._hover_change("120", False)

        pill._hover_change("60", True)
        top, bottom, gloss, shade, ring = pill._glass_colors("60")
        self.assertEqual(
            (top, bottom), (main._mix(main.ACCENT, "#ffffff", 0.22),
                            main.ACCENT),
            "выбранная+ховер: lift ACCENT 0.22",
        )
        self.assertEqual(ring, main.ACCENT_HOVER)
        self.assertAlmostEqual(gloss, 0.34)
        pill._hover_change("60", False)

        pill.set_enabled(False)
        self.assertEqual(
            pill._glass_colors("60"),
            ("#101318", main.BORDER_SOFT, 0.05, 0.06, main.BORDER_SOFT),
            "disabled: приглушённая плоская пилюля",
        )


# ------------------------------------------------------- строки настроек


class TestSettingsRows(AppGuiTestCase):
    def _label_rows(self) -> list:
        return [
            (self.app.scale_choice.master, "Масштаб"),
            (self.app.model_choice.master, "Модель"),
            (self.app.content_choice.master, "Тип видео"),
            (self.app.encoder_choice.master, "Кодировщик"),
            (self.app.quality_choice.master, "Качество"),
            (self.app.tile_choice.master, "Tile"),
            (self.app.interp_switch.master, "Плавность"),
        ]

    def _all_label_wrappers(self) -> list:
        wrappers = []
        for row, text in self._label_rows():
            wrappers.append((text, row.pack_slaves()[0]))
        space_row = self.app.space_switch.master
        wrappers.append(("Экономить место", space_row.pack_slaves()[0]))
        return wrappers

    def test_all_label_wrappers_share_one_axis_width(self):
        wrappers = self._all_label_wrappers()
        widths = set()
        for text, wrapper in wrappers:
            with self.subTest(label=text):
                self.assertEqual(wrapper.winfo_class(), "Frame")
                width = int(wrapper.cget("width"))
                height = int(wrapper.cget("height"))
                self.assertLessEqual(
                    abs(width - self.app._label_px), 1,
                    f"{text}: ширина обёртки {width} != SHARED_LABEL_PX "
                    f"{self.app._label_px}",
                )
                self.assertLessEqual(
                    abs(height - self.app._label_h), 1,
                    f"{text}: высота обёртки {height} != linespace "
                    f"{self.app._label_h}",
                )
                widths.add(width)
        self.assertEqual(
            len(widths), 1,
            f"обёртки меток должны быть одной ширины, получили {sorted(widths)}",
        )

    def test_label_axis_constant_is_longest_label_plus_six(self):
        font = tkfont.Font(font=main.F_BODY_BOLD)
        labels = ("Масштаб", "Модель", "Плавность", "Тип видео",
                  "Кодировщик", "Качество", "Tile")
        expected = max(font.measure(text) for text in labels) + 6
        self.assertEqual(
            self.app._label_px, expected,
            "SHARED_LABEL_PX = max(measure(меток)) + 6",
        )
        if str(font.actual("family")).lower() == "segoe ui":
            self.assertEqual(
                self.app._label_px, 77,
                "на целевом Segoe UI при scaling 1.15 ширина оси должна быть 77px",
            )

    def test_labels_are_not_clipped_in_fixed_wrappers(self):
        font = tkfont.Font(font=main.F_BODY_BOLD)
        for row, text in self._label_rows():
            wrapper = row.pack_slaves()[0]
            width = int(wrapper.cget("width"))
            label = wrapper.pack_slaves()[0]
            with self.subTest(label=text):
                self.assertEqual(label.cget("text"), text)
                self.assertEqual(label.cget("anchor"), "w")
                self.assertLessEqual(
                    font.measure(text), width,
                    f"{text}: текст шире обёртки — будет клиппинг",
                )
                self.assertLessEqual(
                    label.winfo_reqwidth(), width + 1,
                    f"{text}: запрошенная ширина метки больше обёртки",
                )

    def test_label_text_fits_wrapper_height(self):
        """Label метки не должен просить больше высоты, чем даёт обёртка.

        После фикса main.py:1661-1663 / 1769-1771 у Label выставлены
        bd=0, highlightthickness=0, padx=0, pady=0, поэтому
        winfo_reqheight() == linespace == высоте обёртки. В withdrawn-окне
        winfo_height() у детей равен 1, поэтому проверяем запрошенную
        высоту и фактические внутренние отступы виджета.
        """
        font = tkfont.Font(font=main.F_BODY_BOLD)
        is_target_font = str(font.actual("family")).lower() == "segoe ui"
        for row, text in self._label_rows():
            wrapper = row.pack_slaves()[0]
            label = wrapper.pack_slaves()[0]
            with self.subTest(label=text):
                self.assertLessEqual(
                    label.winfo_reqheight(),
                    int(wrapper.cget("height")),
                    f"{text}: Label просит {label.winfo_reqheight()}px "
                    f"при высоте обёртки {wrapper.cget('height')}px — "
                    "текст будет обрезан по вертикали",
                )
                self.assertEqual(
                    label.winfo_reqheight(),
                    int(wrapper.cget("height")),
                    f"{text}: запрошенная высота Label должна точно "
                    "совпадать с высотой обёртки",
                )
                self.assertEqual(
                    int(wrapper.cget("height")), self.app._label_h,
                    f"{text}: высота обёртки должна быть linespace",
                )
                self.assertEqual(int(label.cget("bd")), 0,
                                 f"{text}: у Label остался borderwidth")
                self.assertEqual(int(label.cget("highlightthickness")), 0,
                                 f"{text}: у Label остался highlightthickness")
                self.assertEqual(int(label.cget("padx")), 0,
                                 f"{text}: у Label остался padx")
                self.assertEqual(int(label.cget("pady")), 0,
                                 f"{text}: у Label остался pady")
                if is_target_font:
                    self.assertEqual(
                        label.winfo_reqheight(), 13,
                        f"{text}: на целевом Segoe UI при scaling 1.15 "
                        "reqheight Label должен быть 13px, а не 19px",
                    )

    def test_label_wrappers_do_not_propagate_children_size(self):
        for row, text in self._label_rows():
            wrapper = row.pack_slaves()[0]
            with self.subTest(label=text):
                propagate = int(wrapper.tk.call(
                    "pack", "propagate", wrapper._w))
                self.assertEqual(
                    propagate, 0,
                    f"{text}: обёртка должна иметь pack_propagate(False), "
                    "иначе ось меток поедет",
                )

    def test_controls_have_same_left_gap_and_vertical_rhythm(self):
        rows = self._label_rows()
        rows.append((self.app.space_switch.master, "Экономить место"))
        for row, text in rows:
            slaves = row.pack_slaves()
            with self.subTest(row=text):
                self.assertGreaterEqual(
                    len(slaves), 2, f"{text}: нет управления в строке")
                self.assertEqual(
                    _pair(slaves[1].pack_info()["padx"]),
                    (main.GAP_LBL_CTRL, 0),
                    f"{text}: зазор метка↔управление должен быть "
                    f"GAP_LBL_CTRL={main.GAP_LBL_CTRL}",
                )
                self.assertEqual(
                    _pair(row.pack_info()["pady"]),
                    (0, main.ROW_GY),
                    f"{text}: вертикальный ритм строки pady=(0, ROW_GY)",
                )

    def test_space_row_is_spacer_switch_label(self):
        row = self.app.space_switch.master
        slaves = row.pack_slaves()
        self.assertEqual(
            [widget.winfo_class() for widget in slaves],
            ["Frame", "Canvas", "Label"],
            "порядок pack: spacer → Switch → текст",
        )
        spacer = slaves[0]
        self.assertEqual(int(spacer.cget("width")), self.app._label_px,
                         "spacer должен держать ту же ось меток")
        self.assertEqual(int(spacer.cget("height")), self.app._label_h)
        self.assertEqual(
            _pair(slaves[1].pack_info()["padx"]), (main.GAP_LBL_CTRL, 0),
            "Switch «Экономить место» с зазором GAP_LBL_CTRL",
        )
        self.assertEqual(
            _pair(slaves[2].pack_info()["padx"]), (10, 0),
            "текст идёт после Switch с отступом 10px",
        )

    def test_settings_row_helper_builds_fixed_label_wrapper(self):
        holder = tk.Frame(self.root, bg=main.CARD)
        row = self.app._settings_row(holder, "Кодировщик")
        self.assertEqual(
            _pair(row.pack_info()["padx"]), (main.PAD_H, main.PAD_H))
        self.assertEqual(
            _pair(row.pack_info()["pady"]), (0, main.ROW_GY))

        wrapper = row.pack_slaves()[0]
        label = wrapper.pack_slaves()[0]
        self.assertEqual(int(wrapper.cget("width")), self.app._label_px)
        self.assertEqual(int(wrapper.cget("height")), self.app._label_h)
        self.assertEqual(
            int(wrapper.tk.call("pack", "propagate", wrapper._w)), 0)
        self.assertEqual(label.cget("text"), "Кодировщик")
        self.assertEqual(label.cget("anchor"), "w")


# --------------------------------------------------------- пустые состояния


class TestEmptyStates(AppGuiTestCase):
    def test_drop_hint_is_visible_while_file_list_is_empty(self):
        self.assertTrue(hasattr(self.app, "files_hint"))
        self.assertTrue(hasattr(self.app, "_update_drop_hint"))
        self.assertEqual(self.app.files, [])
        self.assertEqual(
            self.app.files_hint.winfo_manager(), "place",
            "при пустом списке подсказка должна быть видима",
        )
        info = self.app.files_hint.place_info()
        self.assertEqual(info["anchor"], "center")
        self.assertAlmostEqual(float(info["relx"]), 0.5)
        self.assertAlmostEqual(float(info["rely"]), 0.5)
        self.assertEqual(str(info["in"]), str(self.app.file_list))
        text = self.app.files_hint.cget("text")
        self.assertIn("Перетащите", text)
        self.assertIn("Добавить видео", text)

    def test_drop_hint_hides_after_file_added(self):
        path = Path(r"E:\Проверка папки\тест.mp4")
        self.app.files = [path]
        self.app._refresh_files()
        self.assertEqual(
            self.app.files_hint.winfo_manager(), "",
            "с появлением файла подсказка должна скрываться",
        )
        self.assertEqual(self.app.file_list.size(), 1)
        shown = self.app.file_list.get(0)
        self.assertEqual(shown, str(path))
        self.assertIn("Проверка папки", shown,
                      "кириллица в пути не должна теряться")
        self.assertEqual(
            self.app.files_count.cget("text"), "Выбрано видео: 1")

    def test_drop_hint_returns_after_clearing_files(self):
        self.app.files = [Path(r"E:\Проверка папки\тест.mp4")]
        self.app._refresh_files()
        self.app._clear_files()
        self.assertEqual(self.app.files, [])
        self.assertEqual(
            self.app.files_hint.winfo_manager(), "place",
            "после «Очистить» подсказка должна вернуться",
        )
        self.assertEqual(self.app.file_list.size(), 0)
        self.assertEqual(
            self.app.files_count.cget("text"), "Видео не выбраны")

    def test_log_hint_is_hidden_at_startup(self):
        self.assertEqual(
            self.app.log_hint.winfo_manager(), "",
            "на старте журнал не пуст — заглушку показывать нельзя",
        )
        log_text = self.app.log_text.get("1.0", "end").strip()
        self.assertIn("Video Boost", log_text,
                      "приветствие должно быть записано сразу")

    def test_log_hint_appears_after_clear_and_hides_after_message(self):
        self.app._clear_log()
        self.assertEqual(
            self.app.log_text.get("1.0", "end").strip(), "")
        self.assertEqual(
            self.app.log_hint.winfo_manager(), "place",
            "после «Очистить» заглушка журнала должна быть видима",
        )
        info = self.app.log_hint.place_info()
        self.assertEqual(info["anchor"], "center")
        self.assertAlmostEqual(float(info["relx"]), 0.5)
        self.assertAlmostEqual(float(info["rely"]), 0.5)
        self.assertEqual(str(info["in"]), str(self.app.log_text))

        self.app._append_log("тест")
        self.assertEqual(
            self.app.log_hint.winfo_manager(), "",
            "первое сообщение должно скрыть заглушку журнала",
        )
        self.assertIn("тест", self.app.log_text.get("1.0", "end"))


# --------------------------------------------------------------- спиннер


class TestSpinnerSlot(AppGuiTestCase):
    def test_spinner_is_packed_once_and_never_removed(self):
        spinner = self.app.spinner
        master = spinner.master
        before = _pack_slot(spinner)
        self.assertEqual(spinner.winfo_manager(), "pack")
        self.assertIn(spinner, master.pack_slaves())
        self.assertEqual(
            spinner.itemcget(self.app._spin_arc, "outline"), "",
            "в покое дуга спиннера невидима (outline='')",
        )

        self.app._set_spinner(True)
        self.assertEqual(
            spinner.itemcget(self.app._spin_arc, "outline"), main.ACCENT_2,
            "при старте дуга окрашивается в ACCENT_2",
        )
        self.assertEqual(
            _pack_slot(spinner), before,
            "спиннер не должен перепаковываться при включении",
        )
        self.assertEqual(spinner.winfo_manager(), "pack")
        self.assertIn(spinner, master.pack_slaves())
        self.assertIsNotNone(self.app._spin_job,
                             "анимация спиннера должна запуститься")

        self.app._set_spinner(False)
        self.assertEqual(
            spinner.itemcget(self.app._spin_arc, "outline"), "",
            "после остановки дуга снова невидима",
        )
        self.assertEqual(
            _pack_slot(spinner), before,
            "спиннер не должен перепаковываться при остановке",
        )
        self.assertEqual(spinner.winfo_manager(), "pack")
        self.assertIn(spinner, master.pack_slaves())
        self.assertIsNone(self.app._spin_job,
                          "анимация спиннера должна остановиться")

    def test_spinner_toggle_does_not_shift_progress_or_percent(self):
        progress_before = _pack_slot(self.app.progress)
        percent_before = _pack_slot(self.app.pct_label)
        row = self.app.progress.master
        order_before = [str(w) for w in row.pack_slaves()]

        self.app._set_spinner(True)
        self.assertEqual(_pack_slot(self.app.progress), progress_before)
        self.assertEqual(_pack_slot(self.app.pct_label), percent_before)
        self.assertEqual([str(w) for w in row.pack_slaves()], order_before,
                         "порядок виджетов в прогресс-ряду не должен меняться")

        self.app._set_spinner(False)
        self.assertEqual(_pack_slot(self.app.progress), progress_before)
        self.assertEqual(_pack_slot(self.app.pct_label), percent_before)
        self.assertEqual([str(w) for w in row.pack_slaves()], order_before)


# ----------------------------------------------------------------- шапка


class TestHeaderAlignment(AppGuiTestCase):
    def test_header_title_and_subtitle_share_x_axis(self):
        self.app._paint_header()
        header = self.app.header
        title = header.coords(self.app._header_title)
        face = header.coords(self.app._header_title_face)
        subtitle = header.coords(self.app._header_sub)

        self.assertAlmostEqual(title[0], 22)
        self.assertAlmostEqual(face[0], 22)
        self.assertAlmostEqual(subtitle[0], 22)
        self.assertAlmostEqual(title[1], 21, msg="тень заголовка y=21")
        self.assertAlmostEqual(face[1], 20, msg="заголовок y=20")
        self.assertAlmostEqual(subtitle[1], 47, msg="подзаголовок y=47")
        self.assertAlmostEqual(
            title[1] - face[1], 1.0,
            "тень должна быть смещена ровно на 1px",
        )

    def test_version_badge_is_anchored_to_right_edge(self):
        self.app._paint_header()
        header = self.app.header
        width = header.winfo_width()
        coords = header.coords(self.app._header_ver)
        self.assertEqual(
            header.itemcget(self.app._header_ver, "anchor"), "e")
        self.assertAlmostEqual(
            coords[0], width - 22,
            msg="версия прижата к правой кромке с отступом 22px",
        )
        self.assertAlmostEqual(coords[1], 20)


if __name__ == "__main__":
    unittest.main(verbosity=2)
