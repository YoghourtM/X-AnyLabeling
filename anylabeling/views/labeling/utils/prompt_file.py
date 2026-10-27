"""Load a text prompt from a .txt file into a prompt line edit.

A prompt file holds one entry per line, e.g. ``tactile_paving: tactile
paving, guide tiles``; blank lines and lines starting with ``#`` are
skipped. The entries are joined with ``; ``, which the VLM annotator and
the SAM 3.1 server both read as an entry separator.
"""

import os

from PyQt6.QtCore import QCoreApplication
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QFileDialog, QLineEdit, QMessageBox

from anylabeling.views.labeling.utils.qt import new_icon

MAX_PROMPT_FILE_BYTES = 64 * 1024

_last_directory = None


def _tr(text):
    return QCoreApplication.translate("PromptFile", text)


def read_prompt_file(path):
    """Return the prompt stored in ``path`` as a single line.

    UTF-8 (with or without BOM) and GB18030 files are accepted.
    """
    if os.path.getsize(path) > MAX_PROMPT_FILE_BYTES:
        raise ValueError(
            f"larger than {MAX_PROMPT_FILE_BYTES // 1024} KB; "
            "is this a prompt file?"
        )
    with open(path, "rb") as stream:
        raw = stream.read()
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError("not UTF-8 or GB18030 text")
    lines = (line.strip() for line in text.splitlines())
    return "; ".join(
        line for line in lines if line and not line.startswith("#")
    )


def image_directory(labeling_widget):
    """Folder of the current image, else the last opened folder."""
    filename = getattr(labeling_widget, "filename", None)
    if filename and os.path.isfile(filename):
        return os.path.dirname(filename)
    return getattr(labeling_widget, "last_open_dir", None) or ""


def load_prompt_file(line_edit, start_directory=""):
    """Ask for a prompt file and put its prompt into ``line_edit``.

    Returns True when the line edit was filled.
    """
    global _last_directory
    title = _tr("Load prompt from file")
    path, _ = QFileDialog.getOpenFileName(
        line_edit,
        title,
        _last_directory or start_directory,
        _tr("Text files (*.txt);;All files (*)"),
    )
    if not path:
        return False
    _last_directory = os.path.dirname(path)
    try:
        prompt = read_prompt_file(path)
    except (OSError, ValueError) as exc:
        QMessageBox.warning(
            line_edit,
            title,
            _tr("Cannot read {path}: {error}").format(path=path, error=exc),
        )
        return False
    if not prompt:
        QMessageBox.warning(
            line_edit,
            title,
            _tr("{path} has no prompt entries.").format(path=path),
        )
        return False
    line_edit.setText(prompt)
    line_edit.setCursorPosition(0)
    line_edit.setFocus()
    return True


def add_prompt_file_action(line_edit, labeling_widget=None):
    """Add a trailing "load from file" button inside ``line_edit``."""
    action = QAction(new_icon("open", "svg"), _tr("Load prompt from file"))
    action.setParent(line_edit)
    action.setToolTip(
        _tr(
            "Load the prompt from a .txt file: one entry per line, "
            "lines starting with # are ignored"
        )
    )
    action.triggered.connect(
        lambda: load_prompt_file(line_edit, image_directory(labeling_widget))
    )
    line_edit.addAction(action, QLineEdit.ActionPosition.TrailingPosition)
    return action


def setup_batch_prompt_input(line_edit, labeling_widget):
    """Prefill the batch prompt with the auto-labeling prompt; add loading."""
    auto_labeling = getattr(labeling_widget, "auto_labeling_widget", None)
    edit_text = getattr(auto_labeling, "edit_text", None)
    if edit_text is not None and edit_text.text().strip():
        line_edit.setText(edit_text.text().strip())
        line_edit.setCursorPosition(0)
    return add_prompt_file_action(line_edit, labeling_widget)
