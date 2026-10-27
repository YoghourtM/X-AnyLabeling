import os
import stat
import sys
import tempfile
import textwrap
import threading
import time
import unittest
from unittest.mock import Mock, patch

from PIL import Image
from PyQt6.QtGui import QColor, QImage
from PyQt6.QtWidgets import QApplication

from anylabeling.services.auto_labeling.types import AutoLabelingResult
from anylabeling.services.auto_labeling.utils.vlm import load_settings
from anylabeling.services.auto_labeling.utils.vlm.providers import (
    CodexCLIProvider,
    OpenAIChatProvider,
    VLMCancelledError,
    VLMCongestionError,
    VLMFatalError,
    VLMProviderError,
    classified_error,
)
from anylabeling.services.auto_labeling.utils.vlm.scheduler import (
    AdaptiveWindow,
    run_adaptive_batch,
)
from anylabeling.services.auto_labeling.vlm_annotator import VLMAnnotator
from anylabeling.views.labeling.utils.vlm_batch import VLMBatchThread


_app = QApplication.instance() or QApplication([])


def _write_executable(directory, name, body):
    path = os.path.join(directory, name)
    with open(path, "w", encoding="utf-8") as stream:
        stream.write(f"#!{sys.executable}\n" + textwrap.dedent(body))
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
    return path


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class TestAdaptiveWindow(unittest.TestCase):
    def test_slow_start_then_additive_increase_after_backoff(self):
        clock = FakeClock()
        window = AdaptiveWindow(8, cooldown=10, clock=clock)
        sizes = []
        for _ in range(7):
            window.on_success(1.0)
            sizes.append(window.current)
        # 1 -> 2 after one success, -> 4 after two more, -> 8 after four.
        self.assertEqual(sizes, [2, 2, 4, 4, 4, 4, 8])

        clock.now = 5
        self.assertTrue(window.on_congestion(started_at=4))
        self.assertEqual((window.current, window.ssthresh), (4, 4))
        # Requests that started before the decrease do not shrink it again.
        self.assertFalse(window.on_congestion(started_at=4.5))
        self.assertEqual(window.current, 4)

        for _ in range(8):  # still cooling down: no growth
            window.on_success(1.0)
        self.assertEqual(window.current, 4)

        clock.now = 16
        for _ in range(4):
            window.on_success(1.0)
        self.assertEqual(window.current, 5)  # +1 per round, not doubling

    def test_window_never_drops_below_one_or_exceeds_limit(self):
        clock = FakeClock()
        window = AdaptiveWindow(3, cooldown=0, clock=clock)
        for _ in range(20):
            window.on_success(1.0)
        self.assertEqual(window.current, 3)
        for step in range(5):
            clock.now += 1
            window.on_congestion(started_at=clock.now)
        self.assertEqual(window.current, 1)

    def test_stall_threshold_tracks_latency(self):
        window = AdaptiveWindow(4, min_stall_seconds=5, clock=FakeClock())
        self.assertEqual(window.stall_seconds(600), 600)
        for latency in (10, 12, 11, 10):
            window.on_success(latency)
        self.assertGreater(window.stall_seconds(600), 10)
        self.assertLess(window.stall_seconds(600), 40)
        self.assertEqual(window.stall_seconds(20), 20)


class TestRunAdaptiveBatch(unittest.TestCase):
    def _run(self, items, work, **kwargs):
        options = dict(
            max_window=4,
            hard_timeout=30,
            cooldown=0.05,
            poll_seconds=0.01,
            min_stall_seconds=5,
        )
        options.update(kwargs)
        results, failures, windows = {}, {}, []
        stats = run_adaptive_batch(
            items,
            work,
            on_result=lambda item, result: results.__setitem__(item, result),
            on_failure=lambda item, error: failures.__setitem__(item, error),
            on_status=lambda s, w: windows.append(w),
            **options,
        )
        return stats, results, failures, windows[-1]

    def test_concurrency_ramps_up_to_the_limit(self):
        lock = threading.Lock()
        active = [0, 0]  # current, peak

        def work(item, cancel_event):
            with lock:
                active[0] += 1
                active[1] = max(active[1], active[0])
            time.sleep(0.03)
            with lock:
                active[0] -= 1
            return item * 2

        stats, results, failures, _ = self._run(list(range(24)), work)
        self.assertEqual(results, {i: i * 2 for i in range(24)})
        self.assertEqual((stats.succeeded, stats.failed), (24, 0))
        self.assertEqual(active[1], 4)

    def test_rejections_back_off_and_are_retried(self):
        attempts = {}
        lock = threading.Lock()

        def work(item, cancel_event):
            with lock:
                attempts[item] = attempts.get(item, 0) + 1
                first = attempts[item] == 1
            if item % 3 == 0 and first:
                raise VLMCongestionError("429 Too Many Requests")
            return item

        stats, results, failures, window = self._run(list(range(12)), work)
        self.assertEqual(sorted(results), list(range(12)))
        self.assertFalse(failures)
        self.assertEqual(stats.retries, 4)
        self.assertGreaterEqual(window.decreases, 1)

    def test_exhausted_retries_are_reported(self):
        def work(item, cancel_event):
            if item == "bad":
                raise ValueError("unparseable reply")
            return item

        stats, results, failures, _ = self._run(
            ["a", "bad", "b"], work, max_retries=2
        )
        self.assertEqual(set(results), {"a", "b"})
        self.assertIsInstance(failures["bad"], ValueError)
        self.assertEqual((stats.failed, stats.retries), (1, 2))

    def test_fatal_error_aborts_the_batch(self):
        def work(item, cancel_event):
            raise VLMFatalError("401 unauthorized")

        stats, results, failures, _ = self._run(list(range(10)), work)
        self.assertIn("401", stats.aborted)
        self.assertFalse(results)
        self.assertEqual(stats.done, 1)

    def test_cancel_stops_submitting_and_interrupts_running(self):
        started = threading.Event()
        cancelled = threading.Event()

        def work(item, cancel_event):
            started.set()
            if cancel_event.wait(5):
                raise VLMCancelledError("cancelled")
            return item

        # Run in a helper thread so the test can flip the cancel flag.
        box = {}
        runner = threading.Thread(
            target=lambda: box.update(
                out=self._run(
                    list(range(50)), work, is_cancelled=cancelled.is_set
                )
            )
        )
        runner.start()
        self.assertTrue(started.wait(5))
        cancelled.set()
        runner.join(10)
        self.assertFalse(runner.is_alive())
        stats, results, _, _ = box["out"]
        self.assertEqual(stats.aborted, "cancelled")
        self.assertFalse(results)

    def test_circuit_breaker_at_concurrency_one(self):
        def work(item, cancel_event):
            raise VLMProviderError("relay returned garbage")

        stats, _, _, _ = self._run(
            list(range(100)), work, max_retries=10, max_consecutive_failures=5
        )
        self.assertIn("consecutive failures", stats.aborted)
        self.assertLess(stats.retries, 100)

    def test_stalled_request_shrinks_window_without_killing_it(self):
        def work(item, cancel_event):
            time.sleep(0.6 if item == 9 else 0.01)
            return item

        stats, results, _, window = self._run(
            list(range(10)), work, min_stall_seconds=0.1, cooldown=0.01
        )
        self.assertEqual(len(results), 10)
        self.assertGreaterEqual(window.decreases, 1)


class TestErrorClassification(unittest.TestCase):
    def test_classified_error(self):
        self.assertIsInstance(
            classified_error("x", "HTTP 429 Too Many Requests"),
            VLMCongestionError,
        )
        self.assertIsInstance(
            classified_error("x", "stream disconnected before completion"),
            VLMCongestionError,
        )
        self.assertIsInstance(
            classified_error("x", "401 Unauthorized: not logged in"),
            VLMFatalError,
        )
        error = classified_error("x", "schema mismatch")
        self.assertIs(type(error), VLMProviderError)

    def test_codex_rate_limit_exit_is_congestion(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = _write_executable(
                tmp,
                "codex",
                'import sys; print(\'{"type":"error","message":'
                '"rate limit reached"}\'); sys.exit(1)\n',
            )
            image = os.path.join(tmp, "a.jpg")
            Image.new("RGB", (8, 8)).save(image)
            with self.assertRaises(VLMCongestionError):
                CodexCLIProvider(fake).annotate(image, "p", {}, 30)

    def test_openai_errors_are_mapped(self):
        import openai

        def raising(exc):
            create = Mock(side_effect=exc)
            return Mock(chat=Mock(completions=Mock(create=create)))

        response = Mock(status_code=429, headers={})
        provider = OpenAIChatProvider("http://relay/v1", "k", "m")
        with tempfile.TemporaryDirectory() as tmp:
            image = os.path.join(tmp, "a.jpg")
            Image.new("RGB", (8, 8)).save(image)
            for exc, expected in (
                (
                    openai.RateLimitError(
                        "slow down", response=response, body=None
                    ),
                    VLMCongestionError,
                ),
                (
                    openai.AuthenticationError(
                        "bad key",
                        response=Mock(status_code=401, headers={}),
                        body=None,
                    ),
                    VLMFatalError,
                ),
            ):
                with patch.object(
                    provider, "_client", return_value=raising(exc)
                ):
                    with self.assertRaises(expected):
                        provider.annotate(image, "p", {}, 30)


class TestBatchThreadAndFileSource(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.files = []
        for index in range(5):
            path = os.path.join(self.tmp.name, f"img{index}.jpg")
            Image.new("RGB", (300, 150), "white").save(path)
            self.files.append(path)
        with patch(
            "anylabeling.services.auto_labeling.model.get_config",
            return_value={},
        ):
            self.model = VLMAnnotator(
                {"type": "vlm_annotator", "name": "t", "display_name": "t"},
                Mock(),
            )

    def tearDown(self):
        self.tmp.cleanup()

    def test_label_space_comes_from_the_file_not_the_canvas(self):
        canvas = QImage(40, 20, QImage.Format.Format_RGB32)
        canvas.fill(QColor("black"))
        provider = Mock()
        provider.name = "fake"
        provider.annotate.return_value = {
            "objects": [
                {
                    "label": "x",
                    "bbox": [0, 0, 500, 500],
                    "polygon": [[0, 0], [500, 0], [500, 500]],
                    "confidence": 0.5,
                }
            ]
        }
        with (
            patch(
                "anylabeling.services.auto_labeling.vlm_annotator.load_settings",
                return_value=load_settings(os.devnull),
            ),
            patch(
                "anylabeling.services.auto_labeling.vlm_annotator.build_provider",
                return_value=provider,
            ),
        ):
            result = self.model.predict_shapes(canvas, self.files[0], "x")
        sent_path, prompt = provider.annotate.call_args.args[:2]
        self.assertEqual(sent_path, self.files[0])
        self.assertIn("300x150", prompt)
        self.assertEqual(
            [(p.x(), p.y()) for p in result.shapes[0].points],
            [(0.0, 0.0), (150.0, 0.0), (150.0, 75.0)],
        )

    def test_thread_labels_every_image_and_reports_failures(self):
        saved = []

        def predict(image, image_file, text_prompt, cancel_event):
            if image_file.endswith("img3.jpg"):
                raise ValueError("bad reply")
            return AutoLabelingResult([], replace=True)

        self.model.predict_shapes = predict
        settings = load_settings(os.devnull)
        settings["batch"].update(max_concurrency=3, max_retries=0)
        app = Mock(cancel_processing=False)
        thread = VLMBatchThread(
            app,
            self.files,
            self.model,
            "x",
            lambda app, image_file, result: saved.append(image_file),
        )
        finished = Mock()
        thread.processing_finished.connect(finished)
        with patch(
            "anylabeling.views.labeling.utils.vlm_batch.load_settings",
            return_value=settings,
        ):
            thread.run()  # synchronously, on this thread
        self.assertEqual(
            sorted(saved), sorted(self.files[:3] + self.files[4:])
        )
        self.assertEqual(
            [path for path, _ in thread.failures], [self.files[3]]
        )
        finished.assert_called_once()


if __name__ == "__main__":
    unittest.main()
