"""
Ноды ComfyUI для клипа «Спешка». Категория в меню: Спешка.

  Спешка: промпт сцены — выбор сцены/героя из раскадровки, стилевой хвост добавляется сам.
  Спешка: стиль       — приводит картинки к единому стилю (палитра, полутона, бумага, зерно).
"""
import json
from pathlib import Path

import numpy as np
import torch

from .shpeshka_style import stylize

HERE = Path(__file__).resolve().parent


def _prompts_dir():
    """Берём промпты из папки проекта (путь пишет установщик), иначе — из копии рядом с нодой."""
    link = HERE / "project_path.txt"
    if link.exists():
        p = Path(link.read_text(encoding="utf-8").strip()) / "prompts"
        if p.is_dir():
            return p
    return HERE / "prompts"


def _load():
    d = _prompts_dir()
    scenes = json.loads((d / "scenes.json").read_text(encoding="utf-8"))
    char = json.loads((d / "character.json").read_text(encoding="utf-8"))
    return scenes, char


MODES = ["сцена (Schnell)", "сцена с героем (Kontext)", "герой: лист (Schnell)", "герой: в рост (Schnell)",
         "только своя команда (extra)"]


class ShpeshkaScenePrompt:
    @classmethod
    def INPUT_TYPES(cls):
        scenes, _ = _load()
        names = [f"{s['id']} {s['title']}" for s in scenes["scenes"]]
        return {
            "required": {
                "clip": ("CLIP",),
                "scene": (names,),
                "mode": (MODES,),
                "add_style": ("BOOLEAN", {"default": True, "label_on": "стиль клипа", "label_off": "без стиля"}),
            },
            "optional": {
                "extra": ("STRING", {"multiline": True, "default": "",
                                     "placeholder": "дописать к промпту (необязательно)"}),
            },
        }

    RETURN_TYPES = ("CONDITIONING", "STRING")
    RETURN_NAMES = ("conditioning", "text")
    FUNCTION = "build"
    CATEGORY = "Спешка"

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        # перечитываем JSON при каждом запуске, чтобы правки промптов подхватывались без перезапуска
        d = _prompts_dir()
        return sum((d / f).stat().st_mtime for f in ("scenes.json", "character.json"))

    def build(self, clip, scene, mode, add_style, extra=""):
        scenes, char = _load()
        sid = scene.split(" ", 1)[0]
        sc = next(s for s in scenes["scenes"] if s["id"] == sid)
        suffix = scenes["style_suffix"] if add_style else ""

        if mode == MODES[4]:
            if not extra.strip():
                raise ValueError("Режим «только своя команда»: напишите текст в поле extra.")
            text = extra.strip() + (suffix if add_style else "")
            import nodes
            return (nodes.CLIPTextEncode().encode(clip, text)[0], text)
        if mode == MODES[1]:
            if not sc.get("hero"):
                raise ValueError(f"В сцене {sid} нет героя — выберите режим «сцена (Schnell)».")
            text = sc["hero"] + char["keep"]  # Kontext: инструкция, стилевой хвост не нужен
        elif mode == MODES[2]:
            text = char["sheet"] + suffix
        elif mode == MODES[3]:
            text = char["single"] + suffix
        else:
            text = sc["prompt"] + suffix
        if extra.strip():
            text = text.rstrip(". ") + ". " + extra.strip()

        import nodes  # стандартная нода ComfyUI
        cond = nodes.CLIPTextEncode().encode(clip, text)[0]
        return (cond, text)


class ShpeshkaStyle:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "strength": ("FLOAT", {"default": 0.7, "min": 0.0, "max": 1.0, "step": 0.05,
                                       "tooltip": "сила притяжения к палитре"}),
                "halftone": ("INT", {"default": 8, "min": 0, "max": 32,
                                     "tooltip": "размер полутоновой ячейки в px, 0 = выкл"}),
                "offset": ("INT", {"default": 2, "min": 0, "max": 12,
                                   "tooltip": "сдвиг цвета от контура в px, 0 = выкл"}),
                "grain": ("FLOAT", {"default": 0.035, "min": 0.0, "max": 0.2, "step": 0.005}),
                "paper": ("FLOAT", {"default": 0.04, "min": 0.0, "max": 0.2, "step": 0.005}),
                "grain_seed": ("INT", {"default": 0, "min": 0, "max": 2**31 - 1,
                                 "tooltip": "зерно; в пачке у каждого кадра своё"}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "apply"
    CATEGORY = "Спешка"

    def apply(self, images, strength, halftone, offset, grain, paper, grain_seed):
        out = []
        for i in range(images.shape[0]):
            rgb = images[i].detach().cpu().numpy()[..., :3]
            res = stylize(rgb, strength, halftone, offset, grain, paper, grain_seed + i)
            out.append(torch.from_numpy(np.ascontiguousarray(res, dtype=np.float32)))
        return (torch.stack(out),)


NODE_CLASS_MAPPINGS = {
    "ShpeshkaScenePrompt": ShpeshkaScenePrompt,
    "ShpeshkaStyle": ShpeshkaStyle,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "ShpeshkaScenePrompt": "Спешка: промпт сцены",
    "ShpeshkaStyle": "Спешка: стиль",
}
