import ctypes
import sys
from ctypes import wintypes


DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_USE_IMMERSIVE_DARK_MODE_OLD = 19
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWA_BORDER_COLOR = 34
DWMWA_CAPTION_COLOR = 35
DWMWA_TEXT_COLOR = 36
DWMWA_SYSTEMBACKDROP_TYPE = 38

DWMWCP_ROUND = 2
DWMSBT_MAINWINDOW = 2


def apply_modern_window_effects(widget, theme_mode):
    if sys.platform != "win32":
        return

    try:
        hwnd = wintypes.HWND(int(widget.winId()))
    except RuntimeError:
        return

    dark = 1 if theme_mode == "dark" else 0
    _set_int_attribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, dark)
    _set_int_attribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE_OLD, dark)
    _set_int_attribute(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, DWMWCP_ROUND)
    _set_int_attribute(hwnd, DWMWA_SYSTEMBACKDROP_TYPE, DWMSBT_MAINWINDOW)

    if theme_mode == "dark":
        caption = _colorref("#171d26")
        border = _colorref("#2f3948")
        text = _colorref("#f3f7fb")
    else:
        caption = _colorref("#fbfdff")
        border = _colorref("#c9d4e2")
        text = _colorref("#1f2937")

    _set_color_attribute(hwnd, DWMWA_CAPTION_COLOR, caption)
    _set_color_attribute(hwnd, DWMWA_BORDER_COLOR, border)
    _set_color_attribute(hwnd, DWMWA_TEXT_COLOR, text)


def _set_int_attribute(hwnd, attribute, value):
    data = ctypes.c_int(value)
    _dwm_set_window_attribute(hwnd, attribute, data)


def _set_color_attribute(hwnd, attribute, color):
    data = ctypes.c_int(color)
    _dwm_set_window_attribute(hwnd, attribute, data)


def _dwm_set_window_attribute(hwnd, attribute, data):
    try:
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd,
            ctypes.c_uint(attribute),
            ctypes.byref(data),
            ctypes.sizeof(data),
        )
    except (AttributeError, OSError):
        pass


def _colorref(hex_color):
    value = hex_color.lstrip("#")
    red = int(value[0:2], 16)
    green = int(value[2:4], 16)
    blue = int(value[4:6], 16)
    return red | (green << 8) | (blue << 16)
