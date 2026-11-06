#!/usr/bin/env python3
"""Собирает два графа ComfyUI (обычный формат, перетаскиваются в окно ComfyUI):
   workflows/kadr_schnell.json   — новый кадр по вашему промпту (Flux Schnell)
   workflows/pravka_kontext.json — правка / вариация готового кадра (Flux Kontext)
Промпты в графах пустые. Имена моделей — типовые; если у вас другие, выберите свои в нодах.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLIP_L, T5, VAE = "clip_l.safetensors", "t5xxl_fp8_e4m3fn_scaled.safetensors", "ae.safetensors"
SCHNELL, KONTEXT = "flux1-schnell.safetensors", "flux1-dev-kontext_fp8_scaled.safetensors"
STYLE_DEFAULTS = ["#111111, #E9DFC8", 0.9, 0.35, 21, 0.035, 0.02, 0, 0, 0]
OURS, NOTE = ("#4a3a1c", "#2e2412"), ("#432", "#653")


class WF:
    def __init__(self):
        self.nodes, self.links = [], []

    def node(self, type_, pos, size, inputs=(), outputs=(), widgets=(), title=None, color=None):
        n = {"id": len(self.nodes) + 1, "type": type_, "pos": list(pos), "size": list(size),
             "flags": {}, "order": len(self.nodes), "mode": 0,
             "inputs": [{"name": a, "type": t, "link": None} for a, t in inputs],
             "outputs": [{"name": a, "type": t, "links": [], "slot_index": i} for i, (a, t) in enumerate(outputs)],
             "properties": {"Node name for S&R": type_}, "widgets_values": list(widgets)}
        if title:
            n["title"] = title
        if color:
            n["color"], n["bgcolor"] = color
        self.nodes.append(n)
        return n

    def link(self, a, a_slot, b, b_input):
        lid = len(self.links) + 1
        a["outputs"][a_slot]["links"].append(lid)
        slot = next(i for i, x in enumerate(b["inputs"]) if x["name"] == b_input)
        b["inputs"][slot]["link"] = lid
        self.links.append([lid, a["id"], a_slot, b["id"], slot, a["outputs"][a_slot]["type"]])

    def dump(self, name):
        p = ROOT / "workflows" / name
        p.parent.mkdir(exist_ok=True)
        p.write_text(json.dumps({
            "last_node_id": len(self.nodes), "last_link_id": len(self.links), "nodes": self.nodes,
            "links": self.links, "groups": [], "config": {},
            "extra": {"ds": {"scale": 0.75, "offset": [40, 40]}}, "version": 0.4,
        }, indent=1, ensure_ascii=False), encoding="utf-8")
        print("->", p.relative_to(ROOT))


def common(w, unet_name, dtype, title):
    unet = w.node("UNETLoader", (0, 0), (380, 90), outputs=[("MODEL", "MODEL")], widgets=[unet_name, dtype], title=title)
    clip = w.node("DualCLIPLoader", (0, 140), (380, 130), outputs=[("CLIP", "CLIP")],
                  widgets=[CLIP_L, T5, "flux", "default"], title="Текстовые энкодеры")
    vae = w.node("VAELoader", (0, 320), (380, 60), outputs=[("VAE", "VAE")], widgets=[VAE], title="VAE")
    return unet, clip, vae


def tail(w, x, ks, vae, prefix):
    dec = w.node("VAEDecode", (x, 0), (200, 50), inputs=[("samples", "LATENT"), ("vae", "VAE")],
                 outputs=[("IMAGE", "IMAGE")])
    raw = w.node("PreviewImage", (x, 100), (320, 520), inputs=[("images", "IMAGE")], title="До стиля (не сохраняется)")
    style = w.node("ShpeshkaStyle", (x + 360, 0), (340, 330), inputs=[("images", "IMAGE")],
                   outputs=[("IMAGE", "IMAGE")], widgets=STYLE_DEFAULTS, color=OURS)
    save = w.node("SaveImage", (x + 360, 380), (340, 520), inputs=[("images", "IMAGE")],
                  widgets=[prefix], title="После стиля (сохраняется)")
    w.link(ks, 0, dec, "samples")
    w.link(vae, 0, dec, "vae")
    w.link(dec, 0, raw, "images")
    w.link(dec, 0, style, "images")
    w.link(style, 0, save, "images")


def kadr_schnell():
    w = WF()
    unet, clip, vae = common(w, SCHNELL, "fp8_e4m3fn", "Модель: Flux Schnell")
    prompt = w.node("CLIPTextEncode", (440, 0), (440, 260), inputs=[("clip", "CLIP")],
                    outputs=[("CONDITIONING", "CONDITIONING")], widgets=[""], title="Ваш промпт")
    zero = w.node("ConditioningZeroOut", (440, 310), (300, 30), inputs=[("conditioning", "CONDITIONING")],
                  outputs=[("CONDITIONING", "CONDITIONING")])
    size = w.node("EmptySD3LatentImage", (440, 390), (320, 110), outputs=[("LATENT", "LATENT")],
                  widgets=[768, 1344, 4], title="Размер 9:16, batch = вариантов за раз")
    ks = w.node("KSampler", (920, 0), (320, 270),
                inputs=[("model", "MODEL"), ("positive", "CONDITIONING"), ("negative", "CONDITIONING"),
                        ("latent_image", "LATENT")], outputs=[("LATENT", "LATENT")],
                widgets=[0, "randomize", 4, 1.0, "euler", "simple", 1.0])
    w.node("Note", (0, 430), (380, 200), title="Подсказка", color=NOTE, widgets=[
        "Новый кадр, Flux Schnell.\n\n"
        "• Модель должна быть Schnell: 4 шага, CFG 1.\n"
        "• Красная нода = у вас другое имя файла,\n"
        "  выберите свой в списке.\n"
        "• Слева превью «до стиля», справа «после» —\n"
        "  сохраняется только «после».\n"
        "• Нода «Спешка: стиль» по умолчанию под силуэты;\n"
        "  всё выключается нулями."])
    w.link(unet, 0, ks, "model")
    w.link(clip, 0, prompt, "clip")
    w.link(prompt, 0, ks, "positive")
    w.link(prompt, 0, zero, "conditioning")
    w.link(zero, 0, ks, "negative")
    w.link(size, 0, ks, "latent_image")
    tail(w, 1280, ks, vae, "shpeshka/kadr")
    w.dump("kadr_schnell.json")


def pravka_kontext():
    w = WF()
    unet, clip, vae = common(w, KONTEXT, "default", "Модель: Flux Kontext")
    img = w.node("LoadImage", (0, 430), (380, 420), outputs=[("IMAGE", "IMAGE"), ("MASK", "MASK")],
                 widgets=["example.png", "image"], title="Исходный кадр")
    scale = w.node("FluxKontextImageScale", (440, 430), (260, 30), inputs=[("image", "IMAGE")],
                   outputs=[("IMAGE", "IMAGE")])
    enc = w.node("VAEEncode", (440, 500), (200, 50), inputs=[("pixels", "IMAGE"), ("vae", "VAE")],
                 outputs=[("LATENT", "LATENT")])
    prompt = w.node("CLIPTextEncode", (440, 0), (440, 260), inputs=[("clip", "CLIP")],
                    outputs=[("CONDITIONING", "CONDITIONING")], widgets=[""], title="Ваша команда (на английском)")
    ref = w.node("ReferenceLatent", (440, 310), (240, 50),
                 inputs=[("conditioning", "CONDITIONING"), ("latent", "LATENT")],
                 outputs=[("CONDITIONING", "CONDITIONING")])
    guid = w.node("FluxGuidance", (700, 310), (200, 60), inputs=[("conditioning", "CONDITIONING")],
                  outputs=[("CONDITIONING", "CONDITIONING")], widgets=[2.5])
    zero = w.node("ConditioningZeroOut", (700, 400), (200, 30), inputs=[("conditioning", "CONDITIONING")],
                  outputs=[("CONDITIONING", "CONDITIONING")])
    ks = w.node("KSampler", (940, 0), (320, 270),
                inputs=[("model", "MODEL"), ("positive", "CONDITIONING"), ("negative", "CONDITIONING"),
                        ("latent_image", "LATENT")], outputs=[("LATENT", "LATENT")],
                widgets=[0, "randomize", 20, 1.0, "euler", "simple", 1.0])
    w.node("Note", (0, 900), (380, 200), title="Подсказка", color=NOTE, widgets=[
        "Правка / вариация готового кадра, Flux Kontext.\n\n"
        "• Загрузите кадр, напишите команду: что изменить\n"
        "  и что сохранить («...keep everything else the same»).\n"
        "• Kontext: 20 шагов, CFG 1, FluxGuidance 2.5.\n"
        "• Для «кипящей линии» гоняйте одну команду\n"
        "  с разными seed."])
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
    tail(w, 1300, ks, vae, "shpeshka/pravka")
    w.dump("pravka_kontext.json")


if __name__ == "__main__":
    kadr_schnell()
    pravka_kontext()
