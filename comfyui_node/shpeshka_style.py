"""Ядро стилизации: палитра, несовмещённая печать, полутона, бумага, зерно.
Используется и нодой ComfyUI, и scripts/unify.py. Нужны только numpy и pillow.
Все эффекты отключаемы, палитра задаётся строкой HEX-цветов."""
import re

import numpy as np
from PIL import Image

# Пример палитры. Это только значение по умолчанию: в ноде и в unify.py задаётся своя.
DEFAULT_PALETTE = "#1B1A17, #E8DCC0, #6B7040, #A4482B, #3E6B68, #E3A93B, #8A8577, #232F3E"
LUMA = np.array([0.30, 0.59, 0.11], dtype=np.float32)


def parse_palette(text):
    """'#112233, #445566 ...' -> массив (N, 3) 0..1. Пустая строка -> None."""
    hexes = re.findall(r"#?([0-9a-fA-F]{6})\b", text or "")
    if not hexes:
        return None
    return np.array([[int(h[i:i + 2], 16) for i in (0, 2, 4)] for h in hexes], np.float32) / 255.0


def luminance(rgb):
    return rgb @ LUMA


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


def stylize(rgb, palette_text=DEFAULT_PALETTE, strength=0.7, dot=8, offset=2,
            grain=0.035, paper=0.04, seed=0):
    """rgb: numpy (H, W, 3) float 0..1. Любой эффект выключается нулём, палитра — пустой строкой."""
    pal = parse_palette(palette_text)
    rgb = palette_map(rgb.astype(np.float32), pal, strength)
    if offset:
        rgb = misregister(rgb, offset, max(1, offset // 2))
    if dot > 0:
        # точки цветом самого тёмного цвета палитры (или почти чёрным, если палитры нет)
        ink = pal[np.argmin(pal @ LUMA)] if pal is not None else np.array([0.1, 0.1, 0.09], np.float32)
        rgb = halftone(rgb, ink, cell=dot)
    tint = pal[np.argmax(pal @ LUMA)] if pal is not None else None
    return grain_and_paper(rgb, seed, grain, paper, tint)
