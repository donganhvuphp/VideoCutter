#!/usr/bin/env bash
set -euo pipefail

# Ensure venv & deps
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt pyinstaller

# Optional: provide an icon if you have one (replace icon.icns)
ICON_ARG=()
if [[ -f icon.icns ]]; then
  ICON_ARG=(--icon icon.icns)
fi

# Build .app
pyinstaller \
  --name "Video Cutter" \
  --windowed \
  --noconfirm \
  "${ICON_ARG[@]}" \
  app.py

# Output location
echo "\nBuilt app at: dist/Video Cutter.app"

echo "\nNote: Ensure ffmpeg is installed system-wide (e.g., 'brew install ffmpeg'). The app shells out to ffmpeg."
