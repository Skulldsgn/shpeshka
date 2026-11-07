"""Ядро стилизации: палитра, несовмещённая печать, полутона, бумага, зерно.
Используется и нодой ComfyUI, и scripts/unify.py. Нужны только numpy и pillow.
Все эффекты отключаемы, палитра задаётся строкой HEX-цветов."""
import re

import numpy as np
from PIL import Image, ImageFilter

# Значения по умолчанию — под силуэты на бумаге. В ноде и в unify.py всё задаётся своё.
DEFAULT_PALETTE = "#111111, #E9DFC8"
LUMA = np.array([0.30, 0.59, 0.11], dtype=np.float32)


def parse_palette(text):
    """'#112233, #445566 ...' -> массив (N, 3) 0..1. Пустая строка -> None."""
    hexes = re.findall(r"#?([0-9a-fA-F]{6})\b", text or "")
    if not hexes:
        return None
    return np.array([[int(h[i:i + 2], 16) for i in (0, 2, 4)] for h in hexes], np.float32) / 255.0


def luminance(rgb):
    return rgb @ LUMA


def color_mask(rgb, lo=0.15, ramp=0.12):
    """1 там, где цвет насыщенный (красный, синий...), 0 на чёрном, белом и серых.
    Тушь, заливка деталей и полутона насыщенные цвета не трогают: красный тёмный по яркости, но это не тушь."""
    sat = rgb.max(-1) - rgb.min(-1)
    return np.clip((sat - lo) / ramp, 0, 1)


# ---------- цвет ----------

def palette_map(rgb, palette, strength=0.7, softness=0.06):
    """Мягкое притяжение цветов к палитре с частичным сохранением яркости."""
    if palette is None or strength <= 0:
        return rgb
    flat = rgb.reshape(-1, 3)
    d = (((flat[:, None, :] - palette[None, :, :]) ** 2) * LUMA).sum(-1)
    k = np.exp(-(d - d.min(1, keepdims=True)) / softness)
    k /= k.sum(1, keepdims=True)
    mapped = k @ palette
    mapped = np.clip(mapped + (flat @ LUMA - mapped @ LUMA)[:, None] * 0.5, 0, 1)
    return (flat * (1 - strength) + mapped * strength).reshape(rgb.shape)


def ink_fill(rgb, ink, threshold, fill_px=0, soft=0.05):
    """Всё темнее порога заливается сплошной тушью.
    fill_px: светлые детали внутри тёмных масс тоньше этого размера (блики, черты лица) тоже заливаются."""
    if threshold <= 0:
        return rgb
    keep = 1 - color_mask(rgb)
    m = np.clip((threshold - luminance(rgb)) / soft + 0.5, 0, 1) * keep
    if fill_px > 1:
        m = np.maximum(m, _round_close(m, fill_px / 2)) * keep
    return rgb * (1 - m[..., None]) + ink * m[..., None]


def _box(a, r, axis):
    """Скользящее среднее ширины 2r+1 вдоль оси (края дублируются)."""
    pad = [(0, 0)] * a.ndim
    pad[axis] = (r + 1, r)
    c = np.cumsum(np.pad(a, pad, mode="edge"), axis=axis, dtype=np.float64)
    n = a.shape[axis]
    hi = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis)
    lo = np.take(c, np.arange(0, n), axis=axis)
    return ((hi - lo) / (2 * r + 1)).astype(np.float32)


def _blur(a, sigma):
    """Гаусс ≈ три прохода box-фильтра (float, без потери точности)."""
    r = max(1, int(round((np.sqrt(4 * sigma * sigma + 1) - 1) / 2)))  # 3 бокса шириной 2r+1 ≈ σ
    out = a.astype(np.float32)
    for _ in range(3):
        out = _box(_box(out, r, 0), r, 1)
    return out


def _round_close(m, r):
    """Морфологическое закрытие круглым окном радиуса r (через гаусс + порог).
    Квадратное окно оставляло ступеньки и прямоугольники на углах; круглое даёт плавные формы."""
    sigma = max(r / 2.0, 0.5)
    lo, ramp = 0.023, 0.02  # уровень гаусса на расстоянии r от края (Φ(-2)) и мягкость перехода
    dil = np.clip((_blur(m, sigma) - lo) / ramp, 0, 1)                # расширение на r
    ero = np.clip((_blur(dil, sigma) - (1 - lo - ramp)) / ramp, 0, 1)  # сужение обратно на r
    return ero


# ---------- фактуры ----------

def misregister(rgb, dx=2, dy=1):
    lum = luminance(rgb)[..., None]
    chroma = np.roll(rgb - lum, (dy, dx), axis=(0, 1))
    return np.clip(lum + chroma, 0, 1)


def halftone(rgb, ink, cell=8, angle=45, opacity=0.55):
    h, wd = rgb.shape[:2]
    yy, xx = np.mgrid[0:h, 0:wd].astype(np.float32)
    a = np.deg2rad(angle)
    u = xx * np.cos(a) + yy * np.sin(a)
    v = -xx * np.sin(a) + yy * np.cos(a)
    dist = np.sqrt(((u % cell) - cell / 2) ** 2 + ((v % cell) - cell / 2) ** 2) / (cell / 2)
    dark = 1 - luminance(rgb)
    band = np.clip((dark - 0.25) / 0.35, 0, 1)  # точки только в средних тонах и тенях
    band = band * (1 - 0.65 * color_mask(rgb))  # на цветных плашках — лёгкие точки, а не сплошная грязь
    radius = np.sqrt(np.clip(dark, 0, 1)) * 0.9
    dot = (dist < radius).astype(np.float32) * band * opacity
    return rgb * (1 - dot[..., None]) + ink * dot[..., None]


_paper_cache = {}


def paper_texture(h, w):
    if (h, w) not in _paper_cache:
        rng = np.random.default_rng(1234)  # одинаковая бумага на всех кадрах
        tex = np.zeros((h, w), np.float32)
        for scale, amp in ((4, 0.5), (16, 0.3), (64, 0.2)):
            small = rng.random((max(2, h // scale), max(2, w // scale))).astype(np.float32)
            img = Image.fromarray((small * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
            tex += np.asarray(img, np.float32) / 255.0 * amp
        _paper_cache[(h, w)] = (tex - tex.mean()) / (tex.std() + 1e-6)
    return _paper_cache[(h, w)]


def grain_and_paper(rgb, seed, grain, paper, paper_tint):
    h, w = rgb.shape[:2]
    out = rgb
    if paper > 0:
        out = out * (1 + paper_texture(h, w)[..., None] * paper)
        if paper_tint is not None:
            out = out * 0.94 + paper_tint * 0.06
    if grain > 0:
        out = out + np.random.default_rng(seed).normal(0, grain, (h, w, 1)).astype(np.float32)
    return np.clip(out, 0, 1)


def stylize(rgb, palette_text=DEFAULT_PALETTE, strength=0.9, dot=0, offset=0,
            grain=0.02, paper=0.035, seed=0, ink_threshold=0.35, fill_px=0):
    """rgb: numpy (H, W, 3) float 0..1. Любой эффект выключается нулём, палитра — пустой строкой."""
    pal = parse_palette(palette_text)
    # тушь = самый тёмный цвет палитры (или почти чёрный, если палитры нет)
    ink = pal[np.argmin(pal @ LUMA)] if pal is not None else np.array([0.07, 0.07, 0.07], np.float32)
    rgb = ink_fill(rgb.astype(np.float32), ink, ink_threshold, fill_px)
    rgb = palette_map(rgb, pal, strength)
    if offset:
        rgb = misregister(rgb, offset, max(1, offset // 2))
    if dot > 0:
        rgb = halftone(rgb, ink, cell=dot)
    tint = pal[np.argmax(pal @ LUMA)] if pal is not None else None
    return grain_and_paper(rgb, seed, grain, paper, tint)
