#!/usr/bin/env python3
"""Economy-news reel renderer (editorial / newspaper style).

Usage:
  python reel.py check   story.json            # validate schema, timing, text fit (no rendering)
  python reel.py stills  story.json OUTDIR     # one PNG per scene (end state) + first frame
  python reel.py audio   story.json OUT.wav    # narration + background music
  python reel.py render  story.json OUTDIR     # full video: OUTDIR/<output_name>.mp4

story.json format: see ../references/story-schema.md
Requires: python3, pillow, numpy, ffmpeg; pyopenjtalk for narration; Noto CJK fonts.
"""
import json, os, re, subprocess, sys, glob, shutil
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1080, 1920, 30
TOTAL_DEFAULT = 60.0

# ---------------------------------------------------------------- fonts
FONT_DIRS = ["/usr/share/fonts", "/usr/local/share/fonts", os.path.expanduser("~/.fonts"),
             os.path.expanduser("~/.local/share/fonts"), "/Library/Fonts", "/System/Library/Fonts",
             os.path.expanduser("~/Library/Fonts"), "C:/Windows/Fonts"]
WANT = {
    "SERIF_B": ["NotoSerifCJK-Black.ttc", "NotoSerifJP-Black.otf", "NotoSerifCJKjp-Black.otf", "NotoSerifCJK-Bold.ttc", "NotoSerifJP-Bold.otf"],
    "SERIF":   ["NotoSerifCJK-Bold.ttc", "NotoSerifJP-Bold.otf", "NotoSerifCJKjp-Bold.otf", "NotoSerifCJK-SemiBold.ttc"],
    "SANS_R":  ["NotoSansCJK-Regular.ttc", "NotoSansJP-Regular.otf", "NotoSansCJKjp-Regular.otf"],
    "SANS_M":  ["NotoSansCJK-Medium.ttc", "NotoSansJP-Medium.otf", "NotoSansCJKjp-Medium.otf", "NotoSansCJK-Regular.ttc"],
    "SANS_B":  ["NotoSansCJK-Bold.ttc", "NotoSansJP-Bold.otf", "NotoSansCJKjp-Bold.otf"],
}
_paths = {}
def _find(key):
    if key in _paths:
        return _paths[key]
    for name in WANT[key]:
        for d in FONT_DIRS:
            hits = glob.glob(os.path.join(d, "**", name), recursive=True)
            if hits:
                _paths[key] = hits[0]
                return hits[0]
    raise SystemExit(f"FONT MISSING: {WANT[key][0]} (install fonts-noto-cjk, or Noto Serif JP / Noto Sans JP)")

def _jp_index(path):
    if not path.endswith(".ttc"):
        return 0
    for i in range(10):
        try:
            if "JP" in ImageFont.truetype(path, 10, index=i).getname()[0]:
                return i
        except Exception:
            break
    return 0

_fc = {}
def F(key, size):
    k = (key, size)
    if k not in _fc:
        p = _find(key)
        _fc[k] = ImageFont.truetype(p, size, index=_jp_index(p))
    return _fc[k]

# ---------------------------------------------------------------- design tokens
PAPER = (243, 238, 228); INK = (22, 21, 19); GREY = (110, 104, 96)
LIGHT = (196, 188, 176); RED = (190, 46, 30)
ML, MR, MR_LOW = 90, W - 90, 960        # MR_LOW: keep lower area clear of Instagram's side buttons
TEXT_W = MR_LOW - ML                     # usable text width for body copy

def paper():
    rng = np.random.default_rng(7)
    base = np.ones((H, W, 3), np.float32) * np.array(PAPER, np.float32)
    noise = rng.normal(0, 3.2, (H, W, 1)).astype(np.float32)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    vig = 1 - 0.05 * (((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    return Image.fromarray(np.clip(base * vig[..., None] + noise, 0, 255).astype(np.uint8))
PAPER_IMG = None

def eo(t):
    t = max(0.0, min(1.0, t)); return 1 - (1 - t) ** 5
def prog(t, s, d=0.6):
    return eo((t - s) / d)

_tc = {}
def text_img(s, font, fill):
    k = (s, id(font), fill)
    if k not in _tc:
        l, tp, r, b = font.getbbox(s)
        im = Image.new("RGBA", (max(1, r + 4), b + 8), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((0, 0), s, font=font, fill=fill + (255,))
        _tc[k] = im
    return _tc[k]

def reveal(img, xy, s, font, fill, p, anchor="l"):
    if p <= 0 or not s:
        return 0
    ti = text_img(s, font, fill); w, h = ti.size; x, y = xy
    if anchor == "r": x -= w
    elif anchor == "m": x -= w // 2
    off = int(round((1 - p) * h))
    if off < h:
        crop = ti.crop((0, 0, w, h - off)); img.paste(crop, (int(x), int(y + off)), crop)
    return w

def hline(d, x0, x1, y, p, fill, wd=2):
    if p > 0:
        d.rectangle((x0, y, x0 + (x1 - x0) * p, y + wd - 1), fill=fill)

def tw(s, font):
    return font.getlength(s)

# ---------------------------------------------------------------- Japanese line wrapping
NO_START = set("、。，．・：；？！ー」』）】〕〉》％%…‥ぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮヵヶ")
NO_END = set("「『（【〔〈《")
def wrap(text, font, width):
    """Wrap Japanese text to width, keeping kinsoku rules. Explicit \\n forces a break."""
    out = []
    for para in str(text).split("\n"):
        line = ""
        for ch in para:
            if tw(line + ch, font) <= width or not line:
                line += ch; continue
            if ch in NO_START:                    # hang punctuation on the current line
                line += ch; continue
            carry = ""
            while line and line[-1] in NO_END:
                carry = line[-1] + carry; line = line[:-1]
            # keep runs of ASCII digits/letters together
            m = re.search(r"[0-9A-Za-z.,%]+$", line)
            if m and re.match(r"[0-9A-Za-z.,%]", ch) and m.start() > 0:
                carry = line[m.start():] + carry; line = line[:m.start()]
            out.append(line); line = carry + ch
        out.append(line)
    return out

# ---------------------------------------------------------------- shared chrome
class Ctx:
    def __init__(self, story, idx, chapter_no, chapters):
        self.s = story; self.idx = idx; self.no = chapter_no; self.n = chapters

def masthead(img, d, ctx, page=True):
    st = ctx.s
    reveal(img, (ML, 196), st.get("brand", "ECONOMY BRIEF"), F("SANS_B", 30), INK, 1)
    reveal(img, (MR, 196), st["date_label"], F("SANS_M", 28), GREY, 1, anchor="r")
    hline(d, ML, MR, 250, 1, INK, 4); hline(d, ML, MR, 260, 1, INK, 1)
    hline(d, ML, MR, 1590, 1, LIGHT, 1)
    reveal(img, (ML, 1606), "出典：" + st["sources"], F("SANS_R", 24), GREY, 1)
    if page and ctx.no:
        reveal(img, (MR, 1602), f"{ctx.no:02d} / {ctx.n:02d}", F("SERIF", 28), INK, 1, anchor="r")

def section(img, t, ctx, title):
    w = reveal(img, (ML, 300), f"{ctx.no:02d}", F("SERIF_B", 46), RED, prog(t, 0.05, 0.5))
    reveal(img, (ML + w + 18, 309), title, F("SANS_M", 34), GREY, prog(t, 0.12, 0.5))

HEAD_SIZE, HEAD_LH = 88, 120
BODY_SIZE, BODY_LH = 40, 66

def heading(img, d, t, lines, y0=380):
    for k, s in enumerate(lines):
        reveal(img, (ML - 4, y0 + k * HEAD_LH), s, F("SERIF_B", HEAD_SIZE), INK, prog(t, 0.15 + 0.08 * k, 0.7))
    yb = y0 + len(lines) * HEAD_LH + 24
    hline(d, ML, ML + 90, yb, prog(t, 0.45, 0.5), RED, 7)
    return yb + 50

def body(img, t, text, y0, start=0.45):
    lines = wrap(text, F("SANS_R", BODY_SIZE), TEXT_W)
    for k, s in enumerate(lines):
        reveal(img, (ML, y0 + k * BODY_LH), s, F("SANS_R", BODY_SIZE), INK, prog(t, start + 0.07 * k, 0.6))
    return y0 + len(lines) * BODY_LH

def finish(img, t, dur, fade_in=True):
    a = min(1.0, (dur - t) / 0.18)
    if fade_in: a = min(a, t / 0.12)
    return Image.blend(PAPER_IMG, img, max(0.0, a)) if a < 1 else img

def chapter_top(img, d, t, ctx, sc):
    masthead(img, d, ctx)
    section(img, t, ctx, sc["section"])
    y = heading(img, d, t, sc["heading"])
    if sc.get("body"):
        y = body(img, t, sc["body"], y)
    return y

# ---------------------------------------------------------------- scene types
def s_hook(img, d, t, ctx, sc):
    t = 99.0  # fully visible from frame 0: this frame is the thumbnail
    masthead(img, d, ctx, page=False)
    reveal(img, (ML, 330), sc["kicker"], F("SANS_B", 36), RED, 1)
    y = 410
    for s in sc["headline"]:
        reveal(img, (ML - 6, y), s, F("SERIF_B", 128), INK, 1); y += 165
    hline(d, ML, ML + 90, y + 30, 1, RED, 7)
    y = body(img, t, sc["lead"], y + 90)
    st = sc.get("stat")
    if st:
        y0 = max(y + 70, 1110)
        hline(d, ML, MR_LOW, y0, 1, INK, 2)
        vw = reveal(img, (ML - 8, y0 + 30), st["value"], F("SERIF_B", 260 if len(st["value"]) <= 3 else 190), RED, 1)
        x = ML + vw + 30
        reveal(img, (x, y0 + 95), st["unit"], F("SERIF_B", 64), INK, 1)
        if st.get("sub"):
            reveal(img, (x + 4, y0 + 190), st["sub"], F("SANS_R", 34), GREY, 1)
        hline(d, ML, MR_LOW, y0 + 360, 1, LIGHT, 1)

def s_text(img, d, t, ctx, sc):
    chapter_top(img, d, t, ctx, sc)

def s_grid(img, d, t, ctx, sc):
    y = chapter_top(img, d, t, ctx, sc) + 50
    g = sc["grid"]
    reveal(img, (ML, y), g["label"], F("SANS_B", 30), GREY, prog(t, 0.9, 0.5))
    hline(d, ML, MR_LOW, y + 52, prog(t, 0.95, 0.6), INK, 2)
    cols = g.get("columns", 4); cw = TEXT_W / cols
    for i, name in enumerate(g["items"]):
        r, c = divmod(i, cols); x, yy = ML + c * cw, y + 76 + r * 70
        p = prog(t, 1.0 + 0.03 * i, 0.5)
        if name in g.get("highlight", []):
            if p > 0: d.rectangle((x - 4, yy - 6, x + cw - 24, yy + 52), fill=RED)
            reveal(img, (x + 10, yy - 2), name, F("SANS_B", 34), PAPER, p)
        else:
            reveal(img, (x, yy), name, F("SANS_M", 32), INK, p)

def s_timeline(img, d, t, ctx, sc):
    y = chapter_top(img, d, t, ctx, sc) + 70
    items = sc["timeline"]; xd = ML + 200
    d.rectangle((xd, y + 22, xd + 1, y + 22 + (len(items) - 1) * 100 * prog(t, 0.9, 1.6)), fill=INK)
    for k, it in enumerate(items):
        yy = y + k * 100; hot = it.get("highlight", False); p = prog(t, 1.0 + 0.18 * k, 0.5)
        if p > 0:
            r = 11 if hot else 8
            d.ellipse((xd - r + 1, yy + 22 - r, xd + r + 1, yy + 22 + r), fill=RED if hot else INK)
        reveal(img, (ML, yy), it["date"], F("SERIF", 34), RED if hot else GREY, p)
        reveal(img, (xd + 40, yy - 2), it["event"], F("SANS_B" if hot else "SANS_M", 36), RED if hot else INK, p)

def s_bars(img, d, t, ctx, sc):
    y = chapter_top(img, d, t, ctx, sc) + 60
    ch = sc["chart"]
    reveal(img, (ML, y), ch["title"], F("SANS_B", 30), GREY, prog(t, 0.9, 0.5))
    x0 = ML + 150
    vmax = max([r["value"] for r in ch["rows"]] + [ch.get("marker", {}).get("value", 0)])
    scale = (MR_LOW - 260 - x0) / vmax
    top = y + 70
    for k, r in enumerate(ch["rows"]):
        yy = top + k * 110; col = RED if r.get("highlight") else INK
        p = prog(t, 1.0 + 0.25 * k, 0.9)
        reveal(img, (ML, yy + 8), r["label"], F("SANS_M", 36), INK, prog(t, 0.95 + 0.25 * k, 0.5))
        bw = r["value"] * scale * p
        if p > 0: d.rectangle((x0, yy, x0 + bw, yy + 64), fill=col)
        if p > 0.95:
            lab = r.get("display", str(r["value"]))
            if r.get("label_inside"):
                reveal(img, (x0 + bw - 18, yy + 6), lab, F("SERIF_B", 44), PAPER, 1, anchor="r")
            else:
                reveal(img, (x0 + bw + 18, yy + 6), lab, F("SERIF_B", 44), col, 1)
    bottom = top + len(ch["rows"]) * 110 - 30
    mk = ch.get("marker")
    if mk and prog(t, 1.6, 0.5) > 0:
        xc = x0 + mk["value"] * scale
        for yy in range(int(top - 20), int(bottom + 10), 14):
            d.rectangle((xc, yy, xc + 1, yy + 7), fill=RED)
        reveal(img, (xc, bottom + 15), mk["label"], F("SANS_M", 26), RED, prog(t, 1.6, 0.5), anchor="m")
    hline(d, x0, MR_LOW - 20, bottom, prog(t, 0.95, 0.6), LIGHT, 1)
    if ch.get("note"):
        lines = wrap(ch["note"], F("SANS_R", 26), TEXT_W)
        for k, s in enumerate(lines):
            reveal(img, (ML, bottom + 80 + k * 40), s, F("SANS_R", 26), GREY, prog(t, 1.5, 0.5))

def s_table(img, d, t, ctx, sc):
    y = chapter_top(img, d, t, ctx, sc) + 60
    hline(d, ML, MR_LOW, y, prog(t, 0.9, 0.6), INK, 2)
    for k, r in enumerate(sc["rows"]):
        yy = y + 30 + k * 190; p = prog(t, 1.0 + 0.2 * k, 0.6)
        col = RED if r.get("highlight", True) else INK
        reveal(img, (ML, yy), r.get("date", ""), F("SERIF", 32), GREY, p)
        reveal(img, (ML, yy + 50), r["name"], F("SANS_B", 40), INK, p)
        reveal(img, (ML, yy + 110), r.get("note", ""), F("SANS_R", 26), GREY, prog(t, 1.1 + 0.2 * k, 0.6))
        vf = F("SERIF_B", 84 if tw(r["value"], F("SERIF_B", 84)) < 470 else 64)
        reveal(img, (MR_LOW, yy + 30), r["value"], vf, col, p, anchor="r")
        hline(d, ML, MR_LOW, yy + 160, prog(t, 1.1 + 0.2 * k, 0.6), LIGHT, 1)

def s_points(img, d, t, ctx, sc):
    y = chapter_top(img, d, t, ctx, sc) + 50
    hline(d, ML, MR_LOW, y, prog(t, 0.8, 0.6), INK, 2)
    for k, it in enumerate(sc["points"]):
        yy = y + 36 + k * 175; p = prog(t, 0.95 + 0.25 * k, 0.6)
        reveal(img, (ML, yy - 8), str(k + 1), F("SERIF_B", 96), RED, p)
        reveal(img, (ML + 110, yy), it["title"], F("SERIF_B", 54), INK, p)
        reveal(img, (ML + 112, yy + 78), it.get("sub", ""), F("SANS_R", 34), INK, prog(t, 1.05 + 0.25 * k, 0.6))
        hline(d, ML, MR_LOW, yy + 140, prog(t, 1.1 + 0.25 * k, 0.6), LIGHT, 1)

def s_summary(img, d, t, ctx, sc):
    # "押さえておきたいポイント" card: checkmark-free numbered takeaways
    y = chapter_top(img, d, t, ctx, sc) + 40
    for k, s in enumerate(sc["takeaways"]):
        p = prog(t, 0.9 + 0.2 * k, 0.6)
        hline(d, ML, MR_LOW, y, p, INK if k == 0 else LIGHT, 2 if k == 0 else 1)
        lines = wrap(s, F("SANS_B", 40), TEXT_W - 80)
        reveal(img, (ML, y + 26), f"{k+1}.", F("SERIF_B", 44), RED, p)
        for j, ln in enumerate(lines):
            reveal(img, (ML + 70, y + 28 + j * 60), ln, F("SANS_B", 40), INK, p)
        y += 60 + len(lines) * 60

def s_outro(img, d, t, ctx, sc):
    masthead(img, d, ctx, page=False)
    y = 480
    for k, s in enumerate(sc.get("headline", ["明日も、", "最新のニュースを", "お届けします。"])):
        reveal(img, (ML - 4, y), s, F("SERIF_B", 100), INK, prog(t, 0.08 * k, 0.5)); y += 140
    hline(d, ML, ML + 90, y + 30, prog(t, 0.3, 0.4), RED, 7)
    y += 80
    for k, s in enumerate(sc.get("sub", ["毎朝、いちばん重要な経済ニュースを1本。", "フォローして、見逃さないでください。"])):
        reveal(img, (ML, y + k * 66), s, F("SANS_R", 40), INK, prog(t, 0.35 + 0.07 * k, 0.5))
    reveal(img, (ML, 1400), sc.get("disclaimer", "※報道時点の情報です。投資判断はご自身で。"), F("SANS_R", 26), GREY, prog(t, 0.5, 0.5))

TYPES = {"hook": s_hook, "text": s_text, "grid": s_grid, "timeline": s_timeline, "bars": s_bars,
         "table": s_table, "points": s_points, "summary": s_summary, "outro": s_outro}

# ---------------------------------------------------------------- story handling
def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def contexts(story):
    chapters = [i for i, sc in enumerate(story["scenes"]) if sc["type"] not in ("hook", "outro")]
    out = []
    for i, sc in enumerate(story["scenes"]):
        no = chapters.index(i) + 1 if i in chapters else 0
        out.append(Ctx(story, i, no, len(chapters)))
    return out

def frame_fn(story):
    global PAPER_IMG
    if PAPER_IMG is None:
        PAPER_IMG = paper()
    ctxs = contexts(story)
    def fn(i, t):
        sc = story["scenes"][i]
        img = PAPER_IMG.copy(); d = ImageDraw.Draw(img)
        TYPES[sc["type"]](img, d, t, ctxs[i], sc)
        if sc["type"] == "hook":
            return finish(img, t, sc["duration"], fade_in=False)
        return finish(img, t, sc["duration"])
    return fn

# ---------------------------------------------------------------- checks
def check(story, verbose=True):
    errs, warns = [], []
    req = ["date_label", "sources", "scenes", "output_name"]
    for k in req:
        if k not in story: errs.append(f"missing top-level key: {k}")
    if errs: return errs, warns
    total = sum(sc["duration"] for sc in story["scenes"])
    target = story.get("total_seconds", TOTAL_DEFAULT)
    if abs(total - target) > 0.01: errs.append(f"durations sum to {total}s, expected {target}s")
    sc0, scn = story["scenes"][0], story["scenes"][-1]
    if sc0["type"] != "hook": errs.append("first scene must be type 'hook'")
    if scn["type"] != "outro": errs.append("last scene must be type 'outro'")
    for i, sc in enumerate(story["scenes"]):
        tag = f"scene {i} ({sc.get('type')})"
        if sc.get("type") not in TYPES: errs.append(f"{tag}: unknown type"); continue
        if "narration" not in sc: errs.append(f"{tag}: missing narration")
        if sc["type"] not in ("hook", "outro"):
            for k in ("section", "heading"):
                if k not in sc: errs.append(f"{tag}: missing {k}")
            for s in sc.get("heading", []):
                if tw(s, F("SERIF_B", HEAD_SIZE)) > MR - ML + 10:
                    errs.append(f"{tag}: heading line too wide: 「{s}」 (max ~10 full-width chars)")
            if len(sc.get("heading", [])) > 2: errs.append(f"{tag}: heading must be 1-2 lines")
            nb = len(wrap(sc.get("body", ""), F("SANS_R", BODY_SIZE), TEXT_W)) if sc.get("body") else 0
            if nb > 5: errs.append(f"{tag}: body wraps to {nb} lines (max 5)")
        if sc["type"] == "hook":
            for s in sc.get("headline", []):
                if tw(s, F("SERIF_B", 128)) > MR - ML + 10:
                    errs.append(f"{tag}: headline line too wide: 「{s}」 (max ~7 full-width chars)")
            nb = len(wrap(sc.get("lead", ""), F("SANS_R", BODY_SIZE), TEXT_W))
            if nb > 4: errs.append(f"{tag}: lead wraps to {nb} lines (max 4)")
        if sc["type"] == "grid" and len(sc["grid"]["items"]) > 20: errs.append(f"{tag}: grid max 20 items")
        if sc["type"] == "timeline":
            if len(sc["timeline"]) > 5: errs.append(f"{tag}: timeline max 5 items")
            for it in sc["timeline"]:
                if tw(it["event"], F("SANS_B", 36)) > MR - ML - 240: errs.append(f"{tag}: timeline event too long: 「{it['event']}」")
        if sc["type"] == "points":
            if len(sc["points"]) > 3: errs.append(f"{tag}: points max 3")
            for it in sc["points"]:
                if tw(it.get("sub", ""), F("SANS_R", 34)) > TEXT_W - 110: errs.append(f"{tag}: point sub too long: 「{it['sub']}」")
                if tw(it["title"], F("SERIF_B", 54)) > TEXT_W - 110: errs.append(f"{tag}: point title too long")
        if sc["type"] == "table" and len(sc["rows"]) > 3: errs.append(f"{tag}: table max 3 rows")
        if sc["type"] == "bars" and len(sc["chart"]["rows"]) > 3: errs.append(f"{tag}: bars max 3 rows")
        if sc["type"] == "summary" and len(sc["takeaways"]) > 3: errs.append(f"{tag}: summary max 3 takeaways")
    # vertical overflow check via a dry render of each scene's last frame
    fn = frame_fn(story)
    for i, sc in enumerate(story["scenes"]):
        img = fn(i, sc["duration"] - 0.3)
        a = np.asarray(img).astype(int)
        band = a[1500:1586, ML:MR_LOW]   # area just above the footer rule must be empty paper
        if (np.abs(band - np.array(PAPER)).sum(axis=2) > 120).mean() > 0.002:
            errs.append(f"scene {i} ({sc['type']}): content runs into the footer area; shorten text")
    if verbose:
        for e in errs: print("ERROR:", e)
        for w_ in warns: print("WARN:", w_)
        print("OK" if not errs else f"{len(errs)} error(s)")
    return errs, warns

# ---------------------------------------------------------------- audio
SR = 48000
def tts_sentence(text, speed):
    import pyopenjtalk
    x, sr = pyopenjtalk.tts(text, speed=speed)
    if sr != SR:
        import math
        idx = np.arange(0, len(x), sr / SR); x = np.interp(idx, np.arange(len(x)), x)
    return x.astype(np.float32) / 32768.0

def trim(x, thr=0.01):
    idx = np.where(np.abs(x) > thr)[0]
    return x[max(0, idx[0] - 480): idx[-1] + 2400] if len(idx) else x

def tts(text, speed):
    parts = [p for p in re.split(r"(?<=。)", text) if p.strip()]
    gap = np.zeros(int(0.22 * SR), np.float32); out = []
    for i, p in enumerate(parts):
        out.append(trim(tts_sentence(p, speed)))
        if i < len(parts) - 1: out.append(gap)
    return np.concatenate(out)

LEAD, TAIL, MAX_SPEED = 0.25, 0.2, 1.3

def voice_track(story, report=True):
    total = sum(sc["duration"] for sc in story["scenes"])
    out = np.zeros(int(total * SR), np.float32); start = 0.0; problems = []
    for i, sc in enumerate(story["scenes"]):
        room = sc["duration"] - LEAD - TAIL; speed = 1.15
        while True:
            v = tts(sc["narration"], speed)
            if len(v) / SR <= room or speed >= MAX_SPEED: break
            speed = round(speed + 0.05, 2)
        fits = len(v) / SR <= room
        if report:
            print(f"scene {i} {start:5.1f}s speed={speed:.2f} {len(v)/SR:5.2f}s/{room:5.2f}s {'OK' if fits else 'TOO LONG'}  {sc['narration']}")
        if not fits: problems.append(i)
        v = v / (np.abs(v).max() + 1e-9) * 0.9
        j = int((start + LEAD) * SR); out[j:j + len(v)] += v[: len(out) - j]
        start += sc["duration"]
    return out, problems

def bgm(total):
    BEAT = 60 / 112; out = np.zeros(int(total * SR), np.float32)
    note = lambda m: 440 * 2 ** ((m - 69) / 12)
    def env(n, a, r):
        t = np.arange(n) / SR; return np.minimum(1, t / a) * np.exp(-t / r)
    chords = [[48, 55, 59, 64], [45, 52, 55, 60], [41, 48, 52, 57], [43, 50, 55, 59]]
    bar = 4 * BEAT; tb = np.arange(int(bar * SR)) / SR
    for b in range(int(np.ceil(total / bar))):
        ch = chords[b % 4]; s = int(b * bar * SR)
        pad = sum(np.sin(2 * np.pi * note(m + 12) * tb) + 0.3 * np.sin(4 * np.pi * note(m + 12) * tb) for m in ch)
        seg = 0.05 * pad * np.minimum(1, tb / 0.3) * np.minimum(1, (bar - tb) / 0.3)
        for k in (0, 2):
            n = int(BEAT * 1.6 * SR); tt = np.arange(n) / SR; j = int(k * BEAT * SR)
            seg[j:j + n] += (0.22 * np.sin(2 * np.pi * note(ch[0] - 12) * tt) * env(n, 0.005, 0.35))[: len(seg) - j]
        arp = ch + [ch[2] + 12]
        for k in range(8):
            n = int(BEAT * 0.9 * SR); tt = np.arange(n) / SR; f = note(arp[[0, 1, 2, 3, 4, 3, 2, 1][k]] + 12)
            j = int(k * BEAT / 2 * SR)
            seg[j:j + n] += (0.07 * (np.sin(2 * np.pi * f * tt) + 0.4 * np.sin(6 * np.pi * f * tt)) * env(n, 0.002, 0.12))[: len(seg) - j]
        rng = np.random.default_rng(b)
        for k in range(4):
            n = int(0.05 * SR); j = int((k + 0.5) * BEAT * SR)
            seg[j:j + n] += (0.03 * rng.standard_normal(n) * env(n, 0.001, 0.012))[: len(seg) - j]
            n = int(0.25 * SR); tt = np.arange(n) / SR; j = int(k * BEAT * SR)
            seg[j:j + n] += (0.25 * np.sin(2 * np.pi * (50 + 80 * np.exp(-tt / 0.03)) * tt) * env(n, 0.002, 0.09))[: len(seg) - j]
        e = min(len(out), s + len(seg)); out[s:e] += seg[: e - s]
    out /= np.abs(out).max() + 1e-9
    fi, fo = int(0.5 * SR), int(1.5 * SR)
    out[:fi] *= np.linspace(0, 1, fi); out[-fo:] *= np.linspace(1, 0, fo)
    return out

def make_audio(story, path):
    import wave
    v, problems = voice_track(story)
    m = bgm(len(v) / SR)
    act = np.convolve((np.abs(v) > 0.02).astype(np.float32), np.ones(int(0.3 * SR)) / (0.3 * SR), "same")
    mix = 0.85 * v + 0.16 * m * (1 - 0.5 * np.clip(act * 3, 0, 1))
    mix /= max(1.0, np.abs(mix).max() / 0.95)
    st = (np.clip(np.stack([mix, mix], 1), -1, 1) * 32767).astype(np.int16)
    w = wave.open(path, "wb"); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes(st.tobytes()); w.close()
    return problems

# ---------------------------------------------------------------- video
def render_scene(fn, i, dur, path):
    tmp = path[:-4] + ".tmp.mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-pix_fmt", "yuv420p", tmp]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in range(int(round(dur * FPS))):
        p.stdin.write(fn(i, f / FPS).tobytes())
    p.stdin.close()
    if p.wait() != 0: raise SystemExit(f"ffmpeg failed on scene {i}")
    os.replace(tmp, path)

def render(story, outdir):
    errs, _ = check(story)
    if errs: raise SystemExit("fix the errors above before rendering")
    os.makedirs(outdir, exist_ok=True); work = os.path.join(outdir, "_scenes"); os.makedirs(work, exist_ok=True)
    fn = frame_fn(story); files = []
    for i, sc in enumerate(story["scenes"]):
        pth = os.path.join(work, f"s{i:02d}.mp4"); render_scene(fn, i, sc["duration"], pth); files.append(pth)
    lst = os.path.join(work, "list.txt")
    with open(lst, "w") as f:
        for p in files: f.write(f"file '{os.path.abspath(p)}'\n")
    silent = os.path.join(work, "video.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", silent], check=True)
    wav = os.path.join(work, "audio.wav")
    problems = make_audio(story, wav)
    final = os.path.join(outdir, story["output_name"] + ".mp4"); tmp = final[:-4] + ".tmp.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", silent, "-i", wav, "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", tmp], check=True)
    os.replace(tmp, final)
    print("WROTE", final)
    if problems: print("WARN: narration too long in scenes", problems, "(spoken faster than limit; shorten them)")
    return final

def stills(story, outdir):
    os.makedirs(outdir, exist_ok=True); fn = frame_fn(story)
    fn(0, 0.0).save(os.path.join(outdir, "00_first_frame.png"))
    for i, sc in enumerate(story["scenes"]):
        fn(i, sc["duration"] - 0.3).save(os.path.join(outdir, f"{i:02d}_{sc['type']}.png"))
    # contact sheet
    ims = [Image.open(os.path.join(outdir, f"{i:02d}_{sc['type']}.png")).resize((360, 640)) for i, sc in enumerate(story["scenes"])]
    cols = 4; rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (360 * cols, 640 * rows), "white")
    for k, im in enumerate(ims): sheet.paste(im, ((k % cols) * 360, (k // cols) * 640))
    sheet.save(os.path.join(outdir, "contact_sheet.png"))
    print("WROTE stills to", outdir)

if __name__ == "__main__":
    if len(sys.argv) < 3: print(__doc__); sys.exit(1)
    cmd, story = sys.argv[1], load(sys.argv[2])
    if cmd == "check":
        e, _ = check(story); sys.exit(1 if e else 0)
    elif cmd == "stills": stills(story, sys.argv[3])
    elif cmd == "audio":
        pr = make_audio(story, sys.argv[3]); sys.exit(1 if pr else 0)
    elif cmd == "render": render(story, sys.argv[3])
    else: print(__doc__); sys.exit(1)
