import json
import os
import stat
import sys
import tempfile
import textwrap
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PyQt6.QtGui import QColor, QImage

from anylabeling.services.auto_labeling.utils.vlm import (
    RESPONSE_SCHEMA,
    ClassSpec,
    VLMCancelledError,
    VLMProviderError,
    build_prompt,
    build_provider,
    load_settings,
    parse_class_prompt,
    parse_detections,
    save_settings,
)
from anylabeling.services.auto_labeling.utils.vlm.providers import (
    ClaudeCLIProvider,
    CodexCLIProvider,
    OpenAIChatProvider,
    run_command,
)
from anylabeling.services.auto_labeling.vlm_annotator import VLMAnnotator


def _write_executable(directory, name, body):
    path = os.path.join(directory, name)
    with open(path, "w", encoding="utf-8") as stream:
        stream.write(f"#!{sys.executable}\n" + textwrap.dedent(body))
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
    return path


class TestClassPrompt(unittest.TestCase):
    def test_comma_separated_names(self):
        self.assertEqual(
            parse_class_prompt("car, person，car"),
            [ClassSpec("car"), ClassSpec("person")],
        )

    def test_descriptions_are_split_by_semicolon_or_newline(self):
        classes = parse_class_prompt(
            "tactile_paving: raised dots, bars; crosswalk\nhole：坑洼"
        )
        self.assertEqual(
            classes,
            [
                ClassSpec("tactile_paving", "raised dots, bars"),
                ClassSpec("crosswalk"),
                ClassSpec("hole", "坑洼"),
            ],
        )

    def test_prompt_mentions_classes_and_size(self):
        prompt = build_prompt(
            [ClassSpec("a", "desc")], 640, 480, instructions="be strict"
        )
        self.assertIn("- a: desc", prompt)
        self.assertIn("640x480", prompt)
        self.assertIn("be strict", prompt)


class TestParseDetections(unittest.TestCase):
    classes = [ClassSpec("tactile_paving")]

    def test_scales_normalized_coordinates_to_pixels(self):
        reply = {
            "objects": [
                {
                    "label": "Tactile_Paving",
                    "bbox": [500, 0, 0, 500],
                    "polygon": [[0, 0], [500, 0], [500, 500], [0, 0]],
                    "confidence": 1.4,
                }
            ]
        }
        [det] = parse_detections(reply, self.classes, 200, 100)
        self.assertEqual(det.label, "tactile_paving")
        self.assertEqual(det.bbox, (0.0, 0.0, 100.0, 50.0))
        self.assertEqual(det.polygon, [(0, 0), (100, 0), (100, 50)])
        self.assertEqual(det.confidence, 1.0)

    def test_fenced_text_unknown_labels_and_bad_geometry(self):
        reply = (
            "Here you go:\n```json\n"
            + json.dumps(
                {
                    "objects": [
                        {"label": "dog", "bbox": [0, 0, 10, 10]},
                        {
                            "label": "tactile_paving",
                            "bbox": "oops",
                            "polygon": [[0, 0], [1000, 0], [1000, 1200]],
                        },
                        {"label": "tactile_paving", "polygon": [[1, 1]]},
                    ]
                }
            )
            + "\n```"
        )
        [det] = parse_detections(reply, self.classes, 100, 100)
        self.assertEqual(det.bbox, (0.0, 0.0, 100.0, 100.0))
        self.assertEqual(len(det.polygon), 3)

    def test_reply_without_objects_is_an_error(self):
        with self.assertRaises(ValueError):
            parse_detections('{"items": []}', self.classes, 10, 10)


class TestProviders(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.image = os.path.join(self.tmp.name, "image.jpg")
        with open(self.image, "wb") as stream:
            stream.write(b"\xff\xd8fake")

    def tearDown(self):
        self.tmp.cleanup()

    def test_codex_cli_round_trip(self):
        fake = _write_executable(
            self.tmp.name,
            "codex",
            """
            import json, sys
            argv = sys.argv
            prompt = sys.stdin.read()
            out = argv[argv.index("--output-last-message") + 1]
            assert argv[argv.index("--image") + 1].endswith("image.jpg")
            assert "--model" in argv and "medium" in argv[-2]
            json.dump({"objects": [], "prompt": prompt}, open(out, "w"))
            """,
        )
        provider = CodexCLIProvider(fake, "m", "medium")
        reply = provider.annotate(self.image, "hello", RESPONSE_SCHEMA, 30)
        self.assertEqual(json.loads(reply)["prompt"], "hello")

    def test_codex_cli_failure_is_reported(self):
        fake = _write_executable(
            self.tmp.name,
            "codex",
            "import sys; sys.stderr.write('boom'); sys.exit(3)\n",
        )
        with self.assertRaisesRegex(VLMProviderError, "boom"):
            CodexCLIProvider(fake).annotate(
                self.image, "p", RESPONSE_SCHEMA, 30
            )

    def test_claude_cli_sends_image_and_reads_structured_output(self):
        fake = _write_executable(
            self.tmp.name,
            "claude",
            """
            import json, sys
            message = json.loads(sys.stdin.readline())
            content = message["message"]["content"]
            assert content[0]["source"]["media_type"] == "image/jpeg"
            assert "--json-schema" in sys.argv and "--tools" in sys.argv
            print(json.dumps({"type": "system"}))
            print(json.dumps({"type": "result", "is_error": False,
                              "structured_output": {"objects": []}}))
            """,
        )
        reply = ClaudeCLIProvider(fake).annotate(
            self.image, "p", RESPONSE_SCHEMA, 30
        )
        self.assertEqual(reply, {"objects": []})

    def test_claude_error_result(self):
        with self.assertRaises(VLMProviderError):
            ClaudeCLIProvider.parse_stream(
                json.dumps({"type": "result", "is_error": True})
            )

    def test_run_command_timeout_and_cancel(self):
        sleeper = [sys.executable, "-c", "import time; time.sleep(30)"]
        with self.assertRaisesRegex(VLMProviderError, "timed out"):
            run_command(sleeper, "", 1, self.tmp.name)
        cancel = threading.Event()
        cancel.set()
        with self.assertRaises(VLMCancelledError):
            run_command(sleeper, "", 30, self.tmp.name, cancel)

    def test_large_stdin_reaches_a_slow_starting_cli(self):
        # Regression: a polling communicate() stopped feeding stdin once the
        # pipe buffer filled, so CLIs that start slowly (node) hung forever.
        slow_reader = [
            sys.executable,
            "-c",
            "import sys, time; time.sleep(1.5); "
            "print(len(sys.stdin.read()))",
        ]
        payload = "x" * (2 * 1024 * 1024)
        code, stdout, _ = run_command(slow_reader, payload, 30, self.tmp.name)
        self.assertEqual((code, stdout.strip()), (0, str(len(payload))))

    def test_missing_command(self):
        with self.assertRaisesRegex(VLMProviderError, "not found"):
            CodexCLIProvider("definitely-not-a-command-xyz").annotate(
                self.image, "p", RESPONSE_SCHEMA, 30
            )

    def test_openai_degrades_response_format(self):
        from openai import BadRequestError

        rejected = BadRequestError(
            "unsupported", response=Mock(status_code=400), body=None
        )
        reply = SimpleNamespace(
            choices=[
                SimpleNamespace(message=SimpleNamespace(content='{"o":1}'))
            ]
        )
        create = Mock(side_effect=[rejected, reply])
        client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create))
        )
        provider = OpenAIChatProvider("http://relay/v1", "k", "gpt")
        with patch.object(provider, "_client", return_value=client):
            self.assertEqual(
                provider.annotate(self.image, "p", RESPONSE_SCHEMA, 30),
                '{"o":1}',
            )
        first, second = (c.kwargs for c in create.call_args_list)
        self.assertEqual(first["response_format"]["type"], "json_schema")
        self.assertEqual(second["response_format"]["type"], "json_object")
        image_part = first["messages"][0]["content"][0]
        self.assertTrue(
            image_part["image_url"]["url"].startswith(
                "data:image/jpeg;base64,"
            )
        )

    def test_build_provider_uses_env_fallback(self):
        with patch.dict(
            os.environ,
            {"OPENAI_API_KEY": "env-key", "OPENAI_BASE_URL": "http://e"},
        ):
            provider = build_provider(
                {"provider": "openai_chat", "openai": {"model": "m"}}
            )
        self.assertEqual(provider.api_key, "env-key")
        self.assertEqual(provider.base_url, "http://e")
        with self.assertRaises(VLMProviderError):
            build_provider({"provider": "nope"})


class TestSettings(unittest.TestCase):
    def test_round_trip_merges_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "vlm", "settings.json")
            settings = load_settings(path)
            self.assertEqual(settings["provider"], "codex_cli")
            settings["openai"]["model"] = "gpt"
            save_settings(settings, path)
            with open(path, "w", encoding="utf-8") as stream:
                json.dump({"openai": {"model": "gpt"}, "bogus": 1}, stream)
            loaded = load_settings(path)
            self.assertEqual(loaded["openai"]["model"], "gpt")
            self.assertEqual(loaded["codex"]["reasoning_effort"], "medium")
            self.assertNotIn("bogus", loaded)


class FakeProvider:
    name = "fake"

    def __init__(self, reply):
        self.reply = reply
        self.calls = []

    def annotate(self, image_path, prompt, schema, timeout, cancel_event=None):
        self.calls.append((image_path, prompt))
        return self.reply


class TestVLMAnnotatorModel(unittest.TestCase):
    def setUp(self):
        with patch(
            "anylabeling.services.auto_labeling.model.get_config",
            return_value={},
        ):
            self.model = VLMAnnotator(
                {
                    "type": "vlm_annotator",
                    "name": "vlm_annotator-test",
                    "display_name": "VLM",
                },
                Mock(),
            )
        self.image = QImage(200, 100, QImage.Format.Format_RGB32)
        self.image.fill(QColor("gray"))
        self.reply = {
            "objects": [
                {
                    "label": "lane",
                    "bbox": [0, 0, 1000, 1000],
                    "polygon": [[100, 100], [500, 100], [500, 900]],
                    "confidence": 0.7,
                }
            ]
        }

    def _predict(self, prompt="lane"):
        provider = FakeProvider(self.reply)
        settings = load_settings(os.devnull)
        with (
            patch(
                "anylabeling.services.auto_labeling.vlm_annotator.load_settings",
                return_value=settings,
            ),
            patch(
                "anylabeling.services.auto_labeling.vlm_annotator.build_provider",
                return_value=provider,
            ),
        ):
            result = self.model.predict_shapes(self.image, None, prompt)
        return result, provider

    def test_polygon_output(self):
        result, provider = self._predict()
        [shape] = result.shapes
        self.assertEqual(shape.shape_type, "polygon")
        self.assertEqual(shape.label, "lane")
        self.assertEqual(
            [(p.x(), p.y()) for p in shape.points],
            [(20.0, 10.0), (100.0, 10.0), (100.0, 90.0)],
        )
        self.assertTrue(result.replace)
        image_path, prompt = provider.calls[0]
        self.assertIn("200x100", prompt)
        self.assertTrue(image_path.endswith(".jpg"))

    def test_rectangle_output_uses_polygon_bounds(self):
        self.model.set_output_mode("rectangle")
        self.model.set_auto_labeling_preserve_existing_annotations_state(True)
        result, _ = self._predict()
        [shape] = result.shapes
        self.assertEqual(shape.shape_type, "rectangle")
        self.assertEqual(
            [(p.x(), p.y()) for p in shape.points],
            [(20.0, 10.0), (100.0, 10.0), (100.0, 90.0), (20.0, 90.0)],
        )
        self.assertFalse(result.replace)

    def test_empty_prompt_is_rejected(self):
        with self.assertRaises(ValueError):
            self._predict(prompt="  ")


if __name__ == "__main__":
    unittest.main()
