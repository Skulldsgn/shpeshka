#!/usr/bin/env python3
"""Собирает графы ComfyUI в обычном (UI) формате, которые можно перетащить в окно ComfyUI.
   python scripts/make_ui_workflows.py   ->  workflows/*.json
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))


class WF:
    def __init__(self):
        self.nodes, self.links = [], []

    def node(self, type_, pos, size, inputs=(), outputs=(), widgets=(), title=None, color=None):
        n = {
            "id": len(self.nodes) + 1, "type": type_, "pos": list(pos), "size": list(size),
            "flags": {}, "order": len(self.nodes), "mode": 0,
            "inputs": [{"name": nm, "type": t, "link": None} for nm, t in inputs],
            "outputs": [{"name": nm, "type": t, "links": [], "slot_index": i} for i, (nm, t) in enumerate(outputs)],
            "properties": {"Node name for S&R": type_},
            "widgets_values": list(widgets),
        }
        if title:
            n["title"] = title
        if color:
            n["color"], n["bgcolor"] = color
        self.nodes.append(n)
        return n

    def link(self, a, a_slot, b, b_input):
        lid = len(self.links) + 1
        t = a["outputs"][a_slot]["type"]
        a["outputs"][a_slot]["links"].append(lid)
        slot = next(i for i, x in enumerate(b["inputs"]) if x["name"] == b_input)
        b["inputs"][slot]["link"] = lid
        self.links.append([lid, a["id"], a_slot, b["id"], slot, t])

    def dump(self, path):
        data = {
            "last_node_id": len(self.nodes), "last_link_id": len(self.links),
            "nodes": self.nodes, "links": self.links, "groups": [],
            "config": {}, "extra": {"ds": {"scale": 0.8, "offset": [40, 40]}}, "version": 0.4,
        }
        Path(path).write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
        print("->", Path(path).relative_to(ROOT))


SPESH = ("#4a3a1c", "#2e2412")  # цвет наших нод
NOTE = ("#432", "#653")


def loaders(w, unet_name, title):
    unet = w.node("UNETLoader", (0, 0), (360, 90), outputs=[("MODEL", "MODEL")],
                  widgets=[unet_name, "fp8_e4m3fn" if "kontext" not in unet_name else "default"], title=title)
    clip = w.node("DualCLIPLoader", (0, 140), (360, 130), outputs=[("CLIP", "CLIP")],
                  widgets=[CFG.get("clip_l") or "clip_l.safetensors",
                           CFG.get("t5") or "t5xxl_fp8_e4m3fn_scaled.safetensors", "flux", "default"],
                  title="Текстовые энкодеры")
    vae = w.node("VAELoader", (0, 320), (360, 60), outputs=[("VAE", "VAE")],
                 widgets=[CFG.get("vae") or "ae.safetensors"], title="VAE")
    return unet, clip, vae


def schnell_frame():
    w = WF()
    unet, clip, vae = loaders(w, CFG["schnell"].get("unet") or "flux1-schnell.safetensors", "Модель: Flux SCHNELL")
    prompt = w.node("ShpeshkaScenePrompt", (420, 0), (420, 230), inputs=[("clip", "CLIP")],
                    outputs=[("conditioning", "CONDITIONING"), ("text", "STRING")],
                    widgets=["s13 Остановился", "сцена (Schnell)", True, ""], color=SPESH)
    zero = w.node("ConditioningZeroOut", (420, 290), (300, 30), inputs=[("conditioning", "CONDITIONING")],
                  outputs=[("CONDITIONING", "CONDITIONING")])
    size = w.node("EmptySD3LatentImage", (420, 370), (300, 110), outputs=[("LATENT", "LATENT")],
                  widgets=[768, 1344, 4], title="Размер кадра 9:16 (batch = сколько вариантов)")
    ks = w.node("KSampler", (880, 0), (320, 270),
                inputs=[("model", "MODEL"), ("positive", "CONDITIONING"), ("negative", "CONDITIONING"),
                        ("latent_image", "LATENT")], outputs=[("LATENT", "LATENT")],
                widgets=[0, "randomize", 4, 1.0, "euler", "simple", 1.0])
    dec = w.node("VAEDecode", (1240, 0), (200, 50), inputs=[("samples", "LATENT"), ("vae", "VAE")],
                 outputs=[("IMAGE", "IMAGE")])
    raw = w.node("PreviewImage", (1240, 100), (300, 420), inputs=[("images", "IMAGE")], title="До стиля")
    style = w.node("ShpeshkaStyle", (1580, 0), (320, 230), inputs=[("images", "IMAGE")],
                   outputs=[("IMAGE", "IMAGE")], widgets=[0.7, 8, 2, 0.035, 0.04, 0], color=SPESH)
    save = w.node("SaveImage", (1580, 280), (320, 420), inputs=[("images", "IMAGE")],
                  widgets=["shpeshka/kadr"], title="После стиля (сохраняется)")
    w.node("Note", (0, 430), (380, 230), widgets=[
        "СПЕШКА — новый кадр (Flux Schnell)\n\n"
        "1. В «Спешка: промпт сцены» выберите сцену и режим.\n"
        "   Стилевой хвост дописывается сам.\n"
        "2. Модель: должен быть SCHNELL (не Kontext!).\n"
        "   4 шага, CFG 1 — только для Schnell.\n"
        "3. batch_size = сколько вариантов за раз.\n"
        "4. Слева превью «до стиля», справа «после»\n"
        "   сохраняется в output/shpeshka.\n\n"
        "Красная нода = нет такого файла модели:\n"
        "выберите свой в выпадающем списке."], title="Подсказка", color=NOTE)
    w.link(unet, 0, ks, "model")
    w.link(clip, 0, prompt, "clip")
    w.link(prompt, 0, ks, "positive")
    w.link(prompt, 0, zero, "conditioning")
    w.link(zero, 0, ks, "negative")
    w.link(size, 0, ks, "latent_image")
    w.link(ks, 0, dec, "samples")
    w.link(vae, 0, dec, "vae")
    w.link(dec, 0, raw, "images")
    w.link(dec, 0, style, "images")
    w.link(style, 0, save, "images")
    w.dump(ROOT / "workflows" / "1_kadr_schnell.json")


def kontext_edit():
    w = WF()
    unet, clip, vae = loaders(w, CFG["kontext"].get("unet") or "flux1-dev-kontext_fp8_scaled.safetensors",
                              "Модель: Flux KONTEXT")
    img = w.node("LoadImage", (0, 430), (360, 380), outputs=[("IMAGE", "IMAGE"), ("MASK", "MASK")],
                 widgets=["example.png", "image"], title="Исходный кадр / герой")
    scale = w.node("FluxKontextImageScale", (420, 430), (260, 30), inputs=[("image", "IMAGE")],
                   outputs=[("IMAGE", "IMAGE")])
    enc = w.node("VAEEncode", (420, 500), (200, 50), inputs=[("pixels", "IMAGE"), ("vae", "VAE")],
                 outputs=[("LATENT", "LATENT")])
    prompt = w.node("ShpeshkaScenePrompt", (420, 0), (420, 230), inputs=[("clip", "CLIP")],
                    outputs=[("conditioning", "CONDITIONING"), ("text", "STRING")],
                    widgets=["s13 Остановился", "сцена с героем (Kontext)", True, ""], color=SPESH)
    ref = w.node("ReferenceLatent", (420, 280), (240, 50),
                 inputs=[("conditioning", "CONDITIONING"), ("latent", "LATENT")],
                 outputs=[("CONDITIONING", "CONDITIONING")])
    guid = w.node("FluxGuidance", (680, 280), (220, 60), inputs=[("conditioning", "CONDITIONING")],
                  outputs=[("CONDITIONING", "CONDITIONING")], widgets=[2.5])
    zero = w.node("ConditioningZeroOut", (680, 370), (220, 30), inputs=[("conditioning", "CONDITIONING")],
                  outputs=[("CONDITIONING", "CONDITIONING")])
    ks = w.node("KSampler", (940, 0), (320, 270),
                inputs=[("model", "MODEL"), ("positive", "CONDITIONING"), ("negative", "CONDITIONING"),
                        ("latent_image", "LATENT")], outputs=[("LATENT", "LATENT")],
                widgets=[0, "randomize", 20, 1.0, "euler", "simple", 1.0])
    dec = w.node("VAEDecode", (1300, 0), (200, 50), inputs=[("samples", "LATENT"), ("vae", "VAE")],
                 outputs=[("IMAGE", "IMAGE")])
    raw = w.node("PreviewImage", (1300, 100), (300, 420), inputs=[("images", "IMAGE")], title="До стиля")
    style = w.node("ShpeshkaStyle", (1640, 0), (320, 230), inputs=[("images", "IMAGE")],
                   outputs=[("IMAGE", "IMAGE")], widgets=[0.7, 8, 2, 0.035, 0.04, 0], color=SPESH)
    save = w.node("SaveImage", (1640, 280), (320, 420), inputs=[("images", "IMAGE")],
                  widgets=["shpeshka/kontext"], title="После стиля (сохраняется)")
    w.node("Note", (0, 860), (380, 220), widgets=[
        "СПЕШКА — правка кадра / герой в сцене (Flux Kontext)\n\n"
        "1. Загрузите кадр. Для сцен с героем — refs/hero.png.\n"
        "2. Режим «сцена с героем (Kontext)» — герой\n"
        "   переносится в выбранную сцену.\n"
        "   Свою команду пишите в поле extra.\n"
        "3. Модель: KONTEXT, 20 шагов, FluxGuidance 2.5.\n"
        "4. Своя правка любого кадра: режим «только своя\n"
        "   команда», add_style выключить, текст в extra."], title="Подсказка", color=NOTE)
    w.link(unet, 0, ks, "model")
    w.link(clip, 0, prompt, "clip")
    w.link(img, 0, scale, "image")
    w.link(scale, 0, enc, "pixels")
    w.link(vae, 0, enc, "vae")
    w.link(prompt, 0, ref, "conditioning")
    w.link(enc, 0, ref, "latent")
    w.link(ref, 0, guid, "conditioning")
    w.link(guid, 0, ks, "positive")
    w.link(prompt, 0, zero, "conditioning")
    w.link(zero, 0, ks, "negative")
    w.link(enc, 0, ks, "latent_image")
    w.link(ks, 0, dec, "samples")
    w.link(vae, 0, dec, "vae")
    w.link(dec, 0, raw, "images")
    w.link(dec, 0, style, "images")
    w.link(style, 0, save, "images")
    w.dump(ROOT / "workflows" / "2_kontext_pravka.json")


if __name__ == "__main__":
    schnell_frame()
    kontext_edit()
