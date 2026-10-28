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
- [3. Images from videos](#3-images-from-videos)
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

**Video links**: downloading from YouTube, Bilibili and other sites needs yt-dlp and ffmpeg; see [part 3](#3-images-from-videos).

## 1. VLM annotation

### Choose the model

1. Open an image or an image folder.
2. Press `Ctrl+A` (or **Auto Labeling** in the left toolbar).
3. Click **No Model** and choose **VLM Annotator (Codex / Claude / OpenAI)**.

### Configure the backend

Click **VLM Settings** in the auto-labeling bar:

- **Backend**: Codex CLI, Claude CLI or OpenAI-compatible API. An empty model name uses `~/.codex/config.toml` for Codex and the CLI default for Claude.
- **OpenAI-compatible API**: the Base URL usually ends at `/v1`, e.g. `https://example.com/v1`; `/chat/completions` is appended to it. An empty Base URL or API key falls back to `OPENAI_BASE_URL` / `OPENAI_API_KEY`.
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

## 3. Images from videos

VLM and SAM 3.1 label single images, so videos are first split into frames. The frames land in an ordinary folder; label it with `Ctrl+B`.

### Local videos

Press `Ctrl+O` (**File > Open Video**), pick a video, then set:

- **Frame interval**: take every Nth frame, e.g. 30 on a 30 fps video gives one frame per second.
- **Filename prefix**
- **Number sequence length**: digits in the frame number.

The frames go to a folder named after the video, next to it, which opens when done.

> If that folder exists, confirming the overwrite deletes the whole folder, including annotations saved in it. Rename the old folder before splitting again with another interval.

### Video links (YouTube, Bilibili, ...)

Install yt-dlp and ffmpeg first:

```bash
conda activate x-anylabeling-cu11
pip install -U "yt-dlp[default,deno]"    # or, in the repository: pip install -e ".[gpu-cu11,video]"
sudo apt install ffmpeg             # Ubuntu
```

`deno` is the JavaScript runtime YouTube needs; it is installed into the same Python environment, and Node.js 22 or later on PATH works too. Old yt-dlp versions break when sites change. When downloads fail, run the `pip install -U` line above first.

1. Click **File > Open Video URL**.
2. Paste links, one per line; time ranges to download may follow each link (see **Download plans** below). Or click **Load links from file...** to pick a .txt file written that way. Share text such as `【title】 https://b23.tv/xxxx` from the Bilibili app can be pasted as is; the link is picked out of it.
3. Set the options in the table below, then click **Start**.
4. The progress window shows which video and section are running, and their download and extraction progress. Cancel at any time; finished parts are kept.
5. When all are done, the frames folder opens; press `Ctrl+B` to label it. Failed downloads are listed with the link, time range and reason, e.g. a login is needed, the video was removed, yt-dlp is outdated, or a network error.

| Option | Meaning |
| --- | --- |
| Frames folder | Frames of all videos go here; default `~/xanylabeling_data/videos/frames_<time>` |
| Frames per second | 1 by default; 0.5 takes one frame every 2 seconds |
| Default time range | Optional, e.g. `90`, `1:30` or `1:02:03`; for links without time ranges of their own. Empty downloads the whole video |
| Max resolution | 1080p by default; only the picture is downloaded, no audio |
| Browser cookies | Uses the login of the chosen browser; log in to the site there first. Bilibili limits the quality without a login; YouTube may ask to confirm you are not a bot |
| Proxy | Empty uses the system network. YouTube needs a proxy in mainland China, e.g. `http://127.0.0.1:7890` |
| Video folder | Downloaded videos are kept here, `~/xanylabeling_data/videos` by default; running the same link again skips the download |
| Keep videos after extracting frames | Unticked, each video is deleted once its frames are saved |
| yt-dlp command | Empty uses yt-dlp from X-AnyLabeling's Python environment, else the one on PATH |

**Download plans**: each line holds a link followed by any number of time ranges. Write them in the links box, or save them as a .txt file (UTF-8 or GBK) and load it:

```text
# tactile paving clips
https://www.bilibili.com/video/BV1FL4y1g7Pd   0:10-0:30   1:00-1:20
https://www.youtube.com/watch?v=aqz-KE-bpKQ   5:00-        # from 5:00 to the end
https://www.youtube.com/watch?v=jNQXAC9IVRw                # no range
```

- Times are seconds, `m:ss` or `h:mm:ss`, e.g. `90`, `1:30`, `1:02:03.5`.
- A range is `start-end`; `~` works in place of `-`, with or without spaces around it. Leave out the end (`5:00-`) to run to the end of the video. Separate ranges with spaces, commas or semicolons.
- Links without ranges get the **Default time range**; if that is empty too, the whole video is downloaded.
- A link on several lines gets the ranges of all of them. Ranges that overlap or touch are joined, e.g. `0:10-0:30` and `0:25-0:40` become `0:10-0:40`.
- `#` starts a comment at the start of a line or after a space. Text before the link is ignored.
- If a line is wrong, nothing starts; the dialog lists the line numbers and reasons, e.g. `Line 3: not a time range: 1:3o-2:00`.
- Each range is downloaded on its own, and only that part. The part of a range past the end of the video is ignored; a range that starts after the end is listed as failed.

**Frame names** are `<site>_<video id>_t<seconds>.jpg`, e.g. `bilibili_BV1FL4y1g7Pd_t000020.jpg` is second 20 of that video. With more than one frame per second, milliseconds are added, e.g. `t000010_500`.

**Sources**: `sources.json` in the frames folder records each video's link, title, uploader, license and time range (one entry per range, `start`/`end` in seconds), and the video time of every frame, so the data can be traced later.

- A link to a playlist or a multi-part video downloads only the video the link points to.
- Running the same video again with the same time range and frame rate overwrites the frames of the same name; saved annotations are kept.

**From a script**: the same plan runs from Python, with the settings saved by the dialog:

```python
from PyQt6.QtCore import QCoreApplication
from anylabeling.views.labeling.utils import video_download as vd

app = QCoreApplication([])
jobs, problems = vd.parse_plan(vd.read_links_file("plan.txt"))
assert not problems, problems
thread = vd.VideoDownloadThread(jobs, "/path/to/frames", vd.load_settings())
thread.progress_updated.connect(lambda pct, text: print(pct, text.splitlines()[-1]))
thread.finished_all.connect(lambda folder, count, failures: print(count, failures))
thread.run()  # returns when everything is done
```

> Only download videos you may use. Frames of other people's videos are for your own training data; do not publish them.

### Tracking across frames

Both ways treat a video as independent images. To keep one ID per object across frames, use upstream's SAM 2 Video (needs the `sam2` package) or SAM 3 Video (needs X-AnyLabeling-Server and the `sam3.pt` checkpoint). This fork's SAM 3.1 service does not track videos.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| VLM reports a login or auth error | Log in again (`codex login` / `claude`) or check the API key |
| Relay returns 400 | JSON Schema output falls back to plain JSON automatically; if it still fails, check that the model accepts images |
| Batch keeps "backing off" | The provider is rate limiting; lower **Max concurrency** or raise the cooldown |
| Batch looks serial | Concurrency starts at 1 and doubles after each successful round (1→2→4). At about 75 s per image with Codex, only 1–2 requests run for the first few minutes; the progress bar shows "concurrency x/y, running z". **Send** always labels only the current image; concurrency applies to `Ctrl+B` batches |
| VLM misses objects | Describe the class in the prompt, or state what to include and exclude in the extra instructions |
| Remote-Server cannot connect | Run `scripts/sam31_server.sh status`; `start` it if stopped |
| SAM 3.1 finds too little | Lower the confidence, or use `detector: image_model` if memory allows |
| SAM 3.1 finds nothing for a class | Give the label several prompts. Grey tactile paving, for example, is missed by `tactile paving` alone but found by `tactile_paving: tactile paving, gray tactile paving, tactile strip` (score 0.53). Try single prompts at confidence 0.1 to compare their scores, then keep the good ones |
| Open Video URL says a login is needed | Log in to the site in a browser, then choose that browser under **Browser cookies**; if reading the cookies fails, close the browser and retry |
| Open Video URL downloads fail | Update yt-dlp with `pip install -U "yt-dlp[default,deno]"`; YouTube also needs a proxy in mainland China |
