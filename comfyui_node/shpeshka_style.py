"""Ядро стиля «Спешки»: палитра, несовмещённая печать, полутона, бумага, зерно.
Используется и нодой ComfyUI, и scripts/unify.py. Нужны только numpy и pillow."""
import numpy as np
from PIL import Image

PALETTE_HEX = {
    "ink": "#1B1A17",
    "paper": "#E8DCC0",
    "olive": "#6B7040",
    "rust": "#A4482B",
    "teal": "#3E6B68",
    "sodium": "#E3A93B",
    "smog": "#8A8577",
    "night": "#232F3E",
}
PALETTE = np.array(
    [[int(h[i:i + 2], 16) for i in (1, 3, 5)] for h in PALETTE_HEX.values()],
    dtype=np.float32,
) / 255.0
INK = PALETTE[0]


# ---------- цвет ----------

def palette_map(rgb, strength=0.7, softness=0.06):
    """rgb: (..., 3) float 0..1. Мягкое притяжение к палитре с сохранением яркости."""
    flat = rgb.reshape(-1, 3)
    w = np.array([0.30, 0.59, 0.11], dtype=np.float32)  # перцептивный вес каналов
    d = (((flat[:, None, :] - PALETTE[None, :, :]) ** 2) * w).sum(-1)
    k = np.exp(-(d - d.min(1, keepdims=True)) / softness)
    k /= k.sum(1, keepdims=True)
    mapped = k @ PALETTE
    # сохраняем исходную яркость наполовину, чтобы не терялся рисунок
    lum_src = flat @ w
    lum_map = mapped @ w
    mapped = np.clip(mapped + (lum_src - lum_map)[:, None] * 0.5, 0, 1)
    out = flat * (1 - strength) + mapped * strength
    return out.reshape(rgb.shape)


def luminance(rgb):
    return rgb @ np.array([0.30, 0.59, 0.11], dtype=np.float32)


# ---------- фактуры ----------

def misregister(rgb, dx=2, dy=1):
    lum = luminance(rgb)[..., None]
    chroma = rgb - lum
    chroma = np.roll(chroma, (dy, dx), axis=(0, 1))
    return np.clip(lum + chroma, 0, 1)


def halftone(rgb, cell=8, angle=45, opacity=0.55):
    h, wd = rgb.shape[:2]
    yy, xx = np.mgrid[0:h, 0:wd].astype(np.float32)
    a = np.deg2rad(angle)
    u = xx * np.cos(a) + yy * np.sin(a)
    v = -xx * np.sin(a) + yy * np.cos(a)
    du = (u % cell) - cell / 2
    dv = (v % cell) - cell / 2
    dist = np.sqrt(du ** 2 + dv ** 2) / (cell / 2)  # 0 в центре ячейки
    dark = 1 - luminance(rgb)
    # точки только в средних тонах и тенях; в светах чисто
    band = np.clip((dark - 0.25) / 0.35, 0, 1)
    radius = np.sqrt(np.clip(dark, 0, 1)) * 0.9
    dot = (dist < radius).astype(np.float32) * band * opacity
    return rgb * (1 - dot[..., None]) + INK * dot[..., None]


_paper_cache = {}


def paper_texture(h, w):
    key = (h, w)
    if key not in _paper_cache:
        rng = np.random.default_rng(1234)  # одинаковая бумага на всех кадрах
        tex = np.zeros((h, w), np.float32)
        for scale, amp in ((4, 0.5), (16, 0.3), (64, 0.2)):
            small = rng.random((max(2, h // scale), max(2, w // scale))).astype(np.float32)
            img = Image.fromarray((small * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
            tex += np.asarray(img, np.float32) / 255.0 * amp
        tex = (tex - tex.mean()) / (tex.std() + 1e-6)
        _paper_cache[key] = tex
    return _paper_cache[key]


def grain_and_paper(rgb, frame_seed, grain=0.035, paper=0.04):
    h, w = rgb.shape[:2]
    rng = np.random.default_rng(frame_seed)
    g = rng.normal(0, grain, (h, w, 1)).astype(np.float32)
    p = paper_texture(h, w)[..., None] * paper
    paper_col = PALETTE[1]
    out = rgb * (1 + p) + g
    # чуть «пожелтить» света под бумагу
    out = out * 0.94 + paper_col * 0.06
    return np.clip(out, 0, 1)



def stylize(rgb, strength=0.7, dot=8, offset=2, grain=0.035, paper=0.04, seed=0):
    """rgb: numpy (H, W, 3) float 0..1 -> то же, в стиле клипа."""
    rgb = palette_map(rgb.astype(np.float32), strength)
    if offset:
        rgb = misregister(rgb, offset, max(1, offset // 2))
    if dot > 0:
        rgb = halftone(rgb, cell=dot)
    return grain_and_paper(rgb, seed, grain, paper)
