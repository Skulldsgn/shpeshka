# Спешка

Вертикальный клип (~60 с) для Reels / Shorts / TikTok: абстрактные таймлапсы бесконечной суеты, рисованная грязно-комиксная стилистика. Без съёмок, всё генерируется локально в ComfyUI (Flux Schnell + Flux Kontext).

![палитра](docs/palette.png)

## Что где

| Путь | Что это |
|---|---|
| `docs/style-bible.md` | стайл-гайд: палитра, линия, фактура, промпт-хвост, команды для Kontext |
| `docs/pipeline.md` | пошаговый процесс: три приёма анимации, выравнивание стиля, монтаж |
| `docs/character.md` | герой клипа: дизайн и как его генерировать |
| `docs/timing.md` | тайминги всех 31 шотов под бит (генерируется) |
| `prompts/character.json` | промпты героя и его поз |
| `prompts/scenes.json` | 15 сцен: промпт, вариант с героем, приём анимации |
| `prompts/timeline.json` | монтажная сетка в тактах |
| `scripts/timing.py` | пересчёт таймингов, нарезка песни, аниматик |
| `scripts/comfy.py` | пакетная генерация через API ComfyUI (ключевые кадры, кипящая линия, Kontext) |
| `scripts/unify.py` | приводит любые кадры к единому стилю: палитра, полутона, бумага, зерно |
| `post/shpeshka_palette.cube` | LUT палитры для DaVinci Resolve |
| `workflows/*_api.json` | графы ComfyUI в формате API (для справки) |
| `config.json` | адрес ComfyUI и имена файлов моделей |

## Быстрый старт

```bash
pip install pillow numpy

# 1. Запустить ComfyUI, вписать имена моделей в config.json

# 2. Герой: выбрать лучшего, сохранить как refs/hero.png
python scripts/comfy.py character single --variants 8

# 3. Герой во всех сценах + фоны сцен без героя
python scripts/comfy.py place refs/hero.png
python scripts/comfy.py keyframes --only s02 s09 s12

# 4. Лучшие кадры положить в selects/ (s01.png, s02.png, ...), дальше по технике сцены:
python scripts/comfy.py boil selects/s01.png --scene s01
python scripts/comfy.py kontext selects/s02.png --preset daycycle
python scripts/comfy.py kontext selects/s03.png --preset clean-plate

# 5. Всё готовое — через единый фильтр
python scripts/unify.py output/boil/s01 final/s01
```

Результаты генерации складываются в `output/` (в git не попадает). Песню в репозиторий не кладём: он публичный.

Аниматик (карточки сцен под музыку):
```bash
python scripts/timing.py --audio песня.mp3 --animatic
```

## Статус

- [x] Стиль и палитра
- [x] Черновая раскадровка
- [x] Скрипты генерации и стилизации
- [x] Песня: 143.55 BPM, окно 0:26.7–1:26.9, тайминги под бит
- [x] Дизайн героя
- [ ] Генерация героя и утверждение `refs/hero.png`
- [ ] Генерация сцен и отбор
- [ ] Анимация, монтаж
