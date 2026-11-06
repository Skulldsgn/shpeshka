"""
Нода ComfyUI «Спешка: стиль» (меню: Спешка).
Ставится между VAE Decode и Save Image. По умолчанию настроена под тёмные силуэты на бумаге.
Каждый эффект выключается нулём, палитра — пустым полем.
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
                                       "tooltip": "HEX-цвета через запятую. Самый тёмный = тушь, самый светлый = бумага. Пусто = без палитры"}),
                "palette_strength": ("FLOAT", {"default": 0.9, "min": 0.0, "max": 1.0, "step": 0.05,
                                               "tooltip": "сила притяжения к палитре, 0 = выкл"}),
                "ink_threshold": ("FLOAT", {"default": 0.35, "min": 0.0, "max": 0.9, "step": 0.01,
                                            "tooltip": "всё темнее этого заливается сплошной тушью; выше = больше чёрного, 0 = выкл"}),
                "fill_details": ("INT", {"default": 0, "min": 0, "max": 101,
                                         "tooltip": "светлые детали внутри силуэтов меньше этого размера (px) заливаются тушью: блики, лица, складки. 0 = выкл. Включайте, только если внутри силуэтов есть блики (обычно 15–30)"}),
                "paper": ("FLOAT", {"default": 0.035, "min": 0.0, "max": 0.2, "step": 0.005,
                                    "tooltip": "бумажная фактура, 0 = выкл"}),
                "grain": ("FLOAT", {"default": 0.02, "min": 0.0, "max": 0.2, "step": 0.005,
                                    "tooltip": "зерно, 0 = выкл"}),
                "halftone": ("INT", {"default": 0, "min": 0, "max": 32,
                                     "tooltip": "полутоновые точки, размер ячейки в px, 0 = выкл"}),
                "offset": ("INT", {"default": 0, "min": 0, "max": 12,
                                   "tooltip": "сдвиг цвета от контура (эффект печати) в px, 0 = выкл"}),
                "grain_seed": ("INT", {"default": 0, "min": 0, "max": 2**31 - 1,
                                       "tooltip": "в пачке у каждого кадра своё зерно"}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "apply"
    CATEGORY = "Спешка"

    def apply(self, images, palette, palette_strength, ink_threshold, fill_details,
              paper, grain, halftone, offset, grain_seed):
        out = []
        for i in range(images.shape[0]):
            rgb = images[i].detach().cpu().numpy()[..., :3]
            res = stylize(rgb, palette, palette_strength, halftone, offset, grain, paper,
                          grain_seed + i, ink_threshold, fill_details)
            out.append(torch.from_numpy(np.ascontiguousarray(res, dtype=np.float32)))
        return (torch.stack(out),)


NODE_CLASS_MAPPINGS = {"ShpeshkaStyle": ShpeshkaStyle}
NODE_DISPLAY_NAME_MAPPINGS = {"ShpeshkaStyle": "Спешка: стиль"}
