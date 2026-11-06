"""
Нода ComfyUI «Спешка: стиль» (меню: Спешка).
Ставится между VAE Decode и Save Image. Каждый эффект выключается нулём,
палитра — пустым полем.
"""
import numpy as np
import torch

from .shpeshka_style import DEFAULT_PALETTE, stylize


class ShpeshkaStyle:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "palette": ("STRING", {"multiline": True, "default": DEFAULT_PALETTE,
                                       "tooltip": "HEX-цвета через запятую. Пусто = без палитры"}),
                "palette_strength": ("FLOAT", {"default": 0.7, "min": 0.0, "max": 1.0, "step": 0.05,
                                               "tooltip": "сила притяжения к палитре, 0 = выкл"}),
                "halftone": ("INT", {"default": 8, "min": 0, "max": 32,
                                     "tooltip": "размер полутоновой ячейки в px, 0 = выкл"}),
                "offset": ("INT", {"default": 2, "min": 0, "max": 12,
                                   "tooltip": "сдвиг цвета от контура в px, 0 = выкл"}),
                "grain": ("FLOAT", {"default": 0.035, "min": 0.0, "max": 0.2, "step": 0.005,
                                    "tooltip": "зерно, 0 = выкл"}),
                "paper": ("FLOAT", {"default": 0.04, "min": 0.0, "max": 0.2, "step": 0.005,
                                    "tooltip": "бумажная фактура, 0 = выкл"}),
                "grain_seed": ("INT", {"default": 0, "min": 0, "max": 2**31 - 1,
                                       "tooltip": "в пачке у каждого кадра своё зерно"}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "apply"
    CATEGORY = "Спешка"

    def apply(self, images, palette, palette_strength, halftone, offset, grain, paper, grain_seed):
        out = []
        for i in range(images.shape[0]):
            rgb = images[i].detach().cpu().numpy()[..., :3]
            res = stylize(rgb, palette, palette_strength, halftone, offset, grain, paper, grain_seed + i)
            out.append(torch.from_numpy(np.ascontiguousarray(res, dtype=np.float32)))
        return (torch.stack(out),)


NODE_CLASS_MAPPINGS = {"ShpeshkaStyle": ShpeshkaStyle}
NODE_DISPLAY_NAME_MAPPINGS = {"ShpeshkaStyle": "Спешка: стиль"}
