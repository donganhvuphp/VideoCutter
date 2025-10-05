#!/usr/bin/env python3
import sys
import os
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List

from PySide6 import QtCore, QtGui, QtWidgets

APP_NAME = "VideoCutter"
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".mkv", ".avi", ".webm"}

class Worker(QtCore.QThread):
    progress = QtCore.Signal(int, int)  # processed, total
    log = QtCore.Signal(str)
    done = QtCore.Signal(bool)

    def __init__(self, input_dirs: List[Path], mode: str, interval_sec: int):
        super().__init__()
        self.input_dirs = input_dirs
        self.mode = mode  # 'frames' or 'segments'
        self.interval_sec = interval_sec
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            if not self._check_ffmpeg():
                self.log.emit("❌ ffmpeg not found. Please install and ensure it is in PATH.")
                self.done.emit(False)
                return

            # Collect all videos from all input directories
            all_videos = []
            for input_dir in self.input_dirs:
                videos = self._collect_videos(input_dir)
                all_videos.extend([(input_dir, video) for video in videos])

            total = len(all_videos)
            if total == 0:
                self.log.emit("No videos found in the selected folder(s).")
                self.done.emit(False)
                return

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            for i, (input_dir, video) in enumerate(all_videos, start=1):
                if self._cancelled:
                    self.log.emit("\n⛔ Cancelled by user.")
                    self.done.emit(False)
                    return

                base = video.stem
                out_root = input_dir / f"{base}-{ts}"
                out_root.mkdir(parents=True, exist_ok=True)

                self.log.emit(f"\n➡️ Processing [{i}/{total}]: {video.name}")
                ok = False
                if self.mode == "frames":
                    ok = self._extract_frames(video, out_root, self.interval_sec)
                else:
                    ok = self._split_segments(video, out_root, self.interval_sec)

                if ok:
                    self.log.emit(f"✅ Done: {video.name} → {out_root}")
                else:
                    self.log.emit(f"❗ Skipped (error): {video.name}")

                self.progress.emit(i, total)

            self.done.emit(True)
        except Exception as e:
            self.log.emit(f"Unexpected error: {e}")
            self.done.emit(False)

    # Helpers
    def _check_ffmpeg(self) -> bool:
        try:
            subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            return True
        except FileNotFoundError:
            return False

    def _collect_videos(self, folder: Path) -> List[Path]:
        files = []
        for p in folder.iterdir():
            if p.is_file() and p.suffix.lower() in VIDEO_EXTS:
                files.append(p)
        files.sort()
        return files

    def _extract_frames(self, video: Path, out_dir: Path, interval_sec: int) -> bool:
        # One frame every N seconds: fps = 1/N
        # Output: frame_000001.jpg, ...
        out_pattern = str(out_dir / "frame_%06d.jpg")
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-i", str(video),
            "-vf", f"fps=1/{max(1, interval_sec)}",
            "-q:v", "2",
            out_pattern,
        ]
        return self._run_ffmpeg(cmd)

    def _split_segments(self, video: Path, out_dir: Path, interval_sec: int) -> bool:
        # Split to N-second chunks. Try stream copy for speed & quality.
        # Output: part_000.mp4 (match original extension when possible)
        ext = video.suffix.lower()
        # Use mp4 for unknown/unsupported extensions
        out_ext = ".mp4" if ext not in {".mp4", ".m4v", ".mov", ".mkv", ".webm"} else ext
        out_pattern = str(out_dir / f"part_%03d{out_ext}")
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-i", str(video),
            "-map", "0",
            "-c", "copy",
            "-f", "segment",
            "-segment_time", str(max(1, interval_sec)),
            "-reset_timestamps", "1",
            out_pattern,
        ]
        # Fallback: if copy fails (e.g., some codecs), re-encode H.264/AAC
        if not self._run_ffmpeg(cmd):
            self.log.emit("   (retrying with re-encode h264/aac)")
            cmd = [
                "ffmpeg", "-hide_banner", "-loglevel", "error",
                "-i", str(video),
                "-map", "0",
                "-c:v", "libx264",
                "-c:a", "aac",
                "-f", "segment",
                "-segment_time", str(max(1, interval_sec)),
                "-reset_timestamps", "1",
                out_pattern,
            ]
            return self._run_ffmpeg(cmd)
        return True

    def _run_ffmpeg(self, cmd: List[str]) -> bool:
        try:
            self.log.emit("   $ " + " ".join(cmd))
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if proc.returncode != 0:
                err = proc.stderr.decode(errors="ignore")
                self.log.emit("   ffmpeg error:\n" + err)
                return False
            return True
        except Exception as e:
            self.log.emit(f"   Exception: {e}")
            return False

class SubfolderSelectionDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Subfolders")
        self.setMinimumSize(600, 500)
        self.selected_folders: List[Path] = []
        self.parent_folder: Path | None = None

        # Layout
        layout = QtWidgets.QVBoxLayout(self)

        # Parent folder selection
        parent_row = QtWidgets.QHBoxLayout()
        self.parent_label = QtWidgets.QLabel("No parent folder selected")
        parent_btn = QtWidgets.QPushButton("Select Parent Folder…")
        parent_btn.clicked.connect(self.select_parent_folder)
        parent_row.addWidget(self.parent_label, 1)
        parent_row.addWidget(parent_btn)
        layout.addLayout(parent_row)

        # Checkbox list
        list_label = QtWidgets.QLabel("Select subfolders to process:")
        layout.addWidget(list_label)

        self.subfolder_list = QtWidgets.QListWidget()
        self.subfolder_list.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        layout.addWidget(self.subfolder_list)

        # Select all / Clear all buttons
        select_row = QtWidgets.QHBoxLayout()
        select_all_btn = QtWidgets.QPushButton("Select All")
        clear_all_btn = QtWidgets.QPushButton("Clear All")
        select_all_btn.clicked.connect(self.select_all)
        clear_all_btn.clicked.connect(self.clear_all)
        select_row.addWidget(select_all_btn)
        select_row.addWidget(clear_all_btn)
        select_row.addStretch()
        layout.addLayout(select_row)

        # OK / Cancel buttons
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def select_parent_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Parent Folder")
        if folder:
            self.parent_folder = Path(folder)
            self.parent_label.setText(str(self.parent_folder))
            self.load_subfolders()

    def load_subfolders(self):
        self.subfolder_list.clear()
        if not self.parent_folder or not self.parent_folder.exists():
            return

        subfolders = [d for d in self.parent_folder.iterdir() if d.is_dir()]
        subfolders.sort()

        for subfolder in subfolders:
            item = QtWidgets.QListWidgetItem(subfolder.name)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.Unchecked)
            item.setData(QtCore.Qt.UserRole, subfolder)
            self.subfolder_list.addItem(item)

    def select_all(self):
        for i in range(self.subfolder_list.count()):
            item = self.subfolder_list.item(i)
            item.setCheckState(QtCore.Qt.Checked)

    def clear_all(self):
        for i in range(self.subfolder_list.count()):
            item = self.subfolder_list.item(i)
            item.setCheckState(QtCore.Qt.Unchecked)

    def accept(self):
        self.selected_folders = []
        for i in range(self.subfolder_list.count()):
            item = self.subfolder_list.item(i)
            if item.checkState() == QtCore.Qt.Checked:
                self.selected_folders.append(item.data(QtCore.Qt.UserRole))

        if not self.selected_folders:
            QtWidgets.QMessageBox.warning(self, "No Selection", "Please select at least one subfolder.")
            return

        super().accept()

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(860, 640)
        self.worker: Worker | None = None

        # Central widget
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)

        # Inputs
        self.input_dirs: List[Path] = []
        self.input_dirs_label = QtWidgets.QLabel("No folders selected")
        self.input_dirs_label.setWordWrap(True)
        in_btn = QtWidgets.QPushButton("Select Folders…")
        clear_btn = QtWidgets.QPushButton("Clear")
        in_btn.clicked.connect(self.pick_input_dirs)
        clear_btn.clicked.connect(self.clear_selection)

        # Mode
        self.mode_frames = QtWidgets.QRadioButton("Cut to **images** (frames)")
        self.mode_segments = QtWidgets.QRadioButton("Cut to **video segments**")
        self.mode_frames.setChecked(True)

        # Interval
        self.interval_spin = QtWidgets.QSpinBox()
        self.interval_spin.setMinimum(1)
        self.interval_spin.setMaximum(36000)
        self.interval_spin.setValue(5)
        self.interval_spin.setSuffix(" s")
        self.interval_label = QtWidgets.QLabel("Interval (seconds)")
        self.interval_hint = QtWidgets.QLabel(
            "For frames: take 1 frame every N seconds. For segments: split each video into N‑second parts.")
        self.interval_hint.setWordWrap(True)

        # Actions
        self.start_btn = QtWidgets.QPushButton("Start")
        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        self.start_btn.clicked.connect(self.start)
        self.cancel_btn.clicked.connect(self.cancel)

        # Progress + Log
        self.progress_bar = QtWidgets.QProgressBar()
        self.log = QtWidgets.QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)
        self.log.document().setMaximumBlockCount(10000)

        # Layouts
        form = QtWidgets.QFormLayout()
        in_row = QtWidgets.QHBoxLayout()
        in_row.addWidget(self.input_dirs_label, 1)
        in_row.addWidget(clear_btn)
        in_row.addWidget(in_btn)
        form.addRow("Input folders (videos)", in_row)

        mode_box = QtWidgets.QGroupBox("Mode")
        mode_layout = QtWidgets.QVBoxLayout()
        mode_layout.addWidget(self.mode_frames)
        mode_layout.addWidget(self.mode_segments)
        mode_box.setLayout(mode_layout)

        ctrl_row = QtWidgets.QHBoxLayout()
        ctrl_row.addWidget(self.start_btn)
        ctrl_row.addWidget(self.cancel_btn)

        v = QtWidgets.QVBoxLayout(central)
        v.addLayout(form)
        v.addWidget(mode_box)
        grid = QtWidgets.QGridLayout()
        grid.addWidget(self.interval_label, 0, 0)
        grid.addWidget(self.interval_spin, 0, 1)
        grid.addWidget(self.interval_hint, 1, 0, 1, 2)
        v.addLayout(grid)
        v.addWidget(self.progress_bar)
        v.addLayout(ctrl_row)
        v.addWidget(self.log, 1)

        self.apply_dark_theme()

    def apply_dark_theme(self):
        palette = QtGui.QPalette()
        base = QtGui.QColor(30, 33, 36)
        alt = QtGui.QColor(40, 44, 48)
        text = QtGui.QColor(220, 220, 220)
        highlight = QtGui.QColor(90, 165, 255)

        palette.setColor(QtGui.QPalette.Window, base)
        palette.setColor(QtGui.QPalette.WindowText, text)
        palette.setColor(QtGui.QPalette.Base, QtGui.QColor(24, 26, 27))
        palette.setColor(QtGui.QPalette.AlternateBase, alt)
        palette.setColor(QtGui.QPalette.Text, text)
        palette.setColor(QtGui.QPalette.Button, alt)
        palette.setColor(QtGui.QPalette.ButtonText, text)
        palette.setColor(QtGui.QPalette.Highlight, highlight)
        palette.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor(0, 0, 0))
        self.setPalette(palette)

        # Style sheet for nicer controls
        self.setStyleSheet(
            """
            QGroupBox { border: 1px solid #3d434a; border-radius: 8px; margin-top: 1.2em; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; color: #cfd3d7; }
            QLabel { color: #e0e0e0; }
            QLineEdit, QPlainTextEdit, QSpinBox { background: #1e2124; color: #e8e8e8; border: 1px solid #3d434a; border-radius: 6px; padding: 6px; }
            QPushButton { background: #2c3136; color: #f0f0f0; border: 1px solid #3d434a; border-radius: 8px; padding: 8px 12px; }
            QPushButton:hover { background: #343a40; }
            QPushButton:disabled { color: #888; }
            QProgressBar { background: #1e2124; border: 1px solid #3d434a; border-radius: 6px; text-align: center; color: #ddd; }
            QProgressBar::chunk { background-color: #5aa5ff; }
            QRadioButton { color: #e0e0e0; }
            """
        )

    def pick_input_dirs(self):
        dialog = SubfolderSelectionDialog(self)
        if dialog.exec():
            self.input_dirs = dialog.selected_folders
            if len(self.input_dirs) == 1:
                self.input_dirs_label.setText(str(self.input_dirs[0]))
            else:
                self.input_dirs_label.setText(
                    f"{len(self.input_dirs)} folders selected:\n" +
                    "\n".join(str(d) for d in self.input_dirs)
                )

    def clear_selection(self):
        self.input_dirs = []
        self.input_dirs_label.setText("No folders selected")

    def start(self):
        if not self.input_dirs:
            QtWidgets.QMessageBox.warning(self, APP_NAME, "Please select at least one input folder.")
            return

        # Validate all input directories
        for input_dir in self.input_dirs:
            if not input_dir.exists() or not input_dir.is_dir():
                QtWidgets.QMessageBox.warning(self, APP_NAME, f"Invalid input folder: {input_dir}")
                return

        interval = int(self.interval_spin.value())
        mode = "frames" if self.mode_frames.isChecked() else "segments"

        self.log.clear()
        self.progress_bar.setValue(0)
        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)

        self.worker = Worker(self.input_dirs, mode, interval)
        self.worker.progress.connect(self.on_progress)
        self.worker.log.connect(self.append_log)
        self.worker.done.connect(self.on_done)
        self.worker.start()

    def cancel(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()

    def on_progress(self, n: int, total: int):
        pct = int(n / max(1, total) * 100)
        self.progress_bar.setValue(pct)

    def append_log(self, text: str):
        self.log.appendPlainText(text)

    def on_done(self, success: bool):
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        if success:
            QtWidgets.QMessageBox.information(self, APP_NAME, "All tasks finished.")
        else:
            QtWidgets.QMessageBox.information(self, APP_NAME, "Finished with issues or cancelled.")

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())
