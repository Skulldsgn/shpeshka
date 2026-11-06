# Спешка

Вертикальный клип (~60 с) для Reels / Shorts / TikTok: абстрактные таймлапсы бесконечной суеты, рисованная грязно-комиксная стилистика. Без съёмок, всё генерируется локально в ComfyUI (Flux Schnell + Flux Kontext).

![палитра](docs/palette.png)

## Что где

| Путь | Что это |
|---|---|
| `docs/style-bible.md` | стайл-гайд: палитра, линия, фактура, промпт-хвост, команды для Kontext |
| `docs/pipeline.md` | пошаговый процесс: три приёма анимации, выравнивание стиля, монтаж |
| `prompts/scenes.json` | раскадровка: 14 сцен с промптами и техникой анимации |
| `scripts/comfy.py` | пакетная генерация через API ComfyUI (ключевые кадры, кипящая линия, Kontext) |
| `scripts/unify.py` | приводит любые кадры к единому стилю: палитра, полутона, бумага, зерно |
| `post/shpeshka_palette.cube` | LUT палитры для DaVinci Resolve |
| `workflows/*_api.json` | графы ComfyUI в формате API (для справки) |
| `config.json` | адрес ComfyUI и имена файлов моделей |

## Быстрый старт

```bash
pip install pillow numpy

# 1. Запустить ComfyUI, вписать имена моделей в config.json

# 2. Ключевые кадры всех сцен (по 4 варианта)
python scripts/comfy.py keyframes

# 3. Лучшие кадры положить в selects/ (s01.png, s02.png, ...), дальше по технике сцены:
python scripts/comfy.py boil selects/s01.png --scene s01
python scripts/comfy.py kontext selects/s02.png --preset daycycle
python scripts/comfy.py kontext selects/s03.png --preset clean-plate

# 4. Всё готовое — через единый фильтр
python scripts/unify.py output/boil/s01 final/s01
```

Результаты генерации складываются в `output/` (в git не попадает).

## Статус

- [x] Стиль и палитра
- [x] Черновая раскадровка
- [x] Скрипты генерации и стилизации
- [ ] Песня: BPM и тайминги сцен под бит
- [ ] Генерация ключевых кадров и отбор
- [ ] Анимация, монтаж
