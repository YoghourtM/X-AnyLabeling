# VLM and SAM 3.1 Annotation

This fork adds two auto-labeling modes that need no manual review:

| Mode | Best for | Runs on | Speed |
| --- | --- | --- | --- |
| **SAM 3.1** (Remote-Server) | Common, visually distinct classes such as person, car, traffic light | Local GPU, docker service | Under 1 s per image |
| **VLM Annotator** | Classes SAM gets wrong or that need semantic understanding, such as tactile paving, construction barriers, specific road surfaces | Codex / Claude / OpenAI-compatible API | 10–60 s per image |

Both produce ordinary polygons or rectangles that you can edit and save in X-AnyLabeling. VLM polygons are not refined by SAM.

- [Setup](#setup)
- [1. VLM annotation](#1-vlm-annotation)
- [2. SAM 3.1 annotation](#2-sam-31-annotation)
- [Troubleshooting](#troubleshooting)

## Setup

**Start X-AnyLabeling**

```bash
conda activate x-anylabeling-cu11
xanylabeling
```

**VLM backend**: pick one in **VLM Settings**.

| Backend | Requirements |
| --- | --- |
| Codex CLI (default) | Install `codex` and run `codex login` once |
| Claude CLI | Install `claude`, run `claude` once and log in |
| OpenAI-compatible API | Base URL, API key and model name of a relay; uses `/chat/completions` and needs image input |

**SAM 3.1 service**: needs the [X-AnyLabeling-Server fork](https://github.com/YoghourtM/X-AnyLabeling-Server/tree/feat/sam3.1), docker, an NVIDIA GPU (about 5.5 GB) and the `sam3.1_multiplex.pt` checkpoint; see [part 2](#2-sam-31-annotation). It is not needed for VLM annotation.

## 1. VLM annotation

### Choose the model

1. Open an image or an image folder.
2. Press `Ctrl+A` (or **Auto Labeling** in the left toolbar).
3. Click **No Model** and choose **VLM Annotator (Codex / Claude / OpenAI)**.

### Configure the backend

Click **VLM Settings** in the auto-labeling bar:

- **Backend**: Codex CLI, Claude CLI or OpenAI-compatible API. An empty model name uses `~/.codex/config.toml` for Codex and the CLI default for Claude.
- **OpenAI-compatible API**: an empty Base URL or API key falls back to `OPENAI_BASE_URL` / `OPENAI_API_KEY`.
- **Timeout per image**: 600 s by default.
- **Max polygon vertices**: 40 by default; raise it for complex outlines.
- **Max image side sent**: 2048 px by default; larger images are downscaled before sending and coordinates are mapped back.
- **Extra instructions**: appended to every request, e.g. "merge adjacent tactile tiles into one instance".
- **Batch**: max concurrency, cooldown after back-off, retries per image; see [Batch](#batch).

Settings are saved to `~/xanylabeling_data/vlm_annotator/settings.json` with mode 600, since it may hold an API key.

### Write the prompt

List the classes; each label is named exactly as written:

```text
crosswalk, tactile_paving, construction_barrier
```

Add descriptions with `name: description`, separating entries with `;` or new lines (descriptions may contain commas):

```text
tactile_paving: raised yellow guide tiles, bars or dots; crosswalk: white zebra stripes
construction_barrier: work-zone fences or water-filled barriers
```

Chinese and English punctuation both work: `:` `：`, `;` `；`, `,` `，`. Everything after the colon is the description, so its commas do not split the class. Classes not in the prompt are dropped.

**Load from a file**: a prompt can also live in a .txt file, one entry per line; lines starting with `#` are comments:

```text
# street classes
tactile_paving: raised yellow guide tiles, bars or dots
crosswalk: white zebra stripes
person
```

Click the folder icon at the right of the prompt box and pick the file. The lines are joined with `; ` into the box so you can check or edit them before sending. UTF-8 and GBK (GB18030) files work. SAM 3.1 text prompts load the same way; see [Tasks](#tasks) for their format.

### Single image

1. Choose **Polygon** or **Rectangle** output. Rectangles are the polygon's bounding box.
2. **Replace (On)** replaces the image's existing shapes; **Replace (Off)** keeps them and adds the new ones.
3. Click **Send**. Edit the result like any other shape, then save.

### Batch

1. With the model and output chosen, press `Ctrl+B` (or **Auto Run** in the left toolbar).
2. Pick the image range, then confirm the prompt: the dialog starts with the auto-labeling bar's prompt, and its folder icon loads one from a file.
3. Images are sent concurrently; the progress bar shows progress, concurrency, running, retries and failures. Each image is saved as soon as it finishes.

Concurrency adapts like a TCP congestion window:

- It starts at 1 and grows while requests succeed, up to **Max concurrency**.
- On rate limits, rejections, timeouts, or a request that takes far longer than usual, it halves and cools down ("backing off").
- After the cooldown it grows again.
- Failed images are retried; the remaining failures are listed at the end.
- Unrecoverable errors (expired login, bad API key, unknown model) or several failures in a row stop the batch with the reason.
- Cancel stops new requests. Running Codex / Claude requests are killed at once; an API request ends when it returns, at most after the timeout.

> Images are sent to the chosen provider (OpenAI, Anthropic or the relay).

## 2. SAM 3.1 annotation

### Start the service

In the X-AnyLabeling-Server repository (`feat/sam3.1` branch):

```bash
cd ~/Documents/X-AnyLabeling-Server
export SAM31_CHECKPOINT=/path/to/sam3.1_multiplex.pt
scripts/sam31_server.sh build    # first time only; needs a SAM 3.1 base image
scripts/sam31_server.sh start    # ready in about 20 s
scripts/sam31_server.sh status
scripts/sam31_server.sh logs
scripts/sam31_server.sh stop     # frees the GPU
```

The service listens on `127.0.0.1:8000` only. The image builds on the local `cgd-sam3:2.10.0-cu128-local` by default; set `BASE_IMAGE` to use another image with the SAM 3.1 `sam3` package. See [docker/sam31/README.md](https://github.com/YoghourtM/X-AnyLabeling-Server/blob/feat/sam3.1/docker/sam31/README.md) in the server repository.

### Connect

1. Click the model button and choose **Remote-Server**.
2. Enter `http://127.0.0.1:8000` as the server URL and leave the API key empty.
3. Choose **Segment Anything 3.1** in the model list, then a task.

### Tasks

**Text prompt**: segments every instance of the given classes.

- The simplest form is English class names separated by commas, e.g. `person, car, traffic light`. Click **Send**; each instance becomes a polygon labelled with its prompt.
- When the label should differ from the prompt, write `label: prompt, prompt`, separating entries with `;` or new lines:

  ```text
  tactile_paving: tactile paving, yellow tactile paving; vehicle: car, vehicle, automobile; person
  ```

  Each prompt after the colon is sent to SAM and its results get the label. When several prompts find the same object (mask IoU ≥ 0.5), only the highest-scoring one is kept; results of one prompt are never merged with each other. Entries without a colon, like `person`, still use the prompt as the label.
- Chinese and English punctuation both work: `:` `：`, `;` `；`, `,` `，`. A `.` also acts as a comma, so keep periods out of prompts.
- Each extra prompt adds about 0.05 s per image (the first request on an image takes about 1 s, mostly image encoding).
- The merge threshold is `merge_iou` in the server's `configs/auto_labeling/segment_anything_3_1.yaml`.
- **Confidence** defaults to 0.5; lower it when objects are missed.
- The folder icon at the right of the prompt box loads the prompt from a .txt file, one entry per line, e.g. one `label: prompt, prompt` per line.
- `Ctrl+B` runs it over a range of images with the same prompt format; the batch dialog can load the file too.

**Click / box (single object)**:

- `Point (q)` adds a positive point and `Point (e)` a negative one; the mask updates after each click.
- `+Rect` draws a box around the object.
- `Clear (b)` resets the prompts; `Finish (f)` confirms the object and asks for its label.
- The first click on an image takes about 0.3 s, later clicks about 0.02 s.

**Example boxes (find similar)**:

- Draw one or more examples with `+Rect` and unwanted ones with `-Rect`, then click `Run Rect` to segment every similar object.

The **mask fineness** slider sets how many points the polygons have.

### Notes

- The default `detector: shared` serves every task from one SAM 3.1 model (about 5.5 GB). Text and example-box scores run about 0.1 lower than the batch pipelines; on one test image `tactile paving` found nothing at 0.5. Lower the confidence first.
- With 16 GB or more, set `detector: image_model` in the server's `configs/auto_labeling/segment_anything_3_1.yaml` for matching scores, then run `scripts/sam31_server.sh restart`.
- SAM 3.1 video tracking is not provided; use the built-in SAM2 video models instead.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| VLM reports a login or auth error | Log in again (`codex login` / `claude`) or check the API key |
| Relay returns 400 | JSON Schema output falls back to plain JSON automatically; if it still fails, check that the model accepts images |
| Batch keeps "backing off" | The provider is rate limiting; lower **Max concurrency** or raise the cooldown |
| VLM misses objects | Describe the class in the prompt, or state what to include and exclude in the extra instructions |
| Remote-Server cannot connect | Run `scripts/sam31_server.sh status`; `start` it if stopped |
| SAM 3.1 finds too little | Lower the confidence, or use `detector: image_model` if memory allows |
