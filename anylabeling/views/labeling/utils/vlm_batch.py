"""Concurrent "Run All Images" for the VLM annotator.

VLM requests are slow (tens of seconds) and mostly waiting on the network or
a CLI, so images are labeled in parallel under the adaptive window from
``utils.vlm.scheduler``. Results are saved on this thread as they arrive.
"""

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QMessageBox

from anylabeling.services.auto_labeling.utils.vlm import load_settings
from anylabeling.services.auto_labeling.utils.vlm.scheduler import (
    run_adaptive_batch,
)
from anylabeling.views.labeling.logger import logger

_MAX_LISTED_FAILURES = 10


class VLMBatchThread(QThread):
    progress_updated = pyqtSignal(int, str)
    processing_finished = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, app, image_files, model, text_prompt, save_result):
        super().__init__()
        self.app = app
        self.image_files = list(image_files)
        self.model = model
        self.text_prompt = text_prompt
        self.save_result = save_result
        self.failures = []
        self.stats = None

    def _work(self, image_file, cancel_event):
        return self.model.predict_shapes(
            None,
            image_file,
            text_prompt=self.text_prompt,
            cancel_event=cancel_event,
        )

    def _on_result(self, image_file, result):
        result.image_path = image_file
        self.save_result(self.app, image_file, result)

    def _on_failure(self, image_file, error):
        logger.error(f"VLM batch failed for {image_file}: {error}")
        self.failures.append((image_file, str(error)))

    def run(self):
        settings = load_settings()
        batch = settings["batch"]
        total = len(self.image_files)
        last_label = None

        def on_status(stats, window):
            nonlocal last_label
            label = self.tr(
                "Progress: {done}/{total}  |  concurrency {window}/{limit}"
                "  |  running {running}  |  retries {retries}"
                "  |  failed {failed}"
            ).format(
                done=stats.done,
                total=total,
                window=stats.window,
                limit=stats.max_window,
                running=stats.in_flight,
                retries=stats.retries,
                failed=stats.failed,
            )
            if window.in_cooldown():
                label += self.tr("  |  backing off")
            if label != last_label:
                last_label = label
                self.progress_updated.emit(stats.done, label)

        try:
            self.stats = run_adaptive_batch(
                self.image_files,
                self._work,
                max_window=int(batch["max_concurrency"]),
                hard_timeout=float(settings["timeout"]),
                max_retries=int(batch["max_retries"]),
                cooldown=float(batch["cooldown_seconds"]),
                is_cancelled=lambda: bool(
                    getattr(self.app, "cancel_processing", False)
                ),
                on_result=self._on_result,
                on_failure=self._on_failure,
                on_status=on_status,
            )
        except Exception as exc:  # noqa: BLE001 - surface to the UI
            logger.exception("VLM batch crashed")
            self.error_occurred.emit(str(exc))
            return
        logger.info(
            f"VLM batch finished: {self.stats.succeeded} succeeded, "
            f"{self.stats.failed} failed, {self.stats.retries} retries, "
            f"aborted={self.stats.aborted!r}"
        )
        if self.stats.aborted and self.stats.aborted != "cancelled":
            self.error_occurred.emit(self.stats.aborted)
        else:
            self.processing_finished.emit()


def _failure_summary(app, thread):
    if not thread.failures:
        return
    lines = [
        f"{image_file}: {error[:160]}"
        for image_file, error in thread.failures[:_MAX_LISTED_FAILURES]
    ]
    if len(thread.failures) > _MAX_LISTED_FAILURES:
        lines.append("...")
    QMessageBox.warning(
        app,
        app.tr("VLM batch"),
        app.tr("{count} image(s) could not be labeled:").format(
            count=len(thread.failures)
        )
        + "\n\n"
        + "\n".join(lines),
    )


def start_vlm_batch(
    app,
    progress_dialog,
    image_files,
    text_prompt,
    *,
    save_result,
    finish_processing,
    reset_state,
):
    """Start the concurrent VLM batch and wire it to the progress dialog."""
    model = app.auto_labeling_widget.model_manager.loaded_model_config["model"]
    thread = VLMBatchThread(app, image_files, model, text_prompt, save_result)
    app._batch_thread = thread

    def on_progress(value, label):
        progress_dialog.setValue(value)
        progress_dialog.setLabelText(label)

    def on_finished():
        finish_processing(app, progress_dialog)
        _failure_summary(app, thread)

    def on_error(message):
        reset_state(app)
        progress_dialog.close()
        logger.error(f"VLM batch stopped: {message}")
        QMessageBox.critical(
            app,
            app.tr("VLM batch"),
            app.tr("Batch stopped: {reason}").format(reason=message[:600]),
        )
        _failure_summary(app, thread)

    thread.progress_updated.connect(on_progress)
    thread.processing_finished.connect(on_finished)
    thread.error_occurred.connect(on_error)
    thread.start()
    return thread
