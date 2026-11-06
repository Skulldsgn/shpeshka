#!/usr/bin/env python3
"""
detect_models.py — находит модели Flux в папке ComfyUI и прописывает их в config.json.

  python scripts/detect_models.py "D:\\AI\\ComfyUI_windows_portable"
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXT = (".safetensors", ".gguf", ".sft", ".ckpt")


def find_models_dir(base):
    base = Path(base)
    for cand in (base / "ComfyUI" / "models", base / "models"):
        if cand.is_dir():
            return cand
    sys.exit(f"Не нашёл папку models внутри {base}")


def scan(models, folders):
    out = []
    for f in folders:
        d = models / f
        if not d.is_dir():
            continue
        for p in d.rglob("*"):
            if p.suffix.lower() in EXT:
                # ComfyUI показывает файлы относительно своей папки, с подпапками через системный разделитель
                out.append((f, os.path.relpath(p, d), p.stat().st_size))
    return out


def pick(items, *must, prefer=()):
    hits = [i for i in items if all(m in i[1].lower() for m in must)]
    if not hits:
        return None
    hits.sort(key=lambda i: (-sum(p in i[1].lower() for p in prefer), i[2]))
    return hits[0]


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    models = find_models_dir(sys.argv[1])
    unets = scan(models, ["diffusion_models", "unet"])
    ckpts = scan(models, ["checkpoints"])
    texts = scan(models, ["text_encoders", "clip"])
    vaes = scan(models, ["vae"])

    cfg_path = ROOT / "config.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    report, problems = [], []

    s_unet = pick(unets, "schnell", prefer=("fp8",))
    s_ckpt = pick(ckpts, "schnell", prefer=("fp8",))
    if s_unet:
        cfg["schnell"]["mode"] = "unet"
        cfg["schnell"]["unet"] = s_unet[1]
        report.append(f"Schnell (unet):      {s_unet[1]}")
    elif s_ckpt:
        cfg["schnell"]["mode"] = "checkpoint"
        report.append(f"Schnell (чекпоинт):  {s_ckpt[1]}")
    else:
        problems.append("Не нашёл Flux Schnell (файл с 'schnell' в имени).")
    if s_ckpt:
        cfg["schnell"]["checkpoint"] = s_ckpt[1]
    else:
        cfg["schnell"]["checkpoint"] = ""

    k = pick(unets, "kontext", prefer=("fp8",)) or pick(ckpts, "kontext", prefer=("fp8",))
    if k:
        if k[0] == "checkpoints":
            problems.append(f"Kontext лежит в checkpoints ({k[1]}): перенесите его в models\\diffusion_models.")
        cfg["kontext"]["unet"] = k[1]
        cfg["kontext"]["weight_dtype"] = "default"
        report.append(f"Kontext:             {k[1]}")
    else:
        problems.append("Не нашёл Flux Kontext (файл с 'kontext' в имени).")

    clip_l = pick(texts, "clip_l")
    t5 = pick(texts, "t5", prefer=("fp8", "scaled"))
    if clip_l and t5:
        cfg["clip_l"], cfg["t5"] = clip_l[1], t5[1]
        report.append(f"Текстовые энкодеры:  {clip_l[1]} + {t5[1]}")
    else:
        cfg["clip_l"] = cfg["t5"] = ""
        report.append("Текстовые энкодеры:  берутся из чекпоинта Schnell")

    vae = pick(vaes, "ae") or pick(vaes, "flux")
    if vae:
        cfg["vae"] = vae[1]
        report.append(f"VAE:                 {vae[1]}")
    else:
        cfg["vae"] = ""
        report.append("VAE:                 берётся из чекпоинта Schnell")

    if (not cfg["vae"] or not cfg["t5"]) and not cfg["schnell"]["checkpoint"]:
        problems.append("Нет ни отдельных VAE/энкодеров, ни чекпоинта Schnell «всё в одном». "
                        "Нужен ae.safetensors в models\\vae (см. README).")

    if any(x and x.lower().endswith(".gguf") for x in (cfg["schnell"].get("unet"), cfg["kontext"]["unet"], cfg["t5"])):
        report.append("Есть .gguf-модели: в ComfyUI должен стоять пакет ComfyUI-GGUF.")

    cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("\n".join(report))
    if problems:
        print("\nВНИМАНИЕ:")
        print("\n".join(" - " + p for p in problems))
    print(f"\nЗаписано в {cfg_path}")


if __name__ == "__main__":
    main()
