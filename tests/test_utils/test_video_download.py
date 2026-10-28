import json
import os
import shutil
import sys
import tempfile
import textwrap
import unittest
from unittest import mock

import cv2
import numpy as np
from PyQt6.QtWidgets import QApplication, QDialog

from anylabeling.views.labeling.utils import video_download as vd
from anylabeling.views.labeling.widgets.video_url_dialog import VideoUrlDialog

_app = QApplication.instance() or QApplication([])

# Stands in for yt-dlp: copies the video named by FAKE_VIDEO to the -o
# template and prints the lines VideoDownloadThread reads.
FAKE_YTDLP = textwrap.dedent(
    """
    import json, os, shutil, sys
    argv = sys.argv[1:]
    url = argv[-1]
    if "fail" in url:
        print("ERROR: [generic] Unable to download webpage: HTTP Error 404",
              file=sys.stderr)
        sys.exit(1)
    target = (argv[argv.index("-o") + 1]
              .replace("%(extractor_key)s", "Fake")
              .replace("%(id)s", "vid_1").replace("%(ext)s", "mp4"))
    shutil.copy(os.environ["FAKE_VIDEO"], target)
    for done in (500, 1000):
        print("XAL-PROGRESS " + json.dumps(
            {"status": "downloading", "downloaded_bytes": done,
             "total_bytes": 1000, "speed": 2048.0}))
    print("XAL-FILE " + target)
    print("XAL-INFO " + json.dumps(
        {"id": "vid_1", "title": "演示", "extractor_key": "Fake",
         "duration": float(os.environ.get("FAKE_DURATION", "60")),
         "webpage_url": url}))
    with open(target + ".argv.json", "w") as stream:
        json.dump(argv, stream)
"""
)


class TestParsing(unittest.TestCase):
    def test_plan_links_ranges_comments_and_share_text(self):
        jobs, problems = vd.parse_plan(
            "# my videos\n"
            "https://www.bilibili.com/video/BV1xx  0:10-0:30  1:00-1:20\n"
            "\n"
            "【盲道】 https://b23.tv/abc 1:00 - 1:30，2:00~2:10  # 注释\n"
            "https://youtu.be/x#t=5 5:00-\n"
            "https://www.youtube.com/watch?v=y\n"
            "https://z 1：00到1：30\n"
        )
        self.assertEqual(problems, [])
        self.assertEqual(
            jobs,
            [
                ("https://www.bilibili.com/video/BV1xx", [(10, 30), (60, 80)]),
                ("https://b23.tv/abc", [(60, 90), (120, 130)]),
                ("https://youtu.be/x#t=5", [(300, None)]),
                ("https://www.youtube.com/watch?v=y", [vd.WHOLE_VIDEO]),
                ("https://z", [(60, 90)]),
            ],
        )

    def test_plan_merges_repeated_links_and_overlapping_ranges(self):
        jobs, _ = vd.parse_plan(
            "https://a 0:25-0:40 0:10-0:30\n"
            "https://a 1:00-\n"
            "https://a 2:00-2:30\n"
            "https://b 10-20 20-30\n"
        )
        self.assertEqual(
            jobs,
            [("https://a", [(10, 40), (60, None)]), ("https://b", [(10, 30)])],
        )

    def test_plan_default_range_and_problems_name_the_line(self):
        jobs, problems = vd.parse_plan(
            "https://a\nhttps://b 1-2\n"
            "https://c 1:3o-2:00\nhttps://d 30-10\njust text\nhttps://e 5\n",
            default=(5.0, 9.0),
        )
        self.assertEqual(
            jobs, [("https://a", [(5, 9)]), ("https://b", [(1, 2)])]
        )
        self.assertEqual(len(problems), 4)
        self.assertTrue(problems[0].startswith("Line 3: not a time range"))
        self.assertIn("Line 4: the end must be after the start", problems[1])
        self.assertIn("Line 5: no http(s) link", problems[2])
        self.assertIn("Line 6", problems[3])

    def test_format_time(self):
        self.assertEqual(
            [vd.format_time(t) for t in (0, 10, 90, 3723.5)],
            ["0:00", "0:10", "1:30", "1:02:03.5"],
        )
        self.assertEqual(vd.format_range(5, None), "0:05-")
        self.assertEqual(vd.format_range(60, 80), "1:00-1:20")

    def test_times(self):
        self.assertIsNone(vd.parse_time("  "))
        self.assertEqual(vd.parse_time("90"), 90)
        self.assertEqual(vd.parse_time("1:30"), 90)
        self.assertEqual(vd.parse_time("1：02：03.5"), 3723.5)
        for bad in ("1:2:3:4", "abc", "-5", "1:"):
            with self.assertRaises(ValueError):
                vd.parse_time(bad)

    def test_section_spec(self):
        self.assertIsNone(vd.section_spec(None, None))
        self.assertIsNone(vd.section_spec(*vd.WHOLE_VIDEO))
        self.assertEqual(vd.section_spec(90, None), "*90-inf")
        self.assertEqual(vd.section_spec(None, 12.5), "*0-12.5")
        with self.assertRaises(ValueError):
            vd.section_spec(20, 10)

    def test_frame_names_add_milliseconds_only_when_needed(self):
        self.assertEqual(
            vd.frame_names("bilibili", "BV1", vd.frame_times(2, 1.0, 10)),
            ["bilibili_BV1_t000010.jpg", "bilibili_BV1_t000011.jpg"],
        )
        self.assertEqual(
            vd.frame_names("youtube", "a-b_c", vd.frame_times(2, 2.0)),
            ["youtube_a-b_c_t000000_000.jpg", "youtube_a-b_c_t000000_500.jpg"],
        )
        self.assertEqual(vd.safe_name("a/b c?"), "a_b_c")
        self.assertEqual(vd.safe_name(""), "video")

    def test_progress_lines(self):
        line = vd.PROGRESS_MARK + json.dumps(
            {
                "status": "downloading",
                "downloaded_bytes": 50,
                "total_bytes_estimate": 200,
                "speed": 1.0,
            }
        )
        self.assertEqual(vd.parse_progress(line)["fraction"], 0.25)
        self.assertIsNone(
            vd.parse_progress(vd.PROGRESS_MARK + '{"status": "finished"}')[
                "fraction"
            ]
        )
        self.assertIsNone(vd.parse_progress("[download] 5%"))
        self.assertIsNone(vd.parse_progress(vd.PROGRESS_MARK + "{oops"))


class TestCommandAndErrors(unittest.TestCase):
    def test_command(self):
        settings = dict(
            vd.DEFAULT_SETTINGS,
            max_height=720,
            cookies_browser="chrome",
            proxy="http://127.0.0.1:7890",
        )
        with mock.patch.object(vd.shutil, "which", return_value=None):
            argv = vd.build_download_command(
                ["yt-dlp"],
                "https://x/v",
                "/o/%(id)s.%(ext)s",
                settings,
                "*1-2",
            )
        self.assertEqual(argv[-2:], ["--", "https://x/v"])
        self.assertIn("--no-playlist", argv)
        option = lambda name: argv[argv.index(name) + 1]  # noqa: E731
        self.assertEqual(option("-f"), "bv*[height<=720]/b[height<=720]/bv*/b")
        self.assertEqual(option("--download-sections"), "*1-2")
        self.assertEqual(option("--cookies-from-browser"), "chrome")
        self.assertEqual(option("--proxy"), "http://127.0.0.1:7890")
        self.assertNotIn("--js-runtimes", argv)
        self.assertEqual(vd.format_selector(0), "bv*/b")
        with mock.patch.object(vd.shutil, "which", return_value="/bin/node"):
            argv = vd.build_download_command(
                ["yt-dlp"], "u", "o", vd.DEFAULT_SETTINGS, None
            )
        self.assertIn("--js-runtimes", argv)
        self.assertNotIn("--download-sections", argv)

    def test_find_ytdlp(self):
        with mock.patch.object(vd.shutil, "which", return_value=None):
            with self.assertRaises(vd.VideoDownloadError):
                vd.find_ytdlp("/missing/yt-dlp")
            with mock.patch.object(
                vd.importlib.util, "find_spec", return_value=None
            ):
                with self.assertRaises(vd.VideoDownloadError):
                    vd.find_ytdlp()
        with mock.patch.object(
            vd.importlib.util, "find_spec", return_value=object()
        ):
            self.assertEqual(vd.find_ytdlp(), [sys.executable, "-m", "yt_dlp"])

    def test_errors_get_a_hint_and_keep_the_detail(self):
        cases = {
            "ERROR: [youtube] Sign in to confirm you're not a bot": "login",
            "ERROR: [BiliBili] HTTP Error 412: Precondition Failed": "login",
            "ERROR: could not find chrome cookies database": "cookies",
            "ERROR: Unsupported URL: https://example.com/": "not a video",
            "ERROR: Unable to download webpage: HTTP Error 404": "not found",
            "ERROR: [youtube] x: Video unavailable": "unavailable",
            "yt-dlp: error: no such option: --js-runtimes": "outdated",
            "ERROR: Unable to download webpage: timed out": "Network",
        }
        for stderr, word in cases.items():
            message = vd.describe_error("WARNING: noise\n" + stderr)
            self.assertIn(word, message, stderr)
            self.assertIn(stderr.splitlines()[-1], message)
        self.assertEqual(vd.describe_error("line 1\nline 2"), "line 2")
        self.assertIn("without", vd.describe_error(""))


class TestSettingsAndSources(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)

    def test_settings_round_trip_keeps_known_keys_only(self):
        path = os.path.join(self.tmp, "s", "settings.json")
        self.assertEqual(vd.load_settings(path), vd.DEFAULT_SETTINGS)
        vd.save_settings(dict(vd.DEFAULT_SETTINGS, fps=0.5, junk=1), path)
        self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
        loaded = vd.load_settings(path)
        self.assertEqual(loaded["fps"], 0.5)
        self.assertNotIn("junk", loaded)

    def test_sources_replace_the_same_run_and_back_up_bad_files(self):
        entry = {"url": "u", "section": None, "fps": 1.0, "frames": [1]}
        vd.update_sources(self.tmp, entry)
        vd.update_sources(self.tmp, dict(entry, frames=[2]))
        vd.update_sources(self.tmp, dict(entry, fps=2.0))
        path = os.path.join(self.tmp, vd.SOURCES_FILE)
        with open(path, encoding="utf-8") as stream:
            videos = json.load(stream)["videos"]
        self.assertEqual([v["frames"] for v in videos], [[2], [1]])
        with open(path, "w") as stream:
            stream.write("{broken")
        vd.update_sources(self.tmp, entry)
        self.assertTrue(os.path.exists(path + ".bak"))

    def test_links_file_encodings(self):
        path = os.path.join(self.tmp, "links.txt")
        with open(path, "wb") as stream:
            stream.write("# 视频\nhttps://b23.tv/x\n".encode("gb18030"))
        self.assertIn("https://b23.tv/x", vd.read_links_file(path))


@unittest.skipIf(shutil.which("ffmpeg") is None, "needs ffmpeg")
class TestDownloadThread(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.video = os.path.join(self.tmp, "source.avi")
        writer = cv2.VideoWriter(
            self.video, cv2.VideoWriter_fourcc(*"MJPG"), 10, (64, 48)
        )
        for index in range(40):  # 4 s at 10 fps
            writer.write(np.full((48, 64, 3), index * 6, np.uint8))
        writer.release()
        script = os.path.join(self.tmp, "fake_ytdlp.py")
        with open(script, "w") as stream:
            stream.write(FAKE_YTDLP)
        self.prefix = [sys.executable, script]
        os.environ["FAKE_VIDEO"] = self.video
        self.addCleanup(os.environ.pop, "FAKE_VIDEO", None)

    def _run(self, urls, start=None, end=None, **settings):
        frames_dir = os.path.join(self.tmp, "frames")
        thread = vd.VideoDownloadThread(
            urls,
            frames_dir,
            dict(
                vd.DEFAULT_SETTINGS,
                video_dir=os.path.join(self.tmp, "videos"),
                **settings,
            ),
            start,
            end,
        )
        result, labels = {}, []
        thread.finished_all.connect(
            lambda d, n, f: result.update(dir=d, count=n, failures=f)
        )
        thread.progress_updated.connect(lambda v, text: labels.append(v))
        with mock.patch.object(vd, "find_ytdlp", return_value=self.prefix):
            thread.run()
        _app.processEvents()
        return frames_dir, result, labels

    def test_frames_sources_and_failures(self):
        frames_dir, result, labels = self._run(
            ["https://fake/v", "https://fake/fail"]
        )
        names = sorted(n for n in os.listdir(frames_dir) if n.endswith("jpg"))
        self.assertEqual(result["count"], 4)
        self.assertEqual(names[0], "fake_vid_1_t000000.jpg")
        self.assertEqual(names[-1], "fake_vid_1_t000003.jpg")
        # Frame k shows the video at k s: the source is 10 frames of
        # brightness 6, 12, ... per second.
        brightness = [
            cv2.imread(os.path.join(frames_dir, name)).mean() for name in names
        ]
        np.testing.assert_allclose(brightness, [0, 60, 120, 180], atol=4)
        self.assertEqual(labels, sorted(labels))
        [(url, error)] = result["failures"]
        self.assertEqual(url, "https://fake/fail")
        self.assertIn("HTTP Error 404", error)
        with open(os.path.join(frames_dir, vd.SOURCES_FILE)) as stream:
            [video] = json.load(stream)["videos"]
        self.assertEqual(video["title"], "演示")
        self.assertEqual(video["frames"][1], {"file": names[1], "time": 1.0})
        self.assertTrue(os.path.isfile(video["video_file"]))
        # No temporary frame folders are left behind.
        videos = os.listdir(os.path.join(self.tmp, "videos"))
        self.assertFalse([n for n in videos if n.startswith(".frames_")])

    def test_section_offsets_times_and_videos_can_be_dropped(self):
        frames_dir, result, _ = self._run(
            ["https://fake/v"], start=10, end=14, fps=2.0, keep_videos=False
        )
        names = sorted(n for n in os.listdir(frames_dir) if n.endswith("jpg"))
        self.assertEqual(
            names[:2],
            [
                "fake_vid_1_t000010_000.jpg",
                "fake_vid_1_t000010_500.jpg",
            ],
        )
        video_dir = os.path.join(self.tmp, "videos")
        argv_files = [n for n in os.listdir(video_dir) if n.endswith(".json")]
        self.assertEqual(argv_files, ["Fake_vid_1_s10-14.mp4.argv.json"])
        self.assertFalse(
            os.path.exists(os.path.join(video_dir, "Fake_vid_1_s10-14.mp4"))
        )

    def test_frames_after_the_section_end_are_dropped(self):
        # The fake download is 4 s long, so frames run past a 2 s section.
        frames_dir, result, _ = self._run(["https://fake/v"], start=10, end=12)
        names = sorted(n for n in os.listdir(frames_dir) if n.endswith("jpg"))
        self.assertEqual(result["count"], 2)
        self.assertEqual(
            names, ["fake_vid_1_t000010.jpg", "fake_vid_1_t000011.jpg"]
        )

    def test_several_sections_of_one_video(self):
        frames_dir, result, labels = self._run(
            [("https://fake/v", [(20, 22), (10, 12)])]
        )
        names = sorted(n for n in os.listdir(frames_dir) if n.endswith("jpg"))
        self.assertEqual(
            names,
            [
                "fake_vid_1_t000010.jpg",
                "fake_vid_1_t000011.jpg",
                "fake_vid_1_t000020.jpg",
                "fake_vid_1_t000021.jpg",
            ],
        )
        self.assertEqual((result["count"], result["failures"]), (4, []))
        self.assertEqual(labels, sorted(labels))
        video_dir = os.path.join(self.tmp, "videos")
        argv_files = sorted(
            n for n in os.listdir(video_dir) if n.endswith(".json")
        )
        self.assertEqual(
            argv_files,
            [
                "Fake_vid_1_s10-12.mp4.argv.json",
                "Fake_vid_1_s20-22.mp4.argv.json",
            ],
        )
        with open(os.path.join(frames_dir, vd.SOURCES_FILE)) as stream:
            videos = json.load(stream)["videos"]
        self.assertEqual(
            [(v["section"], v["start"], v["end"]) for v in videos],
            [("*10-12", 10, 12), ("*20-22", 20, 22)],
        )

    def test_section_after_the_video_end_fails_and_is_removed(self):
        os.environ["FAKE_DURATION"] = "15"
        self.addCleanup(os.environ.pop, "FAKE_DURATION", None)
        frames_dir, result, _ = self._run(
            [("https://fake/v", [(10, 12), (20, 22)])]
        )
        self.assertEqual(result["count"], 2)
        [(label, error)] = result["failures"]
        self.assertEqual(label, "https://fake/v  [0:20-0:22]")
        self.assertIn("after the video ends (0:15)", error)
        video_dir = os.path.join(self.tmp, "videos")
        self.assertFalse(
            os.path.exists(os.path.join(video_dir, "Fake_vid_1_s20-22.mp4"))
        )

    def test_missing_ytdlp_is_reported_once(self):
        thread = vd.VideoDownloadThread(["u"], self.tmp, vd.DEFAULT_SETTINGS)
        result = {}
        thread.finished_all.connect(
            lambda d, n, f: result.update(count=n, failures=f)
        )
        error = vd.VideoDownloadError("yt-dlp is not installed")
        with mock.patch.object(vd, "find_ytdlp", side_effect=error):
            thread.run()
        _app.processEvents()
        self.assertEqual(result, {"count": 0, "failures": [("", str(error))]})


class TestDialog(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.settings_path = os.path.join(self.tmp, "settings.json")
        patcher = mock.patch(
            "anylabeling.views.labeling.widgets.video_url_dialog."
            "QMessageBox.warning"
        )
        self.warning = patcher.start()
        self.addCleanup(patcher.stop)

    def test_accept_validates_and_saves(self):
        dialog = VideoUrlDialog(settings_path=self.settings_path)
        dialog.accept()
        self.assertTrue(self.warning.called)
        self.assertIsNone(dialog.request())
        dialog.links_edit.setPlainText("https://b23.tv/x 2:00-1:00")
        dialog.accept()
        self.assertIn("Line 1", self.warning.call_args[0][2])
        self.assertIsNone(dialog.request())
        dialog.links_edit.setPlainText(
            "https://b23.tv/x\nhttps://b23.tv/y 0:10-0:20 0:40-"
        )
        dialog.start_edit.setText("1:30")
        dialog.end_edit.setText("1:00")
        dialog.accept()
        self.assertIsNone(dialog.request())
        dialog.end_edit.setText("2:00")
        dialog.fps_spin.setValue(0.5)
        dialog.frames_edit.setText(os.path.join(self.tmp, "frames"))
        dialog.accept()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        request = dialog.request()
        # The default range is for links without ranges of their own.
        self.assertEqual(
            request["jobs"],
            [
                ("https://b23.tv/x", [(90, 120)]),
                ("https://b23.tv/y", [(10, 20), (40, None)]),
            ],
        )
        self.assertEqual(vd.load_settings(self.settings_path)["fps"], 0.5)


if __name__ == "__main__":
    unittest.main()
