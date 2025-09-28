# VideoCutter

Batch-cut videos into frames or N-second segments using a clean, dark-themed GUI.

## Prerequisites
- macOS (tested), Linux and Windows should also work for running via `run.sh` (adjust accordingly)
- Python 3.10+
- **ffmpeg** in PATH (macOS: `brew install ffmpeg`)

## Quick Start
```bash
chmod +x run.sh
./run.sh
```

## Usage
1. Click **Browse…** to select an **input folder** containing videos (`.mp4, .mov, .m4v, .mkv, .avi, .webm`).
2. Choose **Output folder** (it will be created if missing).
3. Choose a **Mode**:
   - **Cut to images (frames):** extracts 1 frame every *N* seconds.
   - **Cut to video segments:** splits each video into *N*-second parts.
4. Set **Interval (seconds)** (default `5`).
5. Click **Start**. Outputs will be placed under `/<output>/<video-basename>-<timestamp>/`.

## Build macOS App (.app)
```bash
chmod +x build_macos.sh
./build_macos.sh
open "dist/Video Cutter.app"
```

> The .app still requires **ffmpeg** installed system-wide.

## Notes
- Segmenting tries a fast **stream copy** first; if unsupported, it **re-encodes** to H.264/AAC.
- Logs show the exact ffmpeg commands used.
- Cancelling stops after the current file finishes.
