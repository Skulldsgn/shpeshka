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

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "comfyui_node"))
from shpeshka_style import PALETTE, palette_map, stylize  # noqa: E402  общее ядро с нодой ComfyUI

EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


# ---------- конвейер ----------

def process(img, args, frame_seed):
    rgb = np.asarray(img.convert("RGB"), np.float32) / 255.0
    rgb = stylize(rgb, args.strength, args.dot, args.offset, args.grain, args.paper, frame_seed)
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
