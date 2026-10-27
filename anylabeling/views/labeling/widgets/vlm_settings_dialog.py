from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from anylabeling.services.auto_labeling.utils.vlm import (
    PROVIDER_CLAUDE,
    PROVIDER_CODEX,
    PROVIDER_OPENAI,
    load_settings,
    save_settings,
)
from anylabeling.views.labeling.utils.style import (
    get_cancel_btn_style,
    get_lineedit_style,
    get_ok_btn_style,
)

_CODEX_EFFORTS = ["", "low", "medium", "high", "xhigh", "ultra"]
_CLAUDE_MODELS = ["", "fable", "opus", "sonnet", "haiku"]


class VLMSettingsDialog(QDialog):
    """Backend selection and prompt options for the VLM annotator."""

    def __init__(self, parent=None, settings_path=None):
        super().__init__(parent)
        self.settings_path = settings_path
        self.settings = load_settings(settings_path)
        self.setWindowTitle(self.tr("VLM Annotator Settings"))
        self.setMinimumWidth(560)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self.provider_combo = QComboBox()
        for provider, text in (
            (PROVIDER_CODEX, self.tr("Codex CLI (local login)")),
            (PROVIDER_CLAUDE, self.tr("Claude CLI (local login)")),
            (PROVIDER_OPENAI, self.tr("OpenAI-compatible API")),
        ):
            self.provider_combo.addItem(text, userData=provider)
        form.addRow(self.tr("Backend"), self.provider_combo)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._codex_page())
        self.stack.addWidget(self._claude_page())
        self.stack.addWidget(self._openai_page())
        layout.addWidget(self.stack)
        self.provider_combo.currentIndexChanged.connect(
            self.stack.setCurrentIndex
        )

        common = QFormLayout()
        layout.addLayout(common)
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(10, 7200)
        self.timeout_spin.setSuffix(" s")
        common.addRow(self.tr("Timeout per image"), self.timeout_spin)
        self.vertices_spin = QSpinBox()
        self.vertices_spin.setRange(4, 200)
        common.addRow(self.tr("Max polygon vertices"), self.vertices_spin)
        self.image_side_spin = QSpinBox()
        self.image_side_spin.setRange(256, 8192)
        self.image_side_spin.setSingleStep(256)
        self.image_side_spin.setSuffix(" px")
        common.addRow(self.tr("Max image side sent"), self.image_side_spin)
        self.instructions_edit = QPlainTextEdit()
        self.instructions_edit.setPlaceholderText(
            self.tr(
                "Optional extra instructions appended to every request, "
                "e.g. how to split instances or what to ignore"
            )
        )
        self.instructions_edit.setFixedHeight(90)
        common.addRow(self.tr("Extra instructions"), self.instructions_edit)

        batch_box = QGroupBox(self.tr("Batch (Run All Images)"))
        batch = QFormLayout(batch_box)
        self.concurrency_spin = QSpinBox()
        self.concurrency_spin.setRange(1, 64)
        self.concurrency_spin.setToolTip(
            self.tr(
                "Upper limit of parallel requests. Concurrency starts at 1, "
                "grows while requests succeed, halves on rejections, "
                "timeouts or stalls, then grows again after the cooldown."
            )
        )
        batch.addRow(self.tr("Max concurrency"), self.concurrency_spin)
        self.cooldown_spin = QSpinBox()
        self.cooldown_spin.setRange(0, 3600)
        self.cooldown_spin.setSuffix(" s")
        batch.addRow(self.tr("Cooldown after back-off"), self.cooldown_spin)
        self.retries_spin = QSpinBox()
        self.retries_spin.setRange(0, 10)
        batch.addRow(self.tr("Retries per image"), self.retries_spin)
        layout.addWidget(batch_box)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        save_button.setText(self.tr("Save"))
        save_button.setStyleSheet(get_ok_btn_style())
        save_button.setIcon(QIcon())
        cancel_button.setText(self.tr("Cancel"))
        cancel_button.setStyleSheet(get_cancel_btn_style())
        cancel_button.setIcon(QIcon())
        buttons.accepted.connect(self.save_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._load_values()

    @staticmethod
    def _line_edit(text="", placeholder="", password=False):
        edit = QLineEdit(text)
        edit.setPlaceholderText(placeholder)
        edit.setStyleSheet(get_lineedit_style())
        if password:
            edit.setEchoMode(QLineEdit.EchoMode.Password)
        return edit

    @staticmethod
    def _editable_combo(items):
        combo = QComboBox()
        combo.setEditable(True)
        combo.addItems(items)
        return combo

    def _codex_page(self):
        page = QWidget()
        form = QFormLayout(page)
        self.codex_command = self._line_edit(placeholder="codex")
        self.codex_model = self._line_edit(
            placeholder=self.tr("Empty: model from ~/.codex/config.toml")
        )
        self.codex_effort = self._editable_combo(_CODEX_EFFORTS)
        form.addRow(self.tr("Command"), self.codex_command)
        form.addRow(self.tr("Model"), self.codex_model)
        form.addRow(self.tr("Reasoning effort"), self.codex_effort)
        return page

    def _claude_page(self):
        page = QWidget()
        form = QFormLayout(page)
        self.claude_command = self._line_edit(placeholder="claude")
        self.claude_model = self._editable_combo(_CLAUDE_MODELS)
        form.addRow(self.tr("Command"), self.claude_command)
        form.addRow(self.tr("Model"), self.claude_model)
        return page

    def _openai_page(self):
        page = QWidget()
        form = QFormLayout(page)
        self.openai_base_url = self._line_edit(
            placeholder="https://your-relay.example.com/v1"
        )
        self.openai_api_key = self._line_edit(
            placeholder=self.tr("Empty: use OPENAI_API_KEY"), password=True
        )
        self.openai_model = self._line_edit(placeholder="gpt-5.5")
        self.openai_temperature = QDoubleSpinBox()
        self.openai_temperature.setRange(0.0, 2.0)
        self.openai_temperature.setSingleStep(0.1)
        form.addRow(self.tr("Base URL"), self.openai_base_url)
        form.addRow(self.tr("API key"), self.openai_api_key)
        form.addRow(self.tr("Model"), self.openai_model)
        form.addRow(self.tr("Temperature"), self.openai_temperature)
        hint = QLabel(
            self.tr("Uses the /chat/completions endpoint with image input.")
        )
        hint.setWordWrap(True)
        form.addRow(hint)
        return page

    def _load_values(self):
        s = self.settings
        index = self.provider_combo.findData(s["provider"])
        self.provider_combo.setCurrentIndex(max(index, 0))
        self.stack.setCurrentIndex(max(index, 0))
        self.codex_command.setText(s["codex"]["command"])
        self.codex_model.setText(s["codex"]["model"])
        self.codex_effort.setCurrentText(s["codex"]["reasoning_effort"])
        self.claude_command.setText(s["claude"]["command"])
        self.claude_model.setCurrentText(s["claude"]["model"])
        self.openai_base_url.setText(s["openai"]["base_url"])
        self.openai_api_key.setText(s["openai"]["api_key"])
        self.openai_model.setText(s["openai"]["model"])
        self.openai_temperature.setValue(float(s["openai"]["temperature"]))
        self.timeout_spin.setValue(int(s["timeout"]))
        self.vertices_spin.setValue(int(s["max_vertices"]))
        self.image_side_spin.setValue(int(s["max_image_side"]))
        self.instructions_edit.setPlainText(s["instructions"])
        self.concurrency_spin.setValue(int(s["batch"]["max_concurrency"]))
        self.cooldown_spin.setValue(int(s["batch"]["cooldown_seconds"]))
        self.retries_spin.setValue(int(s["batch"]["max_retries"]))

    def collect_settings(self):
        s = self.settings
        s["provider"] = self.provider_combo.currentData()
        s["codex"].update(
            command=self.codex_command.text().strip() or "codex",
            model=self.codex_model.text().strip(),
            reasoning_effort=self.codex_effort.currentText().strip(),
        )
        s["claude"].update(
            command=self.claude_command.text().strip() or "claude",
            model=self.claude_model.currentText().strip(),
        )
        s["openai"].update(
            base_url=self.openai_base_url.text().strip(),
            api_key=self.openai_api_key.text().strip(),
            model=self.openai_model.text().strip(),
            temperature=self.openai_temperature.value(),
        )
        s["timeout"] = self.timeout_spin.value()
        s["max_vertices"] = self.vertices_spin.value()
        s["max_image_side"] = self.image_side_spin.value()
        s["instructions"] = self.instructions_edit.toPlainText().strip()
        s["batch"].update(
            max_concurrency=self.concurrency_spin.value(),
            cooldown_seconds=self.cooldown_spin.value(),
            max_retries=self.retries_spin.value(),
        )
        return s

    def save_and_accept(self):
        save_settings(self.collect_settings(), self.settings_path)
        self.accept()
