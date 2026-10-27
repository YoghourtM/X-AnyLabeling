"""Translations for the VLM annotator UI.

They ship as a separate ``vlm_<language>.qm`` installed as an extra
QTranslator, so the plugin never has to rebuild the bundled resources.py.
"""

import os

from PyQt6.QtCore import QCoreApplication, QLocale, QTranslator

_TRANSLATIONS_DIR = os.path.join(os.path.dirname(__file__), "translations")
_translator = None


def install_translator(language=None):
    """Install the plugin translator once; returns True when loaded."""
    global _translator
    app = QCoreApplication.instance()
    if _translator is not None or app is None:
        return _translator is not None
    if language is None:
        from anylabeling.config import get_config

        try:
            language = get_config().get("language")
        except Exception:  # noqa: BLE001 - config may be unavailable
            language = None
        language = language or QLocale.system().name()
    path = os.path.join(_TRANSLATIONS_DIR, f"vlm_{language}.qm")
    translator = QTranslator(app)
    if not os.path.isfile(path) or not translator.load(path):
        return False
    app.installTranslator(translator)
    _translator = translator
    return True
