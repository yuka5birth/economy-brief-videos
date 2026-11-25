#!/usr/bin/env bash
# Installs / checks everything kondate.py needs. Safe to run every time.
# Fonts and the narration voice are cached in $KONDATE_ASSETS (default ~/.cache/kondate-reel).
set -u
ok=1
A="${KONDATE_ASSETS:-$HOME/.cache/kondate-reel}"
mkdir -p "$A"
python3 -c "import PIL, numpy" 2>/dev/null || pip install -q --break-system-packages pillow numpy 2>/dev/null || pip install -q pillow numpy
python3 -c "import pyopenjtalk" 2>/dev/null || pip install -q --break-system-packages pyopenjtalk 2>/dev/null || pip install -q pyopenjtalk
python3 -c "import pyopenjtalk; pyopenjtalk.g2p('テスト')" >/dev/null 2>&1 || { echo "NG: pyopenjtalk (narration) not usable"; ok=0; }
command -v ffmpeg >/dev/null || { (apt-get install -y -q ffmpeg >/dev/null 2>&1 || sudo apt-get install -y -q ffmpeg >/dev/null 2>&1); }
command -v ffmpeg >/dev/null || { echo "NG: ffmpeg missing"; ok=0; }

GF=https://raw.githubusercontent.com/google/fonts/main/ofl
for f in zenmarugothic/ZenMaruGothic-Black.ttf zenmarugothic/ZenMaruGothic-Bold.ttf zenmarugothic/ZenMaruGothic-Medium.ttf mplusrounded1c/MPLUSRounded1c-ExtraBold.ttf; do
  n=$(basename "$f")
  [ -s "$A/$n" ] || curl -sfL -o "$A/$n" "$GF/$f" || { echo "NG: font download failed: $n"; ok=0; }
done
V=https://raw.githubusercontent.com/icn-lab/htsvoice-tohoku-f01/master/tohoku-f01-happy.htsvoice
[ -s "$A/tohoku-f01-happy.htsvoice" ] || curl -sfL -o "$A/tohoku-f01-happy.htsvoice" "$V" || { echo "NG: voice download failed"; ok=0; }

[ $ok = 1 ] && echo "SETUP OK ($A)" || { echo "SETUP INCOMPLETE"; exit 1; }
