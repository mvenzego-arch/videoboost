# -*- coding: utf-8 -*-
"""
Video Boost — движок обработки видео.

Пайплайн:
  1. Извлечение кадров (FFmpeg)
  2. Нейросетевой апскейл x2/x3/x4 (Real-ESRGAN ncnn Vulkan) — до 4K и 8K
  3. Интерполяция до 60/120 FPS (RIFE ncnn Vulkan)
  4. Сборка и кодирование на GPU AMD (hevc_amf / h264_amf) с fallback на libx264

Внешние библиотеки не нужны — только стандартная библиотека Python.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, Optional

if getattr(sys, "frozen", False):
    # exe (PyInstaller): папка приложения — рядом с самим exe
    APP_DIR = Path(sys.executable).resolve().parent
else:
    APP_DIR = Path(__file__).resolve().parent
TOOLS_DIR = APP_DIR / "tools"
TEMP_ROOT = APP_DIR / "temp"
DOWNLOAD_DIR = TOOLS_DIR / "downloads"

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

FFMPEG_URL = (
    "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/"
    "ffmpeg-n9.0-latest-win64-gpl-9.0.zip"
)
REALESRGAN_URL = (
    "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/"
    "realesrgan-ncnn-vulkan-20220424-windows.zip"
)
RIFE_URL = (
    "https://github.com/nihui/rife-ncnn-vulkan/releases/download/20221029/"
    "rife-ncnn-vulkan-20221029-windows.zip"
)

MANUAL_HELP = (
    "Не удалось подготовить инструменты автоматически.\n\n"
    "Скачайте их вручную и распакуйте в папку «tools» рядом с программой:\n"
    f"  FFmpeg:       {FFMPEG_URL}\n"
    f"  Real-ESRGAN:  {REALESRGAN_URL}\n"
    f"  RIFE:         {RIFE_URL}\n\n"
    "Внутри папки tools должны появиться: ffmpeg.exe / ffprobe.exe, "
    "realesrgan-ncnn-vulkan.exe с папкой models, rife-ncnn-vulkan.exe "
    "с папками моделей (rife-v4.6 и другие)."
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

LogFn = Callable[[str], None]
ProgressFn = Callable[[float, str], None]
ConfirmFn = Callable[[str], bool]


class Cancelled(Exception):
    """Пользователь отменил обработку."""


class EngineError(Exception):
    """Ошибка обработки, которую нужно показать пользователю."""


@dataclass(frozen=True)
class ToolSpec:
    key: str
    title: str
    url: str
    exe: str
    keep: str  # all | ffmpeg | rife
    weight: int  # приблизительный размер в МБ


TOOL_SPECS = [
    ToolSpec("ffmpeg", "FFmpeg", FFMPEG_URL, "ffmpeg.exe", "ffmpeg", 195),
    ToolSpec("realesrgan", "Real-ESRGAN", REALESRGAN_URL, "realesrgan-ncnn-vulkan.exe", "all", 46),
    ToolSpec("rife", "RIFE", RIFE_URL, "rife-ncnn-vulkan.exe", "rife", 432),
]


@dataclass(frozen=True)
class Preset:
    key: str
    label: str
    scale: int          # масштаб апскейла по умолчанию: 2 | 4
    interpolate: bool
    target_fps: int
    encoder_mode: str   # amf_h264 | amf_hevc | cpu
    quality: str        # speed | balanced | quality
    tile: int
    description: str


# качество кодирования: (qp для AMF, crf для libx264)
QUALITY_LEVELS = {
    "speed": (26, 23),
    "balanced": (22, 21),
    "quality": (19, 18),
}

PRESETS = {
    "fast": Preset(
        "fast", "Быстро", 2, False, 60, "amf_h264", "speed", 256,
        "Апскейл x2 (1080p → 4K) лёгкой моделью, H.264 на GPU, без интерполяции. "
        "Самый быстрый вариант: ~1 час на 1 минуту видео 1080p.",
    ),
    "balanced": Preset(
        "balanced", "Баланс", 2, True, 60, "amf_hevc", "balanced", 384,
        "Апскейл x2 (1080p → 4K) + плавность до 60 FPS, HEVC. "
        "Оптимальный выбор: ~1–2 часа на 1 минуту видео 1080p.",
    ),
    "max": Preset(
        "max", "Максимально", 4, True, 60, "amf_hevc", "quality", 512,
        "Апскейл x4 (1080p → 8K!) тяжёлой моделью + 60 FPS, максимум качества. "
        "На RX 570 очень медленно: десятки часов на 1 минуту видео.",
    ),
}


@dataclass
class Settings:
    preset: Preset
    content: str = "general"          # general | anime
    interpolate: bool = True
    save_space: bool = True           # JPEG-промежутки вместо PNG
    target_fps: int = 60              # конечная частота: 60 | 120
    scale_mode: str = "preset"        # preset | x2 | x3 | x4 | auto_2160 | auto_4320
    model_mode: str = "auto"          # auto | light | heavy
    encoder_mode: str = "preset"      # preset | amf_h264 | amf_hevc | cpu
    quality: str = "preset"           # preset | speed | balanced | quality
    tile_mode: str = "preset"         # preset | t256 | t384 | t512


# Ориентировочная скорость на Radeon RX 570 (4 ГБ), секунд на 1 мегапиксель
# исходного кадра. Числа получены практическими замерами; нужны только для
# оценки времени, на саму обработку не влияют.
MODEL_SPEED = {
    "realesr-animevideov3": 1.0,
    "realesrgan-x4plus-anime": 6.9,
    "realesrgan-x4plus": 22.0,
}
RIFE_MP_PER_SEC = 9.0


@dataclass
class Tools:
    ffmpeg: Path
    ffprobe: Path
    realesrgan: Path
    realesrgan_models: Path
    rife: Path
    rife_model: Path


@dataclass
class VideoInfo:
    path: Path
    width: int
    height: int
    fps: float
    duration: float
    audio_codec: str
    frames_hint: int
    is_hdr: bool


# ---------------------------------------------------------------------------
# Глобальный «активный процесс», чтобы кнопка «Отмена» и закрытие окна
# гарантированно убивали ffmpeg / нейросеть.
# ---------------------------------------------------------------------------

_ACTIVE_LOCK = threading.Lock()
_ACTIVE_PROC: Optional[subprocess.Popen] = None


def _set_active(proc: Optional[subprocess.Popen]) -> None:
    global _ACTIVE_PROC
    with _ACTIVE_LOCK:
        _ACTIVE_PROC = proc


def kill_active_process() -> None:
    with _ACTIVE_LOCK:
        proc = _ACTIVE_PROC
    if proc is not None and proc.poll() is None:
        try:
            proc.kill()
        except Exception:
            pass


def human_size(num: float) -> str:
    num = float(max(0, num))
    for unit in ("Б", "КБ", "МБ", "ГБ", "ТБ"):
        if num < 1024 or unit == "ТБ":
            return f"{num:.1f} {unit}" if unit != "Б" else f"{int(num)} {unit}"
        num /= 1024.0
    return f"{num:.1f} ТБ"


def human_time(seconds: float) -> str:
    seconds = int(max(0.0, seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours} ч {minutes} мин"
    if minutes:
        return f"{minutes} мин {secs} с"
    return f"{secs} с"


def parse_rate(value: str) -> float:
    try:
        if "/" in value:
            a, b = value.split("/", 1)
            b = float(b)
            return float(a) / b if b else 0.0
        return float(value)
    except Exception:
        return 0.0


def safe_rmtree(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)


def cleanup_temp() -> None:
    TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    for item in TEMP_ROOT.iterdir():
        try:
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
            else:
                item.unlink(missing_ok=True)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Загрузка и распаковка инструментов
# ---------------------------------------------------------------------------

class ToolManager:
    def __init__(self, log: LogFn, progress: ProgressFn, cancel: threading.Event):
        self.log = log
        self.progress = progress
        self.cancel = cancel
        self._rife_keep_dirs: set[str] = set()

    # ----- поиск -----------------------------------------------------------

    @staticmethod
    def _find_exe(name: str) -> Optional[Path]:
        if not TOOLS_DIR.exists():
            return None
        hits = [p for p in TOOLS_DIR.rglob(name) if p.is_file()]
        if not hits:
            return None
        return min(hits, key=lambda p: (len(p.parts), str(p).lower()))

    @staticmethod
    def _find_models(exe: Path) -> Optional[Path]:
        for d in exe.parent.rglob("models"):
            if d.is_dir() and any(d.glob("*.param")):
                return d
        return None

    @staticmethod
    def _find_rife_model(exe: Path) -> Optional[Path]:
        candidates = [d for d in exe.parent.rglob("rife-v4.6") if d.is_dir()]
        if not candidates:
            candidates = [d for d in exe.parent.rglob("rife-v4*") if d.is_dir()]
        for d in candidates:
            if any(d.iterdir()):
                return d
        return None

    def find(self) -> Optional[Tools]:
        try:
            ffmpeg = self._find_exe("ffmpeg.exe")
            ffprobe = self._find_exe("ffprobe.exe")
            realesrgan = self._find_exe("realesrgan-ncnn-vulkan.exe")
            rife = self._find_exe("rife-ncnn-vulkan.exe")
            if not (ffmpeg and ffprobe and realesrgan and rife):
                return None
            rg_models = self._find_models(realesrgan)
            rife_model = self._find_rife_model(rife)
            if not rg_models or not rife_model:
                return None
            return Tools(ffmpeg, ffprobe, realesrgan, rg_models, rife, rife_model)
        except OSError:
            return None

    def _spec_ready(self, spec: ToolSpec) -> bool:
        if spec.key == "ffmpeg":
            return bool(self._find_exe("ffmpeg.exe") and self._find_exe("ffprobe.exe"))
        exe = self._find_exe(spec.exe)
        if not exe:
            return False
        if spec.key == "realesrgan":
            return self._find_models(exe) is not None
        return self._find_rife_model(exe) is not None

    # ----- основное --------------------------------------------------------

    def ensure_tools(self) -> Tools:
        tools = self.find()
        if tools is not None:
            return tools

        missing = [s for s in TOOL_SPECS if not self._spec_ready(s)]
        total_weight = sum(s.weight for s in missing) or 1
        self.log(
            "Первый запуск: скачиваю инструменты (~"
            f"{sum(s.weight for s in missing)} МБ). Это может занять 5–15 минут."
        )

        done_weight = 0
        for spec in missing:
            if self.cancel.is_set():
                raise Cancelled()

            base = done_weight / total_weight
            span = spec.weight / total_weight

            def tool_progress(frac: float, text: str, base=base, span=span) -> None:
                self.progress(min(0.99, base + span * max(0.0, min(1.0, frac))), text)

            zip_path = DOWNLOAD_DIR / f"{spec.key}.zip"
            self.log(f"Скачивание {spec.title}...")
            self._download(spec, zip_path, lambda f, t: tool_progress(f * 0.85, t))

            if self.cancel.is_set():
                raise Cancelled()

            self.log(f"Распаковка {spec.title}...")
            self._extract(spec, zip_path, lambda f, t: tool_progress(0.85 + 0.15 * f, t))
            zip_path.unlink(missing_ok=True)
            done_weight += spec.weight
            self.progress(min(0.99, done_weight / total_weight), f"{spec.title}: готово")

        tools = self.find()
        if tools is None:
            raise EngineError(
                "Инструменты скачались, но не найдены. "
                "Проверьте папку tools или установите вручную.\n\n" + MANUAL_HELP
            )

        self.log("Все инструменты готовы.")
        self.log(f"  Real-ESRGAN models: {tools.realesrgan_models}")
        self.log(f"  RIFE model: {tools.rife_model.name}")
        self.progress(1.0, "Инструменты готовы")
        return tools

    # ----- скачивание ------------------------------------------------------

    def _download(self, spec: ToolSpec, dest: Path, progress: Callable[[float, str], None]) -> None:
        DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
        part = dest.with_suffix(dest.suffix + ".part")
        part.unlink(missing_ok=True)

        last_error: Optional[Exception] = None
        for attempt in range(1, 4):
            if self.cancel.is_set():
                raise Cancelled()
            req = urllib.request.Request(
                spec.url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"}
            )
            try:
                with urllib.request.urlopen(req, timeout=60) as resp, open(part, "wb") as fh:
                    total = int(resp.headers.get("Content-Length") or 0)
                    done = 0
                    started = time.time()
                    while True:
                        if self.cancel.is_set():
                            raise Cancelled()
                        chunk = resp.read(256 * 1024)
                        if not chunk:
                            break
                        fh.write(chunk)
                        done += len(chunk)
                        frac = done / total if total else 0.0
                        speed = done / 1048576.0 / max(0.5, time.time() - started)
                        if total:
                            text = (
                                f"{spec.title}: {done / 1048576.0:.0f} / "
                                f"{total / 1048576.0:.0f} МБ · {speed:.1f} МБ/с"
                            )
                        else:
                            text = f"{spec.title}: {done / 1048576.0:.0f} МБ · {speed:.1f} МБ/с"
                        progress(frac, text)
                part.replace(dest)
                return
            except Cancelled:
                part.unlink(missing_ok=True)
                raise
            except Exception as exc:  # noqa: BLE001 — хотим показать любую сетевую ошибку
                last_error = exc
                part.unlink(missing_ok=True)
                self.log(f"  Ошибка скачивания ({exc}). Попытка {attempt}/3.")
                if attempt < 3:
                    self._sleep(2 * attempt)

        raise EngineError(
            f"Не удалось скачать {spec.title}: {last_error}\n\n"
            f"Ссылка: {spec.url}\n\n{MANUAL_HELP}"
        )

    def _sleep(self, seconds: float) -> None:
        end = time.time() + seconds
        while time.time() < end:
            if self.cancel.is_set():
                raise Cancelled()
            time.sleep(0.15)

    # ----- распаковка ------------------------------------------------------

    def _extract(self, spec: ToolSpec, zip_path: Path, progress: Callable[[float, str], None]) -> None:
        if not zip_path.exists():
            raise EngineError(f"Архив {zip_path.name} не найден.")

        dest = TOOLS_DIR / spec.key
        dest.mkdir(parents=True, exist_ok=True)

        try:
            with zipfile.ZipFile(zip_path) as zf:
                infos = [i for i in zf.infolist() if not i.is_dir()]
                if not infos:
                    raise EngineError(f"Архив {zip_path.name} пуст.")

                if spec.key == "rife":
                    self._prepare_rife_keep(zf.namelist())

                dest_root = dest.resolve()
                total = max(1, len(infos))
                for index, info in enumerate(infos, 1):
                    if self.cancel.is_set():
                        raise Cancelled()
                    if not self._keep_member(info.filename, spec):
                        continue

                    target = (dest / info.filename).resolve()
                    try:
                        target.relative_to(dest_root)
                    except ValueError:
                        continue  # защита от путей вида ../../

                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(info) as src, open(target, "wb") as out:
                        shutil.copyfileobj(src, out, 1024 * 1024)

                    if index % 20 == 0 or index == total:
                        progress(index / total, f"Распаковка {spec.title}: {index}/{total}")

        except zipfile.BadZipFile as exc:
            raise EngineError(
                f"Архив {zip_path.name} повреждён или скачан не полностью. "
                "Удалите папку tools/downloads и попробуйте снова."
            ) from exc
        except Cancelled:
            raise
        except EngineError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise EngineError(f"Ошибка распаковки {spec.title}: {exc}") from exc

    def _prepare_rife_keep(self, names: list[str]) -> None:
        model_dirs: set[str] = set()
        for name in names:
            parts = PurePosixPath(name).parts
            if "models" in parts:
                i = parts.index("models")
                if i + 1 < len(parts) and parts[i + 1]:
                    model_dirs.add(parts[i + 1])

        preferred = [d for d in model_dirs if d.lower() == "rife-v4.6"]
        if not preferred:
            preferred = [d for d in model_dirs if d.lower().startswith("rife-v4")]
        if not preferred:
            preferred = sorted(model_dirs)

        self._rife_keep_dirs = {d.lower() for d in preferred}
        if preferred:
            self.log("  Модели RIFE: " + ", ".join(sorted(preferred)))

    def _keep_member(self, name: str, spec: ToolSpec) -> bool:
        parts = PurePosixPath(name).parts
        if not parts:
            return False
        if spec.keep == "all":
            return True
        if spec.keep == "ffmpeg":
            return parts[-1].lower() in ("ffmpeg.exe", "ffprobe.exe")
        # rife: exe + dll + только нужные модели
        low = tuple(p.lower() for p in parts)
        if "models" not in low:
            return True
        i = low.index("models")
        return i + 1 < len(low) and low[i + 1] in self._rife_keep_dirs


# ---------------------------------------------------------------------------
# Обработка видео
# ---------------------------------------------------------------------------

class Pipeline:
    def __init__(
        self,
        tools: Tools,
        log: LogFn,
        progress: ProgressFn,
        confirm: ConfirmFn,
        cancel: threading.Event,
    ):
        self.tools = tools
        self.log = log
        self.progress = progress
        self.confirm = confirm
        self.cancel = cancel
        self._encoders: Optional[str] = None

    # ----- служебное -------------------------------------------------------

    def _check_cancel(self) -> None:
        if self.cancel.is_set():
            raise Cancelled()

    def _tail(self, path: Path, lines: int = 30) -> str:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                data = fh.readlines()
        except OSError:
            return ""
        return "\n".join(line.rstrip() for line in data[-lines:] if line.strip())

    def _error_with_hint(self, label: str, detail: str) -> EngineError:
        low = detail.lower()
        hint = ""
        if any(k in low for k in ("vkalloc", "out of memory", "allocate memory", "device lost", "vkcreate")):
            hint = (
                "\n\nПохоже, не хватило видеопамяти (RX 570 — 4 ГБ). "
                "Попробуйте пресет «Быстро» (без интерполяции) или видео меньшего разрешения."
            )
        elif "vulkan" in low and ("fail" in low or "not found" in low or "no device" in low):
            hint = (
                "\n\nПохоже, проблема с Vulkan/драйвером видеокарты. "
                "Обновите драйвер AMD для RX 570 и перезапустите программу."
            )
        return EngineError(f"{label}: ошибка.\n\n{detail[-2500:]}{hint}")

    def _set_progress_checked(self, value: float, text: str) -> None:
        self.progress(max(0.0, min(1.0, value)), text)

    def _has_encoder(self, name: str) -> bool:
        if self._encoders is None:
            try:
                res = subprocess.run(
                    [str(self.tools.ffmpeg), "-hide_banner", "-encoders"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=CREATE_NO_WINDOW,
                    timeout=30,
                )
                self._encoders = res.stdout or ""
            except Exception:
                self._encoders = ""
        return re.search(rf"\b{re.escape(name)}\b", self._encoders) is not None

    def _run_process(
        self,
        cmd: list[str],
        logpath: Path,
        label: str,
        tick: Optional[Callable[[], None]] = None,
        cwd: Optional[Path] = None,
    ) -> None:
        logpath.parent.mkdir(parents=True, exist_ok=True)
        self._check_cancel()

        with open(logpath, "wb") as logfh:
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=logfh,
                    stderr=subprocess.STDOUT,
                    cwd=str(cwd) if cwd else None,
                    creationflags=CREATE_NO_WINDOW,
                )
            except FileNotFoundError as exc:
                raise EngineError(f"Не найден исполняемый файл: {cmd[0]}") from exc

            _set_active(proc)
            try:
                while True:
                    rc = proc.poll()
                    if rc is not None:
                        break
                    if self.cancel.is_set():
                        try:
                            proc.kill()
                        except Exception:
                            pass
                        try:
                            proc.wait(timeout=5)
                        except Exception:
                            pass
                        raise Cancelled()
                    if tick:
                        tick()
                    time.sleep(0.4)
            finally:
                _set_active(None)

        if rc != 0:
            detail = self._tail(logpath)
            raise self._error_with_hint(f"{label}", detail or f"Код возврата {rc}")

    def _read_progress(self, path: Path, mode: str, total: float) -> Optional[float]:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        if total <= 0:
            return None
        if mode == "time":
            matches = re.findall(r"(?:out_time_us|out_time_ms)=(\d+)", text)
            if matches:
                return min(0.995, (int(matches[-1]) / 1_000_000.0) / total)
        else:
            matches = re.findall(r"frame=(\d+)", text)
            if matches:
                return min(0.995, int(matches[-1]) / total)
        return None

    def _count_frames(self, folder: Path, ext: str) -> int:
        if not folder.exists():
            return 0
        suffix = "." + ext.lower()
        try:
            return sum(1 for p in folder.iterdir() if p.is_file() and p.suffix.lower() == suffix)
        except OSError:
            return 0

    # ----- определение параметров видео ------------------------------------

    def probe(self, path: Path) -> VideoInfo:
        cmd = [
            str(self.tools.ffprobe),
            "-v", "error",
            "-print_format", "json",
            "-show_streams",
            "-show_format",
            str(path),
        ]
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=CREATE_NO_WINDOW,
                timeout=60,
            )
        except Exception as exc:  # noqa: BLE001
            raise EngineError(f"Не удалось проверить видео «{path.name}»: {exc}") from exc

        if res.returncode != 0:
            raise EngineError(
                f"Не удалось прочитать «{path.name}». Возможно, файл повреждён или это не видео.\n"
                + (res.stderr or "")[-800:]
            )

        try:
            data = json.loads(res.stdout)
        except json.JSONDecodeError as exc:
            raise EngineError(f"ffprobe вернул некорректные данные для «{path.name}».") from exc

        streams = data.get("streams", [])
        fmt = data.get("format", {})

        vstream = None
        for s in streams:
            if s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic"):
                vstream = s
                break
        if vstream is None:
            raise EngineError(f"В файле «{path.name}» не найдена видеодорожка.")

        width = int(vstream.get("width") or 0)
        height = int(vstream.get("height") or 0)

        fps = parse_rate(str(vstream.get("avg_frame_rate") or "0/0"))
        if fps <= 0:
            fps = parse_rate(str(vstream.get("r_frame_rate") or "0/0"))

        duration = 0.0
        for raw in (fmt.get("duration"), vstream.get("duration")):
            try:
                duration = float(raw)
                if duration > 0:
                    break
            except (TypeError, ValueError):
                continue

        frames_hint = 0
        try:
            frames_hint = int(vstream.get("nb_frames") or 0)
        except (TypeError, ValueError):
            frames_hint = 0

        if duration <= 0 and frames_hint > 0 and fps > 0:
            duration = frames_hint / fps
        if duration <= 0:
            raise EngineError(
                f"Не удалось определить длительность видео «{path.name}». "
                "Попробуйте пересохранить файл в mp4 или mkv."
            )
        if frames_hint <= 0 and fps > 0:
            frames_hint = max(1, int(round(duration * fps)))

        audio_codec = ""
        for s in streams:
            if s.get("codec_type") == "audio":
                audio_codec = str(s.get("codec_name") or "")
                break

        color_transfer = str(vstream.get("color_transfer") or "").lower()
        is_hdr = color_transfer in ("smpte2084", "arib-std-b67")

        return VideoInfo(
            path=path,
            width=width,
            height=height,
            fps=fps if fps > 0 else 30.0,
            duration=duration,
            audio_codec=audio_codec,
            frames_hint=frames_hint,
            is_hdr=is_hdr,
        )

    # ----- оценка места ----------------------------------------------------

    @staticmethod
    def _estimate_temp(info: VideoInfo, frames: int, save_space: bool,
                       scale: int) -> int:
        px = max(1, info.width * info.height)
        factor = 0.15 if save_space else 0.50
        per_source = px * 3 * factor
        per_upscaled = px * scale * scale * 3 * factor
        return int(frames * (per_source + per_upscaled))

    # ----- разрешение масштаба / модели / кодировщика ----------------------

    @staticmethod
    def _resolve_scale(settings: Settings, info: VideoInfo) -> int:
        """Итоговый масштаб: из настроек, пресета или «авто до 4K/8K»."""
        mode = settings.scale_mode
        if mode in ("x2", "x3", "x4"):
            return int(mode[1])
        if mode in ("auto_2160", "auto_4320"):
            target = 2160 if mode == "auto_2160" else 4320
            if info.height <= 0:
                return max(1, int(settings.preset.scale))
            if info.height >= target:
                return 1                      # уже не ниже цели — апскейл не нужен
            return max(2, min(4, -(-target // max(1, info.height))))
        return max(1, int(settings.preset.scale))

    @staticmethod
    def _resolve_model(settings: Settings, scale: int) -> str:
        """Модель по типу видео; тяжёлая умеет только x4 — иначе лёгкая."""
        want = settings.model_mode
        heavy = (want == "heavy") or (want == "auto" and settings.preset.key == "max")
        if scale < 4 and heavy:
            heavy = False
        if heavy:
            return ("realesrgan-x4plus-anime" if settings.content == "anime"
                    else "realesrgan-x4plus")
        return "realesr-animevideov3"

    @staticmethod
    def _resolve_tile(settings: Settings, scale: int) -> int:
        mode = settings.tile_mode
        if mode == "t256":
            return 256
        if mode == "t384":
            return 384
        if mode == "t512":
            return 512
        tile = int(settings.preset.tile)
        if mode in ("preset", "auto") and scale >= 3 and tile < 384:
            tile = 384                        # крупный tile для больших кадров
        return max(128, min(640, tile))

    @staticmethod
    def _resolve_quality(settings: Settings) -> dict:
        q = settings.quality if settings.quality != "preset" else settings.preset.quality
        qp, crf = QUALITY_LEVELS.get(q, QUALITY_LEVELS["balanced"])
        return {"key": q, "qp": qp, "crf": crf}

    @staticmethod
    def _resolve_encoder(settings: Settings) -> str:
        enc = (settings.encoder_mode if settings.encoder_mode != "preset"
               else settings.preset.encoder_mode)
        return enc if enc in ("amf_h264", "amf_hevc", "cpu") else "amf_hevc"

    # ----- оценка времени --------------------------------------------------

    @staticmethod
    def _estimate_seconds(
        info: VideoInfo, model: str, scale: int,
        frame_count: int, desired: Optional[int] = None,
    ) -> float:
        """Грубая оценка времени обработки (секунды) для подсказки пользователю."""
        mp = max(0.01, info.width * info.height / 1_000_000.0)
        speed = MODEL_SPEED.get(model, 22.0)
        if model == "realesr-animevideov3":
            factor = scale * scale / 4.0      # скорость замерена для x2
        else:
            factor = 1.0                      # x4plus-числа уже для x4
        total = frame_count * mp * speed * factor
        if desired and desired > frame_count:
            mp_out = mp * scale * scale
            total += (desired - frame_count) * mp_out / RIFE_MP_PER_SEC
        total += frame_count * 0.01
        return total

    # ----- главный метод ---------------------------------------------------

    def process_video(self, video_path: Path, settings: Settings) -> Path:
        video = Path(video_path).expanduser().resolve()
        if not video.is_file():
            raise EngineError(f"Файл не найден: {video}")

        self.log("")
        self.log(f"=== {video.name} ===")
        self._check_cancel()

        info = self.probe(video)
        fps_text = f"{info.fps:.3f}".rstrip("0").rstrip(".")
        self.log(
            f"Видео: {info.width}x{info.height}, {fps_text} FPS, "
            f"{info.duration:.1f} c, звук: {info.audio_codec or 'нет'}"
        )
        if info.is_hdr:
            self.log(
                "! HDR-видео будет преобразовано в обычный SDR (8 бит) — "
                "это особенность PNG/JPEG-пайплайна."
            )
        if info.frames_hint > 20000:
            self.log("! Видео длинное: обработка займёт много времени и места на диске.")

        scale = self._resolve_scale(settings, info)
        model = self._resolve_model(settings, scale)
        tile = self._resolve_tile(settings, scale)
        quality = self._resolve_quality(settings)
        enc_mode = self._resolve_encoder(settings)
        if scale >= 2:
            auto_note = ""
            if settings.scale_mode == "auto_2160":
                auto_note = " (авто до 2160p)"
            elif settings.scale_mode == "auto_4320":
                auto_note = " (авто до 4320p)"
            extra = " + плавность %d FPS" % settings.target_fps if settings.interpolate else ""
            self.log(
                f"Апскейл: x{scale}{auto_note} — {model}, tile {tile}, "
                f"качество {quality['key']}{extra}"
            )
        else:
            self.log("Апскейл не требуется: разрешение источника уже достигло цели.")

        TEMP_ROOT.mkdir(parents=True, exist_ok=True)
        job = TEMP_ROOT / f"job_{int(time.time())}_{os.getpid()}"
        frames_dir = job / "frames"
        up_dir = job / "frames_up"
        smooth_dir = job / "frames_smooth"
        job.mkdir(parents=True, exist_ok=True)

        fmt = "jpg" if settings.save_space else "png"
        prog_file = job / "progress.txt"

        try:
            # --- проверка свободного места ---
            need = self._estimate_temp(info, info.frames_hint, settings.save_space, scale)
            free = shutil.disk_usage(TEMP_ROOT).free
            if need > 0 and free < need * 1.10:
                text = (
                    f"Для временных файлов может понадобиться около {human_size(need)}.\n"
                    f"Свободно на диске: {human_size(free)}.\n\n"
                    "Продолжить? Если места не хватит, обработка прервётся.\n"
                    "Совет: включите «Экономить место» или обработайте видео частями."
                )
                if not self.confirm(text):
                    raise Cancelled()

            # --- 1. извлечение кадров ---
            self._check_cancel()
            frames_dir.mkdir(parents=True, exist_ok=True)
            self.log(f"Шаг 1/4: извлекаю кадры ({fmt.upper()})...")
            self._set_progress_checked(0.0, "Извлечение кадров: 0%")
            cmd = [
                str(self.tools.ffmpeg), "-y", "-hide_banner", "-nostdin",
                "-loglevel", "warning",
                "-i", str(video),
                "-map", "0:v:0",
                "-an", "-sn", "-dn",
                "-fps_mode", "passthrough",
                "-progress", str(prog_file),
                "-nostats",
            ]
            if fmt == "jpg":
                cmd += ["-qscale:v", "1"]
            cmd.append(str(frames_dir / f"%06d.{fmt}"))

            def tick_extract() -> None:
                frac = self._read_progress(prog_file, "time", info.duration)
                if frac is not None:
                    self._set_progress_checked(frac, f"Извлечение кадров: {frac * 100:.0f}%")

            self._run_process(cmd, job / "01_extract.log", "Извлечение кадров", tick_extract)

            frame_count = self._count_frames(frames_dir, fmt)
            if frame_count < 2:
                raise EngineError(
                    "Не удалось извлечь кадры. Проверьте, что видео открывается в проигрывателе, "
                    "и что на диске достаточно места."
                )
            self._set_progress_checked(1.0, f"Извлечено кадров: {frame_count}")
            self.log(f"  Извлечено кадров: {frame_count}")

            # --- 2. апскейл ---
            upscale_done = False
            if scale >= 2:
                self._check_cancel()
                up_dir.mkdir(parents=True, exist_ok=True)
                effective_fps = frame_count / info.duration if info.duration > 0 else info.fps
                desired_est = max(2, int(round(info.duration * settings.target_fps)))
                will_interpolate = (
                    settings.interpolate
                    and effective_fps < settings.target_fps * 0.95
                    and desired_est > frame_count + 1
                )
                estimate = self._estimate_seconds(
                    info, model, scale, frame_count,
                    desired_est if will_interpolate else None,
                )
                self.log(
                    f"Шаг 2/4: нейросетевой апскейл x{scale} "
                    f"({model}, tile {tile})..."
                )
                self.log(f"  Модель: {model}. Оценка времени: ~{human_time(estimate)}.")
                if estimate > 3 * 3600:
                    text = (
                        f"Обработка этого видео может занять примерно {human_time(estimate)}.\n\n"
                        f"Масштаб x{scale} и модель {model} — самые тяжёлые режимы: "
                        "на RX 570 каждый кадр обрабатывается десятки секунд.\n\n"
                        "Совет: если ждать долго — выберите масштаб x2 или x3 "
                        "(в карточке «Настройки»), так значительно быстрее, "
                        "а картинка всё равно заметно лучше исходной.\n\n"
                        "Продолжить?"
                    )
                    if not self.confirm(text):
                        raise Cancelled()
                self._set_progress_checked(0.0, "Апскейл: 0%")

                tiles = [tile]
                for fallback in (384, 256, 192, 128):
                    if fallback < tiles[0]:
                        tiles.append(fallback)

                upscaled = False
                last_error: Optional[Exception] = None
                for tile_try in tiles:
                    self._check_cancel()
                    safe_rmtree(up_dir)
                    up_dir.mkdir(parents=True, exist_ok=True)
                    jobs = "1:1:1"
                    cmd = [
                        str(self.tools.realesrgan),
                        "-i", str(frames_dir),
                        "-o", str(up_dir),
                        "-s", str(scale),
                        "-n", model,
                        "-m", str(self.tools.realesrgan_models),
                        "-t", str(tile_try),
                        "-g", "0",
                        "-j", jobs,
                        "-f", fmt,
                    ]

                    tile_started = time.time()

                    def tick_upscale(tile_started=tile_started) -> None:
                        done = self._count_frames(up_dir, fmt)
                        frac = min(0.995, done / frame_count)
                        text = f"Апскейл: {done}/{frame_count} кадров"
                        elapsed = time.time() - tile_started
                        if done >= 2 and elapsed > 1:
                            remain = elapsed / done * (frame_count - done)
                            text += f" · осталось ~{human_time(remain)}"
                        self._set_progress_checked(frac, text)

                    try:
                        self._run_process(
                            cmd, job / "02_upscale.log", "Нейросетевой апскейл",
                            tick_upscale, cwd=self.tools.realesrgan.parent,
                        )
                        done = self._count_frames(up_dir, fmt)
                        if done < frame_count:
                            raise EngineError(
                                f"Апскейл обработал только {done} из {frame_count} кадров. "
                                + self._tail(job / "02_upscale.log")
                            )
                        upscaled = True
                        self._set_progress_checked(1.0, f"Апскейл готов: {done} кадров")
                        self.log(f"  Апскейл готов: {done} кадров")
                        break
                    except Cancelled:
                        raise
                    except EngineError as exc:
                        last_error = exc
                        low = str(exc).lower()
                        if tile_try != tiles[-1] and any(
                            k in low for k in ("vkalloc", "out of memory", "allocate memory", "device lost")
                        ):
                            nxt = tiles[tiles.index(tile_try) + 1]
                            self.log(f"! Не хватило видеопамяти при tile={tile_try}. Пробую tile={nxt}...")
                            continue
                        raise

                if not upscaled:
                    raise last_error or EngineError("Апскейл не удался.")

                # исходные кадры больше не нужны
                safe_rmtree(frames_dir)
                upscale_done = True
            else:
                self.log("Шаг 2/4 пропущен: апскейл не нужен (разрешение уже высокое).")

            up_dir = frames_dir if not upscale_done else up_dir

            # --- 3. интерполяция ---
            self._check_cancel()
            final_dir = up_dir
            out_frames = frame_count
            out_fps = frame_count / info.duration if info.duration > 0 else info.fps
            interpolated = False

            if settings.interpolate:
                effective_fps = frame_count / info.duration if info.duration > 0 else info.fps
                desired = max(2, int(round(info.duration * settings.target_fps)))
                if effective_fps < settings.target_fps * 0.95 and desired > frame_count + 1:
                    self.log(
                        f"Шаг 3/4: интерполяция до {settings.target_fps} FPS "
                        f"({frame_count} -> {desired} кадров)..."
                    )
                    self._set_progress_checked(0.0, "Интерполяция: 0%")

                    upsampled = False
                    rife_error: Optional[Exception] = None
                    for uhd in (False, True):
                        self._check_cancel()
                        safe_rmtree(smooth_dir)
                        smooth_dir.mkdir(parents=True, exist_ok=True)
                        cmd = [
                            str(self.tools.rife),
                            "-i", str(up_dir),
                            "-o", str(smooth_dir),
                            "-n", str(desired),
                            "-m", str(self.tools.rife_model),
                            "-g", "0",
                            "-j", "1:1:1",
                            "-f", f"%08d.{fmt}",
                        ]
                        if uhd:
                            cmd.append("-u")
                            self.log("  UHD-режим RIFE (меньше видеопамяти, чуть ниже точность).")
                        rife_started = time.time()

                        def tick_rife(started=rife_started) -> None:
                            done = self._count_frames(smooth_dir, fmt)
                            frac = min(0.995, done / desired)
                            text = f"Интерполяция: {done}/{desired} кадров"
                            elapsed = time.time() - started
                            if done >= 2 and elapsed > 1:
                                remain = elapsed / done * (desired - done)
                                text += f" · осталось ~{human_time(remain)}"
                            self._set_progress_checked(frac, text)

                        try:
                            self._run_process(
                                cmd, job / "03_rife.log", "Интерполяция кадров",
                                tick_rife, cwd=self.tools.rife.parent,
                            )
                            done = self._count_frames(smooth_dir, fmt)
                            if done < desired:
                                raise EngineError(
                                    f"Интерполяция создала только {done} из {desired} кадров.\n"
                                    + self._tail(job / "03_rife.log")
                                )
                            upsampled = True
                            break
                        except Cancelled:
                            raise
                        except EngineError as exc:
                            rife_error = exc
                            low = str(exc).lower()
                            if not uhd and any(
                                k in low for k in (
                                    "vkalloc", "out of memory", "allocate memory",
                                    "device lost", "vkcreate",
                                )
                            ):
                                self.log("! RIFE: не хватило видеопамяти. Пробую UHD-режим...")
                                continue
                            raise

                    if not upsampled:
                        raise rife_error or EngineError("Интерполяция не удалась.")
                    done = self._count_frames(smooth_dir, fmt)

                    final_dir = smooth_dir
                    out_frames = done
                    out_fps = float(settings.target_fps)
                    interpolated = True
                    self._set_progress_checked(1.0, f"Интерполяция готова: {done} кадров")
                    self.log(f"  Интерполяция готова: {done} кадров, {out_fps:g} FPS")
                    safe_rmtree(up_dir)
                else:
                    self.log(
                        f"Шаг 3/4: интерполяция не нужна "
                        f"({effective_fps:.2f} FPS уже достаточно)."
                    )
            else:
                self.log("Шаг 3/4: интерполяция отключена.")

            # --- 4. кодирование ---
            self._check_cancel()
            out_path = self._unique_output(video)
            part_path = out_path.with_name(out_path.stem + ".part.mp4")

            safe_audio = {"aac", "mp3", "ac3", "eac3", "alac"}
            if info.audio_codec and info.audio_codec not in safe_audio:
                audio_args = ["-c:a", "aac", "-b:a", "192k"]
                self.log(f"  Звук {info.audio_codec} -> AAC 192 кбит/с (для совместимости с MP4).")
            elif info.audio_codec:
                audio_args = ["-c:a", "copy"]
            else:
                audio_args = ["-an"]

            fps_str = f"{out_fps:.6f}"
            amf_codec = "hevc_amf" if enc_mode in ("preset", "amf_hevc") else "h264_amf"
            if enc_mode == "cpu":
                enc_note = "libx264 (CPU)"
            else:
                enc_note = f"{amf_codec} (GPU) / fallback libx264"
            self.log(
                f"Шаг 4/4: кодирование {out_frames} кадров @ {out_fps:.2f} FPS "
                f"({enc_note})..."
            )

            def build_encode_cmd(amf: bool) -> list[str]:
                frame_pattern = f"%08d.{fmt}" if interpolated else f"%06d.{fmt}"
                cmd = [
                    str(self.tools.ffmpeg), "-y", "-hide_banner", "-nostdin",
                    "-loglevel", "warning",
                    "-framerate", fps_str,
                    "-start_number", "1",
                    "-i", str(final_dir / frame_pattern),
                    "-i", str(video),
                    "-map", "0:v:0",
                    "-map", "1:a:0?",
                ]
                if amf:
                    cmd += [
                        "-c:v", amf_codec,
                        "-quality", quality["key"],
                        "-rc", "cqp",
                        "-qp_i", str(quality["qp"]),
                        "-qp_p", str(quality["qp"]),
                    ]
                    if "hevc" in amf_codec:
                        cmd += ["-tag:v", "hvc1"]
                else:
                    cmd += ["-c:v", "libx264", "-preset", "fast",
                            "-crf", str(quality["crf"])]
                cmd += ["-pix_fmt", "yuv420p"]
                cmd += audio_args
                cmd += [
                    "-movflags", "+faststart",
                    "-progress", str(prog_file),
                    "-nostats",
                    str(part_path),
                ]
                return cmd

            def encode_once(amf: bool, label: str) -> None:
                part_path.unlink(missing_ok=True)
                prog_file.unlink(missing_ok=True)

                def tick_encode() -> None:
                    frac = self._read_progress(prog_file, "frames", out_frames)
                    if frac is not None:
                        self._set_progress_checked(frac, f"Кодирование: {frac * 100:.0f}%")

                self._set_progress_checked(0.0, f"{label}: 0%")
                self._run_process(
                    build_encode_cmd(amf), job / f"04_encode_{'amf' if amf else 'x264'}.log",
                    label, tick_encode,
                )
                if not part_path.exists() or part_path.stat().st_size < 2048:
                    raise EngineError(f"{label}: файл результата не создан или пуст.")

            amf_attempted = False
            if enc_mode != "cpu":
                if self._has_encoder(amf_codec):
                    amf_attempted = True
                    try:
                        encode_once(True, "Кодирование на GPU (AMF)")
                    except Cancelled:
                        raise
                    except Exception as exc:  # noqa: BLE001
                        self.log(f"! AMF-кодирование не удалось: {str(exc)[:400]}")
                        self.log("  Переключаюсь на libx264 (медленнее, но совместимо).")
                        amf_attempted = False
                else:
                    self.log(f"  Кодировщик {amf_codec} недоступен — использую libx264.")

            if not amf_attempted:
                encode_once(False, "Кодирование (libx264)")

            self._set_progress_checked(1.0, "Сборка файла...")
            os.replace(part_path, out_path)
            self.log(f"  Файл сохранён: {out_path}")

            try:
                out_info = self.probe(out_path)
                self.log(
                    f"Готово: {out_path.name} — {out_info.width}x{out_info.height}, "
                    f"{out_info.fps:.2f} FPS, {out_info.duration:.1f} c, "
                    f"{human_size(out_path.stat().st_size)}"
                )
            except EngineError:
                self.log("Готово, но не удалось проверить итоговый файл.")

            return out_path

        finally:
            safe_rmtree(job)
            self.log("Временные файлы удалены.")

    # ----- вспомогательное -------------------------------------------------

    @staticmethod
    def _unique_output(video: Path) -> Path:
        candidate = video.with_name(f"{video.stem}_UPSCALED.mp4")
        index = 2
        while candidate.exists():
            candidate = video.with_name(f"{video.stem}_UPSCALED_{index}.mp4")
            index += 1
        return candidate
