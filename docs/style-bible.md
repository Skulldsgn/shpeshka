# Заметки по стилю

> Справочник с идеями, ни на что в проекте не влияет. Берите то, что нравится, остальное игнорируйте.

Единый стиль держится на четырёх слоях. Каждый следующий страхует предыдущий:

1. **Промпт**: одинаковый стилевой хвост и негатив во всех сценах.
2. **Flux Kontext**: доводит «выбившиеся» кадры до эталона и делает вариации без перегенерации.
3. **Пост-обработка** (нода «Спешка: стиль», `scripts/unify.py` или LUT в DaVinci): жёстко приводит каждый кадр к палитре, добавляет полутона, зерно и бумагу. Именно этот слой гарантирует, что разные генерации выглядят как один мультфильм.
4. *(по желанию)* **Своя LoRA** на 15–20 лучших кадрах, когда наберётся материал.

---

## Палитра (8 цветов)

| Роль | HEX | Где использовать |
|---|---|---|
| Чернила | `#1B1A17` | контуры, глубокие тени |
| Бумага | `#E8DCC0` | светлые плоскости, небо днём |
| Олива | `#6B7040` | одежда, стены, транспорт |
| Ржавчина | `#A4482B` | акценты, кирпич, светофор |
| Грязная бирюза | `#3E6B68` | холодные тени, стекло |
| Натриевый жёлтый | `#E3A93B` | фонари, окна, тёплый свет |
| Смог | `#8A8577` | асфальт, бетон, дымка |
| Ночь | `#232F3E` | ночное небо, глубокий фон |

Палитра в картинке: `docs/palette.png`. Правило: в кадре 1 тёплый источник света (натриевый жёлтый) против холодных теней (бирюза или ночь). Чистого белого и чистого чёрного нет.

## Линия и форма

- Жирный чернильный контур, неровный, будто тушью. Толщина везде одинаковая.
- Тени плоские, одним тоном, без градиентов. Внутри теней штриховка или полутона.
- Фигуры вытянутые и угловатые, плечи вперёд, головы маленькие. **Лиц крупно не показываем**: глаза пустые или тёмные, черты условные.
- Архитектура слегка кривая, перспектива преувеличена (широкий угол, низкая точка).

## Фактура

- Бумажное зерно и потёртость на весь кадр.
- Полутоновые точки в средних тонах и тенях.
- Лёгкая несовмещённость печати: тень цвета чуть съезжает от контура (делается в `unify.py`).

## Композиция 9:16

- Главное держим в центральных 60% по высоте: сверху и снизу интерфейс TikTok и Reels.
- Горизонт низко или очень высоко, без «середины».
- В каждом кадре одна ясная вещь: поток, фигура или объект.

---

## Пример стилевого хвоста промпта

```
, 2D hand-drawn cartoon illustration, gritty urban comic art, thick uneven black ink outlines,
flat cel shading with hard-edged shadows, halftone dot shading, muted palette of olive green,
rust red, dirty teal, sodium yellow and smoggy grey, warm streetlight against cool shadows,
aged paper texture, slightly crooked exaggerated perspective, lanky angular figures with hollow eyes,
vertical composition
```

## Негатив

Flux Schnell с cfg 1 негатив почти игнорирует, поэтому «запреты» лучше формулировать в позитиве (`flat`, `hand-drawn`). Если используете сэмплер с настоящим CFG, вот негатив:

```
photorealistic, photo, 3d render, CGI, glossy, smooth gradients, anime, chibi, cute,
detailed realistic faces, text, watermark, logo, signature, pure white, oversaturated neon
```

Не используем: персонажей и логотип Gorillaz, имена художников в промпте. Стиль описываем признаками, а не чужими именами.

---

## Flux Kontext: готовые инструкции

Kontext понимает команды на английском. Главное правило: всегда добавлять, что сохранить.

**Привести выбившийся кадр к стилю:**
```
Redraw this image as a flat 2D hand-drawn comic illustration with thick uneven black ink outlines,
hard-edged flat shadows, halftone dots and aged paper texture, using only muted olive, rust,
dirty teal, sodium yellow and smoggy grey colors. Keep the composition, camera angle and all objects
exactly the same.
```

**Смена времени суток (приём 2, таймлапс):**
```
Change the time of day to [early morning with cold blue light | harsh noon sun with short shadows |
orange sunset with long shadows | night with glowing sodium streetlights and lit windows].
Keep the composition, buildings, objects, line art and drawing style exactly the same.
```

**Чистый фон для параллакса (приём 3):**
```
Remove all people and cars from the scene and fill the space with the street behind them.
Keep everything else, the lighting and the drawing style exactly the same.
```

**Отделить персонажа:**
```
Remove the background completely and place the figure on a plain flat white background.
Keep the figure, its pose, outlines and colors exactly the same.
```
После этого фон вырезается нодой RMBG / BiRefNet.

**Вариация для «кипящей линии»** (если img2img на Schnell даёт слишком разные кадры):
```
Redraw the same image with slightly different hand-drawn ink lines, as the next frame of
a hand-drawn animation. Keep everything else exactly the same.
```

### Kontext + эталон стиля

Выберите 1 лучший кадр как «эталон» (`refs/style_master.png`). Чтобы подтянуть другой кадр к нему, склейте их нодой **Image Stitch** (эталон слева, целевой справа) и дайте команду:
```
Redraw the right image in exactly the same drawing style, line weight, colors and texture
as the left image. Keep the content and composition of the right image.
```
Потом обрежьте правую половину. Работает не всегда идеально, но хорошо выравнивает линию и палитру.
