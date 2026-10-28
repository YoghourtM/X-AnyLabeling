"""Download videos from links with yt-dlp and extract frames for labeling.

yt-dlp runs as an external program, like ffmpeg in ``video.py``: video
sites change often, and keeping up must only need ``pip install -U
"yt-dlp[default,deno]"``, never a new X-AnyLabeling release. Frames are named
``<site>_<video id>_t<seconds>.jpg`` so frames of several videos can share
one folder, and ``sources.json`` in that folder records where each frame
came from.
"""

import copy
import importlib.util
import json
import math
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
from datetime import datetime

from PyQt6.QtCore import QCoreApplication, Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import QDialog, QMessageBox, QProgressDialog

from anylabeling.config import get_work_directory
from anylabeling.views.labeling.logger import logger
from anylabeling.views.labeling.utils.qt import new_action
from anylabeling.views.labeling.utils.style import get_progress_dialog_style

PROGRESS_MARK = "XAL-PROGRESS "
FILE_MARK = "XAL-FILE "
INFO_MARK = "XAL-INFO "
SOURCES_FILE = "sources.json"
INFO_FIELDS = (
    "id",
    "title",
    "uploader",
    "webpage_url",
    "license",
    "duration",
    "extractor_key",
    "upload_date",
    "height",
)
PROGRESS_FIELDS = (
    "status",
    "downloaded_bytes",
    "total_bytes",
    "total_bytes_estimate",
    "speed",
    "eta",
)
BROWSERS = ("", "chrome", "chromium", "edge", "firefox", "brave", "safari")
MAX_HEIGHTS = (480, 720, 1080, 1440, 2160, 0)  # 0: best available
MAX_LINKS_FILE_BYTES = 1024 * 1024
_MAX_LISTED_FAILURES = 10
# Share of each video's progress bar spent downloading; the rest is ffmpeg.
_DOWNLOAD_SHARE = 0.8

DEFAULT_SETTINGS = {
    "fps": 1.0,
    "max_height": 1080,
    "cookies_browser": "",
    "proxy": "",
    "video_dir": "",
    "keep_videos": True,
    "ytdlp_command": "",
}


def _tr(text):
    return QCoreApplication.translate("VideoDownload", text)


class VideoDownloadError(Exception):
    """A failure whose message is meant for the user."""


# Settings -------------------------------------------------------------------


def get_settings_path():
    return os.path.join(
        get_work_directory(),
        "xanylabeling_data",
        "video_download",
        "settings.json",
    )


def default_video_dir():
    return os.path.join(get_work_directory(), "xanylabeling_data", "videos")


def load_settings(path=None):
    path = path or get_settings_path()
    settings = copy.deepcopy(DEFAULT_SETTINGS)
    try:
        with open(path, encoding="utf-8") as stream:
            stored = json.load(stream)
    except (OSError, ValueError):
        return settings
    if isinstance(stored, dict):
        settings.update(
            (key, value) for key, value in stored.items() if key in settings
        )
    return settings


def save_settings(settings, path=None):
    path = path or get_settings_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as stream:
        json.dump(settings, stream, ensure_ascii=False, indent=2)
    # The proxy URL may carry a password.
    os.chmod(path, 0o600)


# Input parsing --------------------------------------------------------------


def read_links_file(path):
    """Text of a links file; UTF-8 (with or without BOM) or GB18030."""
    if os.path.getsize(path) > MAX_LINKS_FILE_BYTES:
        raise ValueError(
            f"larger than {MAX_LINKS_FILE_BYTES // 1024} KB; "
            "is this a links file?"
        )
    with open(path, "rb") as stream:
        raw = stream.read()
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("not UTF-8 or GB18030 text")


_URL = re.compile(r"https?://[^\s<>\"'，。、）)】]+", re.IGNORECASE)
_DASHES = "-~～–—到至"
_RANGE_SEPARATORS = re.compile(r"[\s,，;；、]+")
_COMMENT = re.compile(r"(?:^|\s)#")
WHOLE_VIDEO = (0.0, None)


def parse_plan(text, default=None):
    """Return ``(jobs, problems)`` from a download plan.

    Each line holds a link, optionally followed by time ranges::

        https://www.bilibili.com/video/BV1xx  0:10-0:30  1:00-1:20
        https://youtu.be/abc  5:00-    # from 5:00 to the end

    Blank lines and ``#`` comments are skipped, and text before the link
    is ignored, so share text such as ``【title】 https://b23.tv/xyz`` works
    as pasted. A link without ranges gets ``default``, else the whole
    video. ``jobs`` is ``[(url, [(start, end), ...])]`` with ``end`` None
    for the video end; a link on several lines gets the ranges of all of
    them, and ranges that overlap are joined. ``problems`` describes each
    line that was skipped.
    """
    sections, problems = {}, []
    for number, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = _URL.search(line)
        if match is None:
            problems.append(
                _tr("Line {line}: no http(s) link").format(line=number)
            )
            continue
        rest = _COMMENT.split(line[match.end() :], maxsplit=1)[0]
        # "1:00 - 1:30" is one range.
        rest = re.sub(rf"\s*([{_DASHES}])\s*", r"\1", rest).strip()
        try:
            ranges = [
                parse_range(token)
                for token in _RANGE_SEPARATORS.split(rest)
                if token
            ]
        except ValueError as exc:
            problems.append(
                _tr("Line {line}: {problem}").format(line=number, problem=exc)
            )
            continue
        sections.setdefault(match.group(0), []).extend(
            ranges or [default or WHOLE_VIDEO]
        )
    jobs = [(url, merge_sections(ranges)) for url, ranges in sections.items()]
    return jobs, problems


def parse_range(text):
    """``(start, end)`` from ``1:00-1:30``; ``5:00-`` runs to the end."""
    for dash in _DASHES[1:]:
        text = text.replace(dash, "-")
    start, dash, end = text.partition("-")
    try:
        if not dash or not start:
            raise ValueError
        start, end = parse_time(start), parse_time(end)
    except ValueError:
        raise ValueError(
            _tr("not a time range: {text}").format(text=text)
        ) from None
    if end is not None and end <= start:
        raise ValueError(
            _tr("the end must be after the start: {text}").format(text=text)
        )
    return start, end


def merge_sections(sections):
    """Sort ``(start, end)`` ranges and join those that overlap or touch."""
    merged = []
    for start, end in sorted(sections, key=lambda section: section[0]):
        if merged and (merged[-1][1] is None or start <= merged[-1][1]):
            last_start, last_end = merged[-1]
            if last_end is not None and (end is None or end > last_end):
                merged[-1] = (last_start, end)
            continue
        merged.append((start, end))
    return merged


def format_time(seconds):
    """``0:10``, ``1:30`` or ``1:02:03.5``, as times are written in plans."""
    ms = int(round(float(seconds) * 1000))
    hours, ms = divmod(ms, 3_600_000)
    minutes, ms = divmod(ms, 60_000)
    secs, ms = divmod(ms, 1000)
    text = f"{secs:02d}" + (f".{ms:03d}".rstrip("0") if ms else "")
    return f"{hours}:{minutes:02d}:{text}" if hours else f"{minutes}:{text}"


def format_range(start, end):
    return f"{format_time(start)}-{'' if end is None else format_time(end)}"


def parse_time(text):
    """Seconds from ``90``, ``1:30`` or ``1:02:03.5``; empty gives None."""
    text = text.strip().replace("：", ":")
    if not text:
        return None
    parts = text.split(":")
    if len(parts) > 3 or not all(
        re.fullmatch(r"\d+(\.\d+)?", part) for part in parts
    ):
        raise ValueError(f"not a time: {text!r}")
    seconds = 0.0
    for part in parts:
        seconds = seconds * 60 + float(part)
    return seconds


def _number(value):
    return f"{value:.3f}".rstrip("0").rstrip(".")


def section_spec(start, end):
    """yt-dlp ``--download-sections`` value, or None for the whole video."""
    if not start and end is None:
        return None
    start = start or 0.0
    if end is not None and end <= start:
        raise ValueError("the end must be after the start")
    return f"*{_number(start)}-{'inf' if end is None else _number(end)}"


def safe_name(text, fallback="video"):
    return re.sub(r"[^A-Za-z0-9_-]+", "_", str(text or "")).strip("_") or (
        fallback
    )


def frame_times(count, fps, start=0.0):
    return [round(start + index / fps, 3) for index in range(count)]


def frame_names(site, video_id, times):
    """``<site>_<id>_t000123.jpg``; milliseconds are added when needed."""
    whole = all(abs(t - round(t)) < 1e-6 for t in times)
    names = []
    for t in times:
        if whole:
            stamp = f"t{int(round(t)):06d}"
        else:
            ms = int(round(t * 1000))
            stamp = f"t{ms // 1000:06d}_{ms % 1000:03d}"
        names.append(f"{site}_{video_id}_{stamp}.jpg")
    return names


# yt-dlp ---------------------------------------------------------------------


def find_ytdlp(command=""):
    """argv prefix that runs yt-dlp.

    The configured command wins; else the yt_dlp module of this Python (it
    is updated with pip alongside X-AnyLabeling); else yt-dlp on PATH.
    """
    if command:
        resolved = shutil.which(os.path.expanduser(command))
        if resolved is None:
            raise VideoDownloadError(
                _tr("yt-dlp not found: {command}").format(command=command)
            )
        return [resolved]
    frozen = getattr(sys, "frozen", False)
    if not frozen and importlib.util.find_spec("yt_dlp") is not None:
        return [sys.executable, "-m", "yt_dlp"]
    resolved = shutil.which("yt-dlp")
    if resolved is not None:
        return [resolved]
    raise VideoDownloadError(
        _tr(
            "yt-dlp is not installed. Install it into the Python that runs "
            'X-AnyLabeling: pip install -U "yt-dlp[default,deno]"'
        )
    )


def format_selector(max_height):
    """Best stream with video up to ``max_height``; no audio is needed."""
    if not max_height:
        return "bv*/b"
    height = int(max_height)
    return f"bv*[height<={height}]/b[height<={height}]/bv*/b"


def build_download_command(prefix, url, output_template, settings, section):
    progress = ",".join(PROGRESS_FIELDS)
    info = ",".join(INFO_FIELDS)
    argv = list(prefix) + [
        "--no-playlist",
        "--newline",
        "--progress",
        "--progress-template",
        f"download:{PROGRESS_MARK}%(progress.{{{progress}}})j",
        "-f",
        format_selector(settings.get("max_height")),
        "--print",
        f"after_move:{FILE_MARK}%(filepath)s",
        "--print",
        f"after_move:{INFO_MARK}%(.{{{info}}})j",
        "-o",
        output_template,
    ]
    if section:
        argv += ["--download-sections", section]
    if settings.get("cookies_browser"):
        argv += ["--cookies-from-browser", settings["cookies_browser"]]
    if settings.get("proxy"):
        argv += ["--proxy", settings["proxy"]]
    # YouTube needs a JavaScript runtime. Only deno (the "deno" extra of
    # yt-dlp) is enabled by default; node >= 22 also works, and deno stays
    # first when both are installed.
    if shutil.which("node"):
        argv += ["--js-runtimes", "node"]
    return argv + ["--", url]


def parse_progress(line):
    """Progress dict from one yt-dlp progress line, else None."""
    if not line.startswith(PROGRESS_MARK):
        return None
    try:
        data = json.loads(line[len(PROGRESS_MARK) :])
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    total = data.get("total_bytes") or data.get("total_bytes_estimate")
    done = data.get("downloaded_bytes")
    fraction = None
    if total and done is not None:
        fraction = max(0.0, min(1.0, done / total))
    return {
        "status": data.get("status"),
        "fraction": fraction,
        "speed": data.get("speed"),
        "eta": data.get("eta"),
    }


def _error_hints():
    """(needles, hint) pairs, most specific first."""
    return (
        (
            ("cookies database", "failed to decrypt", "keyring"),
            _tr(
                "Cannot read the browser cookies: close that browser and "
                "try again, or choose another browser."
            ),
        ),
        (
            (
                "sign in to confirm",
                "not a bot",
                "http error 412",
                "precondition failed",
                "login required",
                "members-only",
            ),
            _tr(
                "The site wants a login: log in to it in your browser, then "
                "choose that browser under Browser cookies."
            ),
        ),
        (
            ("unsupported url",),
            _tr("This link is not a video page yt-dlp supports."),
        ),
        (
            ("http error 404", "http error 410"),
            _tr("The page was not found: check the link."),
        ),
        (
            (
                "video unavailable",
                "private video",
                "has been removed",
                "not available in your country",
                "geo restriction",
                "geo-restricted",
            ),
            _tr(
                "The video is unavailable: removed, private or region-locked."
            ),
        ),
        (
            (
                "no such option",
                "unable to extract",
                "nsig",
                "signature",
                "javascript runtime",
                "js runtime",
                "http error 403",
            ),
            _tr(
                "yt-dlp may be outdated: update it with "
                'pip install -U "yt-dlp[default,deno]" and try again.'
            ),
        ),
        (
            (
                "unable to download",
                "timed out",
                "connection refused",
                "connection reset",
                "name resolution",
                "network is unreachable",
                "ssl",
                "eof occurred",
                "proxy",
            ),
            _tr(
                "Network error: check the connection, or set a proxy "
                "(YouTube needs one in mainland China)."
            ),
        ),
        (
            ("ffmpeg",),
            _tr("ffmpeg is required: install it and make sure it is on PATH."),
        ),
    )


def describe_error(stderr_text):
    """A user-facing explanation of a failed yt-dlp run."""
    lines = [line.strip() for line in stderr_text.splitlines()]
    lines = [line for line in lines if line]
    errors = [line for line in lines if line.startswith("ERROR:")]
    detail = (errors or lines[-3:] or [""])[-1]
    lowered = stderr_text.lower()
    for needles, hint in _error_hints():
        if any(needle in lowered for needle in needles):
            return f"{hint}\n{detail}".strip()
    return detail or _tr("yt-dlp failed without an error message.")


# Frames and provenance ------------------------------------------------------


def update_sources(frames_dir, entry):
    """Add ``entry`` to ``sources.json``, replacing the same video run."""
    path = os.path.join(frames_dir, SOURCES_FILE)
    videos = []
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as stream:
                videos = list(json.load(stream)["videos"])
        except (OSError, ValueError, KeyError, TypeError):
            # Keep an unreadable file instead of overwriting it.
            shutil.copy2(path, path + ".bak")
            videos = []
    key = (entry["url"], entry["section"], entry["fps"])
    videos = [
        video
        for video in videos
        if isinstance(video, dict)
        and (video.get("url"), video.get("section"), video.get("fps")) != key
    ]
    videos.append(entry)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as stream:
        json.dump({"videos": videos}, stream, ensure_ascii=False, indent=1)
    os.replace(temporary, path)


def _popen(argv):
    return subprocess.Popen(
        argv,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "NO_COLOR": "1", "PYTHONIOENCODING": "utf-8"},
        start_new_session=os.name == "posix",
    )


def _kill(process):
    """Stop a process and its helpers (yt-dlp starts ffmpeg)."""
    if process.poll() is not None:
        return
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
        process.wait(timeout=5)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        try:
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
        except ProcessLookupError:
            pass


def _format_speed(speed):
    if not speed:
        return ""
    for unit in ("B/s", "KB/s", "MB/s"):
        if speed < 1024:
            return f"{speed:.0f} {unit}"
        speed /= 1024
    return f"{speed:.1f} GB/s"


class VideoDownloadThread(QThread):
    """Downloads each link, extracts its frames, then reports the result."""

    progress_updated = pyqtSignal(int, str)
    # frames folder, number of frames written, [(link, error)]
    finished_all = pyqtSignal(str, int, list)

    def __init__(self, jobs, frames_dir, settings, start=None, end=None):
        """``jobs`` holds links, or ``(link, [(start, end), ...])`` pairs as
        ``parse_plan`` returns them. A bare link gets ``start``-``end``, by
        default the whole video."""
        super().__init__()
        default = WHOLE_VIDEO
        if start is not None or end is not None:
            default = (start or 0.0, end)
        self.jobs = [
            (
                (job, [default])
                if isinstance(job, str)
                else (job[0], merge_sections(job[1]) or [WHOLE_VIDEO])
            )
            for job in jobs
        ]
        self.frames_dir = frames_dir
        self.settings = dict(settings)
        self.cancelled = False
        self._process = None
        self._lock = threading.Lock()

    def cancel(self):
        self.cancelled = True
        with self._lock:
            process = self._process
        if process is not None:
            # Off the UI thread: _kill waits for the process to exit.
            threading.Thread(
                target=_kill, args=(process,), daemon=True
            ).start()

    def _run(self, argv, on_line):
        """Run ``argv``, feeding stdout lines to ``on_line``."""
        logger.debug(f"Running: {argv}")
        process = _popen(argv)
        with self._lock:
            self._process = process
        if self.cancelled:
            _kill(process)
        stderr_lines = []
        drain = threading.Thread(
            target=lambda: stderr_lines.extend(process.stderr), daemon=True
        )
        drain.start()
        try:
            for line in process.stdout:
                on_line(line.rstrip("\n"))
            returncode = process.wait()
        finally:
            drain.join(timeout=5)
            with self._lock:
                self._process = None
        return returncode, "".join(stderr_lines)

    def run(self):
        failures, frames = [], 0
        try:
            prefix = find_ytdlp(self.settings.get("ytdlp_command", ""))
            ffmpeg = shutil.which("ffmpeg")
            if ffmpeg is None:
                raise VideoDownloadError(
                    _tr(
                        "ffmpeg is required: install it and make sure it is "
                        "on PATH."
                    )
                )
        except VideoDownloadError as exc:
            self.finished_all.emit(self.frames_dir, 0, [("", str(exc))])
            return
        # One download per section: yt-dlp writes each to its own file.
        tasks = [
            (number, url, part, len(sections), section)
            for number, (url, sections) in enumerate(self.jobs, 1)
            for part, section in enumerate(sections, 1)
        ]
        share = 100.0 / max(len(tasks), 1)
        for index, (number, url, part, parts, (start, end)) in enumerate(
            tasks
        ):
            if self.cancelled:
                break
            heading = _tr("Video {index}/{total}: {url}").format(
                index=number, total=len(self.jobs), url=url
            )
            label = url
            if (start, end) != WHOLE_VIDEO:
                span = format_range(start, end)
                label = f"{url}  [{span}]"
                heading += "\n" + _tr("Section {part}/{parts}: {span}").format(
                    part=part, parts=parts, span=span
                )

            def report(fraction, status, base=index * share, heading=heading):
                self.progress_updated.emit(
                    int(base + share * fraction), f"{heading}\n{status}"
                )

            try:
                frames += self._download_section(
                    url, start, end, prefix, ffmpeg, report
                )
            except VideoDownloadError as exc:
                logger.error(f"Video download failed for {label}: {exc}")
                failures.append((label, str(exc)))
            except Exception as exc:  # noqa: BLE001 - report, go on
                logger.exception(f"Video download crashed for {label}")
                failures.append((label, f"{type(exc).__name__}: {exc}"))
        self.finished_all.emit(self.frames_dir, frames, failures)

    def _download_section(self, url, start, end, prefix, ffmpeg, report):
        """Download one section of ``url``; return the frames written."""
        report(0.0, _tr("Starting yt-dlp..."))
        video_dir = self.settings.get("video_dir") or default_video_dir()
        os.makedirs(video_dir, exist_ok=True)
        start = float(start or 0.0)
        section = section_spec(start, end)
        suffix = ""
        if section:
            suffix = "_s" + section[1:].replace(".", "_")
        # "%" starts a field in yt-dlp output templates.
        template = os.path.join(
            video_dir.replace("%", "%%"),
            f"%(extractor_key)s_%(id)s{suffix}.%(ext)s",
        )
        argv = build_download_command(
            prefix, url, template, self.settings, section
        )
        state = {"file": None, "info": {}}

        def on_line(line):
            if line.startswith(FILE_MARK):
                state["file"] = line[len(FILE_MARK) :].strip()
            elif line.startswith(INFO_MARK):
                try:
                    state["info"] = json.loads(line[len(INFO_MARK) :])
                except ValueError:
                    pass
            else:
                progress = parse_progress(line)
                if progress is None or progress["fraction"] is None:
                    return
                status = _tr("Downloading {percent}%  {speed}").format(
                    percent=int(progress["fraction"] * 100),
                    speed=_format_speed(progress["speed"]),
                )
                report(_DOWNLOAD_SHARE * progress["fraction"], status.strip())

        returncode, stderr = self._run(argv, on_line)
        if self.cancelled:
            return 0
        video_file = state["file"]
        if returncode != 0 or not video_file or not os.path.isfile(video_file):
            raise VideoDownloadError(describe_error(stderr))
        info = state["info"] if isinstance(state["info"], dict) else {}

        fps = float(self.settings.get("fps") or 1.0)
        try:
            video_length = float(info.get("duration") or 0.0)
        except (TypeError, ValueError):
            video_length = 0.0
        if section and video_length and start >= video_length:
            # yt-dlp still writes a file, made of frames from elsewhere.
            try:
                os.remove(video_file)
            except OSError as exc:
                logger.warning(f"Cannot remove {video_file}: {exc}")
            raise VideoDownloadError(
                _tr(
                    "The section starts after the video ends ({length})."
                ).format(length=format_time(video_length))
            )
        duration = None
        if end is not None:
            duration = end - start
        if video_length:
            duration = min(duration or math.inf, video_length - start)
        work_dir = tempfile.mkdtemp(prefix=".frames_", dir=video_dir)
        try:
            report(_DOWNLOAD_SHARE, _tr("Extracting frames..."))
            names = self._extract(
                ffmpeg, video_file, work_dir, fps, duration, report
            )
            if self.cancelled:
                return 0
            site = safe_name(str(info.get("extractor_key", "")).lower())
            video_id = safe_name(
                info.get("id")
                or os.path.splitext(os.path.basename(video_file))[0]
            )
            times = frame_times(len(names), fps, start)
            if end is not None:
                # ffmpeg may add a frame at the very end of the section.
                kept = [i for i, t in enumerate(times) if t < end]
                names = [names[i] for i in kept]
                times = [times[i] for i in kept]
            final_names = frame_names(site, video_id, times)
            os.makedirs(self.frames_dir, exist_ok=True)
            for name, final in zip(names, final_names):
                shutil.move(
                    os.path.join(work_dir, name),
                    os.path.join(self.frames_dir, final),
                )
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

        keep = bool(self.settings.get("keep_videos", True))
        update_sources(
            self.frames_dir,
            {
                "url": url,
                "page_url": info.get("webpage_url") or url,
                "site": site,
                "id": info.get("id"),
                "title": info.get("title"),
                "uploader": info.get("uploader"),
                "license": info.get("license"),
                "upload_date": info.get("upload_date"),
                "duration": info.get("duration"),
                "height": info.get("height"),
                "section": section,
                "start": start,
                "end": end,
                "fps": fps,
                "downloaded_at": datetime.now().isoformat(timespec="seconds"),
                "video_file": video_file if keep else None,
                "frames": [
                    {"file": name, "time": t}
                    for name, t in zip(final_names, times)
                ],
            },
        )
        if not keep:
            try:
                os.remove(video_file)
            except OSError as exc:
                logger.warning(f"Cannot remove {video_file}: {exc}")
        report(1.0, _tr("{count} frames saved").format(count=len(names)))
        return len(names)

    def _extract(self, ffmpeg, video_file, work_dir, fps, duration, report):
        argv = [
            ffmpeg,
            "-hide_banner",
            "-nostdin",
            "-loglevel",
            "error",
            "-i",
            video_file,
            "-vf",
            # Frame k must show the video at k / fps. A section starts at the
            # keyframe before it, and start_time=0 drops those lead-in frames
            # (negative timestamps). round=up takes the frame on screen at
            # k / fps; the default takes one up to half an interval later.
            f"fps=fps={fps:g}:start_time=0:round=up",
            "-q:v",
            "2",
            "-progress",
            "pipe:1",
            os.path.join(work_dir, "%08d.jpg"),
        ]

        def on_line(line):
            # ffmpeg reports out_time_us (microseconds) as it goes.
            key, _, value = line.partition("=")
            if key != "out_time_us" or not duration or not value.isdigit():
                return
            fraction = min(int(value) / 1e6 / duration, 1.0)
            report(
                _DOWNLOAD_SHARE + (1 - _DOWNLOAD_SHARE) * fraction,
                _tr("Extracting frames {percent}%").format(
                    percent=int(fraction * 100)
                ),
            )

        returncode, stderr = self._run(argv, on_line)
        if self.cancelled:
            return []
        names = sorted(
            name for name in os.listdir(work_dir) if name.endswith(".jpg")
        )
        if returncode != 0 or not names:
            raise VideoDownloadError(
                _tr("ffmpeg could not extract frames: {error}").format(
                    error=(stderr.strip().splitlines() or ["?"])[-1]
                )
            )
        return names


# UI entry points ------------------------------------------------------------


def _show_failures(app, failures):
    lines = []
    for label, error in failures[:_MAX_LISTED_FAILURES]:
        lines.append(f"{label}\n    {error[:300]}" if label else error[:300])
    if len(failures) > _MAX_LISTED_FAILURES:
        lines.append("...")
    QMessageBox.warning(
        app,
        _tr("Open Video URL"),
        _tr("{count} download(s) failed:").format(count=len(failures))
        + "\n\n"
        + "\n".join(lines),
    )


def open_video_url(app):
    """Ask for links, download them, extract frames and open the folder."""
    if not app.may_continue():
        return
    from anylabeling.views.labeling.widgets.video_url_dialog import (
        VideoUrlDialog,
    )

    dialog = VideoUrlDialog(app)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return
    request = dialog.request()
    thread = VideoDownloadThread(
        request["jobs"], request["frames_dir"], request["settings"]
    )
    progress = QProgressDialog(
        _tr("Starting yt-dlp..."), _tr("Cancel"), 0, 100, app
    )
    progress.setWindowTitle(_tr("Open Video URL"))
    progress.setWindowModality(Qt.WindowModality.WindowModal)
    progress.setMinimumDuration(0)
    progress.setMinimumWidth(520)
    progress.setAutoClose(False)
    progress.setAutoReset(False)
    progress.setStyleSheet(get_progress_dialog_style())
    progress.canceled.connect(thread.cancel)
    progress.show()

    def on_progress(value, text):
        if not thread.cancelled:
            progress.setValue(value)
            progress.setLabelText(text)

    def on_finished(frames_dir, count, failures):
        progress.canceled.disconnect(thread.cancel)
        progress.close()
        app._video_download_thread = None
        logger.info(
            f"Video download finished: {count} frames in {frames_dir}, "
            f"{len(failures)} failed, cancelled={thread.cancelled}"
        )
        if failures:
            _show_failures(app, failures)
        if count:
            app.import_image_folder(frames_dir)

    thread.progress_updated.connect(on_progress)
    thread.finished_all.connect(on_finished)
    app._video_download_thread = thread
    thread.start()


def new_open_video_url_action(app):
    """File menu action that opens the video link dialog."""
    from anylabeling.services.auto_labeling.utils.vlm.i18n import (
        install_translator,
    )

    # The fork's strings ship in their own catalog; load it before the
    # action text is translated.
    install_translator()
    return new_action(
        app,
        _tr("Open Video URL"),
        lambda: open_video_url(app),
        None,
        "link",
        _tr(
            "Download videos from YouTube, Bilibili and other sites, then "
            "extract frames"
        ),
    )
