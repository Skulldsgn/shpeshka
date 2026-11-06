#!/usr/bin/env python3
"""
timing.py — пересчитывает монтажную сетку из prompts/timeline.json.

  python scripts/timing.py                          # обновить docs/timing.md
  python scripts/timing.py --audio песня.mp3        # + вырезать минуту песни (output/clip_audio.wav)
  python scripts/timing.py --audio песня.mp3 --animatic   # + аниматик output/animatic.mp4

Аниматик — карточки сцен, порезанные точно по тактам под музыку. По нему удобно
проверить ритм до генерации, а потом заменять карточки готовыми кадрами.
Нужны: pillow, ffmpeg в PATH.
"""
import argparse
import json
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TL = json.loads((ROOT / "prompts" / "timeline.json").read_text(encoding="utf-8"))
SC = {s["id"]: s for s in json.loads((ROOT / "prompts" / "scenes.json").read_text(encoding="utf-8"))["scenes"]}
FPS = 24
TECH = {"boil": "кипящая линия", "daycycle": "смена света", "parallax": "параллакс", "wan": "Wan"}
COLORS = ["#6B7040", "#A4482B", "#3E6B68", "#8A8577", "#232F3E", "#E3A93B"]


def shots():
    bar = 4 * 60 / TL["bpm"]
    t_bar = 0.0
    out = []
    for sec in TL["sections"]:
        for sid, bars in sec["shots"]:
            start = t_bar * bar
            end = (t_bar + bars) * bar
            out.append({
                "section": sec["name"], "id": sid, "bars": bars, "bar_from": t_bar,
                "start": start, "end": end,
                "f_start": round(start * FPS), "f_end": round(end * FPS),
            })
            t_bar += bars
    return out, t_bar * bar


def ts(sec):
    m, s = divmod(sec, 60)
    return f"{int(m)}:{s:05.2f}"


def write_md(sh, total):
    bar = 4 * 60 / TL["bpm"]
    lines = [
        "# Тайминги",
        "",
        f"Песня: **{TL['song']}**, {TL['bpm']} BPM, такт = {bar:.3f} с, доля = {bar / 4:.3f} с.",
        f"Клип: с {ts(TL['song_start'])} по {ts(TL['song_start'] + total)} песни, длительность {total:.2f} с, {FPS} fps.",
        "",
        "Файл сгенерирован `scripts/timing.py` из `prompts/timeline.json`, руками не править.",
        "",
    ]
    cur = None
    for s in sh:
        if s["section"] != cur:
            cur = s["section"]
            note = next(x["note"] for x in TL["sections"] if x["name"] == cur)
            lines += ["", f"## {cur}", "", note, "",
                      "| # | Клип | Песня | Длит. | Кадры (24 fps) | Сцена | Герой | Приём |",
                      "|---|---|---|---|---|---|---|---|"]
        sc = SC[s["id"]]
        n = sh.index(s) + 1
        lines.append(
            f"| {n} | {ts(s['start'])} | {ts(TL['song_start'] + s['start'])} | {s['end'] - s['start']:.2f} с "
            f"| {s['f_start']}–{s['f_end'] - 1} ({s['f_end'] - s['f_start']}) | {s['id']} {sc['title']} "
            f"| {'да' if sc['hero'] else '—'} | {TECH[sc['technique']]} |"
        )
    p = ROOT / "docs" / "timing.md"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("->", p.relative_to(ROOT))


def cut_audio(src, total, out):
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error", "-ss", f"{TL['song_start']:.3f}", "-t", f"{total:.3f}",
        "-i", str(src), "-af", f"afade=t=out:st={total - 0.6:.3f}:d=0.6", str(out)
    ], check=True)
    print("->", out)


def card(s, n, path):
    from PIL import Image, ImageDraw, ImageFont
    w, h = 1080, 1920
    sc = SC[s["id"]]
    col = COLORS[int(s["id"][1:]) % len(COLORS)]
    img = Image.new("RGB", (w, h), col)
    d = ImageDraw.Draw(img)

    def font(size):
        for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "DejaVuSans-Bold.ttf", "arialbd.ttf", "arial.ttf"):
            try:
                return ImageFont.truetype(f, size)
            except OSError:
                continue
        return ImageFont.load_default()

    ink, paper = "#1B1A17", "#E8DCC0"
    d.rectangle([0, 0, w, 230], fill=ink)
    d.rectangle([0, h - 380, w, h], fill=ink)  # зона интерфейса соцсетей
    d.text((60, 70), f"#{n}  {s['section']}", font=font(64), fill=paper)
    d.text((80, 620), s["id"], font=font(260), fill=paper)
    d.text((80, 920), sc["title"], font=font(96), fill=paper)
    d.text((80, 1060), TECH[sc["technique"]] + ("  ·  герой" if sc["hero"] else ""), font=font(56), fill=paper)
    d.text((80, 1160), f"{s['bars']} такт(а) · {s['end'] - s['start']:.2f} с", font=font(56), fill=paper)
    d.text((60, h - 300), "зона интерфейса TikTok / Reels", font=font(44), fill="#8A8577")
    img.save(path)


def animatic(sh, total, audio, out):
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        lst = []
        for n, s in enumerate(sh, 1):
            p = tmp / f"{n:03d}.png"
            card(s, n, p)
            frames = s["f_end"] - s["f_start"]
            lst.append(f"file '{p}'\nduration {frames / FPS:.6f}")
        lst.append(f"file '{tmp / f'{len(sh):03d}.png'}'")
        (tmp / "list.txt").write_text("\n".join(lst), encoding="utf-8")
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(tmp / "list.txt"),
            "-i", str(audio), "-vf", f"fps={FPS},format=yuv420p", "-c:v", "libx264", "-preset", "veryfast",
            "-crf", "28", "-c:a", "aac", "-b:a", "192k", "-shortest", str(out)
        ], check=True)
    print("->", out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--audio", help="исходный файл песни")
    ap.add_argument("--animatic", action="store_true")
    a = ap.parse_args()
    sh, total = shots()
    write_md(sh, total)
    if a.audio:
        out = ROOT / "output"
        out.mkdir(exist_ok=True)
        wav = out / "clip_audio.wav"
        cut_audio(a.audio, total, wav)
        if a.animatic:
            animatic(sh, total, wav, out / "animatic.mp4")


if __name__ == "__main__":
    main()
