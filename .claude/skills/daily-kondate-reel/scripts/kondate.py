#!/usr/bin/env python3
"""Dinner-menu reel renderer (cute style, 1080x1920, 30fps).

  python kondate.py check  story.json          # validate keys, text widths, overflow (no video)
  python kondate.py stills story.json OUTDIR   # one PNG per scene (end state) + contact_sheet.png
  python kondate.py render story.json OUTDIR   # full video OUTDIR/<output_name>.mp4 (narration + BGM)

Scene length follows the narration (lead + voice + tail).
Fonts and the narration voice live in $KONDATE_ASSETS (default ~/.cache/kondate-reel); run setup.sh first.
AI illustrations: story["ai_dir"] (relative to story.json) + story["ai_images"].
See ../references/story-schema.md.
"""
import json, os, re, subprocess, sys, math, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.environ.get("KONDATE_ASSETS", os.path.expanduser("~/.cache/kondate-reel"))
W, H, FPS = 1080, 1920, 30
S = 3  # supersampling for shapes

# ------------------------------------------------------------------ palette
CREAM = (255, 247, 234)
DOT = (252, 232, 212)
COCOA = (92, 60, 44)
COCOA_L = (150, 118, 98)
CORAL = (242, 112, 92)
CORAL_L = (253, 214, 204)
MUSTARD = (246, 186, 66)
MUSTARD_L = (255, 238, 196)
GREEN = (118, 184, 112)
GREEN_D = (64, 136, 72)
SKY = (132, 190, 224)
WHITE = (255, 255, 255)
WOOD = (232, 186, 132)
WOOD_D = (204, 150, 96)
CAT_COL = {"主菜": CORAL, "副菜": GREEN, "汁物": MUSTARD, "主食": SKY}

# ------------------------------------------------------------------ fonts
_fc = {}
def F(kind, size):
    path = {"black": "ZenMaruGothic-Black.ttf", "bold": "ZenMaruGothic-Bold.ttf",
            "med": "ZenMaruGothic-Medium.ttf", "num": "MPLUSRounded1c-ExtraBold.ttf"}[kind]
    k = (kind, size)
    if k not in _fc:
        _fc[k] = ImageFont.truetype(os.path.join(ASSETS, path), size)
    return _fc[k]

def text_img(s, font, fill, stroke=0, stroke_fill=None):
    l, t, r, b = font.getbbox(s, stroke_width=stroke)
    im = Image.new("RGBA", (r - l + 4, b + 6), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((-l + 2, 0), s, font=font, fill=fill,
                            stroke_width=stroke, stroke_fill=stroke_fill)
    return im

def tw(s, font):
    return font.getlength(s)

# ------------------------------------------------------------------ shape helpers (supersampled)
class Canvas:
    """Draw at S× and downsample for smooth edges."""
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.im = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.im)
    def _b(self, box):
        return [v * S for v in box]
    def rrect(self, box, r, fill=None, outline=None, width=0):
        self.d.rounded_rectangle(self._b(box), r * S, fill=fill, outline=outline, width=int(width * S))
    def ellipse(self, box, fill=None, outline=None, width=0):
        self.d.ellipse(self._b(box), fill=fill, outline=outline, width=int(width * S))
    def chord(self, box, a0, a1, fill=None, outline=None, width=0):
        self.d.chord(self._b(box), a0, a1, fill=fill, outline=outline, width=int(width * S))
    def poly(self, pts, fill=None, outline=None, width=0):
        self.d.polygon([(x * S, y * S) for x, y in pts], fill=fill, outline=outline, width=int(width * S))
    def line(self, pts, fill, width, joint="curve"):
        self.d.line([(x * S, y * S) for x, y in pts], fill=fill, width=int(width * S), joint=joint)
        r = width * S / 2
        for x, y in (pts[0], pts[-1]):
            self.d.ellipse((x * S - r, y * S - r, x * S + r, y * S + r), fill=fill)
    def done(self):
        return self.im.resize((self.w, self.h), Image.LANCZOS)

def shadowed(img, dy=10, blur=14, alpha=60):
    """Add a soft warm shadow under an RGBA image."""
    pad = blur * 2
    out = Image.new("RGBA", (img.width + pad * 2, img.height + pad * 2 + dy), (0, 0, 0, 0))
    a = img.split()[3].point(lambda v: v * alpha // 255)
    sh = Image.new("RGBA", img.size, (150, 100, 70, 0)); sh.putalpha(a)
    out.paste(sh, (pad, pad + dy), sh)
    out = out.filter(ImageFilter.GaussianBlur(blur))
    out.alpha_composite(img, (pad, pad))
    out.info["pad"] = pad
    return out

# ------------------------------------------------------------------ dish illustrations
LW = 5
def dish_rice(sz):
    c = Canvas(sz, sz); s = sz
    c.ellipse((0.2 * s, 0.26 * s, 0.8 * s, 0.82 * s), fill=WHITE, outline=COCOA, width=LW)
    for (x, y) in [(0.38, 0.36), (0.52, 0.33), (0.6, 0.42), (0.44, 0.45)]:
        c.ellipse((x * s, y * s, x * s + 0.05 * s, y * s + 0.028 * s), fill=(236, 232, 222))
    c.rrect((0.36 * s, 0.84 * s, 0.64 * s, 0.93 * s), 0.03 * s, fill=CORAL, outline=COCOA, width=LW)
    c.chord((0.1 * s, 0.18 * s, 0.9 * s, 0.92 * s), 0, 180, fill=CORAL, outline=COCOA, width=LW)
    for i in range(5):
        x = 0.24 + i * 0.13
        c.ellipse((x * s, 0.64 * s, x * s + 0.06 * s, 0.64 * s + 0.06 * s), fill=WHITE)
    return c.done()

def dish_soup(sz):
    c = Canvas(sz, sz); s = sz
    c.rrect((0.36 * s, 0.84 * s, 0.64 * s, 0.93 * s), 0.03 * s, fill=(170, 60, 50), outline=COCOA, width=LW)
    c.chord((0.1 * s, 0.2 * s, 0.9 * s, 0.92 * s), 0, 180, fill=(196, 72, 58), outline=COCOA, width=LW)
    c.ellipse((0.1 * s, 0.44 * s, 0.9 * s, 0.68 * s), fill=(222, 168, 96), outline=COCOA, width=LW)
    for (x, y) in [(0.3, 0.5), (0.5, 0.53), (0.62, 0.48)]:
        c.rrect((x * s, y * s, x * s + 0.09 * s, y * s + 0.07 * s), 0.015 * s, fill=WHITE, outline=COCOA, width=2.5)
    for (x, y) in [(0.22, 0.55), (0.42, 0.48), (0.72, 0.56), (0.56, 0.6)]:
        c.ellipse((x * s, y * s, x * s + 0.08 * s, y * s + 0.04 * s), fill=GREEN_D)
    return c.done()

def dish_main(sz):
    c = Canvas(sz, int(sz * 0.8)); s = sz
    c.ellipse((0.03 * s, 0.12 * s, 0.97 * s, 0.76 * s), fill=WHITE, outline=COCOA, width=LW)
    c.ellipse((0.1 * s, 0.17 * s, 0.9 * s, 0.71 * s), outline=SKY, width=4)
    c.ellipse((0.17 * s, 0.22 * s, 0.83 * s, 0.66 * s), fill=(236, 196, 128))
    # napa pieces
    for (x, y, rot) in [(0.24, 0.3, 0), (0.55, 0.26, 1), (0.62, 0.45, 0), (0.3, 0.48, 1), (0.45, 0.38, 0)]:
        w, h = 0.2 * s, 0.11 * s
        x0, y0 = x * s, y * s
        c.rrect((x0, y0, x0 + w, y0 + h), 0.05 * s, fill=(246, 246, 228), outline=COCOA, width=3)
        c.rrect((x0 + (0 if rot else w * 0.55), y0, x0 + (w * 0.45 if rot else w), y0 + h), 0.05 * s, fill=(150, 200, 110))
        c.rrect((x0, y0, x0 + w, y0 + h), 0.05 * s, outline=COCOA, width=3)
    # chicken
    for (x, y) in [(0.33, 0.34), (0.5, 0.47), (0.6, 0.33), (0.4, 0.53), (0.22, 0.4)]:
        c.rrect((x * s, y * s, x * s + 0.15 * s, y * s + 0.09 * s), 0.04 * s, fill=(250, 226, 192), outline=COCOA, width=3)
        c.line([(x * s + 0.03 * s, y * s + 0.03 * s), (x * s + 0.1 * s, y * s + 0.03 * s)], (236, 200, 150), 3)
    for (x, y) in [(0.3, 0.3), (0.52, 0.42), (0.68, 0.52), (0.42, 0.28), (0.6, 0.6)]:
        c.ellipse((x * s, y * s, x * s + 0.025 * s, y * s + 0.025 * s), fill=GREEN_D)
    return c.done()

def dish_shirishiri(sz):
    c = Canvas(sz, int(sz * 0.8)); s = sz
    c.ellipse((0.05 * s, 0.14 * s, 0.95 * s, 0.74 * s), fill=MUSTARD_L, outline=COCOA, width=LW)
    c.ellipse((0.13 * s, 0.2 * s, 0.87 * s, 0.68 * s), fill=WHITE, outline=MUSTARD, width=4)
    rng = np.random.default_rng(3)
    for _ in range(26):
        cx, cy = rng.uniform(0.28, 0.72) * s, rng.uniform(0.3, 0.58) * s
        a = rng.uniform(-0.6, 0.6); L = 0.13 * s
        c.line([(cx - L / 2 * math.cos(a), cy - L / 2 * math.sin(a)), (cx + L / 2 * math.cos(a), cy + L / 2 * math.sin(a))], (244, 128, 48), 6)
    for _ in range(9):
        cx, cy = rng.uniform(0.3, 0.7) * s, rng.uniform(0.32, 0.56) * s
        c.ellipse((cx, cy, cx + 0.07 * s, cy + 0.05 * s), fill=(255, 214, 72), outline=(226, 170, 40), width=2)
    return c.done()

def dish_ohitashi(sz):
    c = Canvas(sz, sz); s = sz
    c.rrect((0.38 * s, 0.84 * s, 0.62 * s, 0.92 * s), 0.03 * s, fill=SKY, outline=COCOA, width=LW)
    c.chord((0.12 * s, 0.22 * s, 0.88 * s, 0.9 * s), 0, 180, fill=SKY, outline=COCOA, width=LW)
    # greens heap above the rim
    for (x, y, w, h) in [(0.2, 0.42, 0.3, 0.17), (0.42, 0.36, 0.3, 0.2), (0.32, 0.3, 0.3, 0.18), (0.5, 0.45, 0.28, 0.13)]:
        c.ellipse((x * s, y * s, (x + w) * s, (y + h) * s), fill=GREEN, outline=COCOA, width=3)
    for (x0, y0, x1, y1) in [(0.3, 0.5, 0.45, 0.4), (0.5, 0.36, 0.64, 0.5), (0.36, 0.34, 0.5, 0.44)]:
        c.line([(x0 * s, y0 * s), (x1 * s, y1 * s)], (250, 250, 236), 5)
    for (x, y) in [(0.4, 0.33), (0.55, 0.4), (0.33, 0.44), (0.47, 0.47)]:
        c.poly([(x * s, y * s), ((x + 0.05) * s, (y - 0.01) * s), ((x + 0.03) * s, (y + 0.03) * s)], fill=(204, 140, 90))
    c.chord((0.12 * s, 0.22 * s, 0.88 * s, 0.9 * s), 0, 180, fill=SKY, outline=COCOA, width=LW)
    for i in range(4):
        x = 0.28 + i * 0.13
        c.ellipse((x * s, 0.66 * s, x * s + 0.05 * s, 0.66 * s + 0.05 * s), fill=WHITE)
    return c.done()

def dish_namul(sz):
    c = Canvas(sz, sz); s = sz
    rng = np.random.default_rng(11)
    c.rrect((0.38 * s, 0.84 * s, 0.62 * s, 0.92 * s), 0.03 * s, fill=MUSTARD_L, outline=COCOA, width=LW)
    c.ellipse((0.2 * s, 0.32 * s, 0.8 * s, 0.66 * s), fill=(250, 246, 226), outline=COCOA, width=3)
    for _ in range(34):
        cx, cy = rng.uniform(0.26, 0.74) * s, rng.uniform(0.36, 0.6) * s
        a = rng.uniform(-0.9, 0.9); L = rng.uniform(0.1, 0.16) * s
        x0, y0 = cx - L / 2 * math.cos(a), cy - L / 2 * math.sin(a)
        x1, y1 = cx + L / 2 * math.cos(a), cy + L / 2 * math.sin(a)
        c.line([(x0, y0), (x1, y1)], (226, 214, 180), 6)
        c.line([(x0, y0), (x1, y1)], (255, 252, 236), 3.5)
        c.ellipse((x1 - 0.012 * s, y1 - 0.012 * s, x1 + 0.012 * s, y1 + 0.012 * s), fill=(236, 214, 130))
    for _ in range(14):
        cx, cy = rng.uniform(0.3, 0.7) * s, rng.uniform(0.36, 0.56) * s
        c.ellipse((cx, cy, cx + 0.014 * s, cy + 0.009 * s), fill=(214, 182, 120))
    for (x, y) in [(0.36, 0.38), (0.58, 0.42)]:
        c.ellipse((x * s, y * s, x * s + 0.07 * s, y * s + 0.035 * s), fill=GREEN)
    c.chord((0.12 * s, 0.22 * s, 0.88 * s, 0.9 * s), 0, 180, fill=MUSTARD_L, outline=COCOA, width=LW)
    for i in range(7):
        x = 0.2 + i * 0.09
        c.line([(x * s, 0.62 * s), ((x + 0.04) * s, 0.7 * s)], MUSTARD, 5)
    return c.done()

def dish_teri(sz):
    c = Canvas(sz, int(sz * 0.82)); s = sz
    c.ellipse((0.03 * s, 0.14 * s, 0.97 * s, 0.78 * s), fill=(70, 96, 150), outline=COCOA, width=LW)
    c.ellipse((0.1 * s, 0.19 * s, 0.9 * s, 0.73 * s), fill=WHITE, outline=(70, 96, 150), width=4)
    c.ellipse((0.16 * s, 0.24 * s, 0.84 * s, 0.68 * s), fill=(214, 150, 80))
    # daikon half-moons
    for (x, y) in [(0.22, 0.34), (0.5, 0.28), (0.6, 0.48), (0.3, 0.5), (0.44, 0.42)]:
        w, h = 0.2 * s, 0.13 * s
        c.chord((x * s, y * s, x * s + w, y * s + h * 2), 180, 360, fill=(240, 208, 150), outline=COCOA, width=3)
    # glazed chicken
    for (x, y) in [(0.36, 0.3), (0.62, 0.36), (0.24, 0.44), (0.48, 0.52), (0.68, 0.52)]:
        c.rrect((x * s, y * s, x * s + 0.14 * s, y * s + 0.1 * s), 0.045 * s, fill=(168, 96, 50), outline=COCOA, width=3)
        c.line([(x * s + 0.03 * s, y * s + 0.028 * s), (x * s + 0.08 * s, y * s + 0.028 * s)], (220, 150, 96), 3)
    for (x, y) in [(0.32, 0.4), (0.55, 0.36), (0.42, 0.6), (0.66, 0.46), (0.5, 0.46)]:
        c.ellipse((x * s, y * s, x * s + 0.028 * s, y * s + 0.028 * s), fill=GREEN_D)
    return c.done()

def dish_goma(sz):
    c = Canvas(sz, sz); s = sz
    rng = np.random.default_rng(5)
    c.rrect((0.38 * s, 0.84 * s, 0.62 * s, 0.92 * s), 0.03 * s, fill=CORAL_L, outline=COCOA, width=LW)
    c.ellipse((0.2 * s, 0.32 * s, 0.8 * s, 0.66 * s), fill=(250, 150, 70), outline=COCOA, width=3)
    for _ in range(30):
        cx, cy = rng.uniform(0.27, 0.73) * s, rng.uniform(0.36, 0.6) * s
        a = rng.uniform(-0.8, 0.8); L = 0.13 * s
        c.line([(cx - L / 2 * math.cos(a), cy - L / 2 * math.sin(a)), (cx + L / 2 * math.cos(a), cy + L / 2 * math.sin(a))], (244, 128, 48), 6)
    for _ in range(40):
        cx, cy = rng.uniform(0.26, 0.74) * s, rng.uniform(0.35, 0.6) * s
        c.ellipse((cx, cy, cx + 0.016 * s, cy + 0.011 * s), fill=(236, 220, 176))
    c.chord((0.12 * s, 0.22 * s, 0.88 * s, 0.9 * s), 0, 180, fill=CORAL_L, outline=COCOA, width=LW)
    for i in range(5):
        x = 0.24 + i * 0.12
        c.ellipse((x * s, 0.66 * s, x * s + 0.05 * s, 0.66 * s + 0.05 * s), fill=CORAL)
    return c.done()

def dish_soup_onion(sz):
    c = Canvas(sz, sz); s = sz
    c.rrect((0.36 * s, 0.84 * s, 0.64 * s, 0.93 * s), 0.03 * s, fill=(170, 60, 50), outline=COCOA, width=LW)
    c.chord((0.1 * s, 0.2 * s, 0.9 * s, 0.92 * s), 0, 180, fill=(196, 72, 58), outline=COCOA, width=LW)
    c.ellipse((0.1 * s, 0.44 * s, 0.9 * s, 0.68 * s), fill=(222, 168, 96), outline=COCOA, width=LW)
    for (x, y) in [(0.25, 0.5), (0.45, 0.47), (0.55, 0.55), (0.33, 0.57), (0.64, 0.49)]:
        c.d.arc([x * s * S, y * s * S, (x + 0.14) * s * S, (y + 0.08) * s * S], 200, 340, fill=(252, 240, 190), width=int(5 * S))
    for (x, y) in [(0.22, 0.55), (0.42, 0.52), (0.7, 0.56), (0.52, 0.6)]:
        c.ellipse((x * s, y * s, x * s + 0.08 * s, y * s + 0.04 * s), fill=GREEN_D)
    return c.done()

# ------------------------------------------------------------------ AI illustrations (cut out from a plain background)
AI_DIR = os.path.join(ASSETS, "ai")  # replaced per story in build_all()
AI_FILES = {}
_cut = {}
def ai_cutout(fname):
    if fname in _cut:
        return _cut[fname]
    from PIL import ImageDraw as _D
    im = Image.open(os.path.join(AI_DIR, fname)).convert("RGB")
    w, h = im.size
    work = im.copy()
    seeds = [(x, 0) for x in range(0, w, 16)] + [(x, h - 1) for x in range(0, w, 16)] + \
            [(0, y) for y in range(0, h, 16)] + [(w - 1, y) for y in range(0, h, 16)]
    for sd in seeds:
        if work.getpixel(sd) != (255, 0, 255):
            _D.floodfill(work, sd, (255, 0, 255), thresh=26)
    a = np.asarray(work).astype(int)
    bgmask = (a[..., 0] == 255) & (a[..., 1] == 0) & (a[..., 2] == 255)
    alpha = Image.fromarray(np.where(bgmask, 0, 255).astype(np.uint8)).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1.6))
    out = im.convert("RGBA"); out.putalpha(alpha)
    out = out.crop(out.getbbox())
    _cut[fname] = out
    return out

def ai_fit(fname, wd):
    im = ai_cutout(fname)
    return im.resize((int(wd), int(im.height * wd / im.width)), Image.LANCZOS)

class _Dishes(dict):
    """Unknown keys fall back to a generic drawing (soup bowl / plate)."""
    def __missing__(self, key):
        k = str(key)
        return self["soup"] if ("soup" in k or "miso" in k or "jiru" in k) else (self["goma"] if "side" in k else self["main"])

DISHES = _Dishes({"rice": dish_rice, "soup": dish_soup, "main": dish_main,
          "shirishiri": dish_shirishiri, "ohitashi": dish_ohitashi, "namul": dish_namul, "teri": dish_teri, "goma": dish_goma, "soup_onion": dish_soup_onion})

LAYOUTS = {
    # key: list of (slot, size_frac, cx, cy)
    5: [("side1", 0.3, 0.2, 0.27), ("side2", 0.25, 0.48, 0.27), ("main", 0.42, 0.75, 0.3), ("rice", 0.33, 0.27, 0.63), ("soup", 0.33, 0.7, 0.63)],
    4: [("side1", 0.3, 0.24, 0.27), ("main", 0.46, 0.68, 0.29), ("rice", 0.33, 0.27, 0.63), ("soup", 0.33, 0.7, 0.63)],
}
TRAY = {"side1": "shirishiri", "side2": "namul", "main": "main", "rice": "rice", "soup": "soup"}

def tray(wd):
    """Meal on a wooden tray. Returns (image, steam anchors)."""
    if "tray" in AI_FILES:
        return ai_fit(AI_FILES["tray"], wd), []
    hh = int(wd * 0.78)
    c = Canvas(wd, hh)
    c.rrect((0.02 * wd, 0.06 * hh, 0.98 * wd, 0.96 * hh), 0.06 * wd, fill=WOOD, outline=COCOA, width=LW)
    c.rrect((0.06 * wd, 0.11 * hh, 0.94 * wd, 0.91 * hh), 0.04 * wd, fill=(240, 200, 150))
    for k in range(5):
        y = (0.2 + 0.15 * k) * hh
        c.line([(0.12 * wd, y), (0.42 * wd, y + 6)], WOOD_D, 3)
        c.line([(0.6 * wd, y + 20), (0.88 * wd, y + 14)], WOOD_D, 3)
    base = c.done()
    cs = Canvas(wd, hh)
    cs.line([(0.14 * wd, 0.9 * hh), (0.86 * wd, 0.86 * hh)], (196, 72, 58), 9)
    cs.line([(0.14 * wd, 0.935 * hh), (0.86 * wd, 0.905 * hh)], (196, 72, 58), 9)
    cs.rrect((0.06 * wd, 0.87 * hh, 0.15 * wd, 0.96 * hh), 0.015 * wd, fill=WHITE, outline=COCOA, width=3)
    base.alpha_composite(cs.done())
    slots = [k for k in TRAY if TRAY[k]]
    steam = []
    for slot, frac, cx, cy in LAYOUTS[len(slots)]:
        img = DISHES[TRAY[slot]](int(frac * wd))
        base.alpha_composite(img, (int(cx * wd - img.width / 2), int(cy * hh - img.height / 2)))
        if slot == "main":
            steam.append((cx * wd, (cy * hh - img.height / 2) + 0.02 * hh))
        if slot == "soup":
            steam.append((cx * wd, 0.6 * hh))
    return base, steam

def steam_img(phase, scale=1.0):
    w, h = int(120 * scale), int(110 * scale)
    c = Canvas(w, h)
    for k, x in enumerate((0.25, 0.5, 0.75)):
        pts = []
        ph = phase * 2 * math.pi + k * 1.7
        for i in range(12):
            yy = h * (0.95 - 0.8 * i / 11)
            xx = w * x + math.sin(ph + i * 0.55) * w * 0.07
            pts.append((xx, yy))
        alpha = int(150 * (0.5 + 0.5 * math.sin(ph)))
        c.line(pts, (190, 150, 128, alpha), 6 * scale)
    return c.done()
STEAM = [steam_img(i / 16) for i in range(16)]

# ------------------------------------------------------------------ background
def background():
    im = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(im)
    for r, y in enumerate(range(260, H - 120, 64)):
        for x in range(32 + (32 if r % 2 else 0), W, 64):
            d.ellipse((x - 5, y - 5, x + 5, y + 5), fill=DOT)
    # gingham bands
    def gingham(y0, y1):
        q = 30
        band = np.full((y1 - y0, W, 3), 255, np.float32)
        col = np.array(CORAL, np.float32)
        yy, xx = np.mgrid[0:y1 - y0, 0:W]
        a = ((xx // q) % 2 == 0).astype(np.float32) * 0.28 + ((yy // q) % 2 == 0).astype(np.float32) * 0.28
        band = band * (1 - a[..., None]) + col * a[..., None]
        im.paste(Image.fromarray(band.astype(np.uint8)), (0, y0))
    gingham(0, 150)
    gingham(H - 110, H)
    c = Canvas(W, 60)
    for x in range(-20, W + 40, 60):
        c.ellipse((x, -30, x + 60, 30), fill=WHITE)
    sc = c.done()
    im.paste(sc, (0, 150), sc)
    flipped = sc.transpose(Image.FLIP_TOP_BOTTOM)
    im.paste(flipped, (0, H - 110 - 60), flipped)
    return im
BG = None

# ------------------------------------------------------------------ building blocks
def chip(label, color=CORAL, size=40):
    f = F("black", size)
    w = int(tw(label, f)) + 64; h = size + 34
    c = Canvas(w, h); c.rrect((0, 0, w, h), h / 2, fill=color)
    im = c.done(); t = text_img(label, f, WHITE)
    im.alpha_composite(t, ((w - t.width) // 2, (h - size) // 2 - 6))
    return im

def card(w, h, fill=WHITE, r=44, border=None):
    c = Canvas(w, h); c.rrect((0, 0, w, h), r, fill=fill, outline=border, width=4 if border else 0)
    return c.done()

def circle_badge(lines, d, color, fg=WHITE, sizes=None, rot=0):
    c = Canvas(d, d); c.ellipse((0, 0, d, d), fill=color)
    c.ellipse((10, 10, d - 10, d - 10), outline=(255, 255, 255, 200), width=4)
    im = c.done()
    sizes = sizes or [int(d * 0.2)] * len(lines)
    total = sum(int(s * 1.15) for s in sizes); y = (d - total) // 2 - 4
    for s_, sz in zip(lines, sizes):
        t = text_img(s_, F("black", sz), fg)
        im.alpha_composite(t, ((d - t.width) // 2, y)); y += int(sz * 1.15)
    return im.rotate(rot, resample=Image.BICUBIC, expand=True) if rot else im

NO_START = set("、。，．・：；？！ー」』）】〕〉》％%…")
def wrap(text, font, width):
    out, line = [], ""
    for ch in text:
        if tw(line + ch, font) <= width or not line or ch in NO_START:
            line += ch
        else:
            out.append(line); line = ch
    out.append(line)
    return out

# ------------------------------------------------------------------ scene composition
class Scene:
    def __init__(self):
        self.els = []      # (img, x, y, t0, kind)
        self.steam = []    # (x, y, scale, t0)
    def steam_add(self, xys):
        t0 = self.els[-1][3] + AN if self.els else 0
        self.steam.append(xys + (t0,))
    def add(self, img, x, y, t0=0.0, kind="up", center=False):
        if center:
            x, y = x - img.width // 2, y - img.height // 2
        self.els.append((img, int(x), int(y), t0, kind))
        return img
    def add_shadowed(self, img, x, y, t0=0.0, kind="pop", **kw):
        sh = shadowed(img, **kw); p = sh.info["pad"]
        self.els.append((sh, int(x - p), int(y - p), t0, kind))

AN = 0.5
def ease_back(t):
    c1 = 1.70158; c3 = c1 + 1
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2
def ease_out(t):
    return 1 - (1 - t) ** 4

def header(sc, label, color=CORAL, date=None, t0=0.0):
    sc.add(chip(label, color), 70, 205, t0, "pop")
    if date:
        t = text_img(date, F("bold", 34), COCOA_L)
        sc.add(t, W - 72 - t.width, 222, t0, "up")

def title_text(sc, s, y, size=92, t0=0.1, color=COCOA):
    t = text_img(s, F("black", size), color)
    sc.add(t, 70, y, t0, "up")
    return y + int(size * 1.3)

# ---- hook (thumbnail): fully visible from frame 0
def build_hook(st, d):
    sc = Scene(); T = -9
    sc.add(chip(st["series"], CORAL, 40), 70, 205, T, "none")
    t = text_img(st["date_long"], F("bold", 36), COCOA_L); sc.add(t, W - 72 - t.width, 220, T, "none")
    top = 300 if st.get("dish_line") else 320
    t = text_img("きょうの", F("black", 96), COCOA); sc.add(t, W // 2 - t.width // 2, top, T, "none")
    t = text_img("夕ごはん", F("black", 170), CORAL, stroke=10, stroke_fill=WHITE)
    sc.add(t, W // 2 - t.width // 2, top + 105, T, "none")
    ty = 700
    if st.get("dish_line"):
        dl = chip(st["dish_line"], COCOA, 40); sc.add(dl, W // 2 - dl.width // 2, top + 338, T, "none"); ty = 740
    tr, steam = tray(900)
    sc.add_shadowed(tr, 90, ty, T, "none", dy=14, blur=18, alpha=70)
    for (x, y) in steam:
        sc.steam_add((90 + x - 60, ty + y - 100, 1.0))
    # info row
    y0 = 1440
    xx = 90
    for lab, col in [(st.get("style", "一汁三菜"), GREEN), ("1000円以内", MUSTARD)]:
        c = chip(lab, col, 46); sc.add(c, xx, y0 + 30, T, "none"); xx += c.width + 24
    b = circle_badge(st.get("price_badge", ["4人分で", "約950円"]), 300, CORAL, sizes=[44, 62], rot=-8)
    sc.add(b, 700, y0 - 120, T, "none")
    return sc

# ---- menu overview
def build_menu(st, d):
    sc = Scene(); header(sc, d["chip"], CORAL, st["date_label"])
    title_text(sc, d["title"], 300, 96)
    tr, steam = tray(760)
    sc.add_shadowed(tr, 160, 450, 0.25, "pop", dy=12, blur=16, alpha=60)
    for (x, y) in steam:
        sc.steam_add((160 + x - 60, 450 + y - 100, 0.85))
    y = 1080
    for k, it in enumerate(d["items"]):
        col = CAT_COL[it["cat"]]
        row = Image.new("RGBA", (900, 84), (0, 0, 0, 0))
        c = chip(it["cat"], col, 32); row.alpha_composite(c, (0, 8))
        t = text_img(it["name"], F("bold", 46), COCOA); row.alpha_composite(t, (c.width + 24, 10))
        sc.add(row, 90, y + k * 92, 0.6 + 0.18 * k, "up")
    return sc

# ---- main dish
def build_main(st, d):
    sc = Scene(); header(sc, d["chip"], CORAL, st["date_label"])
    y = 300
    for k, s in enumerate(d["title"]):
        y = title_text(sc, s, y, 84 if k == 0 else 110, 0.08 + 0.08 * k, COCOA if k == 0 else CORAL) - 6
    plate = DISHES[d.get("dish", "main")](620)
    sc.add_shadowed(plate, 230, 560, 0.3, "pop", dy=12, blur=16, alpha=60)
    if d.get("dish", "main") not in AI_FILES:
        sc.steam_add((230 + 310 - 60, 560 - 20, 1.1))
    b = circle_badge([d["price"]], 230, MUSTARD, fg=COCOA, sizes=[50], rot=8)
    sc.add(b, 760, 520, 0.6, "pop")
    y = 1090
    for k, p in enumerate(d["points"]):
        cw, ch = 940, 128
        cd = card(cw, ch)
        n = circle_badge([str(k + 1)], 76, CORAL, sizes=[42]); cd.alpha_composite(n, (28, (ch - 76) // 2))
        t = text_img(p, F("bold", 42), COCOA); cd.alpha_composite(t, (128, (ch - 52) // 2))
        sc.add_shadowed(cd, 70, y + k * 148, 0.9 + 0.22 * k, "up", dy=6, blur=10, alpha=40)
    return sc

# ---- two cards
def build_pair(st, d):
    sc = Scene(); header(sc, d["chip"], GREEN if "副菜" in d["chip"] else MUSTARD, st["date_label"])
    title_text(sc, d["title"], 300, 90)
    for k, cdat in enumerate(d["cards"]):
        cw, ch = 940, 500
        cd = card(cw, ch)
        dish = DISHES[cdat["dish"]](380)
        cd.alpha_composite(dish, (20, (ch - dish.height) // 2 - 10))
        x = 410
        longest = max(cdat["name"].split("\n"), key=len)
        nf = F("black", 54 if tw(longest, F("black", 54)) <= cw - x - 30 else 46)
        lines = cdat["name"].split("\n") if "\n" in cdat["name"] else wrap(cdat["name"], nf, cw - x - 40)
        yy = 70
        for ln in lines:
            t = text_img(ln, nf, COCOA); cd.alpha_composite(t, (x, yy)); yy += int(nf.size * 1.25)
        p = chip(cdat["price"], CORAL, 40); cd.alpha_composite(p, (x, yy + 14)); yy += p.height + 44
        for ln in cdat["desc"]:
            t = text_img(ln, F("med", 34), COCOA_L); cd.alpha_composite(t, (x, yy)); yy += 50
        sc.add_shadowed(cd, 70, 440 + k * 540, 0.35 + 0.45 * k, "pop", dy=8, blur=12, alpha=45)
        if cdat["dish"] in ("soup", "soup_onion") and cdat["dish"] not in AI_FILES:
            sc.steam_add((70 + 20 + 190 - 60, 440 + k * 540 + 40, 0.9))
    return sc

# ---- how-to (3 steps for the main dish)
def build_howto(st, d):
    sc = Scene(); header(sc, d["chip"], CORAL, st["date_label"])
    title_text(sc, d["title"], 300, 96)
    y0, gap = 480, 230
    cols = [CORAL, MUSTARD, GREEN]
    for k, s_ in enumerate(d["steps"]):
        cd = card(940, 190)
        n = circle_badge([str(k + 1)], 110, cols[k % 3], sizes=[60]); cd.alpha_composite(n, (34, 40))
        lines = s_.split("\n")
        yy = 95 - len(lines) * 32
        for ln in lines:
            t = text_img(ln, F("bold", 46), COCOA); cd.alpha_composite(t, (172, yy)); yy += 64
        sc.add_shadowed(cd, 70, y0 + k * gap, 0.4 + 0.35 * k, "up", dy=6, blur=10, alpha=40)
    if d.get("tip"):
        tp = chip(d["tip"], MUSTARD, 42)
        sc.add(tp, W // 2 - tp.width // 2, y0 + 3 * gap + 20, 0.4 + 0.35 * 3, "pop")
    return sc

# ---- cost receipt
def build_cost(st, d):
    sc = Scene(); header(sc, d["chip"], MUSTARD, st["date_label"])
    title_text(sc, d["title"], 300, 96)
    cw, ch = 940, 280 + len(d["rows"]) * 100
    c = Canvas(cw, ch + 30)
    c.rrect((0, 0, cw, ch), 30, fill=WHITE)
    zig = [(0, ch - 20)] + [(x, ch + (14 if (x // 30) % 2 else -6)) for x in range(0, cw + 1, 30)] + [(cw, ch - 20)]
    c.poly(zig, fill=WHITE)
    rc = c.done()
    sc.add_shadowed(rc, 70, 460, 0.2, "pop", dy=8, blur=12, alpha=45)
    y = 530
    for k, (name, price) in enumerate(d["rows"]):
        row = Image.new("RGBA", (860, 90), (0, 0, 0, 0)); rd = ImageDraw.Draw(row)
        t = text_img(name, F("bold", 40), COCOA); row.alpha_composite(t, (0, 14))
        p = text_img(price, F("num", 46), COCOA); row.alpha_composite(p, (860 - p.width, 8))
        for x in range(t.width + 20, 860 - p.width - 20, 18):
            rd.ellipse((x, 46, x + 6, 52), fill=LIGHT_DOT)
        sc.add(row, 110, y + k * 100, 0.5 + 0.16 * k, "up")
    y2 = y + len(d["rows"]) * 100 + 10
    line = Image.new("RGBA", (860, 8), (0, 0, 0, 0)); ld = ImageDraw.Draw(line)
    for x in range(0, 860, 28):
        ld.rectangle((x, 2, x + 16, 6), fill=COCOA_L)
    sc.add(line, 110, y2, 1.4, "up")
    t = text_img("合計", F("black", 56), COCOA); sc.add(t, 110, y2 + 60, 1.5, "up")
    tot = text_img(d["total"], F("num", 120), CORAL); sc.add(tot, 970 - tot.width - 10, y2 + 20, 1.55, "pop")
    b = circle_badge(d["stamp"], 250, CORAL, sizes=[52, 44], rot=-12)
    sc.add(b, 740, 280, 2.0, "stamp")
    sc.stamp_t = 2.0
    n = text_img(st["note"], F("med", 28), COCOA_L); sc.add(n, W // 2 - n.width // 2, 460 + ch + 60, 1.8, "up")
    return sc
LIGHT_DOT = (214, 196, 180)

# ---- shopping list
def build_shopping(st, d):
    sc = Scene(); header(sc, d["chip"], GREEN, st["date_label"])
    title_text(sc, d["title"], 300, 96)
    n = len(d["items"]); rh = 92; cw, ch = 940, 80 + n * rh
    c = Canvas(cw, ch); c.rrect((0, 0, cw, ch), 36, fill=WHITE)
    for k in range(n):
        y = 40 + (k + 1) * rh
        if k < n - 1:
            c.line([(40, y), (cw - 40, y)], (238, 226, 214), 2)
    for k in range(6):
        c.ellipse((cw / 2 - 150 + k * 60, -14, cw / 2 - 150 + k * 60 + 28, 14), fill=CREAM)
    sc.add_shadowed(c.done(), 70, 440, 0.2, "pop", dy=8, blur=12, alpha=45)
    for k, (name, qty) in enumerate(d["items"]):
        row = Image.new("RGBA", (860, rh), (0, 0, 0, 0))
        bx = Canvas(48, 48); bx.rrect((2, 2, 46, 46), 10, outline=GREEN, width=4); row.alpha_composite(bx.done(), (0, 20))
        t = text_img(name, F("bold", 44), COCOA); row.alpha_composite(t, (72, 14))
        q = text_img(qty, F("med", 38), COCOA_L); row.alpha_composite(q, (860 - q.width, 20))
        sc.add(row, 110, 440 + 40 + k * rh, 0.5 + 0.1 * k, "up")
    rb = chip(d["ribbon"], MUSTARD, 40)
    sc.add(rb, W // 2 - rb.width // 2, 440 + ch + 40, 0.5 + 0.1 * n + 0.2, "pop")
    return sc

# ---- steps
def build_steps(st, d):
    sc = Scene(); header(sc, d["chip"], SKY, st["date_label"])
    title_text(sc, d["title"], 300, 96)
    b = circle_badge(d["badge"], 230, MUSTARD, fg=COCOA, sizes=[36, 54], rot=8)
    sc.add(b, 770, 250, 0.4, "pop")
    y0, gap = 560, 180
    n = len(d["steps"])
    dl = Image.new("RGBA", (12, gap * (n - 1)), (0, 0, 0, 0)); dd = ImageDraw.Draw(dl)
    for yy in range(0, dl.height, 26):
        dd.ellipse((1, yy, 11, yy + 10), fill=LIGHT_DOT)
    sc.add(dl, 70 + 50 - 6, y0 + 50, 0.3, "fade")
    cols = [SKY, CORAL, GREEN, MUSTARD, CORAL]
    for k, s_ in enumerate(d["steps"]):
        circ = circle_badge([str(k + 1)], 100, cols[k % len(cols)], sizes=[54])
        sc.add(circ, 70, y0 + k * gap, 0.5 + 0.25 * k, "pop")
        cd = card(780, 118)
        t = text_img(s_, F("bold", 42), COCOA); cd.alpha_composite(t, (36, (118 - 52) // 2))
        sc.add_shadowed(cd, 200, y0 + k * gap - 9, 0.55 + 0.25 * k, "up", dy=6, blur=10, alpha=40)
    return sc

# ---- outro
def build_outro(st, d):
    sc = Scene()
    sc.add(chip(st["series"], CORAL, 40), W // 2 - chip(st["series"], CORAL, 40).width // 2, 260, 0.0, "pop")
    y = 380
    for k, s_ in enumerate(d["title"]):
        t = text_img(s_, F("black", 112), COCOA if k == 0 else CORAL, stroke=8 if k else 0, stroke_fill=WHITE)
        sc.add(t, W // 2 - t.width // 2, y, 0.1 + 0.1 * k, "up"); y += 150
    tr, steam = tray(620)
    sc.add_shadowed(tr, W // 2 - 310, 720, 0.3, "pop", dy=12, blur=16, alpha=60)
    for (x, yy) in steam:
        sc.steam_add((W // 2 - 310 + x - 50, 720 + yy - 90, 0.75))
    y = 1240
    for s_ in d["sub"]:
        t = text_img(s_, F("bold", 44), COCOA); sc.add(t, W // 2 - t.width // 2, y, 0.6, "up"); y += 64
    c = chip(d["cta"], MUSTARD, 46); sc.add(c, W // 2 - c.width // 2, y + 30, 0.8, "pop")
    if d.get("handle"):
        h = text_img(d["handle"], F("num", 44), CORAL); sc.add(h, W // 2 - h.width // 2, y + 128, 0.85, "up"); y += 60
    n = text_img(d["ai_note"], F("med", 28), COCOA_L); sc.add(n, W // 2 - n.width // 2, y + 150, 0.9, "up")
    return sc

BUILD = {"howto": build_howto, "hook": build_hook, "menu": build_menu, "main": build_main, "pair": build_pair, "cost": build_cost,
         "shopping": build_shopping, "steps": build_steps, "outro": build_outro}

# ------------------------------------------------------------------ frame rendering
def place(frame, el, t):
    img, x, y, t0, kind = el
    if kind == "none" or t >= t0 + AN:
        frame.alpha_composite(img, (x, y)); return
    if t < t0:
        return
    p = (t - t0) / AN
    a = min(1.0, p * 2.2)
    if kind == "up":
        off = int((1 - ease_out(p)) * 40)
        im = img if a >= 1 else _alpha(img, a)
        frame.alpha_composite(im, (x, y + off))
    elif kind == "fade":
        frame.alpha_composite(_alpha(img, ease_out(p)), (x, y))
    else:  # pop / stamp
        s = ease_back(p) if kind == "pop" else (1.6 - 0.6 * ease_out(p))
        s = max(0.05, s)
        w, h = max(1, int(img.width * s)), max(1, int(img.height * s))
        im = img.resize((w, h), Image.BILINEAR)
        if a < 1: im = _alpha(im, a)
        cx, cy = x + img.width / 2, y + img.height / 2
        frame.alpha_composite(im, (int(cx - w / 2), int(cy - h / 2)))

def _alpha(img, a):
    im = img.copy(); im.putalpha(img.split()[3].point(lambda v: int(v * a))); return im

def scene_renderer(sc, dur, gstart):
    static_after = max([el[3] + AN for el in sc.els if el[4] != "none"] + [0])
    bg = BG.convert("RGBA"); cache = {}
    def fn(f):
        t = f / FPS
        if t >= static_after and "s" in cache:
            fr = cache["s"].copy()
        else:
            fr = bg.copy()
            for el in sc.els: place(fr, el, t)
            if t >= static_after: cache["s"] = fr.copy()
        gi = int((gstart + t) * 8) % len(STEAM)
        for (x, y, s, st0) in sc.steam:
            if t < st0: continue
            stm = STEAM[gi] if s == 1.0 else STEAM[gi].resize((int(120 * s), int(110 * s)), Image.BILINEAR)
            fr.alpha_composite(stm, (int(x), int(y)))
        a = min(1.0, (dur - t) / 0.2)
        out = fr.convert("RGB")
        if a < 1: out = Image.blend(BG, out, max(0.0, a))
        return out
    return fn

# ------------------------------------------------------------------ audio
SR = 48000
VOICE = os.path.join(ASSETS, "tohoku-f01-happy.htsvoice")
_eng = None
def tts(text, speed=1.12):
    global _eng
    import pyopenjtalk
    from pyopenjtalk.htsengine import HTSEngine
    if _eng is None:
        _eng = HTSEngine(VOICE.encode())
    out = []
    for p in [p for p in re.split(r"(?<=。)", text) if p.strip()]:
        _eng.set_speed(speed)
        x = _eng.synthesize(pyopenjtalk.extract_fullcontext(p)); _eng.refresh()
        x = np.asarray(x, np.float32) / 32768.0
        idx = np.where(np.abs(x) > 0.01)[0]
        if len(idx): x = x[max(0, idx[0] - 480): idx[-1] + 2400]
        out += [x, np.zeros(int(0.2 * SR), np.float32)]
    return np.concatenate(out[:-1])

LEAD, TAIL = 0.35, 0.75
def plan(story):
    voices, durs = [], []
    for sc in story["scenes"]:
        v = tts(sc["narration"]); voices.append(v)
        dur = max(sc.get("min_duration", 3.0), LEAD + len(v) / SR + TAIL)
        durs.append(math.ceil(dur * FPS) / FPS)
    return voices, durs

def bgm(total):
    """Light, bouncy music-box loop in F major (F–Dm–B♭–C)."""
    BPM = 104; BEAT = 60 / BPM; out = np.zeros(int(total * SR) + SR, np.float32)
    note = lambda m: 440 * 2 ** ((m - 69) / 12)
    def tone(f, n, a=0.004, r=0.25, harm=((1, 1.0), (2, 0.3), (3, 0.12))):
        tt = np.arange(n) / SR
        w = sum(g * np.sin(2 * np.pi * f * h * tt) for h, g in harm)
        return w * np.minimum(1, tt / a) * np.exp(-tt / r)
    chords = [[53, 57, 60], [50, 53, 57], [46, 50, 53], [48, 52, 55]]
    melody = [[72, 69, 72, 74, 72, 69, 67, 69], [69, 65, 69, 72, 69, 65, 64, 65],
              [70, 69, 67, 65, 67, 69, 70, 72], [72, 74, 72, 70, 69, 67, 64, 67]]
    bar = 4 * BEAT
    for b in range(int(np.ceil(total / bar)) + 1):
        ch = chords[b % 4]; s0 = int(b * bar * SR)
        def add(sig, at):
            j = s0 + int(at * SR); e = min(len(out), j + len(sig))
            if j < len(out): out[j:e] += sig[: e - j]
        for k in range(4):  # bass pluck on each beat, root/fifth
            m = ch[0] - 12 if k % 2 == 0 else ch[0] - 5
            add(0.26 * tone(note(m), int(0.6 * SR), r=0.18, harm=((1, 1), (2, 0.5))), k * BEAT)
        for k in (1, 3):  # soft chord stabs (ukulele-ish)
            for i, m in enumerate(ch):
                add(0.07 * tone(note(m + 12), int(0.5 * SR), r=0.14, harm=((1, 1), (2, 0.6), (4, 0.2))), k * BEAT + 0.012 * i)
        for k, m in enumerate(melody[b % 4]):  # music-box melody, 8th notes
            if (b // 4) % 2 == 1 and k % 2 == 1: continue
            add(0.11 * tone(note(m + 12), int(0.9 * SR), r=0.35, harm=((1, 1), (2.76, 0.25), (5.4, 0.08))), k * BEAT / 2)
        rng = np.random.default_rng(b)
        for k in range(8):  # shaker
            n = int(0.04 * SR); tt = np.arange(n) / SR
            add((0.025 if k % 2 else 0.04) * rng.standard_normal(n) * np.exp(-tt / 0.012), k * BEAT / 2)
    out = out[: int(total * SR)]
    out /= np.abs(out).max() + 1e-9
    fi, fo = int(0.3 * SR), int(1.2 * SR)
    out[:fi] *= np.linspace(0, 1, fi); out[-fo:] *= np.linspace(1, 0, fo)
    return out

def chime(n=int(0.8 * SR)):
    tt = np.arange(n) / SR; out = np.zeros(n, np.float32)
    for i, m in enumerate([84, 88, 91]):
        f = 440 * 2 ** ((m - 69) / 12); j = int(i * 0.07 * SR)
        seg = np.sin(2 * np.pi * f * tt[: n - j]) * np.exp(-tt[: n - j] / 0.25)
        out[j:] += seg
    return out / 3

def make_audio(story, voices, durs, stamp_times, path):
    total = sum(durs); vt = np.zeros(int(total * SR), np.float32); fx = np.zeros_like(vt); t = 0.0
    for v, d in zip(voices, durs):
        v = v / (np.abs(v).max() + 1e-9) * 0.9
        j = int((t + LEAD) * SR); vt[j:j + len(v)] += v[: len(vt) - j]; t += d
    for st in stamp_times:
        c = chime(); j = int(st * SR); fx[j:j + len(c)] += c[: len(fx) - j]
    m = bgm(total)
    act = np.convolve((np.abs(vt) > 0.02).astype(np.float32), np.ones(int(0.3 * SR)) / (0.3 * SR), "same")
    mix = 0.85 * vt + 0.2 * m * (1 - 0.45 * np.clip(act * 3, 0, 1)) + 0.25 * fx
    mix /= max(1.0, np.abs(mix).max() / 0.95)
    stv = (np.clip(np.stack([mix, mix], 1), -1, 1) * 32767).astype(np.int16)
    w = wave.open(path, "wb"); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(stv.tobytes()); w.close()

# ------------------------------------------------------------------ commands
def build_all(story):
    global BG
    if BG is None: BG = background()
    if "tray" in story:
        TRAY.clear(); TRAY.update(story["tray"])
    global AI_DIR
    if story.get("ai_dir"):
        AI_DIR = story["ai_dir"] if os.path.isabs(story["ai_dir"]) else os.path.join(story.get("_base", "."), story["ai_dir"])
    for key, fname in story.get("ai_images", {}).items():
        AI_FILES[key] = fname
        if key != "tray":
            DISHES[key] = (lambda f: (lambda sz: ai_fit(f, sz)))(fname)
    return [BUILD[d["type"]](story, d) for d in story["scenes"]]

def check(story):
    errs = []
    for k in ("output_name", "series", "style", "date_label", "date_long", "dish_line", "price_badge", "note", "tray", "scenes"):
        if k not in story: errs.append(f"missing top-level key: {k}")
    if errs:
        for e in errs: print("ERROR:", e)
        return errs
    if tw(story["dish_line"], F("black", 40)) > 880: errs.append("dish_line too long (max ~20 chars)")
    if re.search(r"鶏(?!も|む)", "".join(sc.get("narration", "") for sc in story["scenes"])): errs.append("narration: write 鶏 as とり (pyopenjtalk reads 鶏 as ニワトリ)")
    types = [sc.get("type") for sc in story["scenes"]]
    if types[0] != "hook": errs.append("first scene must be hook")
    if types[-1] != "outro": errs.append("last scene must be outro")
    for i, sc in enumerate(story["scenes"]):
        tag = f"scene {i} ({sc.get('type')})"
        if sc.get("type") not in BUILD: errs.append(f"{tag}: unknown type"); continue
        if not sc.get("narration"): errs.append(f"{tag}: missing narration")
        if re.search(r"[0-9０-９]", sc.get("narration", "")): errs.append(f"{tag}: narration has digits; write numbers in kanji/kana")
        t = sc["type"]
        if "title" in sc and isinstance(sc["title"], str) and tw(sc["title"], F("black", 90 if t == "pair" else 96)) > W - 140 - (260 if t in ("cost", "steps") else 0):
            errs.append(f"{tag}: title too wide: {sc['title']}")
        if t == "main":
            if tw(sc["title"][0], F("black", 84)) > 900 or tw(sc["title"][1], F("black", 110)) > 900: errs.append(f"{tag}: title line too wide")
            for p in sc["points"]:
                if tw(p, F("bold", 42)) > 940 - 160: errs.append(f"{tag}: point too long: {p}")
        if t == "menu":
            for it in sc["items"]:
                if tw(it["name"], F("bold", 46)) > 900 - 140: errs.append(f"{tag}: item name too long: {it['name']}")
        if t == "pair":
            for cd in sc["cards"]:
                for ln in cd["name"].split("\n"):
                    if tw(ln, F("black", 46)) > 940 - 410 - 30: errs.append(f"{tag}: card name line too long (add \\n): {ln}")
                for ln in cd["desc"]:
                    if tw(ln, F("med", 34)) > 940 - 410 - 30: errs.append(f"{tag}: card desc too long: {ln}")
                pass
        if t == "howto":
            for st_ in sc["steps"]:
                for ln in st_.split("\n"):
                    if tw(ln, F("bold", 46)) > 940 - 172 - 30: errs.append(f"{tag}: step line too long (add \\n): {ln}")
        if t in ("steps",):
            for st_ in sc["steps"]:
                if tw(st_, F("bold", 42)) > 780 - 60: errs.append(f"{tag}: step too long: {st_}")
        if t == "cost":
            for name, price in sc["rows"]:
                if tw(name, F("bold", 40)) + tw(price, F("num", 46)) > 860 - 60: errs.append(f"{tag}: row too long: {name}")
        if t == "shopping" and len(sc["items"]) > 10: errs.append(f"{tag}: max 10 shopping items")
    for key, fname in story.get("ai_images", {}).items():
        base = story["ai_dir"] if os.path.isabs(story.get("ai_dir", "")) else os.path.join(story.get("_base", "."), story.get("ai_dir", ""))
        if not os.path.exists(os.path.join(base, fname)): errs.append(f"ai image missing: {key} -> {fname}")
    if not errs:
        scenes = build_all(story)
        bg = np.asarray(BG).astype(int)
        for i, sc in enumerate(scenes):
            fr = np.asarray(scene_renderer(sc, 6.0, 0)(int(5.5 * FPS))).astype(int)
            band = np.abs(fr[1680:1790] - bg[1680:1790]).sum(axis=2) > 60
            right = np.abs(fr[250:1600, 1040:] - bg[250:1600, 1040:]).sum(axis=2) > 60
            if band.mean() > 0.003: errs.append(f"scene {i} ({story['scenes'][i]['type']}): content runs into the bottom area (y>1680); shorten")
            if right.mean() > 0.003: errs.append(f"scene {i} ({story['scenes'][i]['type']}): content touches the right edge; shorten")
    for e in errs: print("ERROR:", e)
    print("OK" if not errs else f"{len(errs)} error(s)")
    return errs

def stills(story, outdir, durs=None):
    os.makedirs(outdir, exist_ok=True)
    scenes = build_all(story)
    durs = durs or [6.0] * len(scenes)
    g = 0.0; ims = []
    for i, (sc, d) in enumerate(zip(scenes, durs)):
        fn = scene_renderer(sc, d, g)
        im = fn(int((d - 0.4) * FPS)); im.save(os.path.join(outdir, f"{i:02d}_{story['scenes'][i]['type']}.png"))
        ims.append(im.resize((360, 640))); g += d
    cols = 5; rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (360 * cols, 640 * rows), "white")
    for k, im in enumerate(ims): sheet.paste(im, ((k % cols) * 360, (k // cols) * 640))
    sheet.save(os.path.join(outdir, "contact_sheet.png"))
    print("WROTE stills to", outdir)

def render(story, outdir):
    if check(story): raise SystemExit("fix the errors above before rendering")
    os.makedirs(outdir, exist_ok=True); work = os.path.join(outdir, "_scenes"); os.makedirs(work, exist_ok=True)
    voices, durs = plan(story)
    for i, (v, d) in enumerate(zip(voices, durs)):
        print(f"scene {i} {story['scenes'][i]['type']:9s} voice {len(v)/SR:5.2f}s  scene {d:5.2f}s")
    print("TOTAL", round(sum(durs), 2), "s")
    scenes = build_all(story)
    files = []; g = 0.0; stamp_times = []
    for i, (sc, d) in enumerate(zip(scenes, durs)):
        if hasattr(sc, "stamp_t"): stamp_times.append(g + sc.stamp_t)
        fn = scene_renderer(sc, d, g)
        pth = os.path.join(work, f"s{i:02d}.mp4"); tmp = pth[:-4] + ".tmp.mp4"
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
               "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-pix_fmt", "yuv420p", tmp]
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        for f in range(int(round(d * FPS))):
            p.stdin.write(fn(f).tobytes())
        p.stdin.close()
        if p.wait() != 0: raise SystemExit(f"ffmpeg failed on scene {i}")
        os.replace(tmp, pth); files.append(pth); g += d
        print("scene", i, "done")
    lst = os.path.join(work, "list.txt")
    with open(lst, "w") as f:
        for p_ in files: f.write(f"file '{os.path.abspath(p_)}'\n")
    silent = os.path.join(work, "video.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", silent], check=True)
    wav = os.path.join(work, "audio.wav"); make_audio(story, voices, durs, stamp_times, wav)
    final = os.path.join(outdir, story["output_name"] + ".mp4"); tmp = final[:-4] + ".tmp.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", silent, "-i", wav, "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", tmp], check=True)
    os.replace(tmp, final); print("WROTE", final)
    json.dump({"durations": durs}, open(os.path.join(work, "timing.json"), "w"))
    return final

if __name__ == "__main__":
    if len(sys.argv) < 3: print(__doc__); sys.exit(1)
    cmd, story = sys.argv[1], json.load(open(sys.argv[2], encoding="utf-8"))
    story["_base"] = os.path.dirname(os.path.abspath(sys.argv[2]))
    if cmd == "check": sys.exit(1 if check(story) else 0)
    elif cmd == "stills": stills(story, sys.argv[3])
    elif cmd == "render": render(story, sys.argv[3])
    else: print(__doc__)
