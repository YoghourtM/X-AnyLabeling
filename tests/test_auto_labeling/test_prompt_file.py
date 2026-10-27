import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from PyQt6.QtWidgets import QApplication, QLineEdit, QWidget

from anylabeling.services.auto_labeling.utils.vlm import parse_class_prompt
from anylabeling.views.labeling.utils import prompt_file
from anylabeling.views.labeling.utils.batch import TextInputDialog
from anylabeling.views.labeling.utils.prompt_file import (
    add_prompt_file_action,
    image_directory,
    load_prompt_file,
    read_prompt_file,
    setup_batch_prompt_input,
)

_app = QApplication.instance() or QApplication([])

PROMPTS = (
    "# street classes\r\n"
    "tactile_paving: 黄色凸起的导盲砖，条纹或圆点\r\n"
    "\r\n"
    "vehicle: car, vehicle\r\n"
    "  person  \r\n"
)


class TestReadPromptFile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        prompt_file._last_directory = None

    def _write(self, data, name="prompts.txt"):
        path = os.path.join(self.tmp.name, name)
        with open(path, "wb") as stream:
            stream.write(data)
        return path

    def test_lines_become_entries(self):
        path = self._write(PROMPTS.encode("utf-8-sig"))
        prompt = read_prompt_file(path)
        self.assertEqual(
            prompt,
            "tactile_paving: 黄色凸起的导盲砖，条纹或圆点; "
            "vehicle: car, vehicle; person",
        )
        # The joined line parses like the original lines minus the comment.
        self.assertEqual(
            parse_class_prompt(prompt),
            parse_class_prompt(PROMPTS.split("\n", 1)[1]),
        )

    def test_gb18030_and_limits(self):
        path = self._write(PROMPTS.encode("gb18030"))
        self.assertIn("导盲砖", read_prompt_file(path))
        big = self._write(b"a" * (prompt_file.MAX_PROMPT_FILE_BYTES + 1))
        with self.assertRaisesRegex(ValueError, "KB"):
            read_prompt_file(big)

    def test_image_directory(self):
        image = self._write(b"x", "a.jpg")
        self.assertEqual(
            image_directory(SimpleNamespace(filename=image)), self.tmp.name
        )
        self.assertEqual(
            image_directory(
                SimpleNamespace(filename=None, last_open_dir="/data")
            ),
            "/data",
        )
        self.assertEqual(image_directory(None), "")

    def test_load_fills_line_edit(self):
        path = self._write(PROMPTS.encode())
        edit = QLineEdit("old")
        with mock.patch.object(
            prompt_file.QFileDialog,
            "getOpenFileName",
            return_value=("", ""),
        ):
            self.assertFalse(load_prompt_file(edit, self.tmp.name))
        self.assertEqual(edit.text(), "old")
        with mock.patch.object(
            prompt_file.QFileDialog,
            "getOpenFileName",
            return_value=(path, ""),
        ) as dialog:
            self.assertTrue(load_prompt_file(edit, "/elsewhere"))
        self.assertTrue(edit.text().startswith("tactile_paving:"))
        self.assertEqual(prompt_file._last_directory, self.tmp.name)
        # The start folder was the one passed in; later dialogs reuse the
        # folder of the last prompt file.
        self.assertEqual(dialog.call_args.args[2], "/elsewhere")

    def test_empty_file_warns(self):
        path = self._write(b"# only a comment\n\n")
        edit = QLineEdit("old")
        with (
            mock.patch.object(
                prompt_file.QFileDialog,
                "getOpenFileName",
                return_value=(path, ""),
            ),
            mock.patch.object(prompt_file.QMessageBox, "warning") as warn,
        ):
            self.assertFalse(load_prompt_file(edit))
        warn.assert_called_once()
        self.assertEqual(edit.text(), "old")


class TestPromptInputs(unittest.TestCase):
    def test_action_triggers_loading_from_image_folder(self):
        edit = QLineEdit()
        widget = SimpleNamespace(filename=None, last_open_dir="/images")
        action = add_prompt_file_action(edit, widget)
        self.assertIn(action, edit.actions())
        with mock.patch.object(prompt_file, "load_prompt_file") as load:
            action.trigger()
        load.assert_called_once_with(edit, "/images")

    def test_batch_dialog_prefills_and_offers_loading(self):
        parent = QWidget()
        parent.auto_labeling_widget = SimpleNamespace(
            edit_text=QLineEdit(" person, car ")
        )
        parent.filename = None
        dialog = TextInputDialog(parent=parent)
        self.assertEqual(dialog.text_input.text(), "person, car")
        self.assertEqual(len(dialog.text_input.actions()), 1)

        edit = QLineEdit()
        setup_batch_prompt_input(edit, SimpleNamespace())
        self.assertEqual(edit.text(), "")


if __name__ == "__main__":
    unittest.main()
