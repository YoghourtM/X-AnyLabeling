import os
from datetime import datetime

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from anylabeling.views.labeling.utils.style import (
    get_cancel_btn_style,
    get_lineedit_style,
    get_ok_btn_style,
)
from anylabeling.views.labeling.utils.video_download import (
    BROWSERS,
    MAX_HEIGHTS,
    default_video_dir,
    load_settings,
    parse_plan,
    parse_time,
    read_links_file,
    save_settings,
)


class VideoUrlDialog(QDialog):
    """Links, time ranges, frame rate and download options for "Open
    Video URL"."""

    def __init__(self, parent=None, settings_path=None):
        super().__init__(parent)
        self.settings_path = settings_path
        self.settings = load_settings(settings_path)
        self._request = None
        self.setWindowTitle(self.tr("Open Video URL"))
        self.setMinimumWidth(620)

        layout = QVBoxLayout(self)
        links_label = QLabel(
            self.tr(
                "Video links, one per line (YouTube, Bilibili and other "
                "sites supported by yt-dlp). Time ranges may follow a "
                "link, e.g. 0:10-0:30 1:00-1:20, or 5:00- to the end:"
            )
        )
        links_label.setWordWrap(True)
        layout.addWidget(links_label)
        self.links_edit = QPlainTextEdit()
        self.links_edit.setPlaceholderText(
            "https://www.bilibili.com/video/BV...  0:10-0:30  1:00-1:20\n"
            "https://www.youtube.com/watch?v=...  5:00-\n"
            "https://www.youtube.com/watch?v=..."
        )
        self.links_edit.setMinimumHeight(110)
        layout.addWidget(self.links_edit)
        load_button = QPushButton(self.tr("Load links from file..."))
        load_button.clicked.connect(self.load_links)
        load_row = QHBoxLayout()
        load_row.addWidget(load_button)
        load_row.addStretch()
        layout.addLayout(load_row)

        form = QFormLayout()
        layout.addLayout(form)
        video_dir = self.settings["video_dir"] or default_video_dir()
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.frames_edit = self._line_edit(
            os.path.join(video_dir, f"frames_{stamp}")
        )
        form.addRow(
            self.tr("Frames folder"), self._with_browse(self.frames_edit)
        )

        self.fps_spin = QDoubleSpinBox()
        self.fps_spin.setRange(0.05, 60.0)
        self.fps_spin.setDecimals(2)
        self.fps_spin.setSingleStep(0.5)
        self.fps_spin.setToolTip(
            self.tr(
                "Frames taken per second of video; 0.5 takes one frame "
                "every 2 seconds"
            )
        )
        form.addRow(self.tr("Frames per second"), self.fps_spin)

        self.start_edit = self._line_edit(placeholder="0:00")
        self.end_edit = self._line_edit(placeholder=self.tr("video end"))
        time_row = QHBoxLayout()
        time_row.addWidget(self.start_edit)
        time_row.addWidget(QLabel(self.tr("to")))
        time_row.addWidget(self.end_edit)
        self.start_edit.setToolTip(
            self.tr(
                "For links without time ranges of their own, e.g. 90, 1:30 "
                "or 1:02:03; empty downloads the whole video"
            )
        )
        self.end_edit.setToolTip(self.start_edit.toolTip())
        form.addRow(self.tr("Default time range"), time_row)

        self.height_combo = QComboBox()
        for height in MAX_HEIGHTS:
            text = f"{height}p" if height else self.tr("Best available")
            self.height_combo.addItem(text, userData=height)
        form.addRow(self.tr("Max resolution"), self.height_combo)

        self.browser_combo = QComboBox()
        for browser in BROWSERS:
            text = browser.capitalize() if browser else self.tr("None")
            self.browser_combo.addItem(text, userData=browser)
        self.browser_combo.setToolTip(
            self.tr(
                "Use the login of this browser: Bilibili limits the quality "
                "without one, YouTube may ask to confirm you are not a bot"
            )
        )
        form.addRow(self.tr("Browser cookies"), self.browser_combo)

        self.proxy_edit = self._line_edit(
            placeholder=self.tr(
                "Empty: system network, e.g. http://127.0.0.1:7890"
            )
        )
        form.addRow(self.tr("Proxy"), self.proxy_edit)

        self.video_dir_edit = self._line_edit(placeholder=default_video_dir())
        self.video_dir_edit.setToolTip(
            self.tr(
                "Downloaded videos are kept here, so running the same link "
                "again skips the download"
            )
        )
        form.addRow(
            self.tr("Video folder"), self._with_browse(self.video_dir_edit)
        )
        self.keep_check = QCheckBox(
            self.tr("Keep videos after extracting frames")
        )
        form.addRow("", self.keep_check)
        self.ytdlp_edit = self._line_edit(
            placeholder=self.tr(
                "Empty: yt-dlp installed with X-AnyLabeling, else on PATH"
            )
        )
        form.addRow(self.tr("yt-dlp command"), self.ytdlp_edit)

        note = QLabel(
            self.tr(
                "Only download videos you may use. Frames of other people's "
                "videos are for your own training data; do not publish them."
            )
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        # Custom buttons: QDialogButtonBox resets the text of standard ones
        # on a language change.
        buttons = QDialogButtonBox()
        ok_button = buttons.addButton(
            self.tr("Start"), QDialogButtonBox.ButtonRole.AcceptRole
        )
        ok_button.setStyleSheet(get_ok_btn_style())
        ok_button.setDefault(True)
        cancel_button = buttons.addButton(
            self.tr("Cancel"), QDialogButtonBox.ButtonRole.RejectRole
        )
        cancel_button.setStyleSheet(get_cancel_btn_style())
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._load_values()

    @staticmethod
    def _line_edit(text="", placeholder=""):
        edit = QLineEdit(text)
        edit.setPlaceholderText(placeholder)
        edit.setStyleSheet(get_lineedit_style())
        return edit

    def _with_browse(self, edit):
        row = QHBoxLayout()
        row.addWidget(edit)
        button = QPushButton(self.tr("Browse..."))
        button.clicked.connect(lambda: self._browse(edit))
        row.addWidget(button)
        return row

    def _browse(self, edit):
        start = edit.text().strip() or edit.placeholderText()
        while start and not os.path.isdir(start):
            start = os.path.dirname(start)
        path = QFileDialog.getExistingDirectory(
            self, self.tr("Choose a folder"), start
        )
        if path:
            edit.setText(path)

    def _load_values(self):
        s = self.settings
        self.fps_spin.setValue(float(s["fps"]))
        index = self.height_combo.findData(int(s["max_height"]))
        self.height_combo.setCurrentIndex(
            index if index >= 0 else self.height_combo.findData(1080)
        )
        index = self.browser_combo.findData(s["cookies_browser"])
        self.browser_combo.setCurrentIndex(max(index, 0))
        self.proxy_edit.setText(s["proxy"])
        self.video_dir_edit.setText(s["video_dir"])
        self.keep_check.setChecked(bool(s["keep_videos"]))
        self.ytdlp_edit.setText(s["ytdlp_command"])

    def load_links(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Load links from file..."),
            "",
            self.tr("Text files (*.txt);;All files (*)"),
        )
        if not path:
            return
        try:
            text = read_links_file(path)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(
                self,
                self.windowTitle(),
                self.tr("Cannot read {path}: {error}").format(
                    path=path, error=exc
                ),
            )
            return
        current = self.links_edit.toPlainText().rstrip()
        self.links_edit.setPlainText(
            f"{current}\n{text}".strip() if current else text.strip()
        )

    def _warn(self, message):
        QMessageBox.warning(self, self.windowTitle(), message)

    def accept(self):
        try:
            start = parse_time(self.start_edit.text())
            end = parse_time(self.end_edit.text())
        except ValueError:
            self._warn(
                self.tr("Write times as seconds, m:ss or h:mm:ss, e.g. 1:30.")
            )
            return
        if end is not None and end <= (start or 0.0):
            self._warn(self.tr("The end time must be after the start time."))
            return
        default = None
        if start is not None or end is not None:
            default = (start or 0.0, end)
        jobs, problems = parse_plan(self.links_edit.toPlainText(), default)
        if problems:
            more = ["..."] if len(problems) > 10 else []
            self._warn(
                self.tr(
                    "Fix these lines; write time ranges as 1:00-1:30, or "
                    "5:00- to the end:"
                )
                + "\n\n"
                + "\n".join(problems[:10] + more)
            )
            return
        if not jobs:
            self._warn(self.tr("Enter at least one video link."))
            return
        frames_dir = os.path.expanduser(self.frames_edit.text().strip())
        if not frames_dir:
            self._warn(self.tr("Choose a frames folder."))
            return
        s = self.settings
        s["fps"] = self.fps_spin.value()
        s["max_height"] = self.height_combo.currentData()
        s["cookies_browser"] = self.browser_combo.currentData()
        s["proxy"] = self.proxy_edit.text().strip()
        s["video_dir"] = os.path.expanduser(self.video_dir_edit.text().strip())
        s["keep_videos"] = self.keep_check.isChecked()
        s["ytdlp_command"] = self.ytdlp_edit.text().strip()
        save_settings(s, self.settings_path)
        self._request = {
            "jobs": jobs,
            "frames_dir": os.path.abspath(frames_dir),
            "settings": dict(s),
        }
        super().accept()

    def request(self):
        """What to download, set once the dialog is accepted."""
        return self._request
