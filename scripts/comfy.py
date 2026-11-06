#!/usr/bin/env python3
"""
comfy.py — пакетная генерация «Спешки» через API запущенного ComfyUI.
Ничего ставить не нужно: только стандартная библиотека Python и стандартные ноды ComfyUI.

Сначала запустите ComfyUI и проверьте имена моделей в config.json.

Команды:
  character  — герой клипа (Flux Schnell): лист с тремя видами или одна фигура в полный рост
      python scripts/comfy.py character sheet --variants 6
      python scripts/comfy.py character single --variants 8

  poses      — библиотека поз утверждённого героя (Kontext)
      python scripts/comfy.py poses refs/hero.png

  place      — герой в сценах раскадровки (Kontext): все сцены с героем или выбранные
      python scripts/comfy.py place refs/hero.png
      python scripts/comfy.py place refs/hero.png --only s04 s13 --variants 4

  keyframes  — ключевые кадры сцен из prompts/scenes.json (Flux Schnell)
      python scripts/comfy.py keyframes                 # все сцены, по 4 варианта
      python scripts/comfy.py keyframes --only s03 s13 --variants 8

  boil       — «кипящая линия»: N почти одинаковых кадров из одного (Schnell img2img)
      python scripts/comfy.py boil output/keyframes/s01_00001_.png --scene s01
      python scripts/comfy.py boil кадр.png --scene s06 --count 4 --denoise 0.3

  kontext    — правка кадра через Flux Kontext (готовые пресеты или своя команда)
      python scripts/comfy.py kontext кадр.png --preset restyle
      python scripts/comfy.py kontext кадр.png --preset daycycle    # 4 времени суток
      python scripts/comfy.py kontext кадр.png --preset clean-plate # фон без людей
      python scripts/comfy.py kontext кадр.png --preset cutout      # фигура на белом
      python scripts/comfy.py kontext кадр.png --instruction "make the paper stacks taller. Keep everything else the same."

  export     — сохранить графы в workflows/*.json (формат API) для справки
"""
import argparse
import json
import random
import sys
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
SCENES = json.loads((ROOT / "prompts" / "scenes.json").read_text(encoding="utf-8"))
CHAR = json.loads((ROOT / "prompts" / "character.json").read_text(encoding="utf-8"))

KEEP = " Keep the composition, camera angle, objects, line art and drawing style exactly the same."
PRESETS = {
    "restyle": [
        "Redraw this image as a flat 2D hand-drawn comic illustration with thick uneven black ink outlines, "
        "hard-edged flat shadows, halftone dots and aged paper texture, using only muted olive, rust, dirty teal, "
        "sodium yellow and smoggy grey colors. Keep the composition, camera angle and all objects exactly the same."
    ],
    "daycycle": [
        "Change the time of day to early morning with cold blue light and long soft shadows." + KEEP,
        "Change the time of day to harsh noon sun with short hard shadows." + KEEP,
        "Change the time of day to orange sunset with very long shadows." + KEEP,
        "Change the time of day to night with glowing sodium streetlights and lit windows." + KEEP,
    ],
    "clean-plate": [
        "Remove all people and cars from the scene and fill the space with the street behind them. "
        "Keep everything else, the lighting and the drawing style exactly the same."
    ],
    "cutout": [
        "Remove the background completely and place the figure on a plain flat white background. "
        "Keep the figure, its pose, outlines and colors exactly the same."
    ],
    "boil": [
        "Redraw the same image with slightly different hand-drawn ink lines, as the next frame of a "
        "hand-drawn animation. Keep everything else exactly the same."
    ],
}


# ---------- графы ----------

def text_loaders(g):
    """Добавляет загрузчики модели/CLIP/VAE для Schnell. Возвращает (model, clip, vae)."""
    s = CFG["schnell"]
    if s["mode"] == "checkpoint":
        g["1"] = {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": s["checkpoint"]}}
        model, clip, vae = ["1", 0], ["1", 1], ["1", 2]
    else:
        g["1"] = {"class_type": "UNETLoader", "inputs": {"unet_name": s["unet"], "weight_dtype": s["weight_dtype"]}}
        g["2"] = {"class_type": "DualCLIPLoader",
                  "inputs": {"clip_name1": CFG["clip_l"], "clip_name2": CFG["t5"], "type": "flux"}}
        g["3"] = {"class_type": "VAELoader", "inputs": {"vae_name": CFG["vae"]}}
        model, clip, vae = ["1", 0], ["2", 0], ["3", 0]
    lora = CFG.get("lora", {})
    if lora.get("name"):
        g["4"] = {"class_type": "LoraLoaderModelOnly",
                  "inputs": {"model": model, "lora_name": lora["name"], "strength_model": lora["strength"]}}
        model = ["4", 0]
    return model, clip, vae


def graph_txt2img(prompt, seed, batch, prefix, width=None, height=None):
    g = {}
    model, clip, vae = text_loaders(g)
    g["10"] = {"class_type": "CLIPTextEncode", "inputs": {"clip": clip, "text": prompt}}
    g["11"] = {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["10", 0]}}
    g["12"] = {"class_type": "EmptySD3LatentImage",
               "inputs": {"width": width or CFG["width"], "height": height or CFG["height"], "batch_size": batch}}
    g["13"] = {"class_type": "KSampler", "inputs": {
        "model": model, "positive": ["10", 0], "negative": ["11", 0], "latent_image": ["12", 0],
        "seed": seed, "steps": CFG["schnell"]["steps"], "cfg": 1.0,
        "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}}
    g["14"] = {"class_type": "VAEDecode", "inputs": {"samples": ["13", 0], "vae": vae}}
    g["15"] = {"class_type": "SaveImage", "inputs": {"images": ["14", 0], "filename_prefix": prefix}}
    return g


def graph_boil(image_name, prompt, seed, count, denoise, prefix):
    g = {}
    model, clip, vae = text_loaders(g)
    g["10"] = {"class_type": "CLIPTextEncode", "inputs": {"clip": clip, "text": prompt}}
    g["11"] = {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["10", 0]}}
    g["20"] = {"class_type": "LoadImage", "inputs": {"image": image_name}}
    g["21"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["20", 0], "vae": vae}}
    g["22"] = {"class_type": "RepeatLatentBatch", "inputs": {"samples": ["21", 0], "amount": count}}
    # 8 шагов вместо 4: при низком denoise у Schnell иначе остаётся 1–2 шага
    g["13"] = {"class_type": "KSampler", "inputs": {
        "model": model, "positive": ["10", 0], "negative": ["11", 0], "latent_image": ["22", 0],
        "seed": seed, "steps": 8, "cfg": 1.0,
        "sampler_name": "euler", "scheduler": "simple", "denoise": denoise}}
    g["14"] = {"class_type": "VAEDecode", "inputs": {"samples": ["13", 0], "vae": vae}}
    g["15"] = {"class_type": "SaveImage", "inputs": {"images": ["14", 0], "filename_prefix": prefix}}
    return g


def graph_kontext(image_name, instruction, seed, prefix):
    k = CFG["kontext"]
    g = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": k["unet"], "weight_dtype": k["weight_dtype"]}},
        "2": {"class_type": "DualCLIPLoader",
              "inputs": {"clip_name1": CFG["clip_l"], "clip_name2": CFG["t5"], "type": "flux"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": CFG["vae"]}},
        "20": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "21": {"class_type": "FluxKontextImageScale", "inputs": {"image": ["20", 0]}},
        "22": {"class_type": "VAEEncode", "inputs": {"pixels": ["21", 0], "vae": ["3", 0]}},
        "10": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": instruction}},
        "23": {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["10", 0], "latent": ["22", 0]}},
        "24": {"class_type": "FluxGuidance", "inputs": {"conditioning": ["23", 0], "guidance": k["guidance"]}},
        "11": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["10", 0]}},
        "13": {"class_type": "KSampler", "inputs": {
            "model": ["1", 0], "positive": ["24", 0], "negative": ["11", 0], "latent_image": ["22", 0],
            "seed": seed, "steps": k["steps"], "cfg": 1.0,
            "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}},
        "14": {"class_type": "VAEDecode", "inputs": {"samples": ["13", 0], "vae": ["3", 0]}},
        "15": {"class_type": "SaveImage", "inputs": {"images": ["14", 0], "filename_prefix": prefix}},
    }
    return g


# ---------- API ComfyUI ----------

def api(path, data=None, headers=None):
    url = CFG["server"].rstrip("/") + path
    req = urllib.request.Request(url, data=data, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        sys.exit(f"ComfyUI вернул ошибку {e.code}:\n{e.read().decode('utf-8', 'replace')}")
    except urllib.error.URLError as e:
        sys.exit(f"Не достучаться до ComfyUI по адресу {CFG['server']} — он запущен? ({e.reason})")


def upload(path):
    path = Path(path)
    boundary = uuid.uuid4().hex
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{path.name}\"\r\n"
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode() + path.read_bytes() + (
        f"\r\n--{boundary}\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\ntrue\r\n--{boundary}--\r\n"
    ).encode()
    res = json.loads(api("/upload/image", body, {"Content-Type": f"multipart/form-data; boundary={boundary}"}))
    return (res.get("subfolder") + "/" if res.get("subfolder") else "") + res["name"]


def run(graph, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"prompt": graph, "client_id": uuid.uuid4().hex}).encode()
    pid = json.loads(api("/prompt", payload, {"Content-Type": "application/json"}))["prompt_id"]
    while True:
        hist = json.loads(api(f"/history/{pid}"))
        if pid in hist:
            break
        time.sleep(1.5)
    status = hist[pid].get("status", {})
    if status.get("status_str") == "error":
        sys.exit(f"Ошибка выполнения в ComfyUI:\n{json.dumps(status.get('messages'), ensure_ascii=False)[:2000]}")
    saved = []
    for node in hist[pid]["outputs"].values():
        for im in node.get("images", []):
            q = urllib.parse.urlencode({"filename": im["filename"], "subfolder": im["subfolder"], "type": im["type"]})
            dst = out_dir / im["filename"]
            dst.write_bytes(api(f"/view?{q}"))
            saved.append(dst)
    for s in saved:
        print("  ->", s.relative_to(ROOT) if s.is_relative_to(ROOT) else s)
    return saved


def scene(sid):
    for s in SCENES["scenes"]:
        if s["id"] == sid:
            return s
    sys.exit(f"Нет сцены {sid} в prompts/scenes.json")


def full_prompt(text):
    return text + SCENES["style_suffix"]


# ---------- команды ----------

def cmd_keyframes(a):
    out = ROOT / CFG["output_dir"] / "keyframes"
    todo = [scene(i) for i in a.only] if a.only else SCENES["scenes"]
    for s in todo:
        print(f"{s['id']} {s['title']}")
        seed = a.seed if a.seed is not None else random.randint(0, 2**32 - 1)
        run(graph_txt2img(full_prompt(s["prompt"]), seed, a.variants, f"shpeshka/{s['id']}"), out)


def cmd_boil(a):
    prompt = full_prompt(scene(a.scene)["prompt"]) if a.scene else full_prompt(a.prompt or "")
    if not a.scene and not a.prompt:
        sys.exit("Укажите --scene sNN или --prompt \"...\"")
    name = upload(a.image)
    seed = a.seed if a.seed is not None else random.randint(0, 2**32 - 1)
    stem = Path(a.image).stem
    run(graph_boil(name, prompt, seed, a.count, a.denoise, f"shpeshka/boil_{stem}"),
        ROOT / CFG["output_dir"] / "boil" / stem)


def cmd_kontext(a):
    if a.instruction:
        steps = [a.instruction]
        tag = "custom"
    elif a.preset:
        steps = PRESETS[a.preset]
        tag = a.preset
    else:
        sys.exit("Укажите --preset или --instruction")
    name = upload(a.image)
    stem = Path(a.image).stem
    base_seed = a.seed if a.seed is not None else random.randint(0, 2**32 - 1)
    out = ROOT / CFG["output_dir"] / "kontext" / f"{stem}_{tag}"
    for i, text in enumerate(steps):
        for v in range(a.variants):
            print(f"[{i + 1}/{len(steps)}] {text[:70]}…")
            run(graph_kontext(name, text, base_seed + v, f"shpeshka/{stem}_{tag}_{i:02d}"), out)


def cmd_character(a):
    out = ROOT / CFG["output_dir"] / "character"
    seed = a.seed if a.seed is not None else random.randint(0, 2**32 - 1)
    if a.kind == "sheet":
        # лист с тремя видами: горизонтальный кадр
        g = graph_txt2img(full_prompt(CHAR["sheet"]), seed, a.variants, "shpeshka/hero_sheet",
                          width=CFG["height"], height=CFG["width"])
    else:
        g = graph_txt2img(full_prompt(CHAR["single"]), seed, a.variants, "shpeshka/hero_single")
    run(g, out)


def cmd_poses(a):
    name = upload(a.image)
    seed = a.seed if a.seed is not None else random.randint(0, 2**32 - 1)
    out = ROOT / CFG["output_dir"] / "character" / "poses"
    for i, text in enumerate(CHAR["poses"]):
        print(f"[{i + 1}/{len(CHAR['poses'])}] {text[:70]}…")
        for v in range(a.variants):
            run(graph_kontext(name, text + CHAR["keep"], seed + v, f"shpeshka/pose_{i:02d}"), out)


def cmd_place(a):
    name = upload(a.image)
    todo = [scene(i) for i in a.only] if a.only else [s for s in SCENES["scenes"] if s["hero"]]
    seed = a.seed if a.seed is not None else random.randint(0, 2**32 - 1)
    for s in todo:
        if not s["hero"]:
            print(f"{s['id']}: сцена без героя, пропускаю")
            continue
        print(f"{s['id']} {s['title']}")
        text = s["hero"] + CHAR["keep"]
        for v in range(a.variants):
            run(graph_kontext(name, text, seed + v, f"shpeshka/{s['id']}_hero"),
                ROOT / CFG["output_dir"] / "hero_scenes" / s["id"])


def cmd_export(_):
    d = ROOT / "workflows"
    d.mkdir(exist_ok=True)
    s = SCENES["scenes"][0]
    graphs = {
        "schnell_keyframe_api.json": graph_txt2img(full_prompt(s["prompt"]), 42, 4, "shpeshka/keyframe"),
        "schnell_boil_api.json": graph_boil("input.png", full_prompt(s["prompt"]), 42, 4, 0.3, "shpeshka/boil"),
        "kontext_edit_api.json": graph_kontext("input.png", PRESETS["restyle"][0], 42, "shpeshka/kontext"),
    }
    for fn, g in graphs.items():
        (d / fn).write_text(json.dumps(g, indent=2, ensure_ascii=False), encoding="utf-8")
        print("  ->", d / fn)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("keyframes")
    p.add_argument("--only", nargs="*", help="id сцен, например s01 s03")
    p.add_argument("--variants", type=int, default=4)
    p.add_argument("--seed", type=int)
    p.set_defaults(fn=cmd_keyframes)

    p = sub.add_parser("boil")
    p.add_argument("image")
    p.add_argument("--scene")
    p.add_argument("--prompt")
    p.add_argument("--count", type=int, default=4)
    p.add_argument("--denoise", type=float, default=0.3)
    p.add_argument("--seed", type=int)
    p.set_defaults(fn=cmd_boil)

    p = sub.add_parser("kontext")
    p.add_argument("image")
    p.add_argument("--preset", choices=list(PRESETS))
    p.add_argument("--instruction")
    p.add_argument("--variants", type=int, default=1, help="сколько вариантов на каждую команду")
    p.add_argument("--seed", type=int)
    p.set_defaults(fn=cmd_kontext)

    p = sub.add_parser("character")
    p.add_argument("kind", choices=["sheet", "single"])
    p.add_argument("--variants", type=int, default=6)
    p.add_argument("--seed", type=int)
    p.set_defaults(fn=cmd_character)

    p = sub.add_parser("poses")
    p.add_argument("image", help="утверждённый герой в полный рост (hero_single)")
    p.add_argument("--variants", type=int, default=2)
    p.add_argument("--seed", type=int)
    p.set_defaults(fn=cmd_poses)

    p = sub.add_parser("place")
    p.add_argument("image", help="утверждённый герой в полный рост (hero_single)")
    p.add_argument("--only", nargs="*", help="id сцен; по умолчанию все сцены с героем")
    p.add_argument("--variants", type=int, default=3)
    p.add_argument("--seed", type=int)
    p.set_defaults(fn=cmd_place)

    p = sub.add_parser("export")
    p.set_defaults(fn=cmd_export)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
