import ast
import os
import unittest
import xml.etree.ElementTree as ET

from PyQt6.QtCore import QTranslator
from PyQt6.QtWidgets import QApplication

import anylabeling
from anylabeling.services.auto_labeling.utils.vlm import i18n

_app = QApplication.instance() or QApplication([])
ROOT = os.path.dirname(anylabeling.__file__)
TS_PATH = os.path.join(i18n._TRANSLATIONS_DIR, "vlm_zh_CN.ts")
QM_PATH = os.path.join(i18n._TRANSLATIONS_DIR, "vlm_zh_CN.qm")


def _string(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _calls(root):
    return (
        node
        for node in ast.walk(root)
        if isinstance(node, ast.Call)
        and node.args
        and isinstance(node.func, ast.Attribute)
    )


def _receiver(call):
    value = call.func.value
    return value.id if isinstance(value, ast.Name) else None


def _tr_calls(relative_path):
    """Yield (context, source) for tr()/translate() calls in a module.

    ``self.tr`` uses the enclosing class as context; ``app.tr`` in
    vlm_batch runs on the LabelingWidget.
    """
    with open(os.path.join(ROOT, relative_path), encoding="utf-8") as stream:
        tree = ast.parse(stream.read())
    for cls in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)):
        for call in _calls(cls):
            source = _string(call.args[0])
            if call.func.attr == "tr" and _receiver(call) == "self" and source:
                yield cls.name, source
    for call in _calls(tree):
        if call.func.attr == "tr" and _receiver(call) == "app":
            source = _string(call.args[0])
            if source:
                yield "LabelingWidget", source
        elif call.func.attr == "translate" and len(call.args) >= 2:
            context, source = map(_string, call.args[:2])
            if context and source:
                yield context, source


class TestVLMTranslations(unittest.TestCase):
    def setUp(self):
        self.entries = {}
        for context in ET.parse(TS_PATH).getroot().iter("context"):
            name = context.findtext("name")
            for message in context.iter("message"):
                self.entries[(name, message.findtext("source"))] = (
                    message.findtext("translation")
                )

    def test_every_plugin_string_has_a_translation(self):
        expected = set()
        for path in (
            "views/labeling/widgets/vlm_settings_dialog.py",
            "views/labeling/utils/vlm_batch.py",
            "services/auto_labeling/vlm_annotator.py",
        ):
            expected.update(_tr_calls(path))
        # Output-mode names are already translated by the bundled zh_CN.qm.
        expected -= {("Model", "Polygon"), ("Model", "Rectangle")}
        expected |= {
            ("AutoLabelingWidget", "VLM Settings"),
            (
                "AutoLabelingWidget",
                "Choose the VLM backend (Codex, Claude, OpenAI API)",
            ),
        }
        self.assertGreater(len(expected), 20)
        missing = sorted(expected - set(self.entries))
        self.assertEqual(missing, [])
        self.assertTrue(all(self.entries[key] for key in expected))

    def test_compiled_catalog_is_current(self):
        translator = QTranslator()
        self.assertTrue(translator.load(QM_PATH))
        for (context, source), translation in self.entries.items():
            self.assertEqual(
                translator.translate(context, source), translation
            )


if __name__ == "__main__":
    unittest.main()
