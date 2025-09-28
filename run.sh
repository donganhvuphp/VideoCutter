#!/usr/bin/env bash
set -euo pipefail

# Create venv
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

echo "Checking ffmpeg..."
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "\n[ERROR] ffmpeg not found. On macOS: brew install ffmpeg"
  exit 1
fi

python app.py
