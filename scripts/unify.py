#!/usr/bin/env python3
"""
unify.py — приводит любые кадры к единому стилю «Спешки».

Что делает с каждым кадром:
  1. Мягко притягивает цвета к палитре из 8 цветов (docs/style-bible.md).
  2. Сдвигает цвет относительно контура (эффект несовмещённой печати).
  3. Полутоновые точки в средних тонах и тенях.
  4. Бумажная фактура (одинаковая на всех кадрах) + зерно (своё на каждом кадре).

Примеры:
  python scripts/unify.py frames_in/ frames_out/
  python scripts/unify.py frame.png out/ --strength 0.8 --dot 7
  python scripts/unify.py --lut post/shpeshka_palette.cube      # LUT для DaVinci
  python scripts/unify.py --swatch docs/palette.png             # картинка палитры

Нужны: pip install pillow numpy
"""
import argparse
import sys
from pathlib import Path

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
EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


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


# ---------- конвейер ----------

def process(img, args, frame_seed):
    rgb = np.asarray(img.convert("RGB"), np.float32) / 255.0
    rgb = palette_map(rgb, args.strength)
    if args.offset:
        rgb = misregister(rgb, args.offset, max(1, args.offset // 2))
    if args.dot > 0:
        rgb = halftone(rgb, cell=args.dot)
    rgb = grain_and_paper(rgb, frame_seed, args.grain, args.paper)
    return Image.fromarray((rgb * 255 + 0.5).astype(np.uint8))


def write_lut(path, size=33, strength=0.7):
    r = np.linspace(0, 1, size, dtype=np.float32)
    # в .cube красный меняется быстрее всех
    b, g, rr = np.meshgrid(r, r, r, indexing="ij")
    grid = np.stack([rr, g, b], -1).reshape(-1, 3)
    out = palette_map(grid, strength)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write('TITLE "shpeshka palette"\n')
        f.write(f"LUT_3D_SIZE {size}\n")
        for row in out:
            f.write(f"{row[0]:.6f} {row[1]:.6f} {row[2]:.6f}\n")
    print(f"LUT: {path}")


def write_swatch(path):
    sw, sh = 160, 220
    img = np.zeros((sh, sw * len(PALETTE), 3), np.uint8)
    for i, c in enumerate(PALETTE):
        img[:, i * sw:(i + 1) * sw] = (c * 255).astype(np.uint8)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(img).save(path)
    print(f"Палитра: {path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", nargs="?", help="файл или папка с кадрами")
    ap.add_argument("output", nargs="?", help="папка для результата")
    ap.add_argument("--strength", type=float, default=0.7, help="сила притяжения к палитре 0..1 (0.7)")
    ap.add_argument("--dot", type=int, default=8, help="размер полутоновой ячейки в px, 0 = выкл (8)")
    ap.add_argument("--offset", type=int, default=2, help="сдвиг цвета от контура в px, 0 = выкл (2)")
    ap.add_argument("--grain", type=float, default=0.035, help="сила зерна (0.035)")
    ap.add_argument("--paper", type=float, default=0.04, help="сила бумажной фактуры (0.04)")
    ap.add_argument("--lut", help="записать .cube LUT (только цвет) и выйти")
    ap.add_argument("--swatch", help="записать картинку палитры и выйти")
    args = ap.parse_args()

    if args.lut:
        write_lut(args.lut, strength=args.strength)
    if args.swatch:
        write_swatch(args.swatch)
    if args.lut or args.swatch:
        return
    if not args.input or not args.output:
        ap.error("нужны input и output (или --lut / --swatch)")

    src = Path(args.input)
    files = sorted(p for p in src.iterdir() if p.suffix.lower() in EXTS) if src.is_dir() else [src]
    if not files:
        sys.exit("Нет кадров во входной папке")
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    for i, f in enumerate(files):
        res = process(Image.open(f), args, frame_seed=i)
        res.save(out / (f.stem + ".png"))
        print(f"[{i + 1}/{len(files)}] {f.name}")


if __name__ == "__main__":
    main()
