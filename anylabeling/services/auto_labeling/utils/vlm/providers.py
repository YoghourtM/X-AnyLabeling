"""VLM backends for direct annotation: codex CLI, claude CLI, OpenAI Chat.

Every provider takes an image file, a prompt and the response JSON schema and
returns the raw reply (a dict when the backend already parsed it, otherwise
text). Parsing and geometry handling live in ``core``.
"""

import base64
import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time

PROVIDER_CODEX = "codex_cli"
PROVIDER_CLAUDE = "claude_cli"
PROVIDER_OPENAI = "openai_chat"
PROVIDERS = (PROVIDER_CODEX, PROVIDER_CLAUDE, PROVIDER_OPENAI)

_MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
}


class VLMProviderError(RuntimeError):
    pass


class VLMCancelledError(VLMProviderError):
    pass


class VLMCongestionError(VLMProviderError):
    """Rejected, overloaded or stalled: back off and retry later."""


class VLMTimeoutError(VLMCongestionError):
    pass


class VLMFatalError(VLMProviderError):
    """Retrying cannot help (authentication, missing command or model)."""


_FATAL_RE = re.compile(
    r"\b401\b|unauthori[sz]ed|not logged in|log ?in required|please log ?in"
    r"|invalid api key|incorrect api key|authentication",
    re.I,
)
_CONGESTION_RE = re.compile(
    r"\b429\b|rate.?limit|too many requests|overload|capacity|quota"
    r"|temporar|try again|unavailable|\b50[0234]\b|server error"
    r"|internal error|timed? ?out|timeout|stream disconnected|websocket"
    r"|connection (?:reset|refused|closed|error)|\b403\b|forbidden"
    r"|upstream|busy",
    re.I,
)


def classified_error(message, detail):
    """Build the error type matching a backend's failure text."""
    text = f"{message}: {detail}"
    if _FATAL_RE.search(detail):
        return VLMFatalError(text)
    if _CONGESTION_RE.search(detail):
        return VLMCongestionError(text)
    return VLMProviderError(text)


def image_mime_type(path):
    """MIME type from the file extension, or None when unknown."""
    return _MIME_TYPES.get(os.path.splitext(path)[1].lower())


def _resolve_command(command):
    resolved = shutil.which(command) if command else None
    if resolved is None:
        raise VLMFatalError(f"command not found: {command!r}")
    return resolved


def _kill(process):
    """Terminate the whole process group (CLIs spawn helpers)."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=5)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def run_command(argv, stdin_text, timeout, cwd, cancel_event=None):
    """Run a CLI with a hard timeout; cancel_event kills it early.

    ``communicate()`` runs uninterrupted on a helper thread: retrying it with
    a timeout stops feeding stdin once the pipe buffer fills (large base64
    images), which leaves the CLI waiting forever.
    """
    process = subprocess.Popen(
        argv,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=cwd,
        env={**os.environ, "NO_COLOR": "1"},
        start_new_session=True,
    )
    outcome = {}

    def talk():
        try:
            outcome["output"] = process.communicate(input=stdin_text)
        except Exception as exc:  # noqa: BLE001 - re-raised below
            outcome["error"] = exc

    talker = threading.Thread(target=talk, daemon=True)
    talker.start()
    deadline = time.monotonic() + float(timeout)
    while True:
        talker.join(0.5)
        if not talker.is_alive():
            break
        if cancel_event is not None and cancel_event.is_set():
            _kill(process)
            talker.join(10)
            raise VLMCancelledError("VLM request cancelled")
        if time.monotonic() > deadline:
            _kill(process)
            talker.join(10)
            raise VLMTimeoutError(
                f"VLM request timed out after {timeout} seconds"
            )
    if "error" in outcome:
        raise outcome["error"]
    stdout, stderr = outcome["output"]
    return process.returncode, stdout, stderr


class CodexCLIProvider:
    name = PROVIDER_CODEX

    def __init__(self, command="codex", model="", reasoning_effort=""):
        self.command = command
        self.model = model
        self.reasoning_effort = reasoning_effort

    def build_argv(self, image_path, schema_path, output_path):
        argv = [
            _resolve_command(self.command),
            "exec",
            "--skip-git-repo-check",
            "--sandbox",
            "read-only",
            "--ephemeral",
            "--image",
            image_path,
            "--output-schema",
            schema_path,
            "--output-last-message",
            output_path,
            "--json",
        ]
        if self.model:
            argv += ["--model", self.model]
        if self.reasoning_effort:
            argv += [
                "--config",
                f'model_reasoning_effort="{self.reasoning_effort}"',
            ]
        return argv + ["-"]

    def annotate(self, image_path, prompt, schema, timeout, cancel_event=None):
        with tempfile.TemporaryDirectory(prefix="xal-vlm-codex-") as work:
            schema_path = os.path.join(work, "schema.json")
            output_path = os.path.join(work, "last_message.json")
            with open(schema_path, "w", encoding="utf-8") as stream:
                json.dump(schema, stream)
            argv = self.build_argv(image_path, schema_path, output_path)
            code, stdout, stderr = run_command(
                argv, prompt, timeout, work, cancel_event
            )
            if code != 0:
                # --json reports provider failures as error events on stdout.
                errors = [
                    line for line in stdout.splitlines() if '"error"' in line
                ]
                raise classified_error(
                    f"codex exited with {code}",
                    (stderr[-800:] + "\n" + "\n".join(errors[-3:])).strip(),
                )
            if not os.path.isfile(output_path):
                raise VLMProviderError("codex produced no final message")
            with open(output_path, "r", encoding="utf-8") as stream:
                return stream.read()


class ClaudeCLIProvider:
    name = PROVIDER_CLAUDE

    def __init__(self, command="claude", model=""):
        self.command = command
        self.model = model

    def build_argv(self, schema):
        argv = [
            _resolve_command(self.command),
            "-p",
            "--input-format",
            "stream-json",
            "--output-format",
            "stream-json",
            "--verbose",
            "--json-schema",
            json.dumps(schema),
            "--tools",
            "",
            "--no-session-persistence",
            "--strict-mcp-config",
            "--disable-slash-commands",
        ]
        if self.model:
            argv += ["--model", self.model]
        return argv

    @staticmethod
    def build_message(image_path, prompt):
        with open(image_path, "rb") as stream:
            data = base64.b64encode(stream.read()).decode("ascii")
        return {
            "type": "user",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": image_mime_type(image_path)
                            or "image/jpeg",
                            "data": data,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            },
        }

    @staticmethod
    def parse_stream(stdout):
        result = None
        for line in stdout.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict) and event.get("type") == "result":
                result = event
        if result is None:
            raise VLMProviderError("claude returned no result event")
        if result.get("is_error"):
            raise classified_error(
                "claude reported an error", str(result)[:800]
            )
        structured = result.get("structured_output")
        if isinstance(structured, dict):
            return structured
        return str(result.get("result", ""))

    def annotate(self, image_path, prompt, schema, timeout, cancel_event=None):
        message = self.build_message(image_path, prompt)
        with tempfile.TemporaryDirectory(prefix="xal-vlm-claude-") as work:
            code, stdout, stderr = run_command(
                self.build_argv(schema),
                json.dumps(message) + "\n",
                timeout,
                work,
                cancel_event,
            )
        if code != 0 and '"type":"result"' not in stdout.replace(" ", ""):
            raise classified_error(
                f"claude exited with {code}", stderr[-800:] or stdout[-800:]
            )
        return self.parse_stream(stdout)


class OpenAIChatProvider:
    """OpenAI-compatible ``/chat/completions`` endpoint (relays included)."""

    name = PROVIDER_OPENAI

    def __init__(self, base_url, api_key, model, temperature=0.0):
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.temperature = temperature

    def _client(self, timeout):
        from openai import OpenAI

        return OpenAI(
            base_url=self.base_url or None,
            api_key=self.api_key or "EMPTY",
            timeout=timeout,
            # Retries and back-off are owned by the batch scheduler.
            max_retries=0,
        )

    @staticmethod
    def _response_formats(schema):
        return (
            {
                "type": "json_schema",
                "json_schema": {
                    "name": "vlm_annotations",
                    "schema": schema,
                    "strict": True,
                },
            },
            {"type": "json_object"},
            None,
        )

    def annotate(self, image_path, prompt, schema, timeout, cancel_event=None):
        if not self.model:
            raise VLMFatalError("OpenAI provider needs a model name")
        import openai

        with open(image_path, "rb") as stream:
            data = base64.b64encode(stream.read()).decode("ascii")
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "data:"
                            f"{image_mime_type(image_path) or 'image/jpeg'};"
                            f"base64,{data}"
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ]
        client = self._client(timeout)
        last_error = None
        # Relays differ in structured-output support: degrade step by step.
        for response_format in self._response_formats(schema):
            if cancel_event is not None and cancel_event.is_set():
                raise VLMCancelledError("VLM request cancelled")
            kwargs = {
                "model": self.model,
                "messages": messages,
                "temperature": self.temperature,
            }
            if response_format is not None:
                kwargs["response_format"] = response_format
            try:
                response = client.chat.completions.create(**kwargs)
            except openai.BadRequestError as exc:
                last_error = exc
                continue
            except openai.APITimeoutError as exc:
                raise VLMTimeoutError(f"OpenAI request timed out: {exc}")
            except (openai.AuthenticationError, openai.NotFoundError) as exc:
                raise VLMFatalError(f"OpenAI request refused: {exc}")
            except (
                openai.RateLimitError,
                openai.PermissionDeniedError,
                openai.InternalServerError,
                openai.APIConnectionError,
            ) as exc:
                raise VLMCongestionError(f"OpenAI request rejected: {exc}")
            except openai.APIStatusError as exc:
                raise classified_error(
                    "OpenAI request failed", f"{exc.status_code} {exc}"
                )
            content = response.choices[0].message.content
            if not content:
                raise VLMProviderError("OpenAI reply has no content")
            return content
        raise VLMProviderError(f"OpenAI request rejected: {last_error}")


def build_provider(settings):
    """Create the provider selected in the VLM annotator settings."""
    provider = settings.get("provider")
    if provider == PROVIDER_CODEX:
        codex = settings.get("codex", {})
        return CodexCLIProvider(
            command=codex.get("command") or "codex",
            model=codex.get("model", ""),
            reasoning_effort=codex.get("reasoning_effort", ""),
        )
    if provider == PROVIDER_CLAUDE:
        claude = settings.get("claude", {})
        return ClaudeCLIProvider(
            command=claude.get("command") or "claude",
            model=claude.get("model", ""),
        )
    if provider == PROVIDER_OPENAI:
        openai = settings.get("openai", {})
        return OpenAIChatProvider(
            base_url=openai.get("base_url")
            or os.environ.get("OPENAI_BASE_URL", ""),
            api_key=openai.get("api_key")
            or os.environ.get("OPENAI_API_KEY", ""),
            model=openai.get("model", ""),
            temperature=float(openai.get("temperature", 0.0)),
        )
    raise VLMProviderError(f"unknown VLM provider: {provider!r}")
