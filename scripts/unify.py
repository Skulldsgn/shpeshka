#!/usr/bin/env python3
"""
unify.py — то же, что нода «Спешка: стиль», но для папки кадров (например, после монтажа или из Wan).

Каждый эффект выключается нулём, палитра — пустой строкой (--palette "").

Примеры:
  python scripts/unify.py кадры/ результат/
  python scripts/unify.py кадр.png результат/ --palette "#111111, #EEE4D0, #C0392B" --dot 0
  python scripts/unify.py --lut post/palette.cube --palette "#111111, #EEE4D0"   # LUT для DaVinci
  python scripts/unify.py --swatch palette.png --palette "..."                    # картинка палитры

Нужны: pillow, numpy (есть во встроенном Python ComfyUI).
"""
import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "comfyui_node"))
from shpeshka_style import DEFAULT_PALETTE, palette_map, parse_palette, stylize  # noqa: E402

EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


def write_lut(path, palette_text, strength, size=33):
    pal = parse_palette(palette_text)
    if pal is None:
        sys.exit("Для LUT нужна палитра (--palette)")
    r = np.linspace(0, 1, size, dtype=np.float32)
    b, g, rr = np.meshgrid(r, r, r, indexing="ij")  # в .cube красный меняется быстрее всех
    out = palette_map(np.stack([rr, g, b], -1).reshape(-1, 3), pal, strength)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write(f'TITLE "palette"\nLUT_3D_SIZE {size}\n')
        for row in out:
            f.write(f"{row[0]:.6f} {row[1]:.6f} {row[2]:.6f}\n")
    print(f"LUT: {path}")


def write_swatch(path, palette_text):
    pal = parse_palette(palette_text)
    if pal is None:
        sys.exit("Палитра пустая")
    img = np.repeat(np.repeat((pal * 255).astype(np.uint8)[None], 160, 1), 220, 0)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(img).save(path)
    print(f"Палитра: {path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", nargs="?", help="файл или папка с кадрами")
    ap.add_argument("output", nargs="?", help="папка для результата")
    ap.add_argument("--palette", default=DEFAULT_PALETTE, help="HEX-цвета через запятую, \"\" = без палитры")
    ap.add_argument("--strength", type=float, default=0.7, help="сила палитры 0..1, 0 = выкл")
    ap.add_argument("--dot", type=int, default=8, help="полутоновая ячейка в px, 0 = выкл")
    ap.add_argument("--offset", type=int, default=2, help="сдвиг цвета от контура в px, 0 = выкл")
    ap.add_argument("--grain", type=float, default=0.035, help="зерно, 0 = выкл")
    ap.add_argument("--paper", type=float, default=0.04, help="бумага, 0 = выкл")
    ap.add_argument("--lut", help="записать .cube LUT палитры и выйти")
    ap.add_argument("--swatch", help="записать картинку палитры и выйти")
    a = ap.parse_args()

    if a.lut:
        write_lut(a.lut, a.palette, a.strength)
    if a.swatch:
        write_swatch(a.swatch, a.palette)
    if a.lut or a.swatch:
        return
    if not a.input or not a.output:
        ap.error("нужны input и output (или --lut / --swatch)")

    src = Path(a.input)
    files = sorted(p for p in src.iterdir() if p.suffix.lower() in EXTS) if src.is_dir() else [src]
    if not files:
        sys.exit("Нет кадров во входной папке")
    out = Path(a.output)
    out.mkdir(parents=True, exist_ok=True)
    for i, f in enumerate(files):
        rgb = np.asarray(Image.open(f).convert("RGB"), np.float32) / 255.0
        rgb = stylize(rgb, a.palette, a.strength, a.dot, a.offset, a.grain, a.paper, i)
        Image.fromarray((rgb * 255 + 0.5).astype(np.uint8)).save(out / (f.stem + ".png"))
        print(f"[{i + 1}/{len(files)}] {f.name}")


if __name__ == "__main__":
    main()
