# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

VideoCutter is a PySide6-based GUI application that batch-processes videos using ffmpeg. It can either extract frames at intervals or split videos into segments.

## Dependencies

**Critical external dependency**: ffmpeg must be installed and available in PATH. The application shells out to ffmpeg for all video processing. On macOS: `brew install ffmpeg`

Python dependencies are minimal:
- PySide6>=6.6 (Qt6 bindings for Python)
- pyinstaller (build-time only)

## Common Commands

**Run the application** (creates venv, installs deps, launches GUI):
```bash
./run.sh
```

**Build macOS .app bundle**:
```bash
./build_macos.sh
```
The resulting app is placed in `dist/Video Cutter.app`. Note: the .app still requires system-wide ffmpeg.

**Manual venv setup** (if needed):
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

## Architecture

This is a single-file application (`app.py`) with two main classes:

**Worker (QThread)**: Background thread that processes videos. Key responsibilities:
- Discovers video files in input directory (VIDEO_EXTS: .mp4, .mov, .m4v, .mkv, .avi, .webm)
- Calls ffmpeg via subprocess for each video
- Two modes:
  - `frames`: Extracts 1 frame per N seconds using `fps=1/N` filter, outputs as JPEG
  - `segments`: Splits video into N-second chunks. Tries stream copy first (`-c copy`) for speed; falls back to H.264/AAC re-encode if stream copy fails
- Emits signals for progress, logging, and completion
- Supports cancellation (finishes current video before stopping)

**MainWindow (QMainWindow)**: GUI with dark theme. User selects input/output directories, mode, and interval. Displays progress bar and ffmpeg command logs.

## Output Structure

For each video processed, creates a timestamped subdirectory:
```
<output_folder>/<video-basename>-<YYYYMMDD_HHMMSS>/
  ├── frame_000001.jpg (frames mode)
  ├── frame_000002.jpg
  └── ...
or
  ├── part_000.mp4 (segments mode)
  ├── part_001.mp4
  └── ...
```

## Development Notes

- All video processing is done by shelling out to ffmpeg with `subprocess.run()`
- Logging displays exact ffmpeg commands used for debugging
- The app verifies ffmpeg is available before processing
- When stream copy fails for segmenting, it automatically retries with re-encode (user is notified via log)
- This repository is not currently a git repo
- No test suite or linting is configured