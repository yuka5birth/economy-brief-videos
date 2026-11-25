#!/usr/bin/env bash
# Installs / checks everything reel.py needs. Safe to run every time.
set -u
ok=1
python3 -c "import PIL, numpy" 2>/dev/null || pip install -q --break-system-packages pillow numpy 2>/dev/null || pip install -q pillow numpy
python3 -c "import pyopenjtalk" 2>/dev/null || pip install -q --break-system-packages pyopenjtalk 2>/dev/null || pip install -q pyopenjtalk
python3 -c "import pyopenjtalk; pyopenjtalk.g2p('テスト')" >/dev/null 2>&1 || { echo "NG: pyopenjtalk (narration) not usable"; ok=0; }
command -v ffmpeg >/dev/null || { (apt-get install -y -q ffmpeg >/dev/null 2>&1 || sudo apt-get install -y -q ffmpeg >/dev/null 2>&1); }
command -v ffmpeg >/dev/null || { echo "NG: ffmpeg missing"; ok=0; }
if ! fc-list 2>/dev/null | grep -qi "Noto Serif CJK\|Noto Serif JP"; then
  (apt-get install -y -q fonts-noto-cjk fonts-noto-cjk-extra >/dev/null 2>&1 || sudo apt-get install -y -q fonts-noto-cjk fonts-noto-cjk-extra >/dev/null 2>&1)
fi
fc-list 2>/dev/null | grep -qi "Noto Serif CJK\|Noto Serif JP" || { echo "NG: Noto Serif/Sans CJK JP fonts missing"; ok=0; }
[ $ok = 1 ] && echo "SETUP OK" || { echo "SETUP INCOMPLETE"; exit 1; }
