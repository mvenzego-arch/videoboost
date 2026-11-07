# -*- coding: utf-8 -*-
r"""
Video Boost — графический интерфейс (tkinter, только стандартная библиотека).

Чёрная тема со скруглениями: панели-карточки, кнопки-капсулы,
пилюли-пресеты, тумблеры, своя полоса прогресса с бегущим бликом,
плавные анимации, тултипы. Журнал дублируется в папку logs\ рядом с программой.
"""

from __future__ import annotations

import atexit
import json
import math
import os
import queue
import re
import sys
import threading
import time
import tkinter as tk
import traceback
from pathlib import Path
from tkinter import filedialog, messagebox
from tkinter import font as tkfont
from typing import Callable, Optional

import engine

# ------------------------------------------------------------------ палитра

BG = "#070809"          # фон окна
CARD = "#10141b"        # карточки
CARD_TOP = "#1c2333"    # жидкое стекло: верх карточки (светлее)
CARD_BOT = "#0f1219"    # низ карточки
CARD_2 = "#161c26"      # поля
FIELD = "#0c0f15"       # список, дорожка прогресса
BORDER = "#212a38"
BORDER_SOFT = "#181f2a"
GLASS_EDGE = "#2e3a52"   # светлая стеклянная кромка
GLASS_EDGE_DARK = "#141a26"
TEXT = "#e8eef8"
TEXT_2 = "#b7c0d0"
MUTED = "#7b8697"
ACCENT = "#7c5cff"      # фиолетовый
ACCENT_HOVER = "#8f73ff"
ACCENT_2 = "#22d3ee"    # голубой
ACCENT_SOFT = "#2a2440"
GREEN = "#2fbf71"
ORANGE = "#fb923c"
RED = "#f87171"
DARK = "#05070b"        # фон журнала
DARK_TOP = "#0a0e18"    # стеклянный журнал: верх
HANDLER_BG = "#0c1020"
HEADER_BG = "#0c1020"   # фон шапки
HEADER_TOP = "#161d34"
HEADER_BOT = "#0a0d18"
HEADER_BORDER = "#20294a"

# ------------------------------------------------------------ шрифты

F_TITLE = ("Segoe UI", 24, "bold")
F_SUB = ("Segoe UI", 11)
F_SECTION = ("Segoe UI", 13, "bold")
F_BODY = ("Segoe UI", 10)
F_BODY_BOLD = ("Segoe UI", 10, "bold")
F_SMALL = ("Segoe UI", 9)
F_CAPTION = ("Segoe UI", 8, "bold")
F_BTN = ("Segoe UI", 11, "bold")
F_BTN_SMALL = ("Segoe UI", 10, "bold")

VIDEO_TYPES = [
    ("Видео", "*.mp4 *.mkv *.mov *.avi *.webm *.m4v *.ts *.wmv *.flv *.mpg *.mpeg *.3gp"),
    ("Все файлы", "*.*"),
]

VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v",
              ".ts", ".wmv", ".flv", ".mpg", ".mpeg", ".3gp"}

PREFS_FILE = engine.APP_DIR / "ui_settings.json"
LOGS_DIR = engine.APP_DIR / "logs"

PRESET_PILLS = [
    ("fast", "Быстро", "x2 · до 4K"),
    ("balanced", "Баланс", "x2 · до 4K · 60 FPS"),
    ("max", "Максимально", "x4 · до 8K · 60 FPS"),
]
SCALE_PILLS = [
    ("x2", "x2"), ("x3", "x3"), ("x4", "x4"),
    ("auto_2160", "4K авто"), ("auto_4320", "8K авто"),
]
MODEL_PILLS = [("auto", "Авто"), ("light", "Лёгкая"), ("heavy", "Тяжёлая")]
ENCODER_PILLS = [("preset", "Авто"), ("amf_h264", "H.264"),
                 ("amf_hevc", "H.265"), ("cpu", "CPU")]
QUALITY_PILLS = [("preset", "Авто"), ("speed", "Скорость"),
                 ("balanced", "Баланс"), ("quality", "Макс")]
TILE_PILLS = [("preset", "Авто"), ("t256", "256"), ("t384", "384"),
              ("t512", "512")]
FPS_PILLS = [("60", "60 FPS"), ("120", "120 FPS")]
CONTENT_PILLS = [("general", "Обычное", ""), ("anime", "Аниме", "")]

TOOLTIPS = {
    "start": "Обработать все выбранные видео с этими настройками",
    "cancel": "Остановить обработку и удалить временные файлы",
    "open": "Показать папку с готовыми файлами",
    "interp": "Нейросеть RIFE добавит промежуточные кадры и поднимет частоту кадров",
    "fps": "До какой частоты кадров дотягивать плавность",
    "space": "Промежуточные кадры в JPEG: экономит десятки ГБ, качество почти не меняется",
    "content": "Для аниме модель работает заметно лучше",
    "prepare": "Скачать FFmpeg, Real-ESRGAN и RIFE (~700 МБ) — нужно один раз",
    "scale": "Насколько увеличим картинку: x2 — 1080p → 4K, x3 — ~5–6K, "
             "x4 — 1080p → 8K. «4K авто» и «8K авто» сами подберут масштаб "
             "под каждый файл (если источник уже крупный — апскейл пропустят)",
    "model": "Лёгкая модель обрабатывает кадр за секунды, тяжёлая — за десятки "
             "секунд, зато детальнее (тяжёлая работает только при x4)",
    "encoder": "GPU (AMD AMF) — быстро; CPU — медленнее, но иногда выручает",
    "quality": "Сжатие готового видео: «Макс» — лучший поток, «Скорость» — быстрее",
    "tile": "Размер куска кадра, обрабатываемого за раз. Меньше tile — меньше "
            "видеопамяти (актуально для x4/8K)",
}


def _mix(c1: str, c2: str, t: float) -> str:
    t = max(0.0, min(1.0, t))
    try:
        r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
        r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
    except (ValueError, IndexError):
        return c1
    return "#{:02x}{:02x}{:02x}".format(
        round(r1 + (r2 - r1) * t),
        round(g1 + (g2 - g1) * t),
        round(b1 + (b2 - b1) * t),
    )


def round_rect(canvas: tk.Canvas, x1: float, y1: float, x2: float, y2: float,
               r: float = 10, **kwargs):
    r = max(0.0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    points = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)


def rounded_span(x1: float, y1: float, x2: float, y2: float, r: float,
                 y: float) -> tuple:
    """Горизонтальный отрезок строки y внутри скруглённого прямоугольника."""
    r = max(0.0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    xa, xb = x1, x2
    cy_top, cy_bot = y1 + r, y2 - r
    if y < cy_top:
        dy = cy_top - y
        dx = math.sqrt(max(0.0, r * r - dy * dy))
        xa = max(xa, x1 + r - dx)
    elif y > cy_bot:
        dy = y - cy_bot
        dx = math.sqrt(max(0.0, r * r - dy * dy))
        xa = max(xa, x1 + r - dx)
    if y < cy_top:
        dy = cy_top - y
        dx = math.sqrt(max(0.0, r * r - dy * dy))
        xb = min(xb, x2 - r + dx)
    elif y > cy_bot:
        dy = y - cy_bot
        dx = math.sqrt(max(0.0, r * r - dy * dy))
        xb = min(xb, x2 - r + dx)
    return xa, xb


def glass_fill(canvas: tk.Canvas, x1: float, y1: float, x2: float, y2: float,
               r: float, top: str, bottom: str, tags: str = "",
               gloss: float = 0.0, shadex: float = 0.10) -> None:
    """Вертикальный стеклянный градиент со сглаженными краями.

    gloss — сила блика у верхней кромки (0..1);
    shadex — лёгкое затемнение правого сегмента (объём «3D»).
    """
    height = max(1.0, y2 - y1)
    step = 1
    y = y1
    while y <= y2:
        t = (y - y1) / height
        color = _mix(top, bottom, t)
        if gloss > 0.0:
            k = max(0.0, 1.0 - (y - y1) / (height * 0.30))
            color = _mix(color, "#ffffff", gloss * k * 0.55)
        xa, xb = rounded_span(x1, y1, x2, y2, r, y)
        if xb > xa + 1:
            mid = x1 + (x2 - x1) * 0.62
            if xb > mid + 1 and shadex > 0.0:
                canvas.create_line(xa, y, mid, y, fill=color, tags=tags)
                canvas.create_line(mid, y, xb, y,
                                   fill=_mix(color, "#000000", shadex),
                                   tags=tags)
            else:
                canvas.create_line(xa, y, xb, y, fill=color, tags=tags)
        y += step


def glass_pill_text(canvas: tk.Canvas, cx: float, cy: float, text: str,
                    fill_col: str, font, shadow: bool = True) -> None:
    """Текст с мягкой «подложкой» снизу — объёмная надпись."""
    if shadow:
        canvas.create_text(cx, cy + 1.5, text=text, fill="#000000", font=font)
    canvas.create_text(cx, cy, text=text, fill=fill_col, font=font)


# ------------------------------------------------------------------ журнал


class FileLogger:
    """Дублирует журнал в файл logs\… и прибирает старые файлы."""

    def __init__(self) -> None:
        self.fh = None
        try:
            LOGS_DIR.mkdir(parents=True, exist_ok=True)
            name = time.strftime("video_boost_%Y-%m-%d_%H-%M-%S.log")
            self.path = LOGS_DIR / name
            self.fh = open(self.path, "a", encoding="utf-8", buffering=1)
            self._cleanup()
        except OSError:
            self.fh = None

    def write(self, text: str) -> None:
        if self.fh is None:
            return
        try:
            self.fh.write(text + "\n")
        except OSError:
            pass

    def close(self) -> None:
        if self.fh is not None:
            try:
                self.fh.close()
            except OSError:
                pass
            self.fh = None

    @staticmethod
    def _cleanup(keep: int = 20) -> None:
        try:
            files = sorted(LOGS_DIR.glob("video_boost_*.log"),
                           key=lambda p: p.stat().st_mtime, reverse=True)
            for old in files[keep:]:
                old.unlink(missing_ok=True)
        except OSError:
            pass


# ------------------------------------------------------------------ тултипы


class Tooltip:
    """Небольшая подсказка с плавным появлением."""

    def __init__(self, widget: tk.Misc, text: str, delay: int = 420):
        self.widget = widget
        self.text = text
        self.delay = delay
        self._job: Optional[str] = None
        self._tip: Optional[tk.Toplevel] = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event=None) -> None:
        self._cancel()
        try:
            if str(self.widget["state"]) == "disabled":
                return
        except Exception:
            pass
        self._job = self.widget.after(self.delay, self._show)

    def _cancel(self) -> None:
        if self._job:
            try:
                self.widget.after_cancel(self._job)
            except Exception:
                pass
            self._job = None

    def _show(self) -> None:
        if self._tip is not None:
            return
        try:
            x = self.widget.winfo_rootx() + 8
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
            self._tip = tk.Toplevel(self.widget)
            self._tip.wm_overrideredirect(True)
            self._tip.wm_attributes("-topmost", True)
            frame = tk.Frame(self._tip, bg="#000000", padx=1, pady=1)
            frame.pack()
            inner = tk.Label(frame, text=self.text, bg="#12151d", fg="#dbe1ee",
                             font=("Segoe UI", 9), justify="left",
                             wraplength=280, padx=10, pady=6)
            inner.pack()
            self._tip.wm_geometry(f"+{x}+{y}")
            self._tip.update_idletasks()
            try:
                self._tip.wm_attributes("-alpha", 0.0)
                for step in range(1, 6):
                    self._tip.wm_attributes("-alpha", step / 5)
                    self._tip.update_idletasks()
                    time.sleep(0.012)
            except Exception:
                pass
        except Exception:
            self._tip = None

    def _hide(self, _event=None) -> None:
        self._cancel()
        if self._tip is not None:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None


# ------------------------------------------------------------ переключатель


class Switch(tk.Canvas):
    """Тумблер «жидкое стекло»: стеклянная дорожка, глянцевый шар-ползунок."""

    W = 52
    H = 28
    KNOB = 20
    PAD = 4

    def __init__(self, master: tk.Misc, variable: tk.BooleanVar,
                 on_change: Optional[Callable[[], None]] = None):
        super().__init__(master, width=self.W + 4, height=self.H + 6, bg=CARD,
                         highlightthickness=0, bd=0)
        self.var = variable
        self.on_change = on_change
        self.enabled = True
        self._pos = 1.0 if variable.get() else 0.0
        self._job: Optional[str] = None
        self.bind("<Button-1>", self._clicked)
        try:
            self._paint()
        except tk.TclError:
            pass

    def _knob_x(self) -> float:
        travel = self.W - 2 * self.PAD - self.KNOB
        return self.PAD + travel * self._pos + 2

    def _paint(self) -> None:
        self.delete("all")
        h = self.H
        cy = h / 2 + 2
        r = h / 2
        on = bool(self.var.get())
        if not self.enabled:
            track_on, track_off = "#1b2029", "#1b2029"
        else:
            track_on, track_off = ACCENT, "#232b3a"
        # стеклянная дорожка
        base = track_on if on else track_off
        top = _mix(base, "#ffffff", 0.14)
        glass_fill(self, 2, 2, 2 + self.W, 2 + h, r, top,
                   _mix(base, "#000000", 0.25), gloss=0.16, shadex=0.10)
        round_rect(self, 2, 2, 2 + self.W, 2 + h, r=r, fill="",
                   outline=_mix(base, "#000000", 0.45), width=1)
        # глянцевый шар
        x = self._knob_x()
        kx0, ky0 = x, cy - self.KNOB / 2
        kx1, ky1 = x + self.KNOB, cy + self.KNOB / 2
        kk = self.KNOB / 2
        kcx, kcy = x + kk, cy
        kds = self.KNOB
        knob_col = "#f2f5fb" if self.enabled else "#77808f"
        rim = _mix(knob_col, "#000000", 0.35)
        self.create_oval(kx0, ky0 + 1.5, kx1, ky1 + 1.5, fill=rim, width=0)
        self.create_oval(kx0, ky0, kx1, ky1, fill=knob_col, width=0,
                         outline=rim)
        # световое «пятно» на шаре — эффект линзы
        self.create_oval(kcx - kk * 0.55, kcy - kk * 0.62,
                         kcx + kk * 0.05, kcy - kk * 0.05,
                         fill="#ffffff", width=0)
        # полоска-индикатор внутри дорожки
        if self.enabled and (abs(self._pos - 1.0) < 0.02 or abs(self._pos) < 0.02):
            gx = (x + self.KNOB + 2) if abs(self._pos - 1.0) < 0.02 else 7
            self.create_oval(gx, cy - 2, gx + 4, cy + 2,
                             fill=_mix(base, "#ffffff", 0.75), width=0)

    def _animate(self, steps: int = 9, interval: int = 16) -> None:
        if self._job:
            try:
                self.after_cancel(self._job)
            except Exception:
                pass
            self._job = None
        start = self._pos
        target = 1.0 if self.var.get() else 0.0

        def tick(i: int = 0) -> None:
            i += 1
            t = i / steps
            eased = t * t * (3 - 2 * t)          # smoothstep
            self._pos = start + (target - start) * eased
            self._paint()
            if i < steps:
                self._job = self.after(interval, tick, i)
            else:
                self._pos = target
                self._paint()
                self._job = None

        tick()

    def set(self, value: bool, animate: bool = True) -> None:
        self.var.set(bool(value))
        if animate:
            self._animate()
        else:
            self._pos = 1.0 if value else 0.0
            self._paint()

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        try:
            self.configure(cursor="hand2" if enabled else "arrow")
        except tk.TclError:
            pass
        self._paint()

    def _clicked(self, _event=None) -> None:
        if not self.enabled:
            return
        self.var.set(not self.var.get())
        self._animate()
        if self.on_change:
            self.on_change()


# -------------------------------------------------------------- пилюли

class PillChoice(tk.Frame):
    """Выбор варианта — стеклянные пилюли с плавной сменой цвета."""

    def __init__(self, master: tk.Misc, options: list, value: str,
                 on_change: Optional[Callable[[str], None]] = None,
                 big: bool = True):
        super().__init__(master, bg=CARD)
        self.options = [
            (k, t, (o[2] if len(o) > 2 else "")) for o in options
            for k, t in [(o[0], o[1])]
        ]
        self.value = value
        self.on_change = on_change
        self.enabled = True
        self.big = big
        self.h = 44 if big else 28
        self._canv: dict[str, tk.Canvas] = {}
        self._hover: dict[str, bool] = {o[0]: False for o in self.options}

        for i, (key, _t, _c) in enumerate(self.options):
            canv = tk.Canvas(self, bg=CARD, highlightthickness=0, bd=0,
                             height=self.h, cursor="hand2")
            canv.grid(row=0, column=i, sticky="ew", padx=0 if i == 0 else 6)
            self.columnconfigure(i, weight=1)
            canv.bind("<Button-1>", lambda _e, k=key: self._choose(k))
            canv.bind("<Enter>", lambda _e, k=key: self._hover_change(k, True))
            canv.bind("<Leave>", lambda _e, k=key: self._hover_change(k, False))
            canv.bind("<Configure>", lambda _e, k=key: self._redraw(k))
            self._canv[key] = canv
            self._redraw(key)

    # ----- палитра состояний

    def _palette(self, key: str):
        if not self.enabled:
            return ("#101318", BORDER_SOFT, "#5c6675", MUTED)
        if key == self.value:
            return (ACCENT, ACCENT_HOVER, "#ffffff", "#e9e2ff")
        if self._hover.get(key):
            return ("#26304a", "#171d2b", TEXT, "#cfd6e6")
        return ("#1d2534", "#12161f", TEXT_2, "#98a2b5")

    def _glass_colors(self, key: str) -> tuple:
        """(top, bottom) пилюли с учётом объёма стекла."""
        top, bot, _t, _c = self._palette(key)
        lift = _mix(top, "#ffffff", 0.16)
        return lift, bot

    def _redraw(self, key: str, override: Optional[tuple] = None) -> None:
        canv = self._canv.get(key)
        if canv is None:
            return
        w = canv.winfo_width()
        if w <= 2:
            w = 140
        h = self.h
        fill, _border, tcol, ccol = self._palette(key)
        if override:
            tcol = override[2]
        option = next(o for o in self.options if o[0] == key)
        title, caption = option[1], option[2]

        top, bottom = self._glass_colors(key)
        if override:
            top = override[0]
            bottom = override[1]
        canv.delete("all")
        selected = key == self.value and self.enabled
        glass_fill(canv, 1, 1, w - 2, h - 1, min(16, (h - 1) / 2),
                   top, bottom, gloss=0.34 if selected else 0.16,
                   shadex=0.14 if selected else 0.08)
        ring = (_mix(top, "#ffffff", 0.35) if selected
                else _mix(top, "#000000", 0.30))
        round_rect(canv, 1, 1, w - 2, h - 1, r=min(16, (h - 1) / 2),
                   fill="", outline=ring, width=1)
        big_font = ("Segoe UI", 11, "bold")
        small_font = ("Segoe UI", 9, "bold")
        font = big_font if self.big else small_font
        shadow = _mix(fill, "#000000", 0.55)
        cy = h / 2 - (6 if caption else 0)
        canv.create_text(w / 2, cy + 1.5, text=title, fill=shadow, font=font)
        canv.create_text(w / 2, cy, text=title, fill=tcol, font=font)
        if caption:
            canv.create_text(w / 2, h / 2 + 11, text=caption, fill=ccol,
                             font=("Segoe UI", 8, "bold"))

    def redraw_all(self) -> None:
        for o in self.options:
            self._redraw(o[0])

    def _animate_colors(self, key: str, steps: int = 8, interval: int = 22) -> None:
        # стеклянная пилюля перерисовывается целиком — «fade» не требуется
        self._redraw(key)

    # ----- поведение

    def _choose(self, key: str) -> None:
        if not self.enabled or key == self.value:
            return
        old = self.value
        self.value = key
        self._animate_colors(old)
        self._animate_colors(key)
        if self.on_change:
            self.on_change(key)

    def _hover_change(self, key: str, on: bool) -> None:
        self._hover[key] = on
        if not self.enabled and on:
            return
        self._animate_colors(key, steps=5, interval=18)

    def set(self, key: str) -> None:
        if key not in [o[0] for o in self.options]:
            return
        self.value = key
        self.redraw_all()

    def get(self) -> str:
        return self.value

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        for canv in self._canv.values():
            try:
                canv.configure(cursor="hand2" if enabled else "arrow")
            except tk.TclError:
                pass
        self.redraw_all()


# ------------------------------------------------------------- полоса прогресса


class BoostBar(tk.Canvas):
    """Стеклянная полоса прогресса 3D: вогнутый трек, градиент, бегущий блик."""

    HEIGHT = 14

    def __init__(self, master: tk.Misc):
        super().__init__(master, bg=CARD, height=self.HEIGHT,
                         highlightthickness=0, bd=0)
        self._frac = 0.0
        self._fill = ACCENT
        self._active = False
        self._shim_x = 0.0
        self._shim_job: Optional[str] = None
        self.bind("<Configure>", lambda _e: self._paint())

    def set(self, frac: float) -> None:
        self._frac = max(0.0, min(1.0, float(frac)))
        self._paint()

    def set_color(self, color: str) -> None:
        self._fill = color
        self._paint()

    def set_active(self, active: bool) -> None:
        if active and not self._shim_job:
            self._shim_job = self.after(50, self._shimmer)
        if not active and self._shim_job:
            try:
                self.after_cancel(self._shim_job)
            except Exception:
                pass
            self._shim_job = None
        self._active = active

    def _shimmer(self) -> None:
        if not self._active:
            self._shim_job = None
            return
        self._shim_x += 5
        self._paint()
        self._shim_job = self.after(50, self._shimmer)

    def _paint(self) -> None:
        try:
            w = self.winfo_width()
            if w <= 2:
                w = 300
        except Exception:
            w = 300
        h = self.HEIGHT
        self.delete("all")

        # вогнутый стеклянный трек
        round_rect(self, 0.5, 0.5, w - 0.5, h - 0.5, r=(h - 1) / 2,
                   fill="#090b10", outline="")
        self.create_line(4, 1.5, w - 4, 1.5, fill="#010203")
        round_rect(self, 1.5, 2.5, w - 1.5, h - 0.5, r=(h - 2) / 2,
                   fill="", outline="#000000", width=1)
        round_rect(self, 0.5, 0.5, w - 0.5, h - 0.5, r=(h - 1) / 2, fill="",
                   outline=_mix("#090b10", "#ffffff", 0.10), width=1)

        fill_px = (w - 4) * self._frac
        if fill_px > 2:
            x0, x1 = 2.0, 2.0 + fill_px
            r = min(h / 2 - 2, max(2, fill_px / 2))
            # градиент заливки: голубой -> выбранный цвет
            segs = max(3, min(12, int(fill_px / 24)))
            for i in range(segs):
                t = i / max(1, segs - 1)
                col = _mix(ACCENT_2, self._fill, t)
                sx = round(x0 + (fill_px - 1) * (i / segs))
                ex = round(x0 + (fill_px - 1) * ((i + 1) / segs))
                if ex < sx:
                    ex = sx
                round_rect(self, sx, 2, ex, h - 2, r=r, fill=col, outline="")
            if fill_px > 30:
                self.create_line(6, 3.4, x1 - 3, 3.4,
                                 fill=_mix(self._fill, "#ffffff", 0.62))
                self.create_line(6, h - 4.5, x1 - 3, h - 4.5,
                                 fill=_mix(self._fill, "#000000", 0.30))
            if self._active and fill_px > 44:
                span = fill_px - 26
                if span > 0:
                    bx = x0 + 2 + (self._shim_x % span)
                    light = _mix(self._fill, "#ffffff", 0.50)
                    round_rect(self, bx, 3.5, bx + 17, h - 3.5,
                               r=(h - 5) / 2, fill=light, outline="")


# ----------------------------------------------------------- скроллбар


class SlimScrollbar(tk.Canvas):
    """Современный тонкий скроллбар: без стрелок, капсула-бегунок."""

    THUMB_MIN = 34

    COLORS = {
        "idle": "#2c3547",
        "hover": "#43506c",
        "active": "#5d6f96",
    }

    def __init__(self, master: tk.Misc, orient: str = "vertical",
                 bg: str = FIELD):
        super().__init__(master, width=12, height=12, bg=bg,
                         highlightthickness=0, bd=0)
        self.orient = orient
        self._first, self._last = 0.0, 1.0
        self._view = None
        self._drag_off = None
        self._state = "idle"
        self.bind("<Configure>", lambda _e: self._paint(), add="+")
        self.bind("<Enter>", lambda _e: self._state_change("hover"), add="+")
        self.bind("<Leave>", lambda _e: self._state_change("idle"), add="+")
        self.bind("<ButtonPress-1>", self._press, add="+")
        self.bind("<B1-Motion>", self._drag, add="+")
        self.bind("<ButtonRelease-1>", self._release, add="+")

    # ---- подключение к виджету (Listbox / Text)

    def attach(self, widget: tk.Misc) -> None:
        if self.orient == "vertical":
            self._view = widget.yview
            widget.configure(yscrollcommand=self.set)
        else:
            self._view = widget.xview
            widget.configure(xscrollcommand=self.set)

    def set(self, first, last) -> None:  # noqa: ANN001
        """Вызывается виджетом: (first, last) в долях содержимого."""
        try:
            self._first, self._last = float(first), float(last)
        except (TypeError, ValueError):
            return
        self._paint()

    # ---- отрисовка

    def _axis_len(self) -> int:
        try:
            n = (self.winfo_height() if self.orient == "vertical"
                 else self.winfo_width())
        except Exception:
            n = 0
        return max(0, n)

    def _geometry(self):
        """(usable, tlen, span, t0, t1) или None, если прокрутки нет."""
        total = self._axis_len()
        if total < 50:
            return None
        visible = self._last - self._first
        if visible >= 0.999 or visible <= 0:
            return None
        usable = total - 2
        tlen = max(self.THUMB_MIN, int(round(usable * visible)))
        span = usable - tlen
        t0 = 1 + int(round(self._first * span))
        t1 = t0 + tlen
        if span <= 0:
            return None
        return t0, t1, span, tlen

    def _paint(self) -> None:
        self.delete("all")
        geo = self._geometry()
        if geo is None:
            return
        t0, t1 = geo[0], geo[1]
        color = self.COLORS.get(self._state, self.COLORS["idle"])
        if self.orient == "vertical":
            x0, x1 = 3, self.winfo_width() - 3
            round_rect(self, x0, t0, x1, t1, r=(x1 - x0) / 2,
                       fill=color, outline="")
        else:
            y0, y1 = 3, self.winfo_height() - 3
            round_rect(self, t0, y0, t1, y1, r=(y1 - y0) / 2,
                       fill=color, outline="")
    def _state_change(self, new: str) -> None:
        if self._state == "active" and new != "active":
            return
        self._state = new
        self._paint()

    # ---- события мыши

    def _axis_pos(self, event) -> int:  # noqa: ANN001
        return event.y if self.orient == "vertical" else event.x

    def _press(self, event) -> None:  # noqa: ANN001
        geo = self._geometry()
        if geo is None:
            return
        t0, t1 = geo[0], geo[1]
        pos = self._axis_pos(event)
        try:
            self.grab_set()
        except tk.TclError:
            pass
        if pos < t0:
            self._view("scroll", -1, "pages")
        elif pos > t1:
            self._view("scroll", 1, "pages")
        else:
            self._drag_off = pos - t0
            self._state = "active"
            self._paint()

    def _drag(self, event) -> None:  # noqa: ANN001
        if self._drag_off is None:
            return
        geo = self._geometry()
        if geo is None:
            return
        _t0, _t1, span, _tlen = geo
        pos = self._axis_pos(event)
        target = min(max(pos - self._drag_off - 1, 0), span) / span
        visible = self._last - self._first
        new_first = min(max(target, 0.0), 1.0 - visible)
        self._view("moveto", new_first)

    def _release(self, _event=None) -> None:
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self._drag_off = None
        self._state = "hover"
        self._paint()


# ---------------------------------------------------------- скруглённая панель


class RoundPanel(tk.Canvas):
    """Стеклянная карточка: градиент, блик у кромки, объёмная нижняя грань."""

    def __init__(self, master: tk.Misc, canvas_bg: str, fill: str,
                 border: str, radius: int = 14,
                 glass_top: str = CARD_TOP, glass_bot: str = CARD_BOT,
                 req_height: int = 10):
        super().__init__(master, bg=canvas_bg, highlightthickness=0, bd=0,
                         height=req_height)
        self.fill = fill
        self.border = border
        self.radius = radius
        self.glass_top = glass_top
        self.glass_bot = glass_bot
        self._win = None
        self.body = tk.Frame(self, bg=fill, bd=0, highlightthickness=0)
        self.bind("<Configure>", self._layout)

    def _layout(self, _event=None) -> None:
        try:
            w = self.winfo_width()
            h = self.winfo_height()
        except Exception:
            return
        if w < 10 or h < 10:
            return
        r = max(2, min(self.radius, w / 2 - 2, h / 2 - 2))
        self.delete("all")

        # мягкая тень снизу (объём «парящей» карточки)
        round_rect(self, 2, 1, w - 2, h - 1, r=r + 1,
                   fill=_mix(BG, "#000000", 0.55), outline="")
        round_rect(self, 3, 2, w - 3, h + 4, r=r,
                   fill=_mix(BG, "#000000", 0.30), outline="")

        # стеклянное тело
        glass_fill(self, 1, 1, w - 2, h - 2, r, self.glass_top, self.glass_bot,
                   gloss=0.30, shadex=0.06)
        # светлая кромка стекла
        round_rect(self, 1, 1, w - 2, h - 2, r=r, fill="",
                   outline=self.border if self.border != BORDER else GLASS_EDGE,
                   width=1)
        try:
            self.create_line(1 + r, 1.5, w - 2 - r, 1.5,
                             fill=_mix(GLASS_EDGE, "#ffffff", 0.30))
        except tk.TclError:
            pass
        m = max(4, int(r))
        # пересоздаём окно с содержимым: delete("all") удаляет и его,
        # иначе после любого ресайза карточки остаются пустыми
        self._win = self.create_window(m, m, anchor="nw", window=self.body)
        self.itemconfigure(self._win, width=int(max(20, w - 2 * m)),
                           height=int(max(20, h - 2 * m)))

    def configure(self, cnf=None, **kw):  # noqa: ANN001
        if cnf:
            merged = dict(cnf)
            merged.update(kw)
            kw = merged
            cnf = None
        changed_border = False
        if "highlightbackground" in kw:
            self.border = kw.pop("highlightbackground")
            changed_border = True
        result = super().configure(cnf, **kw)
        if changed_border:
            try:
                if self.winfo_width() > 10:
                    self._layout()
            except (tk.TclError, AttributeError):
                pass
        return result


# ------------------------------------------------------------- кнопка-капсула


class RoundButton(tk.Canvas):
    """Капсула-кнопка из «жидкого стекла»: градиент, блик, нажатие-утопление."""

    KINDS = {
        "accent": dict(h=44, padx=22, size=11, base=ACCENT, hover=ACCENT_HOVER,
                       fg="#ffffff", pressed="#5a3fd6", gloss=0.38,
                       d_base="#232036", d_fg="#c9bfff"),
        "secondary": dict(h=36, padx=16, size=10, base="#1a2230", hover="#242d40",
                          fg="#c7cfdd", pressed="#12161f", gloss=0.16,
                          d_base="#181c24", d_fg="#5f6878"),
        "danger": dict(h=36, padx=16, size=10, base="#3a1a22", hover="#4c212c",
                       fg="#ff9aa8", pressed="#2c151b", gloss=0.18,
                       d_base="#231a1e", d_fg="#7c5a62"),
    }

    def __init__(self, master: tk.Misc, kind: str, text: str, command,
                 state: str = "normal"):
        spec = self.KINDS[kind]
        self._font = tkfont.Font(family="Segoe UI", size=spec["size"],
                                 weight="bold")
        self._spec = spec
        self._text = text
        self._command = command
        self._state = state
        self._cur = spec["base"]
        self._job = None
        self._pressing = False
        self._w_btn = spec["padx"] * 2 + self._font.measure(text)
        super().__init__(master, width=max(64, self._w_btn), height=spec["h"],
                         bg=master.cget("bg"), highlightthickness=0, bd=0,
                         cursor="hand2")
        self._redraw()
        self.bind("<Enter>", self._on_enter, add="+")
        self.bind("<Leave>", self._on_leave, add="+")
        self.bind("<ButtonPress-1>", self._on_press, add="+")
        self.bind("<ButtonRelease-1>", self._on_release, add="+")

    # совместимость с прежним ttk-интерфейсом: configure(state=…, text=…)

    def cget(self, key):  # noqa: ANN001
        if key == "state":
            return self._state
        return super().cget(key)

    def configure(self, cnf=None, **kw):  # noqa: ANN001
        if cnf:
            merged = dict(cnf)
            merged.update(kw)
            kw = merged
            cnf = None
        if "state" in kw:
            self._state = kw.pop("state")
            self._apply_state()
        if "text" in kw:
            self._text = kw.pop("text")
            self._remeasure()
        return super().configure(cnf, **kw)

    def _remeasure(self) -> None:
        self._w_btn = self._spec["padx"] * 2 + self._font.measure(self._text)
        try:
            self.configure(width=max(64, self._w_btn), height=self._spec["h"])
        except tk.TclError:
            return
        self._redraw()

    def _apply_state(self) -> None:
        try:
            self.configure(cursor="hand2" if self._state == "normal" else "arrow")
        except tk.TclError:
            pass
        self._stop_job()
        self._pressing = False
        self._cur = self._spec["base"]
        self._redraw()

    def _stop_job(self) -> None:
        if self._job:
            try:
                self.after_cancel(self._job)
            except Exception:
                pass
            self._job = None

    def _fade(self, target: str, steps: int = 6, interval: int = 20) -> None:
        if self._state != "normal":
            return
        self._stop_job()
        start = self._cur
        st = {"i": 0}

        def tick() -> None:
            st["i"] += 1
            self._cur = _mix(start, target, st["i"] / steps)
            self._redraw()
            if st["i"] < steps:
                self._job = self.after(interval, tick)
            else:
                self._cur = target
                self._redraw()
                self._job = None

        tick()

    def _redraw(self) -> None:
        if self._state == "disabled":
            fill, fg = self._spec["d_base"], self._spec["d_fg"]
        else:
            fill, fg = self._cur, self._spec["fg"]
        w = max(64, self._w_btn)
        h = self._spec["h"]
        try:
            self.configure(width=w, height=h)
        except tk.TclError:
            return
        self.delete("all")
        pressed = (self._pressing or self._state == "disabled"
                   or fill == self._spec["pressed"])
        gloss = self._spec["gloss"] if not pressed else 0.0
        shade_x = 0.12 if not pressed else 0.04
        first = _mix(fill, "#ffffff", 0.16)
        glass_fill(self, 0.5, 0.5, w - 1, h - 1, (h - 1) / 2,
                   first, fill, gloss=gloss, shadex=shade_x)
        # стеклянная кромка и верхний свет
        round_rect(self, 0.5, 0.5, w - 1, h - 1, r=(h - 1) / 2, fill="",
                   outline=_mix(fill, "#000000", 0.38), width=1)
        self.create_text(w / 2 + 0.5, h / 2 + 1.5, text=self._text,
                         fill=_mix(fg, "#000000", 0.55), font=self._font)
        self.create_text(w / 2, h / 2, text=self._text, fill=fg,
                         font=self._font)

    # ----- события

    def _on_enter(self, _e=None) -> None:
        if self._state == "normal":
            self._fade(self._spec["hover"])

    def _on_leave(self, _e=None) -> None:
        self._pressing = False
        if self._state == "normal":
            self._fade(self._spec["base"])

    def _on_press(self, _e=None) -> None:
        if self._state != "normal":
            return
        self._pressing = True
        self._stop_job()
        self._cur = self._spec["pressed"]
        self._redraw()

    def _on_release(self, _e=None) -> None:
        if self._state != "normal" or not self._pressing:
            return
        self._pressing = False
        self._cur = self._spec["hover"]
        self._redraw()
        if self._command:
            self._command()


# ------------------------------------------- перетаскивание файлов из проводника


class DragDropHook:
    """Приём файлов мышкой в окно программы (чистый ctypes, только Windows).

    Возвращает файлы через callback(список_путей).
    """

    WM_DROPFILES = 0x0233
    GWLP_WNDPROC = -4

    def __init__(self, widget: tk.Misc, callback: Callable[[list], None]):
        import ctypes
        from ctypes import wintypes

        LongPtr = ctypes.c_ssize_t
        WndProcType = ctypes.WINFUNCTYPE(
            LongPtr, wintypes.HWND, wintypes.UINT, ctypes.c_size_t,
            wintypes.LPARAM,
        )

        user32 = ctypes.WinDLL("user32")
        shell32 = ctypes.WinDLL("shell32")
        user32.GetWindowLongPtrW.restype = LongPtr
        user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, wintypes.INT]
        user32.SetWindowLongPtrW.restype = LongPtr
        user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, wintypes.INT, LongPtr]
        user32.CallWindowProcW.restype = LongPtr
        user32.CallWindowProcW.argtypes = [
            WndProcType, wintypes.HWND, wintypes.UINT, ctypes.c_size_t,
            wintypes.LPARAM,
        ]
        shell32.DragAcceptFiles.argtypes = [wintypes.HWND, wintypes.BOOL]
        shell32.DragQueryFileW.restype = ctypes.c_uint
        shell32.DragQueryFileW.argtypes = [wintypes.HANDLE, ctypes.c_uint,
                                           wintypes.LPWSTR, ctypes.c_uint]
        shell32.DragFinish.argtypes = [wintypes.HANDLE]

        self.widget = widget
        self.callback = callback
        self._user32 = user32
        self._shell32 = shell32

        hwnd = widget.winfo_id()
        self.hwnd = hwnd
        old_value = user32.GetWindowLongPtrW(hwnd, self.GWLP_WNDPROC)
        self._old_proc = WndProcType(old_value)

        def _proc(h, msg, wp, lp):  # noqa: ANN001
            try:
                if msg == self.WM_DROPFILES:
                    try:
                        files = self._query_files(wp)
                    finally:
                        self._shell32.DragFinish(wp)
                    if self.callback is not None:
                        self.callback(files)
                    return 0
            except Exception:
                pass
            return user32.CallWindowProcW(self._old_proc, h, msg, wp, lp)

        self._new_proc = WndProcType(_proc)    # держим ссылку (иначе GC)
        addr = ctypes.cast(self._new_proc, ctypes.c_void_p).value
        if addr is None:
            raise OSError("не удалось получить адрес WndProc")
        user32.SetWindowLongPtrW(hwnd, self.GWLP_WNDPROC, addr)
        shell32.DragAcceptFiles(hwnd, True)

    def _query_files(self, hdrop):
        count = self._shell32.DragQueryFileW(hdrop, 0xFFFFFFFF, None, 0)
        buf = ctypes.create_unicode_buffer(2048)
        files = []
        for i in range(count):
            self._shell32.DragQueryFileW(hdrop, i, buf, 2048)
            files.append(buf.value)
        return files


# ------------------------------------------------------------------ окно


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.files: list[Path] = []
        self.events: queue.Queue = queue.Queue()
        self.cancel_event = threading.Event()
        self.running = False
        self.outputs: list[str] = []
        self.current_file = ""
        self.pending_asks: list[tuple[threading.Event, dict]] = []
        self.closing = False

        # анимации
        self._prog_target = 0.0
        self._prog_shown = 0.0
        self._prog_job: Optional[str] = None
        self._spin_job: Optional[str] = None
        self._spin_angle = 0
        self._pulse_job: Optional[str] = None
        self._pulse_state = 0
        self._tween_jobs: dict[str, str] = {}
        self._btn_uid = 0
        self._tools_final = False
        self._panels: list = []

        self._file_index = 0
        self._file_total = 0

        self.prefs_loaded = False
        self._prefs: dict = {}
        self._ui_ready = False
        self._load_prefs()

        self._flogger = FileLogger()
        atexit.register(self._flogger.close)

        self._configure_root()
        self._build_ui()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(80, self._poll)
        atexit.register(engine.kill_active_process)

        self._dnd = None
        self._drop_ready = False
        try:
            self._dnd = DragDropHook(self.root, self._on_drop)
            self._drop_ready = True
        except Exception:
            self._drop_ready = False

        self._append_log("Video Boost 1.2 — 4K/8K, гибкие настройки и «жидкое стекло».")
        self._append_log("Проверяю инструменты...")
        if self._drop_ready:
            self._append_log("Перетаскивание видео в окно включено.")
        else:
            self._append_log(
                "Перетаскивание файлов в окно недоступно — добавляйте через кнопку."
            )
        self._animate_entrance()
        self._header_shimmer()
        self._breathe_tools_status()
        self.root.after(400, self._mark_ui_ready)
        threading.Thread(target=self._tools_check_worker, daemon=True).start()

    def _mark_ui_ready(self) -> None:
        """После реального показа окна размер можно сохранять в prefs."""
        self._ui_ready = True
        self._save_prefs()

    # ------------------------------------------------------------- окно

    def _resource(self, name: str) -> Path:
        """Путь к файлу ресурса (в exe — во временной папке распаковки)."""
        if getattr(sys, "frozen", False):
            base = Path(getattr(sys, "_MEIPASS", "."))
        else:
            base = Path(__file__).resolve().parent
        return base / name

    def _apply_icon(self, path: str) -> None:
        """Иконка окна после маппинга — иначе в exe-сборке ломается раскладка."""
        try:
            self.root.iconbitmap(path)
        except Exception:
            pass

    def _configure_root(self) -> None:
        self.root.title("Video Boost — улучшение видео и плавности")
        try:
            ico = self._resource("video_boost.ico")
            if ico.exists():
                if getattr(sys, "frozen", False):
                    # В собранном exe мгновенный iconbitmap (до маппинга окна)
                    # оставляет всю раскладку неупакованной — задаём иконку
                    # отложенно, после того как окно реально отобразится.
                    icon_path = str(ico)
                    self.root.after(
                        120, lambda p=icon_path: self._apply_icon(p))
                else:
                    self.root.iconbitmap(str(ico))
        except Exception:
            pass
        width, height = 1100, 980
        try:
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            # оставляем место под заголовок окна и панель задач
            max_h = max(780, sh - 100)
            height = min(height, max_h)
            x = max(0, (sw - width) // 2)
            y = max(8, (sh - 100 - height) // 2)
            self.root.geometry(f"{width}x{height}+{x}+{y}")

            # сохранённый размер применяем только если окно целиком
            # помещается на экране — иначе низ уезжает под панель задач
            geo = str(self._prefs.get("geometry") or "")
            m = re.match(r"(\d+)x(\d+)([+-]\d+)?([+-]\d+)?", geo)
            if m:
                gw, gh = int(m.group(1)), int(m.group(2))
                gx = int(m.group(3)) if m.group(3) else x
                gy = int(m.group(4)) if m.group(4) else y
                if (960 <= gw <= sw and 780 <= gh <= max_h
                        and gx >= 0 and gy >= 0
                        and gx + gw <= sw and gy + gh <= sh - 48):
                    self.root.geometry(f"{gw}x{gh}+{gx}+{gy}")
        except Exception:
            self.root.geometry(f"{width}x{height}")
        self.root.minsize(960, 780)
        self.root.configure(bg=BG)
        try:
            self.root.tk.call("tk", "scaling", 1.15)
        except Exception:
            pass

    # ------------------------------------------------------------ помощники

    def _tween(self, key: str, apply_fn: Callable[[float], None],
               steps: int = 8, interval: int = 26, on_done=None) -> None:
        old = self._tween_jobs.pop(key, None)
        if old:
            try:
                self.root.after_cancel(old)
            except Exception:
                pass
        state = {"i": 0}

        def step() -> None:
            state["i"] += 1
            apply_fn(state["i"] / steps)
            if state["i"] < steps:
                self._tween_jobs[key] = self.root.after(interval, step)
            else:
                self._tween_jobs.pop(key, None)
                if on_done:
                    on_done()

        self._tween_jobs[key] = self.root.after(0, step)

    def _tween_attr(self, key: str, widget: tk.Misc, attr: str,
                    c_from: str, c_to: str, steps: int = 8, interval: int = 26,
                    on_done=None) -> None:
        def apply(t: float) -> None:
            try:
                widget.configure(**{attr: _mix(c_from, c_to, t)})
            except tk.TclError:
                pass
        self._tween(key, apply, steps=steps, interval=interval, on_done=on_done)

    def _flash(self, widget: tk.Misc, attr: str, start_color: str,
               end_color: str, interval: int = 30, steps: int = 7) -> None:
        self._tween_attr(f"flash:{id(widget)}", widget, attr, start_color,
                         end_color, interval=interval, steps=steps)

    def _make_btn(self, parent, kind: str, text: str, command,
                  state: str = "normal", tooltip: Optional[str] = None):
        btn = RoundButton(parent, kind, text, command, state=state)
        if tooltip:
            Tooltip(btn, tooltip)
        return btn

    def _panel(self, master: tk.Misc, fill: str = CARD, border: str = BORDER,
               radius: int = 14, canvas_bg: str = BG) -> RoundPanel:
        panel = RoundPanel(master, canvas_bg=canvas_bg, fill=fill,
                           border=border, radius=radius)
        self._panels.append(panel)
        return panel

    def _badge(self, parent: tk.Misc, text: str) -> tk.Canvas:
        c = tk.Canvas(parent, width=30, height=26, bg=parent.cget("bg"),
                      highlightthickness=0, bd=0)
        round_rect(c, 1, 1, 29, 25, r=11, fill="#3a2a8f", outline="#6a56d6",
                   width=1)
        c.create_text(16, 13.5, text=text, fill="#cfc4ff",
                      font=("Segoe UI", 10, "bold"))
        return c

    def _section_title(self, parent: tk.Misc, number: str, text: str) -> None:
        row = tk.Frame(parent, bg=parent.cget("bg"))
        row.pack(anchor="w", fill="x", padx=12, pady=(8, 2))
        self._badge(row, number).pack(side="left")
        tk.Label(row, text="  " + text, bg=parent.cget("bg"), fg=TEXT,
                 font=F_SECTION).pack(side="left")

    # -------------------------------------------------------------- UI

    def _build_ui(self) -> None:
        outer = tk.Frame(self.root, bg=BG)
        outer.pack(fill="both", expand=True, padx=18, pady=12)

        # ---------------- шапка ----------------
        self.header = tk.Canvas(outer, bg=BG, highlightthickness=0, height=64)
        self.header.pack(fill="x")
        self.header.bind("<Configure>", self._paint_header)

        self._header_title = self.header.create_text(
            22, 22, anchor="w", text="Video Boost",
            fill="#010208", font=F_TITLE,
        )
        self._header_title_face = self.header.create_text(
            22, 20, anchor="w", text="Video Boost",
            fill="#f8faff", font=F_TITLE,
        )
        self._header_sub = self.header.create_text(
            24, 47, anchor="w",
            text="Нейросетевое улучшение качества и плавности видео  ·  AMD Radeon RX 570",
            fill="#9aa5c6", font=F_SUB,
        )
        self._header_ver = self.header.create_text(
            -18, 44, anchor="e", text="v1.2  ·  GPU · 4K/8K",
            fill="#5d6788", font=("Segoe UI", 10, "bold"),
        )

        # ---------------- тело ----------------
        body = tk.Frame(outer, bg=BG)
        body.pack(fill="x", pady=(10, 0))
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)

        left = self._panel(body)
        left.grid(row=0, column=0, sticky="nsew")
        right = self._panel(body)
        right.grid(row=0, column=1, sticky="nsew", padx=(12, 0))

        # файлы и запуск — в одной карточке: колонки выровнены по высоте,
        # под списком файлов не остаётся пустой «дыры»
        self._build_files_card(left.body)
        self._build_start_card(left.body)
        self._build_settings_card(right.body)
        self._start_card = left

        # ---------------- нижняя строка (всегда видна) ----------------
        footer = tk.Frame(outer, bg=BG)
        footer.pack(side="bottom", fill="x", pady=(8, 0))

        self.tools_status = tk.Label(
            footer, text="● Проверяю инструменты...", bg=BG, fg=MUTED,
            font=("Segoe UI", 9),
        )
        self.tools_status.pack(side="left")

        self.prepare_btn = self._make_btn(
            footer, "secondary", "Скачать / проверить инструменты",
            self._prepare_tools, tooltip=TOOLTIPS["prepare"],
        )
        self.prepare_btn.pack(side="right")

        # ---------------- журнал ----------------
        log_panel = self._panel(outer, fill=DARK, border="#1a2233", radius=14)
        log_panel.pack(fill="both", expand=True, pady=(10, 0))
        self._build_log_card(log_panel.body)

        # подгоняем высоту карточек под их содержимое
        self._fit_panels()

    def _fit_panels(self) -> None:
        self.root.update_idletasks()
        for panel in self._panels:
            try:
                req = panel.body.winfo_reqheight()
                panel.configure(height=max(120, int(req) + 2 * panel.radius + 3))
            except (tk.TclError, AttributeError):
                pass

    def _paint_header(self, event=None) -> None:
        canvas = self.header
        try:
            w = max(1, canvas.winfo_width())
            h = max(1, canvas.winfo_height())
        except Exception:
            return
        canvas.delete("bg")
        canvas.delete("glass")
        # стеклянная панель шапки: градиент + диагональный блик
        glass_fill(canvas, 1, 1, w - 2, h - 2, 18, HEADER_TOP, HEADER_BOT,
                   gloss=0.30, shadex=0.10, tags="glass")
        canvas.create_polygon(
            w * 0.58, 1, w * 0.70, 1, w * 0.56, h - 2, w * 0.47, h - 2,
            fill=_mix(HEADER_TOP, "#ffffff", 0.055), outline="", tags="glass",
        )
        round_rect(canvas, 1, 1, w - 2, h - 2, r=18, fill="",
                   outline=HEADER_BORDER, width=1, tags="glass")
        canvas.create_line(1 + 18, 1.5, w - 2 - 18, 1.5,
                           fill=_mix(HEADER_BORDER, "#ffffff", 0.40),
                           tags="glass")
        # тёмная дорожка под бегущим бликом
        round_rect(canvas, 12, h - 7, w - 12, h - 4, r=2,
                   fill="#1c2547", outline="", tags="glass")
        canvas.tag_lower("glass")
        try:
            canvas.coords(self._header_ver, w - 18, 44)
        except Exception:
            pass

    def _header_shimmer(self) -> None:
        """Бегущий световой отрезок по дорожке в шапке."""
        try:
            if not self.root.winfo_exists():
                return
            w = self.header.winfo_width()
            h = self.header.winfo_height()
        except Exception:
            return
        if w > 60 and h > 20:
            self.header.delete("shim")
            x0min, x1max = 12, w - 12
            span = max(110, (x1max - x0min) // 3)
            travel = (x1max - x0min) + span
            pos = x0min - span / 2 + (time.time() * 110) % travel
            glow = _mix(ACCENT, ACCENT_2, 0.55)
            core = _mix(ACCENT_2, "#ffffff", 0.40)
            for dx0, dx1, color in (
                (-span / 2, -span * 0.1, _mix("#1c2547", glow, 0.45)),
                (-span * 0.1, span * 0.35, glow),
                (span * 0.35, span / 2, core),
            ):
                a = pos + dx0
                b = pos + dx1
                if b <= x0min or a >= x1max:
                    continue
                self.header.create_rectangle(
                    max(a, x0min), h - 7, min(b, x1max), h - 4,
                    fill=color, outline="", tags="shim")
        self.root.after(60, self._header_shimmer)


    # ---------------------------------------------------------- файлы

    def _build_files_card(self, card: tk.Frame) -> None:
        self._section_title(card, "1", "Видео")
        tk.Label(card, text="Можно добавить несколько файлов — "
                            "или перетащите их прямо в это окно",
                 bg=CARD, fg=MUTED, font=("Segoe UI", 9)).pack(
            anchor="w", padx=12, pady=(0, 6))

        list_panel = RoundPanel(card, canvas_bg=CARD, fill=FIELD,
                                border=BORDER, radius=10,
                                glass_top="#141a26", glass_bot="#0a0d12",
                                req_height=120)
        list_panel.pack(fill="both", expand=True, padx=12)
        list_wrap = list_panel.body

        self.file_list = tk.Listbox(
            list_wrap, height=5, selectmode="extended", bg=FIELD, fg=TEXT,
            selectbackground=ACCENT, selectforeground="#ffffff",
            activestyle="none", borderwidth=0, highlightthickness=0,
            font=("Segoe UI", 10),
        )
        self.vscroll = SlimScrollbar(list_wrap, "vertical", bg=FIELD)
        self.hscroll = SlimScrollbar(list_wrap, "horizontal", bg=FIELD)
        self.vscroll.attach(self.file_list)
        self.hscroll.attach(self.file_list)
        self.vscroll.pack(side="right", fill="y")
        self.hscroll.pack(side="bottom", fill="x")
        self.file_list.pack(side="left", fill="both", expand=True)

        self.file_menu = tk.Menu(self.root, tearoff=0, font=("Segoe UI", 9),
                                 bg=CARD, fg=TEXT_2, activebackground=ACCENT,
                                 activeforeground="#ffffff", bd=0)
        self.file_menu.add_command(label="➕ Добавить видео…",
                                   command=self._add_files)
        self.file_menu.add_command(label="🗑 Удалить выбранное",
                                   command=self._remove_selected)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="📂 Открыть папку файла",
                                   command=self._open_file_folder)
        self.file_menu.add_command(label="⭕ Очистить список",
                                   command=self._clear_files)
        self.file_list.bind("<Button-3>", self._show_file_menu)
        self.file_list.bind("<Delete>", lambda _e: self._remove_selected())

        buttons = tk.Frame(card, bg=CARD)
        buttons.pack(fill="x", padx=12, pady=(6, 2))
        self.add_btn = self._make_btn(buttons, "secondary", "Добавить видео…",
                                      self._add_files)
        self.add_btn.pack(side="left")
        self.remove_btn = self._make_btn(buttons, "secondary", "Удалить выбранное",
                                         self._remove_selected)
        self.remove_btn.pack(side="left", padx=(6, 0))
        self.clear_btn = self._make_btn(buttons, "secondary", "Очистить",
                                        self._clear_files)
        self.clear_btn.pack(side="left", padx=(6, 0))

        self.files_count = tk.Label(card, text="Видео не выбраны", bg=CARD,
                                    fg=MUTED, font=("Segoe UI", 9), anchor="w")
        self.files_count.pack(fill="x", padx=13, pady=(3, 8))

    def _build_settings_card(self, card: tk.Frame) -> None:
        self._section_title(card, "2", "Настройки")

        prefs_preset = self._prefs.get("preset", "balanced")
        if prefs_preset not in [o[0] for o in PRESET_PILLS]:
            prefs_preset = "balanced"
        self.preset_choice = PillChoice(
            card, PRESET_PILLS, prefs_preset,
            on_change=lambda _k: self._on_preset_changed(),
        )
        self.preset_choice.pack(fill="x", padx=12)
        Tooltip(self.preset_choice,
                "Пресет задаёт базу — настройки ниже можно менять вручную.")

        self.preset_desc = tk.Label(card, text="", bg=CARD, fg=MUTED,
                                    font=F_SMALL, justify="left",
                                    wraplength=340, anchor="w")
        self.preset_desc.pack(fill="x", padx=13, pady=(5, 2))

        self._make_separator(card)

        # --- качество картинки ---
        scale_row = self._settings_row(card, "Масштаб")
        self.scale_choice = PillChoice(
            scale_row, SCALE_PILLS, self._pref_in("scale", SCALE_PILLS, "preset"),
            on_change=lambda _k: self._on_manual_change(), big=False)
        self.scale_choice.pack(side="left", fill="x", expand=True, padx=(6, 0))
        Tooltip(self.scale_choice, TOOLTIPS["scale"])

        model_row = self._settings_row(card, "Модель")
        self.model_choice = PillChoice(
            model_row, MODEL_PILLS, self._pref_in("model", MODEL_PILLS, "auto"),
            on_change=lambda _k: self._on_manual_change(), big=False)
        self.model_choice.pack(side="left", fill="x", expand=True, padx=(6, 0))
        Tooltip(self.model_choice, TOOLTIPS["model"])

        interp_row = tk.Frame(card, bg=CARD)
        interp_row.pack(fill="x", padx=12, pady=(3, 0))
        tk.Label(interp_row, text="Плавность", bg=CARD, fg=TEXT_2,
                 font=F_BODY_BOLD, width=11, anchor="w").pack(side="left")
        interp_on = (bool(self._prefs.get("interpolate", True))
                     if self.prefs_loaded else True)
        self.interp_var = tk.BooleanVar(value=interp_on)
        self.interp_switch = Switch(interp_row, self.interp_var,
                                    on_change=self._on_interp_changed)
        self.interp_switch.pack(side="left")
        self._interp_user_changed = self.prefs_loaded and ("interpolate" in self._prefs)
        self.fps_choice = PillChoice(
            interp_row, FPS_PILLS, self._pref_in("fps", FPS_PILLS, "60"),
            on_change=lambda _k: self._on_manual_change(), big=False)
        self.fps_choice.pack(side="left", fill="x", expand=True, padx=(12, 0))
        Tooltip(self.fps_choice, TOOLTIPS["fps"])

        content_row = self._settings_row(card, "Тип видео")
        self.content_choice = PillChoice(
            content_row, CONTENT_PILLS, self._pref_in("content", CONTENT_PILLS, "general"),
            on_change=lambda _k: self._on_manual_change(), big=False)
        self.content_choice.pack(side="left", fill="x", expand=True, padx=(6, 0))
        Tooltip(self.content_choice, TOOLTIPS["content"])

        self._make_separator(card)

        # --- кодирование ---
        enc_row = self._settings_row(card, "Кодировщик")
        self.encoder_choice = PillChoice(
            enc_row, ENCODER_PILLS, self._pref_in("encoder", ENCODER_PILLS, "preset"),
            on_change=lambda _k: self._on_manual_change(), big=False)
        self.encoder_choice.pack(side="left", fill="x", expand=True, padx=(6, 0))
        Tooltip(self.encoder_choice, TOOLTIPS["encoder"])

        qual_row = self._settings_row(card, "Качество")
        self.quality_choice = PillChoice(
            qual_row, QUALITY_PILLS, self._pref_in("quality", QUALITY_PILLS, "preset"),
            on_change=lambda _k: self._on_manual_change(), big=False)
        self.quality_choice.pack(side="left", fill="x", expand=True, padx=(6, 0))
        Tooltip(self.quality_choice, TOOLTIPS["quality"])

        tile_row = self._settings_row(card, "Tile")
        self.tile_choice = PillChoice(
            tile_row, TILE_PILLS, self._pref_in("tile", TILE_PILLS, "preset"),
            on_change=lambda _k: self._on_manual_change(), big=False)
        self.tile_choice.pack(side="left", fill="x", expand=True, padx=(6, 0))
        Tooltip(self.tile_choice, TOOLTIPS["tile"])

        # --- место на диске ---
        space_on = (bool(self._prefs.get("save_space", True))
                    if self.prefs_loaded else True)
        self.space_var = tk.BooleanVar(value=space_on)
        row2 = tk.Frame(card, bg=CARD)
        row2.pack(fill="x", padx=12, pady=(6, 0))
        self.space_switch = Switch(row2, self.space_var,
                                   on_change=self._on_manual_change)
        self.space_switch.pack(side="left")
        tk.Label(row2, text="Экономить место: JPEG-промежутки",
                 bg=CARD, fg=TEXT, font=F_BODY).pack(
            side="left", padx=(10, 0))
        Tooltip(self.space_switch, TOOLTIPS["space"])

        note = tk.Label(
            card,
            text="Скорость на RX 570: x2 ~1–2 ч на минуту 1080p; x3 — дольше; "
                 "x4 (8K) — десятки часов (предупредим).",
            bg=CARD, fg=MUTED, font=F_SMALL, justify="left",
            wraplength=340, anchor="w",
        )
        note.pack(fill="x", padx=13, pady=(3, 4))

        # перенос описаний подстраиваем под фактическую ширину карточки,
        # иначе при смене размера окна остаётся лишняя пустая строка
        def _fit_wrap(_event=None) -> None:
            try:
                width = card.winfo_width() - 26
            except Exception:
                return
            if width < 240:
                return
            try:
                if abs(int(self.preset_desc.cget("wraplength")) - width) < 2:
                    return
            except (tk.TclError, ValueError):
                pass
            self.preset_desc.configure(wraplength=width)
            note.configure(wraplength=width)

        card.bind("<Configure>", _fit_wrap, add="+")
        self.root.after(50, _fit_wrap)

        if self.prefs_loaded:
            self._on_preset_changed(animate=False, apply_defaults=False)
        else:
            self._on_preset_changed(animate=False)

    def _settings_row(self, card: tk.Frame, label_text: str,
                      width: int = 11) -> tk.Frame:
        """Строка «название — управление» в карточке настроек; возвращает row."""
        row = tk.Frame(card, bg=CARD)
        row.pack(fill="x", padx=12, pady=(2, 0))
        tk.Label(row, text=label_text, bg=CARD, fg=TEXT_2,
                 font=F_BODY_BOLD, width=width, anchor="w").pack(side="left")
        return row

    def _make_separator(self, card: tk.Frame, pady: tuple = (5, 2)) -> None:
        sep = tk.Frame(card, bg=BORDER, height=1)
        sep.pack(fill="x", padx=12, pady=pady)

    def _pref_in(self, key: str, pills: list, default: str) -> str:
        value = self._prefs.get(key, default)
        if not isinstance(value, str):
            value = default
        return value if any(o[0] == value for o in pills) else default

    def _on_manual_change(self) -> None:
        self._save_prefs()

    def _on_interp_changed(self) -> None:
        self._interp_user_changed = True
        self._save_prefs()

    def _on_preset_changed(self, animate: bool = True,
                           apply_defaults: bool = True) -> None:
        key = self.preset_choice.get()
        preset = engine.PRESETS.get(key)
        if not preset:
            return
        if apply_defaults:
            default_scale = {2: "x2", 3: "x3", 4: "x4"}.get(preset.scale, "x2")
            self.scale_choice.set(default_scale)
            self.model_choice.set("auto")
            self.fps_choice.set(str(preset.target_fps))
            self.encoder_choice.set("preset")
            self.quality_choice.set("preset")
            self.tile_choice.set("preset")
            self._interp_user_changed = False
        if not self._interp_user_changed:
            self.interp_switch.set(bool(preset.interpolate), animate=animate)
        self.preset_desc.configure(text=preset.description)
        self._save_prefs()
        if animate:
            self.preset_desc.configure(fg="#33405a")
            self._flash(self.preset_desc, "fg", "#33405a", MUTED)

    def _build_start_card(self, card: tk.Frame) -> None:
        self._make_separator(card, pady=(8, 2))
        self._section_title(card, "3", "Запуск")

        row = tk.Frame(card, bg=CARD)
        row.pack(fill="x", padx=12, pady=(6, 0))

        self.start_btn = self._make_btn(row, "accent", "▶  Начать обработку",
                                        self._start, tooltip=TOOLTIPS["start"])
        self.start_btn.pack(side="left")

        self.cancel_btn = self._make_btn(row, "danger", "Отмена", self._cancel,
                                         state="disabled",
                                         tooltip=TOOLTIPS["cancel"])
        self.cancel_btn.pack(side="left", padx=(8, 0))

        self.open_btn = self._make_btn(row, "secondary",
                                       "Открыть папку",
                                       self._open_output_folder, state="disabled",
                                       tooltip=TOOLTIPS["open"])
        self.open_btn.pack(side="left", padx=(8, 0))

        # прогресс: спиннер + полоса + проценты
        prow = tk.Frame(card, bg=CARD)
        prow.pack(fill="x", padx=12, pady=(8, 0))

        self.spinner = tk.Canvas(prow, width=18, height=18, bg=CARD,
                                 highlightthickness=0, bd=0)
        self._spin_arc = self.spinner.create_arc(
            1, 1, 17, 17, start=0, extent=95, style="arc",
            outline=ACCENT_2, width=3,
        )
        self.spinner.pack(side="left")
        self.spinner.pack_forget()

        self.progress = BoostBar(prow)
        self.progress.pack(side="left", fill="x", expand=True, padx=(6, 8))

        self.pct_label = tk.Label(prow, text="0%", bg=CARD, fg=TEXT_2,
                                  font=F_BODY_BOLD, width=5,
                                  anchor="e")
        self.pct_label.pack(side="right")

        self.status_var = tk.StringVar(value="Готов к работе")
        self.status_label = tk.Label(card, textvariable=self.status_var, bg=CARD,
                                     fg=MUTED, font=F_BODY, anchor="w")
        self.status_label.pack(fill="x", padx=13, pady=(0, 6))

        self.root.bind("<Return>", self._on_return)
        self.root.bind("<Escape>", self._on_escape)

    def _build_log_card(self, card: tk.Frame) -> None:
        title_row = tk.Frame(card, bg=CARD)
        title_row.pack(anchor="w", fill="x", padx=12, pady=(10, 4))
        self._badge(title_row, "≡").pack(side="left")
        tk.Label(title_row, text="  Журнал", bg=CARD, fg=TEXT,
                 font=F_SECTION).pack(side="left")

        self.clear_log_btn = self._make_btn(title_row, "secondary", "Очистить",
                                            self._clear_log)
        self.clear_log_btn.pack(side="right")

        log_panel = RoundPanel(card, canvas_bg=CARD, fill=DARK,
                               border="#1a2233", radius=12,
                               glass_top=DARK_TOP, glass_bot=DARK,
                               req_height=150)
        log_panel.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        log_wrap = log_panel.body

        self.log_text = tk.Text(
            log_wrap, height=4, bg=DARK, fg="#d6deee", insertbackground="#d6deee",
            relief="flat", wrap="word", font=("Segoe UI", 10), state="disabled",
            padx=10, pady=8, borderwidth=0,
        )
        self.log_scroll = SlimScrollbar(log_wrap, "vertical", bg=DARK)
        self.log_scroll.attach(self.log_text)
        self.log_scroll.pack(side="right", fill="y")
        self.log_text.pack(side="left", fill="both", expand=True)

        self.log_text.tag_configure("muted", foreground="#5b6472")
        self.log_text.tag_configure("err", foreground="#fca5a5")
        self.log_text.tag_configure("warn", foreground="#fcd34d")
        self.log_text.tag_configure("ok", foreground="#86efac")
        self.log_text.tag_configure("step", foreground="#a5b4fc")

    def _clear_log(self) -> None:
        try:
            self.log_text.configure(state="normal")
            self.log_text.delete("1.0", "end")
            self.log_text.configure(state="disabled")
        except tk.TclError:
            pass


    # --------------------------------------------------------- анимации

    def _animate_entrance(self) -> None:
        try:
            self.root.attributes("-alpha", 0.0)
        except Exception:
            return

        def fade(step: int = 0) -> None:
            alpha = min(1.0, step / 10)
            try:
                self.root.attributes("-alpha", alpha)
            except Exception:
                return
            if step < 10:
                self.root.after(24, fade, step + 1)
            else:
                try:
                    self.root.attributes("-alpha", 1.0)
                except Exception:
                    pass

        fade()

    def _breathe_tools_status(self) -> None:
        """Мягкое «дыхание» статуса инструментов, пока он проверяется."""
        if self._tools_final:
            return
        t = (time.time() % 4) * 0.5          # 0..2
        wave = t if t <= 1 else 2 - t        # треугольная волна 0..1..0
        try:
            self.tools_status.configure(fg=_mix(MUTED, ACCENT, wave))
        except tk.TclError:
            return
        self.root.after(120, self._breathe_tools_status)

    def _set_progress(self, frac: float) -> None:
        frac = max(0.0, min(1.0, float(frac)))
        self._prog_target = frac
        if self._prog_job is None:
            self._ease_progress()

    def _ease_progress(self) -> None:
        diff = self._prog_target - self._prog_shown
        if abs(diff) < 0.0015:
            self._prog_shown = self._prog_target
            self.progress.set(self._prog_shown)
            self.pct_label.configure(text=f"{int(round(self._prog_shown * 100))}%")
            self._prog_job = None
            return
        self._prog_shown += diff * 0.16
        self.progress.set(self._prog_shown)
        self.pct_label.configure(text=f"{int(round(self._prog_shown * 100))}%")
        self._prog_job = self.root.after(16, self._ease_progress)

    def _set_spinner(self, on: bool) -> None:
        try:
            if on:
                self.spinner.pack(side="left")
            else:
                if self._spin_job:
                    try:
                        self.root.after_cancel(self._spin_job)
                    except Exception:
                        pass
                    self._spin_job = None
                self.spinner.pack_forget()
        except tk.TclError:
            return
        if on and self._spin_job is None:
            self._spin_tick()

    def _spin_tick(self) -> None:
        self._spin_angle = (self._spin_angle + 6) % 360
        try:
            self.spinner.itemconfigure(self._spin_arc, start=-self._spin_angle,
                                       extent=95, outline=ACCENT_2)
        except tk.TclError:
            self._spin_job = None
            return
        self._spin_job = self.root.after(34, self._spin_tick)

    def _set_card_pulse(self, on: bool) -> None:
        if not on:
            if self._pulse_job:
                try:
                    self.root.after_cancel(self._pulse_job)
                except Exception:
                    pass
                self._pulse_job = None
            try:
                self._start_card.configure(highlightbackground=BORDER)
            except tk.TclError:
                pass
            return
        if self._pulse_job:
            return

        def tick() -> None:
            self._pulse_state = 1 - self._pulse_state
            color = ACCENT_SOFT if self._pulse_state else BORDER
            try:
                self._start_card.configure(highlightbackground=color)
            except tk.TclError:
                self._pulse_job = None
                return
            self._pulse_job = self.root.after(900, tick)

        self._pulse_job = self.root.after(0, tick)

    # ---------------------------------------------------------- файлы

    def _add_paths(self, paths) -> int:
        """Добавляет пути (диалог или drag&drop). Возвращает сколько реально новых."""
        existing = {str(p).lower() for p in self.files}
        added = 0
        for raw in paths:
            if not raw:
                continue
            p = Path(raw).resolve()
            if str(p).lower() not in existing:
                self.files.append(p)
                existing.add(str(p).lower())
                added += 1
        return added

    def _add_files(self) -> None:
        if self.running:
            return
        paths = filedialog.askopenfilenames(
            title="Выберите видеофайлы", filetypes=VIDEO_TYPES, parent=self.root,
        )
        if not paths:
            return
        added = self._add_paths(paths)
        self._refresh_files()
        if added:
            self._append_log(f"Добавлено видео: {added}")

    def _on_drop(self, raw_paths) -> None:
        """Файлы перетащены мышкой в окно программы."""
        if self.running or not raw_paths:
            return
        paths = [p for p in raw_paths
                 if p and Path(p).suffix.lower() in VIDEO_EXTS]
        added = self._add_paths(paths)
        self._refresh_files()
        if added:
            self._append_log(f"Добавлено видео (перетащены в окно): {added}")
        else:
            self._append_log("В окно перетащены файлы без видео — ничего не добавлено.")

    def _remove_selected(self) -> None:
        if self.running:
            return
        selected = list(self.file_list.curselection())
        for index in reversed(selected):
            if 0 <= index < len(self.files):
                del self.files[index]
        self._refresh_files()

    def _clear_files(self) -> None:
        if self.running:
            return
        self.files.clear()
        self._refresh_files()

    def _open_file_folder(self) -> None:
        selection = self.file_list.curselection()
        if not selection:
            return
        path = self.files[selection[0]]
        try:
            os.startfile(str(path.parent))  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Не удалось открыть папку", str(exc),
                                 parent=self.root)

    def _show_file_menu(self, event) -> None:  # noqa: ANN001
        try:
            self.file_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.file_menu.grab_release()

    def _refresh_files(self) -> None:
        self.file_list.delete(0, "end")
        for path in self.files:
            self.file_list.insert("end", str(path))
        if self.files:
            self.files_count.configure(text=f"Выбрано видео: {len(self.files)}",
                                       fg=ACCENT)
            self._flash(self.files_count, "fg", ACCENT, TEXT)
        else:
            self.files_count.configure(text="Видео не выбраны", fg=MUTED)
        self._refresh_start_button_text()

    def _refresh_start_button_text(self) -> None:
        if self.running:
            return
        count = len(self.files)
        if count > 1:
            self.start_btn.configure(text=f"▶  Начать обработку ({count})")
        else:
            self.start_btn.configure(text="▶  Начать обработку")

    # ---------------------------------------------------------------- tools

    @staticmethod
    def _find_tools() -> bool:
        manager = engine.ToolManager(lambda _m: None, lambda _f, _t: None,
                                     threading.Event())
        return manager.find() is not None

    def _tools_check_worker(self) -> None:
        try:
            ready = self._find_tools()
        except Exception:
            ready = False
        self.events.put(("tools", ready))

    def _prepare_tools(self) -> None:
        if self.running:
            return
        if self._find_tools():
            self._append_log("Инструменты уже готовы — можно обрабатывать видео.")
            return
        if not messagebox.askyesno(
            "Подготовка инструментов",
            "Для работы нужно скачать инструменты (~700 МБ):\n\n"
            "  • FFmpeg (~195 МБ)\n"
            "  • Real-ESRGAN (~46 МБ)\n"
            "  • RIFE (~432 МБ)\n\n"
            "Это делается один раз и занимает 5–15 минут.\nСкачать сейчас?",
            parent=self.root,
        ):
            return

        self.cancel_event = threading.Event()
        self._set_running(True)
        self.status_var.set("Подготовка инструментов...")
        threading.Thread(target=self._tools_download_worker, daemon=True).start()

    def _tools_download_worker(self) -> None:
        q = self.events
        cancel = self.cancel_event
        try:
            manager = engine.ToolManager(
                log=lambda m: q.put(("log", m)),
                progress=lambda f, t: q.put(("progress", f, t)),
                cancel=cancel,
            )
            manager.ensure_tools()
            q.put(("done", True, [], ""))
        except engine.Cancelled:
            q.put(("done", False, [], "Отменено пользователем."))
        except Exception as exc:  # noqa: BLE001
            q.put(("done", False, [], str(exc)))

    # ---------------------------------------------------------------- start

    def _confirm_from_worker(self, text: str) -> bool:
        event = threading.Event()
        box: dict = {}
        self.pending_asks.append((event, box))
        self.events.put(("ask", text, event, box))
        event.wait()
        return bool(box.get("answer", False))

    def _start(self) -> None:
        if self.running:
            return
        if not self.files:
            messagebox.showinfo("Нет видео",
                                "Сначала добавьте хотя бы один видеофайл.",
                                parent=self.root)
            return

        preset = engine.PRESETS[self.preset_choice.get()]
        settings = engine.Settings(
            preset=preset,
            content=self.content_choice.get(),
            interpolate=bool(self.interp_var.get()),
            save_space=bool(self.space_var.get()),
            target_fps=int(self.fps_choice.get() or "60"),
            scale_mode=self.scale_choice.get(),
            model_mode=self.model_choice.get(),
            encoder_mode=self.encoder_choice.get(),
            quality=self.quality_choice.get(),
            tile_mode=self.tile_choice.get(),
        )
        self._save_prefs()

        if not self._find_tools():
            if not messagebox.askyesno(
                "Первый запуск",
                "Инструменты ещё не скачаны.\n\n"
                "Сейчас будут загружены FFmpeg, Real-ESRGAN и RIFE "
                "(~700 МБ, 5–15 минут). Скачать и начать?",
                parent=self.root,
            ):
                return

        files = list(self.files)
        self.outputs = []
        self.current_file = ""
        self._file_index = 0
        self._file_total = len(files)
        self.cancel_event = threading.Event()
        self._set_running(True)
        self.progress.set_color(ACCENT)
        self._set_progress(0.0)
        self.status_var.set("Подготовка...")
        threading.Thread(target=self._worker, args=(files, settings),
                         daemon=True).start()

    def _worker(self, files: list, settings: engine.Settings) -> None:
        q = self.events
        cancel = self.cancel_event
        try:
            manager = engine.ToolManager(
                log=lambda m: q.put(("log", m)),
                progress=lambda f, t: q.put(("progress", f, t)),
                cancel=cancel,
            )
            tools = manager.ensure_tools()
            engine.cleanup_temp()

            pipeline = engine.Pipeline(
                tools,
                log=lambda m: q.put(("log", m)),
                progress=lambda f, t: q.put(("progress", f, t)),
                confirm=self._confirm_from_worker,
                cancel=cancel,
            )

            outputs: list[str] = []
            for index, path in enumerate(files, 1):
                if cancel.is_set():
                    raise engine.Cancelled()
                q.put(("file", index, len(files), Path(path).name))
                result = pipeline.process_video(Path(path), settings)
                outputs.append(str(result))

            q.put(("done", True, outputs, ""))
        except engine.Cancelled:
            q.put(("done", False, [], "Отменено пользователем."))
        except Exception as exc:  # noqa: BLE001
            q.put(("done", False, [], str(exc)))

    def _cancel(self) -> None:
        if not self.running:
            return
        self.cancel_event.set()
        engine.kill_active_process()
        self.cancel_btn.configure(state="disabled")
        self.status_var.set("Останавливаю...")
        self.status_label.configure(fg=ORANGE)
        self.progress.set_color(ORANGE)
        self._append_log("Отмена: останавливаю текущий процесс...")

    def _open_output_folder(self) -> None:
        if not self.outputs:
            return
        folder = os.path.dirname(self.outputs[-1])
        try:
            os.startfile(folder)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Не удалось открыть папку", str(exc),
                                 parent=self.root)

    # ------------------------------------------------------------ run state

    def _set_running(self, running: bool) -> None:
        self.running = running
        state = "disabled" if running else "normal"

        for widget in (self.add_btn, self.remove_btn, self.clear_btn,
                       self.prepare_btn):
            widget.configure(state=state)

        self.preset_choice.set_enabled(not running)
        self.content_choice.set_enabled(not running)
        self.scale_choice.set_enabled(not running)
        self.model_choice.set_enabled(not running)
        self.fps_choice.set_enabled(not running)
        self.encoder_choice.set_enabled(not running)
        self.quality_choice.set_enabled(not running)
        self.tile_choice.set_enabled(not running)
        self.interp_switch.set_enabled(not running)
        self.space_switch.set_enabled(not running)

        self.progress.set_active(running)

        if running:
            self.start_btn.configure(state="disabled")
            self.cancel_btn.configure(state="normal")
            self.open_btn.configure(state="disabled")
            self.status_label.configure(fg=ACCENT)
            self._set_spinner(True)
            self._set_card_pulse(True)
        else:
            self.start_btn.configure(state="normal")
            self.cancel_btn.configure(state="disabled")
            self.open_btn.configure(state="normal" if self.outputs else "disabled")
            self._set_spinner(False)
            self._set_card_pulse(False)
            self._refresh_start_button_text()


    # ---------------------------------------------------------------- queue

    def _poll(self) -> None:
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]

                if kind == "log":
                    self._append_log(event[1])

                elif kind == "progress":
                    frac, text = float(event[1]), event[2]
                    if self._file_total > 1 and self._file_index >= 1:
                        overall = (self._file_index - 1 + frac) / self._file_total
                    else:
                        overall = frac
                    self._set_progress(overall)
                    if self.current_file:
                        self.status_var.set(f"{self.current_file}  ·  {text}")
                    else:
                        self.status_var.set(text)

                elif kind == "file":
                    index, total, name = event[1], event[2], event[3]
                    self._file_index, self._file_total = index, total
                    self.current_file = f"Файл {index}/{total}: {name}"
                    self._set_progress(0.0)
                    self.status_var.set(self.current_file)
                    self._append_log(f"Файл {index} из {total}: {name}")

                elif kind == "ask":
                    text, wait_event, box = event[1], event[2], event[3]
                    if self.closing:
                        box["answer"] = False
                    else:
                        box["answer"] = messagebox.askyesno(
                            "Уточнение", text, parent=self.root)
                    wait_event.set()

                elif kind == "tools":
                    ready = bool(event[1])
                    self._tools_final = True
                    if ready:
                        self.tools_status.configure(text="● Инструменты готовы",
                                                    fg=GREEN)
                        self._append_log("Инструменты готовы.")
                    else:
                        self.tools_status.configure(
                            text="● Инструменты будут скачаны при первом запуске (~700 МБ)",
                            fg=ORANGE,
                        )
                        self._append_log(
                            "Инструменты ещё не скачаны — "
                            "это произойдёт при первом запуске."
                        )

                elif kind == "done":
                    self._handle_done(bool(event[1]), list(event[2]), str(event[3]))

        except queue.Empty:
            pass

        if not self.closing:
            self.root.after(80, self._poll)

    def _handle_done(self, ok: bool, outputs: list, message: str) -> None:
        self.current_file = ""
        self._file_index = 0
        self._file_total = 0
        self._set_running(False)

        if ok:
            self._set_progress(1.0)
            self.progress.set_color(GREEN)
            self.pct_label.configure(fg=GREEN)
            self.status_label.configure(fg=GREEN)
            self.outputs = outputs
            self.open_btn.configure(state="normal" if outputs else "disabled")
            if outputs:
                self.status_var.set("Готово — файлы сохранены рядом с исходниками")
                self._append_log("Обработка завершена успешно.")
                self._flash(self._start_card, "highlightbackground", GREEN,
                            BORDER, steps=10)
                messagebox.showinfo("Video Boost", "Готово!\n\n" + "\n".join(outputs),
                                    parent=self.root)
            else:
                self.status_var.set("Инструменты готовы")
                self.status_label.configure(fg=TEXT_2)
                self.progress.set_color(ACCENT)
                messagebox.showinfo("Video Boost",
                                    "Инструменты готовы. Можно обрабатывать видео.",
                                    parent=self.root)
        else:
            self._set_progress(0.0)
            self.status_label.configure(fg=RED)
            if message == "Отменено пользователем.":
                self.status_var.set("Отменено")
                self.progress.set_color(ACCENT)
                self._append_log("Обработка отменена.")
            else:
                self.status_var.set("Ошибка — подробности в журнале")
                self.progress.set_color(RED)
                self._append_log("ОШИБКА: " + message)
                short = message if len(message) < 1800 else message[:1800] + "\n…"
                messagebox.showerror("Ошибка обработки", short, parent=self.root)

        if self.closing:
            self.root.destroy()

    # ----------------------------------------------------------------- log

    def _append_log(self, message: str) -> None:
        timestamp = time.strftime("[%H:%M:%S] ")
        self._flogger.write(timestamp + message)

        try:
            self.log_text.configure(state="normal")
        except tk.TclError:
            return

        low = message.lower()
        if "ошибка" in low or "не удалось" in low or "error" in low or "не найден" in low:
            tag = "err"
        elif message.startswith("!") or "внимание" in low:
            tag = "warn"
        elif "готово" in low or "сохранён" in low or "завершена" in low:
            tag = "ok"
        elif message.startswith("Шаг") or message.startswith("==="):
            tag = "step"
        else:
            tag = ""

        self.log_text.insert("end", timestamp, "muted")
        self.log_text.insert("end", message.rstrip() + "\n", tag)

        try:
            lines = int(self.log_text.index("end-1c").split(".")[0])
            if lines > 3000:
                self.log_text.delete("1.0", f"{lines - 2500}.0")
        except (ValueError, tk.TclError):
            pass

        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    # ------------------------------------------------------- сохранение UI

    def _load_prefs(self) -> None:
        self.prefs_loaded = False
        try:
            with open(PREFS_FILE, "r", encoding="utf-8-sig") as fh:
                self._prefs = json.load(fh)
            self.prefs_loaded = True
        except (OSError, ValueError):
            self._prefs = {}

    # размер окна применяется в _configure_root уже с учётом экрана

    def _save_prefs(self) -> None:
        try:
            data = {
                "preset": self.preset_choice.get(),
                "content": self.content_choice.get(),
                "interpolate": bool(self.interp_var.get()),
                "save_space": bool(self.space_var.get()),
                "scale": self.scale_choice.get(),
                "model": self.model_choice.get(),
                "fps": self.fps_choice.get(),
                "encoder": self.encoder_choice.get(),
                "quality": self.quality_choice.get(),
                "tile": self.tile_choice.get(),
                "geometry": (self.root.geometry() if self._ui_ready
                             else str(self._prefs.get("geometry") or "")),
            }
            with open(PREFS_FILE, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
        except (OSError, tk.TclError, AttributeError):
            pass

    # -------------------------------------------------------------- hotkeys

    def _on_return(self, _event=None) -> None:
        if not self.running:
            self._start()

    def _on_escape(self, _event=None) -> None:
        if self.running:
            self._cancel()

    # ----------------------------------------------------------------- close

    def _on_close(self) -> None:
        self._save_prefs()
        self._flogger.close()
        if self.running:
            if not messagebox.askyesno(
                "Выход", "Обработка ещё идёт. Остановить её и выйти?",
                parent=self.root,
            ):
                return
            self.closing = True
            self.cancel_event.set()
            engine.kill_active_process()
            for wait_event, box in list(self.pending_asks):
                box["answer"] = False
                wait_event.set()
            self.root.after(900, self.root.destroy)
        else:
            self.root.destroy()


def main() -> None:
    root = tk.Tk()
    app = App(root)

    def report_callback_exception(exc, val, tb):  # noqa: ANN001
        app._append_log(f"Ошибка интерфейса: {val}")
        traceback.print_exception(exc, val, tb)

    root.report_callback_exception = report_callback_exception
    root.mainloop()


if __name__ == "__main__":
    main()
