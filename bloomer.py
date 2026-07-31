"""Bloomer - a small, configurable BTD6 single-player XP macro for Windows."""

from __future__ import annotations

import copy
import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import json
from pathlib import Path
import queue
import random
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Sequence


APP_NAME = "Bloomer"
APP_VERSION = "0.1.2"
CONFIG_PATH = Path(__file__).with_name("config.json")


@dataclass(frozen=True)
class MonkeySpec:
    name: str
    category: str
    default_hotkey: str
    water_map: bool = False
    passive: bool = False
    custom_binding: bool = False


MONKEYS: dict[str, MonkeySpec] = {
    # Primary
    "Dart Monkey": MonkeySpec("Dart Monkey", "Primary", "q"),
    "Boomerang Monkey": MonkeySpec("Boomerang Monkey", "Primary", "w"),
    "Bomb Shooter": MonkeySpec("Bomb Shooter", "Primary", "e"),
    "Tack Shooter": MonkeySpec("Tack Shooter", "Primary", "r"),
    "Ice Monkey": MonkeySpec("Ice Monkey", "Primary", "t"),
    "Glue Gunner": MonkeySpec("Glue Gunner", "Primary", "y"),
    # Military
    "Sniper Monkey": MonkeySpec("Sniper Monkey", "Military", "z"),
    "Monkey Sub": MonkeySpec("Monkey Sub", "Military", "x", water_map=True),
    "Monkey Buccaneer": MonkeySpec("Monkey Buccaneer", "Military", "c", water_map=True),
    "Monkey Ace": MonkeySpec("Monkey Ace", "Military", "v"),
    "Heli Pilot": MonkeySpec("Heli Pilot", "Military", "b"),
    "Mortar Monkey": MonkeySpec("Mortar Monkey", "Military", "n"),
    "Dartling Gunner": MonkeySpec("Dartling Gunner", "Military", "m"),
    # BTD6 intentionally ships this tower without a default binding.
    "Desperado": MonkeySpec("Desperado", "Military", "[", custom_binding=True),
    # Magic
    "Wizard Monkey": MonkeySpec("Wizard Monkey", "Magic", "a"),
    "Super Monkey": MonkeySpec("Super Monkey", "Magic", "s"),
    "Ninja Monkey": MonkeySpec("Ninja Monkey", "Magic", "d"),
    "Alchemist": MonkeySpec("Alchemist", "Magic", "f"),
    "Druid": MonkeySpec("Druid", "Magic", "g"),
    # Mermonkey is amphibious, but water-heavy placement is more reliable for farming.
    "Mermonkey": MonkeySpec("Mermonkey", "Magic", "p", water_map=True, custom_binding=True),
    # Support
    "Banana Farm": MonkeySpec("Banana Farm", "Support", "h", passive=True),
    "Spike Factory": MonkeySpec("Spike Factory", "Support", "j"),
    "Monkey Village": MonkeySpec("Monkey Village", "Support", "k", passive=True),
    "Engineer Monkey": MonkeySpec("Engineer Monkey", "Support", "l"),
    "Beast Handler": MonkeySpec("Beast Handler", "Support", "i"),
}


# Six valid two-path builds. Main-path tiers are filled from config (3 or 4).
BUILD_SHAPES: tuple[tuple[int, int], ...] = (
    (0, 1), (0, 2), (1, 0), (1, 2), (2, 0), (2, 1)
)
UPGRADE_KEYS = (",", ".", "/")


DEFAULT_CONFIG: dict = {
    "last_tower": "Dart Monkey",
    "window": {
        "title_contains": "BloonsTD6|Bloons TD 6",
        "fallback_width": 1920,
        "fallback_height": 1200,
        "bring_to_front": True,
    },
    "loop": {
        "completed_games": 0,
        "count_defeats": True,
        "start_delay_seconds": 5.0,
        "navigation_delay_seconds": 2.5,
        "load_delay_seconds": 8.0,
        "round_pulse_seconds": 22.0,
        "action_interval_seconds": 3.5,
        "restart_delay_seconds": 7.0,
        "max_target_towers": 8,
        "placement_every_actions": 4,
        "main_path_tier": 4,
    },
    "hotkeys": {
        "upgrade_top": ",",
        "upgrade_middle": ".",
        "upgrade_bottom": "/",
        "start_round": "space",
        "cancel": "escape",
        "tower_overrides": {
            "Mermonkey": "p",
            "Desperado": "[",
        },
    },
    "detection": {
        "placement_change_threshold": 4.2,
        "upgrade_change_threshold": 1.25,
        "end_blue_ratio": 0.055,
        "end_text_ratio": 0.008,
    },
    "points": {
        "home_play": [0.500, 0.865],
        "beginner": [0.285, 0.890],
        "map_search": [0.045, 0.153],
        "map_search_field": [0.500, 0.060],
        "map_card": [0.255, 0.250],
        "difficulty_easy": [0.305, 0.400],
        "mode_standard": [0.307, 0.510],
        "dismiss_loading": [0.500, 0.500],
        "victory_home": [0.335, 0.765],
        "defeat_restart": [0.435, 0.755],
    },
    "placements": {
        "monkey_meadow": [
            [0.120, 0.150], [0.235, 0.145], [0.465, 0.160], [0.690, 0.155],
            [0.785, 0.260], [0.360, 0.330], [0.470, 0.335], [0.660, 0.455],
            [0.775, 0.455], [0.325, 0.500], [0.450, 0.475], [0.575, 0.530],
            [0.735, 0.600], [0.195, 0.675], [0.335, 0.715], [0.445, 0.700],
            [0.650, 0.750], [0.780, 0.775], [0.300, 0.895], [0.480, 0.885],
            [0.620, 0.900], [0.750, 0.900]
        ],
        "spice_islands": [
            [0.110, 0.175], [0.235, 0.155], [0.385, 0.175], [0.525, 0.165],
            [0.735, 0.165], [0.085, 0.390], [0.300, 0.360], [0.475, 0.385],
            [0.735, 0.370], [0.140, 0.650], [0.335, 0.625], [0.520, 0.640],
            [0.750, 0.650], [0.095, 0.850], [0.275, 0.835], [0.450, 0.855],
            [0.620, 0.845], [0.780, 0.865]
        ],
        "helpers": [[0.365, 0.335], [0.740, 0.500], [0.620, 0.900]],
    },
}


CALIBRATABLE_POINTS = {
    "Home: Play": "home_play",
    "Map category: Beginner": "beginner",
    "Open map search": "map_search",
    "Map search text field": "map_search_field",
    "First search result / Monkey Meadow": "map_card",
    "Difficulty: Easy": "difficulty_easy",
    "Mode: Standard": "mode_standard",
    "Victory: Home": "victory_home",
    "Defeat: Restart": "defeat_restart",
}


def deep_merge(default: dict, loaded: dict) -> dict:
    """Return loaded values overlaid on defaults without losing new default keys."""
    result = copy.deepcopy(default)
    for key, value in loaded.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path: Path = CONFIG_PATH) -> dict:
    if not path.exists():
        return copy.deepcopy(DEFAULT_CONFIG)
    try:
        return deep_merge(DEFAULT_CONFIG, json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not read {path.name}: {exc}") from exc


def save_config(config: dict, path: Path = CONFIG_PATH) -> None:
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")


def generate_build(rng: random.Random, main_tier: int = 4) -> tuple[tuple[int, int, int], list[int]]:
    """Return a valid randomized build and a randomized, order-safe upgrade sequence."""
    main_path, cross_path = rng.choice(BUILD_SHAPES)
    desired = [0, 0, 0]
    desired[main_path] = main_tier
    desired[cross_path] = 2

    remaining = desired.copy()
    sequence: list[int] = []
    while any(remaining):
        available = [index for index, count in enumerate(remaining) if count > 0]
        path = rng.choice(available)
        sequence.append(path)
        remaining[path] -= 1
    return tuple(desired), sequence


def target_map_name(spec: MonkeySpec) -> str:
    return "Spice Islands" if spec.water_map else "Monkey Meadow"


@dataclass
class PixelFrame:
    """A compact top-down BGRA screen frame captured through Windows GDI."""

    width: int
    height: int
    data: bytes | bytearray

    @property
    def size(self) -> tuple[int, int]:
        return self.width, self.height

    @classmethod
    def solid(cls, width: int, height: int, color: tuple[int, int, int]) -> "PixelFrame":
        r, g, b = color
        return cls(width, height, bytearray((b, g, r, 0xFF)) * (width * height))

    def fill_rect(self, box: tuple[int, int, int, int], color: tuple[int, int, int]) -> None:
        if not isinstance(self.data, bytearray):
            self.data = bytearray(self.data)
        left, top, right, bottom = box
        left, top = max(0, left), max(0, top)
        right, bottom = min(self.width, right), min(self.height, bottom)
        r, g, b = color
        pixel = bytes((b, g, r, 0xFF))
        row = pixel * max(0, right - left)
        for y in range(top, bottom):
            start = (y * self.width + left) * 4
            self.data[start:start + len(row)] = row

    def crop(self, box: tuple[int, int, int, int]) -> "PixelFrame":
        left, top, right, bottom = box
        left, top = max(0, left), max(0, top)
        right, bottom = min(self.width, right), min(self.height, bottom)
        width, height = max(0, right - left), max(0, bottom - top)
        output = bytearray(width * height * 4)
        row_bytes = width * 4
        for output_y, source_y in enumerate(range(top, bottom)):
            source_start = (source_y * self.width + left) * 4
            output_start = output_y * row_bytes
            output[output_start:output_start + row_bytes] = self.data[source_start:source_start + row_bytes]
        return PixelFrame(width, height, output)

    def sampled_rgb(self, target_samples: int = 35000):
        total_pixels = max(1, self.width * self.height)
        step = max(1, int((total_pixels / target_samples) ** 0.5))
        for y in range(0, self.height, step):
            row_start = y * self.width * 4
            for x in range(0, self.width, step):
                index = row_start + x * 4
                yield self.data[index + 2], self.data[index + 1], self.data[index]


def normalized_crop(image: PixelFrame, box: Sequence[float]) -> PixelFrame:
    width, height = image.size
    left, top, right, bottom = box
    return image.crop((
        max(0, int(left * width)), max(0, int(top * height)),
        min(width, int(right * width)), min(height, int(bottom * height)),
    ))


def image_diff_score(before: PixelFrame, after: PixelFrame) -> float:
    """Mean absolute RGB difference, normalized to a convenient 0..255 scale."""
    if before.size != after.size:
        return 255.0
    total = 0
    count = 0
    for index in range(0, len(before.data), 4):
        total += abs(before.data[index] - after.data[index])
        total += abs(before.data[index + 1] - after.data[index + 1])
        total += abs(before.data[index + 2] - after.data[index + 2])
        count += 3
    return total / count if count else 0.0


def classify_end_screen(image: PixelFrame, detection: dict) -> str | None:
    """Classify the standard blue BTD6 end dialog as victory or defeat."""
    sample = normalized_crop(image, (0.245, 0.155, 0.745, 0.790))
    pixels = list(sample.sampled_rgb())
    if not pixels:
        return None

    # The panel has a muted cornflower-blue fill. Requiring red/yellow title pixels
    # prevents Spice Islands' ocean from being mistaken for an end dialog.
    blue = sum(
        1 for r, g, b in pixels
        if 48 <= r <= 145 and 90 <= g <= 190 and 145 <= b <= 245 and b > r * 1.25
    ) / len(pixels)
    red = sum(
        1 for r, g, b in pixels
        if r >= 185 and g <= 105 and b <= 75 and r > g * 1.8
    ) / len(pixels)
    gold = sum(
        1 for r, g, b in pixels
        if r >= 190 and 115 <= g <= 225 and b <= 100 and r > b * 2.0
    ) / len(pixels)

    if blue < float(detection["end_blue_ratio"]):
        return None
    text_threshold = float(detection["end_text_ratio"])
    if red >= text_threshold and red > gold * 0.72:
        return "defeat"
    if gold >= text_threshold:
        return "victory"
    return None


@dataclass(frozen=True)
class WindowRect:
    left: int
    top: int
    width: int
    height: int

    @property
    def bbox(self) -> tuple[int, int, int, int]:
        return (self.left, self.top, self.left + self.width, self.top + self.height)

    def point(self, normalized: Sequence[float]) -> tuple[int, int]:
        return (
            self.left + round(float(normalized[0]) * self.width),
            self.top + round(float(normalized[1]) * self.height),
        )


class WindowsController:
    """Small Win32 input/window wrapper; avoids intrusive global hook packages."""

    VK = {
        "backspace": 0x08, "tab": 0x09, "enter": 0x0D, "shift": 0x10,
        "control": 0x11, "alt": 0x12, "escape": 0x1B, "space": 0x20,
        "f8": 0x77,
    }
    KEYUP = 0x0002
    LEFTDOWN = 0x0002
    LEFTUP = 0x0004
    RIGHTDOWN = 0x0008
    RIGHTUP = 0x0010

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise RuntimeError("Bloomer currently supports Windows only.")
        self.user32 = ctypes.windll.user32
        self.gdi32 = ctypes.windll.gdi32
        self._configure_apis()
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            try:
                self.user32.SetProcessDPIAware()
            except AttributeError:
                pass

    def _configure_apis(self) -> None:
        """Declare pointer-sized Win32 signatures (ctypes otherwise assumes c_int)."""
        self.user32.GetDC.argtypes = [wintypes.HWND]
        self.user32.GetDC.restype = wintypes.HDC
        self.user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
        self.user32.ReleaseDC.restype = ctypes.c_int
        self.user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        self.user32.GetClientRect.restype = wintypes.BOOL
        self.user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
        self.user32.ClientToScreen.restype = wintypes.BOOL
        self.user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        self.user32.SetForegroundWindow.restype = wintypes.BOOL
        self.user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        self.user32.ShowWindow.restype = wintypes.BOOL
        self.user32.VkKeyScanW.argtypes = [wintypes.WCHAR]
        self.user32.VkKeyScanW.restype = ctypes.c_short

        self.gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
        self.gdi32.CreateCompatibleDC.restype = wintypes.HDC
        self.gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
        self.gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
        self.gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
        self.gdi32.SelectObject.restype = wintypes.HGDIOBJ
        self.gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
        self.gdi32.DeleteObject.restype = wintypes.BOOL
        self.gdi32.DeleteDC.argtypes = [wintypes.HDC]
        self.gdi32.DeleteDC.restype = wintypes.BOOL
        self.gdi32.BitBlt.argtypes = [
            wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            wintypes.HDC, ctypes.c_int, ctypes.c_int, wintypes.DWORD,
        ]
        self.gdi32.BitBlt.restype = wintypes.BOOL
        self.gdi32.GetDIBits.argtypes = [
            wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
            ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT,
        ]
        self.gdi32.GetDIBits.restype = ctypes.c_int

    def find_window(self, title_fragments: str) -> int | None:
        fragments = [part.strip().casefold() for part in title_fragments.split("|") if part.strip()]
        found: list[int] = []
        callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

        @callback_type
        def callback(hwnd: int, _lparam: int) -> bool:
            if not self.user32.IsWindowVisible(hwnd):
                return True
            length = self.user32.GetWindowTextLengthW(hwnd)
            if not length:
                return True
            buffer = ctypes.create_unicode_buffer(length + 1)
            self.user32.GetWindowTextW(hwnd, buffer, length + 1)
            title = buffer.value.casefold()
            if any(fragment in title for fragment in fragments):
                found.append(hwnd)
                return False
            return True

        self.user32.EnumWindows(callback, 0)
        return found[0] if found else None

    def client_rect(self, hwnd: int | None, fallback_width: int, fallback_height: int) -> WindowRect:
        if not hwnd:
            return WindowRect(0, 0, fallback_width, fallback_height)
        rect = wintypes.RECT()
        origin = wintypes.POINT(0, 0)
        if self.user32.GetClientRect(hwnd, ctypes.byref(rect)) and self.user32.ClientToScreen(hwnd, ctypes.byref(origin)):
            width = rect.right - rect.left
            height = rect.bottom - rect.top
            if width > 100 and height > 100:
                return WindowRect(origin.x, origin.y, width, height)
        return WindowRect(0, 0, fallback_width, fallback_height)

    def focus(self, hwnd: int | None) -> None:
        if hwnd:
            self.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            self.user32.SetForegroundWindow(hwnd)
            time.sleep(0.35)

    def click(self, x: int, y: int) -> None:
        self.user32.SetCursorPos(x, y)
        time.sleep(0.045)
        self.user32.mouse_event(self.LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.045)
        self.user32.mouse_event(self.LEFTUP, 0, 0, 0, 0)

    def right_click(self, x: int, y: int) -> None:
        self.user32.SetCursorPos(x, y)
        time.sleep(0.045)
        self.user32.mouse_event(self.RIGHTDOWN, 0, 0, 0, 0)
        time.sleep(0.045)
        self.user32.mouse_event(self.RIGHTUP, 0, 0, 0, 0)

    def press(self, key: str) -> None:
        key = key.casefold()
        modifiers: list[int] = []
        if key in self.VK:
            vk = self.VK[key]
        elif len(key) == 1:
            result = self.user32.VkKeyScanW(key)
            if result == -1:
                raise ValueError(f"Windows cannot map hotkey {key!r}")
            vk = result & 0xFF
            flags = (result >> 8) & 0xFF
            if flags & 1:
                modifiers.append(self.VK["shift"])
            if flags & 2:
                modifiers.append(self.VK["control"])
            if flags & 4:
                modifiers.append(self.VK["alt"])
        else:
            raise ValueError(f"Unsupported hotkey {key!r}; use one character or a named key")

        for modifier in modifiers:
            self.user32.keybd_event(modifier, 0, 0, 0)
        self.user32.keybd_event(vk, 0, 0, 0)
        time.sleep(0.045)
        self.user32.keybd_event(vk, 0, self.KEYUP, 0)
        for modifier in reversed(modifiers):
            self.user32.keybd_event(modifier, 0, self.KEYUP, 0)

    def hotkey(self, modifier: str, key: str) -> None:
        modifier_vk = self.VK.get(modifier.casefold())
        if modifier_vk is None:
            raise ValueError(f"Unsupported modifier {modifier!r}")
        self.user32.keybd_event(modifier_vk, 0, 0, 0)
        try:
            self.press(key)
        finally:
            self.user32.keybd_event(modifier_vk, 0, self.KEYUP, 0)

    def type_text(self, value: str) -> None:
        for character in value:
            self.press(character)
            time.sleep(0.025)

    def cursor_position(self) -> tuple[int, int]:
        point = wintypes.POINT()
        self.user32.GetCursorPos(ctypes.byref(point))
        return point.x, point.y

    def f8_down(self) -> bool:
        return bool(self.user32.GetAsyncKeyState(self.VK["f8"]) & 0x8000)

    def screenshot(self, rect: WindowRect) -> PixelFrame:
        """Capture a client rectangle with GDI as a top-down 32-bit BGRA frame."""

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [
                ("biSize", wintypes.DWORD),
                ("biWidth", wintypes.LONG),
                ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD),
                ("biBitCount", wintypes.WORD),
                ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD),
                ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG),
                ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD),
            ]

        class BITMAPINFO(ctypes.Structure):
            _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]

        screen_dc = self.user32.GetDC(0)
        memory_dc = self.gdi32.CreateCompatibleDC(screen_dc)
        bitmap = self.gdi32.CreateCompatibleBitmap(screen_dc, rect.width, rect.height)
        previous = self.gdi32.SelectObject(memory_dc, bitmap)
        try:
            copied = self.gdi32.BitBlt(
                memory_dc, 0, 0, rect.width, rect.height,
                screen_dc, rect.left, rect.top, 0x00CC0020 | 0x40000000,
            )
            if not copied:
                raise RuntimeError("Windows could not capture the BTD6 window.")
            info = BITMAPINFO()
            info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            info.bmiHeader.biWidth = rect.width
            info.bmiHeader.biHeight = -rect.height
            info.bmiHeader.biPlanes = 1
            info.bmiHeader.biBitCount = 32
            info.bmiHeader.biCompression = 0
            buffer = (ctypes.c_ubyte * (rect.width * rect.height * 4))()
            lines = self.gdi32.GetDIBits(
                memory_dc, bitmap, 0, rect.height, ctypes.byref(buffer), ctypes.byref(info), 0
            )
            if lines != rect.height:
                raise RuntimeError(f"Windows captured only {lines}/{rect.height} screen rows.")
            return PixelFrame(rect.width, rect.height, bytes(buffer))
        finally:
            self.gdi32.SelectObject(memory_dc, previous)
            self.gdi32.DeleteObject(bitmap)
            self.gdi32.DeleteDC(memory_dc)
            self.user32.ReleaseDC(0, screen_dc)


@dataclass
class PlacedTower:
    name: str
    point: tuple[float, float]
    build: tuple[int, int, int]
    sequence: list[int]
    helper: bool = False
    upgrade_index: int = 0
    failed_upgrades: int = 0

    @property
    def complete(self) -> bool:
        return self.upgrade_index >= len(self.sequence)

    @property
    def build_label(self) -> str:
        return "".join(str(value) for value in self.build)


class MacroEngine:
    def __init__(
        self,
        config: dict,
        tower_name: str,
        log: Callable[[str], None],
        finished: Callable[[], None],
    ) -> None:
        self.config = copy.deepcopy(config)
        self.spec = MONKEYS[tower_name]
        self.log = log
        self.finished = finished
        self.stop_event = threading.Event()
        self.controller = WindowsController()
        self.rng = random.Random()
        self.hwnd: int | None = None
        self.rect = WindowRect(0, 0, 1920, 1200)
        self.thread: threading.Thread | None = None
        self._target_hotkey = self.config["hotkeys"]["tower_overrides"].get(
            tower_name, self.spec.default_hotkey
        )

    def start(self) -> None:
        self.thread = threading.Thread(target=self._run_guarded, name="bloomer-macro", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()

    def _run_guarded(self) -> None:
        try:
            self._run()
        except Exception as exc:  # pragma: no cover - hardware/UI integration path
            self.log(f"ERROR: {type(exc).__name__}: {exc}")
        finally:
            self.finished()

    def _wait(self, seconds: float) -> bool:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if self.stop_event.wait(min(0.10, max(0.0, deadline - time.monotonic()))):
                return False
        return True

    def _run(self) -> None:
        window = self.config["window"]
        self.hwnd = self.controller.find_window(str(window["title_contains"]))
        self.rect = self.controller.client_rect(
            self.hwnd, int(window["fallback_width"]), int(window["fallback_height"])
        )
        if self.hwnd is None:
            self.log(
                "BTD6 window was not found; using the configured full-screen rectangle. "
                "Stop with F8 if the cursor does not land correctly."
            )
        elif bool(window["bring_to_front"]):
            self.controller.focus(self.hwnd)

        self.log(
            f"Viewport: {self.rect.width}x{self.rect.height} at "
            f"({self.rect.left}, {self.rect.top})"
        )
        self.log(f"Starting in {float(self.config['loop']['start_delay_seconds']):g}s; F8 stops immediately.")
        if not self._wait(float(self.config["loop"]["start_delay_seconds"])):
            return

        completed = 0
        limit = int(self.config["loop"]["completed_games"])
        need_navigation = True
        while not self.stop_event.is_set() and (limit == 0 or completed < limit):
            if need_navigation:
                if not self._navigate_to_game():
                    return
            result = self._play_one_game()
            if result is None:
                return
            if result == "victory" or bool(self.config["loop"]["count_defeats"]):
                completed += 1
            self.log(f"Cycle finished ({result}); completed cycles: {completed}")
            if limit and completed >= limit:
                break
            need_navigation = result == "victory"
            if not self._handle_end(result):
                return

        self.log("Macro stopped." if self.stop_event.is_set() else "Requested cycle count completed.")

    def _click_point(self, key: str) -> None:
        self.controller.click(*self.rect.point(self.config["points"][key]))

    def _navigate_to_game(self) -> bool:
        delay = float(self.config["loop"]["navigation_delay_seconds"])
        map_name = target_map_name(self.spec)
        self.log(f"Navigating to {map_name} / Easy / Standard...")
        self._click_point("home_play")
        if not self._wait(delay):
            return False
        self._click_point("beginner")
        if not self._wait(delay):
            return False

        # Always search by exact map name. BTD6 remembers the last open page, so
        # blindly clicking the first card can select Tree Stump instead of Monkey
        # Meadow when a previous session left the Beginner list on page two.
        self._click_point("map_search")
        if not self._wait(0.8):
            return False
        # Opening search does not focus its top-center text box on every BTD6
        # layout, so click the field explicitly before replacing its contents.
        self._click_point("map_search_field")
        if not self._wait(0.25):
            return False
        self.controller.hotkey("control", "a")
        self.controller.press("backspace")
        self.controller.type_text(map_name)
        self.controller.press("enter")
        if not self._wait(delay):
            return False

        self._click_point("map_card")
        if not self._wait(delay):
            return False
        self._click_point("difficulty_easy")
        if not self._wait(delay):
            return False
        self._click_point("mode_standard")
        if not self._wait(float(self.config["loop"]["load_delay_seconds"])):
            return False
        # Harmless on a loaded map; dismisses a loading/tip overlay if one is present.
        self._click_point("dismiss_loading")
        return self._wait(0.8)

    def _screenshot(self) -> PixelFrame:
        return self.controller.screenshot(self.rect)

    def _point_crop(self, image: PixelFrame, point: Sequence[float], radius: float = 0.032) -> PixelFrame:
        x, y = float(point[0]), float(point[1])
        aspect_adjustment = self.rect.height / max(1, self.rect.width)
        return normalized_crop(
            image,
            (x - radius * aspect_adjustment, y - radius, x + radius * aspect_adjustment, y + radius),
        )

    def _try_place(
        self,
        name: str,
        hotkey: str,
        point: tuple[float, float],
        helper: bool = False,
        fixed_build: tuple[int, int, int] | None = None,
    ) -> PlacedTower | None:
        before = self._point_crop(self._screenshot(), point)
        self.controller.press(hotkey)
        if not self._wait(0.16):
            return None
        self.controller.click(*self.rect.point(point))
        if not self._wait(0.24):
            return None
        # Escape opens Pause whenever placement failed (for example, because the
        # tower is unaffordable). Right-click safely cancels a ghost placement or
        # deselects a placed tower without opening Pause.
        self.controller.right_click(*self.rect.point(point))
        if not self._wait(0.55):
            return None
        after = self._point_crop(self._screenshot(), point)
        score = image_diff_score(before, after)
        threshold = float(self.config["detection"]["placement_change_threshold"])
        if score < threshold:
            self.log(f"Placement not confirmed at {point[0]:.3f}, {point[1]:.3f} (change {score:.1f}).")
            return None

        if fixed_build is None:
            build, sequence = generate_build(self.rng, int(self.config["loop"]["main_path_tier"]))
        else:
            build = fixed_build
            sequence = [path for path, count in enumerate(build) for _ in range(count)]
        tower = PlacedTower(name, point, build, sequence, helper=helper)
        role = "helper" if helper else "target"
        self.log(f"Placed {role} {name} with planned build {tower.build_label} (change {score:.1f}).")
        return tower

    def _try_upgrade(self, tower: PlacedTower) -> bool:
        if tower.complete:
            return False
        self.controller.click(*self.rect.point(tower.point))
        if not self._wait(0.38):
            return False

        # BTD6 opens the upgrade panel opposite the selected tower.
        panel_box = (0.735, 0.10, 1.0, 0.94) if tower.point[0] < 0.50 else (0.0, 0.10, 0.265, 0.94)
        before = normalized_crop(self._screenshot(), panel_box)
        path = tower.sequence[tower.upgrade_index]
        configured_keys = (
            str(self.config["hotkeys"]["upgrade_top"]),
            str(self.config["hotkeys"]["upgrade_middle"]),
            str(self.config["hotkeys"]["upgrade_bottom"]),
        )
        self.controller.press(configured_keys[path])
        if not self._wait(0.45):
            return False
        after_first = normalized_crop(self._screenshot(), panel_box)
        if not self._wait(0.30):
            return False
        after_settled = normalized_crop(self._screenshot(), panel_box)
        self.controller.right_click(*self.rect.point(tower.point))

        change = image_diff_score(before, after_settled)
        motion = image_diff_score(after_first, after_settled)
        threshold = float(self.config["detection"]["upgrade_change_threshold"])
        success = change >= threshold and change >= max(threshold, motion * 1.18)
        if success:
            tower.upgrade_index += 1
            tower.failed_upgrades = 0
            self.log(
                f"{tower.name} {tower.build_label}: bought path {path + 1} "
                f"({tower.upgrade_index}/{len(tower.sequence)})."
            )
        else:
            tower.failed_upgrades += 1
        return success

    def _pulse_round(self) -> None:
        # Two quick presses start+fast-forward when paused. During an active round,
        # they toggle speed twice and leave its state unchanged.
        key = str(self.config["hotkeys"]["start_round"])
        self.controller.press(key)
        time.sleep(0.13)
        self.controller.press(key)

    def _play_one_game(self) -> str | None:
        self.log(f"Farming {self.spec.name}. End-screen detection is active.")
        placement_key = "spice_islands" if self.spec.water_map else "monkey_meadow"
        candidates = [tuple(point) for point in self.config["placements"][placement_key]]
        self.rng.shuffle(candidates)
        helper_points = [tuple(point) for point in self.config["placements"]["helpers"]]
        target_towers: list[PlacedTower] = []
        helpers: list[PlacedTower] = []

        # Try the farm target before spending anything on a helper.
        first = self._try_place(self.spec.name, self._target_hotkey, candidates.pop())
        if first:
            target_towers.append(first)

        # An unaffordable starting tower, Banana Farm, or Village needs a cheap start.
        if not first or self.spec.passive:
            helper = self._try_place(
                "Dart Monkey", MONKEYS["Dart Monkey"].default_hotkey, helper_points[0],
                helper=True, fixed_build=(0, 2, 3),
            )
            if helper:
                helpers.append(helper)

        next_round_pulse = time.monotonic()
        next_action = time.monotonic() + float(self.config["loop"]["action_interval_seconds"])
        next_detection = time.monotonic()
        action_number = 0
        max_targets = int(self.config["loop"]["max_target_towers"])
        place_every = max(1, int(self.config["loop"]["placement_every_actions"]))

        while not self.stop_event.is_set():
            now = time.monotonic()
            if now >= next_detection:
                end_state = classify_end_screen(self._screenshot(), self.config["detection"])
                if end_state:
                    self.log(f"Detected {end_state} screen.")
                    return end_state
                next_detection = now + 1.25

            if now >= next_round_pulse:
                self._pulse_round()
                next_round_pulse = now + float(self.config["loop"]["round_pulse_seconds"])

            if now >= next_action:
                action_number += 1
                acted = False

                # Passive targets get a second small defender once cash permits.
                if self.spec.passive and len(helpers) == 1 and action_number % 5 == 0:
                    helper = self._try_place(
                        "Bomb Shooter", MONKEYS["Bomb Shooter"].default_hotkey, helper_points[1],
                        helper=True, fixed_build=(2, 0, 3),
                    )
                    if helper:
                        helpers.append(helper)
                    acted = True

                should_place = (
                    not acted and candidates and len(target_towers) < max_targets
                    and (not target_towers or action_number % place_every == 0)
                )
                if should_place:
                    candidate = candidates.pop()
                    tower = self._try_place(self.spec.name, self._target_hotkey, candidate)
                    if tower:
                        target_towers.append(tower)
                    else:
                        # Retry valid-looking coordinates later; lack of cash is common.
                        candidates.insert(0, candidate)
                    acted = True

                if not acted:
                    pending_helpers = [tower for tower in helpers if not tower.complete]
                    pending_targets = [tower for tower in target_towers if not tower.complete]
                    # Keep passive-farm defenders alive, but spend most actions on the target.
                    if pending_helpers and (not pending_targets or (self.spec.passive and action_number % 4 == 1)):
                        self._try_upgrade(self.rng.choice(pending_helpers))
                    elif pending_targets:
                        self._try_upgrade(self.rng.choice(pending_targets))
                    elif candidates and len(target_towers) < max_targets:
                        candidate = candidates.pop()
                        tower = self._try_place(self.spec.name, self._target_hotkey, candidate)
                        if tower:
                            target_towers.append(tower)
                        else:
                            candidates.insert(0, candidate)

                next_action = time.monotonic() + float(self.config["loop"]["action_interval_seconds"])

            if not self._wait(0.08):
                return None
        return None

    def _handle_end(self, result: str) -> bool:
        if result == "defeat":
            self._click_point("defeat_restart")
        else:
            self._click_point("victory_home")
        return self._wait(float(self.config["loop"]["restart_delay_seconds"]))


class CalibrationDialog(tk.Toplevel):
    def __init__(self, app: "BloomerApp") -> None:
        super().__init__(app.root)
        self.app = app
        self.title("Calibrate navigation points")
        self.resizable(False, False)
        self.transient(app.root)
        self.grab_set()

        ttk.Label(
            self,
            text=(
                "Select a UI target, press Capture, then move the cursor over that target in BTD6.\n"
                "The point is recorded after four seconds and normalized to the game window."
            ),
            justify="left",
        ).grid(row=0, column=0, columnspan=2, padx=12, pady=12, sticky="w")
        self.listbox = tk.Listbox(self, width=46, height=len(CALIBRATABLE_POINTS), exportselection=False)
        for label in CALIBRATABLE_POINTS:
            self.listbox.insert("end", label)
        self.listbox.selection_set(0)
        self.listbox.grid(row=1, column=0, columnspan=2, padx=12, sticky="ew")
        self.status = ttk.Label(self, text="")
        self.status.grid(row=2, column=0, columnspan=2, padx=12, pady=8, sticky="w")
        ttk.Button(self, text="Capture selected (4s)", command=self.capture).grid(row=3, column=0, padx=12, pady=12)
        ttk.Button(self, text="Done", command=self.destroy).grid(row=3, column=1, padx=12, pady=12)

    def capture(self) -> None:
        selection = self.listbox.curselection()
        if not selection:
            return
        label = self.listbox.get(selection[0])
        key = CALIBRATABLE_POINTS[label]
        self.status.configure(text=f"Move the pointer to: {label}")
        self.update_idletasks()
        self.app.root.iconify()
        self.after(4000, lambda: self._finish_capture(key, label))

    def _finish_capture(self, key: str, label: str) -> None:
        controller = self.app.controller
        window = self.app.config["window"]
        hwnd = controller.find_window(str(window["title_contains"]))
        rect = controller.client_rect(hwnd, int(window["fallback_width"]), int(window["fallback_height"]))
        x, y = controller.cursor_position()
        normalized = [
            min(1.0, max(0.0, (x - rect.left) / max(1, rect.width))),
            min(1.0, max(0.0, (y - rect.top) / max(1, rect.height))),
        ]
        self.app.config["points"][key] = normalized
        save_config(self.app.config)
        self.app.root.deiconify()
        self.lift()
        self.grab_set()
        self.status.configure(text=f"Saved {label}: {normalized[0]:.4f}, {normalized[1]:.4f}")


class BloomerApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.controller = WindowsController()
        self.config = load_config()
        self.engine: MacroEngine | None = None
        self.messages: queue.Queue[str] = queue.Queue()
        self._f8_was_down = False

        self.root.title(f"{APP_NAME} {APP_VERSION}")
        self.root.geometry("680x670")
        self.root.minsize(620, 590)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.tower_var = tk.StringVar(value=str(self.config["last_tower"]))
        self.hotkey_var = tk.StringVar()
        self.width_var = tk.StringVar(value=str(self.config["window"]["fallback_width"]))
        self.height_var = tk.StringVar(value=str(self.config["window"]["fallback_height"]))
        self.title_var = tk.StringVar(value=str(self.config["window"]["title_contains"]))
        self.cycles_var = tk.StringVar(value=str(self.config["loop"]["completed_games"]))
        self.round_var = tk.StringVar(value=str(self.config["loop"]["round_pulse_seconds"]))
        self.status_var = tk.StringVar(value="Ready - put BTD6 on its main menu before starting.")

        self._build_ui()
        self._tower_changed()
        self.root.after(80, self._poll)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=16)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="BTD6 XP farmer", font=("Segoe UI", 16, "bold")).grid(
            row=0, column=0, columnspan=4, sticky="w"
        )
        ttk.Label(
            outer,
            text="Easy Standard on Monkey Meadow; water towers automatically use Spice Islands.",
        ).grid(row=1, column=0, columnspan=4, sticky="w", pady=(2, 14))

        ttk.Label(outer, text="Monkey to farm").grid(row=2, column=0, sticky="w")
        tower_box = ttk.Combobox(
            outer, textvariable=self.tower_var, values=list(MONKEYS), state="readonly", width=29
        )
        tower_box.grid(row=2, column=1, columnspan=2, sticky="ew", padx=(8, 8))
        tower_box.bind("<<ComboboxSelected>>", lambda _event: self._tower_changed())

        ttk.Label(outer, text="Placement hotkey").grid(row=3, column=0, sticky="w", pady=(10, 0))
        ttk.Entry(outer, textvariable=self.hotkey_var, width=8).grid(row=3, column=1, sticky="w", padx=8, pady=(10, 0))
        self.binding_note = ttk.Label(outer, text="")
        self.binding_note.grid(row=3, column=2, columnspan=2, sticky="w", pady=(10, 0))

        ttk.Separator(outer).grid(row=4, column=0, columnspan=4, sticky="ew", pady=14)
        ttk.Label(outer, text="Fallback resolution").grid(row=5, column=0, sticky="w")
        ttk.Entry(outer, textvariable=self.width_var, width=9).grid(row=5, column=1, sticky="w", padx=(8, 2))
        ttk.Label(outer, text="x").grid(row=5, column=2)
        ttk.Entry(outer, textvariable=self.height_var, width=9).grid(row=5, column=3, sticky="w", padx=(2, 0))

        ttk.Label(outer, text="Window title contains").grid(row=6, column=0, sticky="w", pady=(10, 0))
        ttk.Entry(outer, textvariable=self.title_var).grid(
            row=6, column=1, columnspan=3, sticky="ew", padx=(8, 0), pady=(10, 0)
        )

        ttk.Label(outer, text="Cycles (0 = infinite)").grid(row=7, column=0, sticky="w", pady=(10, 0))
        ttk.Entry(outer, textvariable=self.cycles_var, width=9).grid(row=7, column=1, sticky="w", padx=8, pady=(10, 0))
        ttk.Label(outer, text="Round pulse (seconds)").grid(row=7, column=2, sticky="e", pady=(10, 0))
        ttk.Entry(outer, textvariable=self.round_var, width=9).grid(row=7, column=3, sticky="w", padx=(8, 0), pady=(10, 0))

        controls = ttk.Frame(outer)
        controls.grid(row=8, column=0, columnspan=4, sticky="ew", pady=16)
        self.start_button = ttk.Button(controls, text="Start farming", command=self.start)
        self.start_button.pack(side="left")
        self.stop_button = ttk.Button(controls, text="Stop (F8)", command=self.stop, state="disabled")
        self.stop_button.pack(side="left", padx=8)
        ttk.Button(controls, text="Save settings", command=self.save_settings).pack(side="left", padx=8)
        ttk.Button(controls, text="Calibrate points...", command=self.calibrate).pack(side="left")

        ttk.Label(outer, textvariable=self.status_var, wraplength=630).grid(
            row=9, column=0, columnspan=4, sticky="w", pady=(0, 8)
        )
        self.log_box = tk.Text(outer, height=16, wrap="word", state="disabled", font=("Consolas", 9))
        self.log_box.grid(row=10, column=0, columnspan=4, sticky="nsew")
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=self.log_box.yview)
        scrollbar.grid(row=10, column=4, sticky="ns")
        self.log_box.configure(yscrollcommand=scrollbar.set)

        ttk.Label(
            outer,
            text="Emergency stop: F8. Keep this macro out of co-op, races, ranked events, and other competitive modes.",
            foreground="#8a2d2d",
        ).grid(row=11, column=0, columnspan=4, sticky="w", pady=(10, 0))

        outer.columnconfigure(1, weight=1)
        outer.columnconfigure(3, weight=1)
        outer.rowconfigure(10, weight=1)

    def _tower_changed(self) -> None:
        name = self.tower_var.get()
        spec = MONKEYS[name]
        self.hotkey_var.set(str(self.config["hotkeys"]["tower_overrides"].get(name, spec.default_hotkey)))
        if spec.custom_binding:
            self.binding_note.configure(text="Assign this same key in BTD6 Settings > Hotkeys.", foreground="#9a5b00")
        else:
            self.binding_note.configure(text=f"BTD6 default ({spec.category})", foreground="#444444")

    def _read_settings(self) -> None:
        try:
            width = int(self.width_var.get())
            height = int(self.height_var.get())
            cycles = int(self.cycles_var.get())
            round_seconds = float(self.round_var.get())
        except ValueError as exc:
            raise ValueError("Resolution, cycles, and round pulse must be numeric.") from exc
        if width < 800 or height < 600:
            raise ValueError("Fallback resolution must be at least 800 x 600.")
        if cycles < 0:
            raise ValueError("Cycles cannot be negative.")
        if round_seconds < 5:
            raise ValueError("Round pulse must be at least 5 seconds.")
        hotkey = self.hotkey_var.get().strip()
        if len(hotkey) != 1:
            raise ValueError("Placement hotkey must be exactly one character.")

        name = self.tower_var.get()
        self.config["last_tower"] = name
        self.config["window"]["fallback_width"] = width
        self.config["window"]["fallback_height"] = height
        self.config["window"]["title_contains"] = self.title_var.get().strip()
        self.config["loop"]["completed_games"] = cycles
        self.config["loop"]["round_pulse_seconds"] = round_seconds
        self.config["hotkeys"]["tower_overrides"][name] = hotkey

    def save_settings(self) -> None:
        try:
            self._read_settings()
            save_config(self.config)
        except (ValueError, OSError) as exc:
            messagebox.showerror(APP_NAME, str(exc), parent=self.root)
            return
        self.status_var.set(f"Settings saved to {CONFIG_PATH.name}.")

    def start(self) -> None:
        if self.engine is not None:
            return
        try:
            self._read_settings()
            save_config(self.config)
        except (ValueError, OSError) as exc:
            messagebox.showerror(APP_NAME, str(exc), parent=self.root)
            return

        spec = MONKEYS[self.tower_var.get()]
        if spec.custom_binding:
            answer = messagebox.askokcancel(
                APP_NAME,
                f"{spec.name} has no BTD6 default placement key.\n\n"
                f"Confirm that {self.hotkey_var.get()!r} is assigned to {spec.name} in "
                "BTD6 Settings > Hotkeys.",
                parent=self.root,
            )
            if not answer:
                return

        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.status_var.set("Running. Bloomer will minimize; press F8 to stop.")
        self.engine = MacroEngine(self.config, self.tower_var.get(), self.messages.put, self._engine_finished)
        self.root.after(350, self.root.iconify)
        self.engine.start()

    def stop(self) -> None:
        if self.engine:
            self.engine.stop()
            self.status_var.set("Stopping...")

    def _engine_finished(self) -> None:
        self.messages.put("__ENGINE_FINISHED__")

    def calibrate(self) -> None:
        if self.engine is not None:
            messagebox.showinfo(APP_NAME, "Stop the macro before calibrating.", parent=self.root)
            return
        try:
            self._read_settings()
            save_config(self.config)
        except (ValueError, OSError) as exc:
            messagebox.showerror(APP_NAME, str(exc), parent=self.root)
            return
        CalibrationDialog(self)

    def _append_log(self, value: str) -> None:
        stamp = time.strftime("%H:%M:%S")
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"[{stamp}] {value}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _poll(self) -> None:
        down = self.controller.f8_down()
        if down and not self._f8_was_down:
            self.stop()
        self._f8_was_down = down

        try:
            while True:
                message = self.messages.get_nowait()
                if message == "__ENGINE_FINISHED__":
                    self.engine = None
                    self.start_button.configure(state="normal")
                    self.stop_button.configure(state="disabled")
                    self.status_var.set("Stopped. Review the activity log below.")
                    self.root.deiconify()
                    self.root.lift()
                else:
                    self._append_log(message)
        except queue.Empty:
            pass
        self.root.after(80, self._poll)

    def close(self) -> None:
        if self.engine:
            self.engine.stop()
        self.root.destroy()


def main() -> int:
    if sys.platform != "win32":
        print("Bloomer currently supports Windows only.", file=sys.stderr)
        return 1
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except AttributeError:
            pass
    root = tk.Tk()
    try:
        BloomerApp(root)
    except RuntimeError as exc:
        messagebox.showerror(APP_NAME, str(exc), parent=root)
        root.destroy()
        return 1
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
