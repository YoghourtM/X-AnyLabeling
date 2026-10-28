# VLM 标注与 SAM 3.1 标注

本 fork 在 X-AnyLabeling 上新增了两种不需要人工审核的自动标注方式：

| 方式 | 适合的类别 | 运行位置 | 速度 |
| --- | --- | --- | --- |
| **SAM 3.1**（Remote-Server） | 常见、外观明确的类别，如行人、车辆、交通灯 | 本机 GPU，docker 服务 | 每张不到 1 秒 |
| **VLM Annotator** | SAM 认不准、需要理解语义的类别，如导盲砖、施工围挡、特定路面 | Codex / Claude / OpenAI 兼容 API | 每张十几秒到一分钟 |

两种方式的结果都是普通的多边形或矩形标注，可以直接在 X-AnyLabeling 里编辑和保存。VLM 生成的多边形不会再经过 SAM 精修。

- [准备工作](#准备工作)
- [一、VLM 标注](#一vlm-标注)
- [二、SAM 3.1 标注](#二sam-31-标注)
- [三、从视频获取图片](#三从视频获取图片)
- [常见问题](#常见问题)

## 准备工作

**启动 X-AnyLabeling**

```bash
conda activate x-anylabeling-cu11
xanylabeling
```

**VLM 后端**：三选一，在“VLM 设置”里切换。

| 后端 | 需要准备 |
| --- | --- |
| Codex CLI（默认） | 安装 `codex` 并在终端运行一次 `codex login` |
| Claude CLI | 安装 `claude`，在终端运行一次 `claude` 并按提示登录 |
| OpenAI 兼容 API | 中转站地址（Base URL）、API key 和模型名，接口为 `/chat/completions`，需支持图片输入 |

**SAM 3.1 服务**：需要 [X-AnyLabeling-Server fork](https://github.com/YoghourtM/X-AnyLabeling-Server/tree/feat/sam3.1)、docker、NVIDIA GPU（约 5.5 GB 显存）和 `sam3.1_multiplex.pt` 权重，启动方法见[第二部分](#二sam-31-标注)。只用 VLM 标注时不需要它。

**视频链接**：从 YouTube、B 站等网站下载视频需要 yt-dlp 和 ffmpeg，见[第三部分](#三从视频获取图片)。

## 一、VLM 标注

### 1. 选择模型

1. 打开图片或图片目录。
2. 按 `Ctrl+A`（或左侧工具栏的“自动标注”）打开自动标注栏。
3. 点击“无模型”按钮，选择 **VLM Annotator (Codex / Claude / OpenAI)**。

### 2. 设置后端

点击自动标注栏上的 **VLM 设置**：

- **后端**：Codex CLI、Claude CLI 或 OpenAI 兼容 API。模型名留空时，Codex 使用 `~/.codex/config.toml` 里的模型，Claude 使用 CLI 默认模型。
- **OpenAI 兼容 API**：Base URL 一般填到 `/v1` 为止，例如 `https://example.com/v1`，程序会在后面拼上 `/chat/completions`。Base URL 和 API key 留空时，分别读取环境变量 `OPENAI_BASE_URL` 和 `OPENAI_API_KEY`。
- **单张超时**：默认 600 秒。
- **多边形最大顶点数**：默认 40，类别边界复杂时可以调大。
- **发送图片最长边**：默认 2048 像素，超过时先缩小再发送，返回的坐标会换算回原图。
- **附加说明**：附加到每次请求的额外要求，例如“相邻的导盲砖合并成一个实例”“忽略远处小于 20 像素的目标”。
- **批量**：最大并发、降速后冷却时间、单张重试次数，见[批量标注](#5-批量标注)。

点击保存后，设置写入 `~/xanylabeling_data/vlm_annotator/settings.json`。文件权限为 600，因为其中可能有 API key。

### 3. 写提示词

在输入框里写要标注的类别，标签名就是这里写的类别名：

```text
crosswalk, tactile_paving, construction_barrier
```

类别不好理解时，用“类别名: 描述”的写法，条目之间用分号或换行分隔，描述里可以有逗号：

```text
tactile_paving: 黄色凸起的导盲砖，条纹或圆点; crosswalk: 白色斑马线
construction_barrier: 施工围挡或水马
```

中英文标点都可以：冒号 `:` `：`、分号 `;` `；`、逗号 `,` `，`。冒号后面的整段都是描述，描述里的逗号不会把类别拆开。模型返回的提示词以外的类别会被丢弃。

**从文件加载**：提示词也可以写在 .txt 文件里，每行一个条目，`#` 开头的行是注释：

```text
# 街景类别
tactile_paving: 黄色凸起的导盲砖，条纹或圆点
crosswalk: 白色斑马线
person
```

点击输入框右侧的文件夹图标选择文件，各行会用 `; ` 连成一行填进输入框，可以先检查、修改再发送。文件支持 UTF-8 和 GBK（GB18030）编码。SAM 3.1 的文本提示也能用同样的方式加载，写法见[第二部分](#3-三个任务)。

### 4. 单张标注

1. 在输出下拉框里选择 **多边形** 或 **矩形**。矩形取多边形的外接框。
2. **标签覆盖** 开关：开启时，新结果替换当前图片已有的标注；关闭时保留已有标注，只追加新结果。
3. 点击 **发送**，等待返回。结果出现后可以像普通标注一样修改，再保存。

### 5. 批量标注

1. 先选好模型和输出方式，按 `Ctrl+B`（或左侧工具栏的“自动运行”）。
2. 选择图片范围，然后确认提示词：弹窗会预先填好自动标注栏里的提示词，也可以点右侧的文件夹图标从文件加载。
3. 多张图片并发请求，进度栏显示“进度 / 并发 / 进行中 / 重试 / 失败”，每张图完成后立即保存。

并发数像 TCP 拥塞窗口一样自动调整：

- 从 1 开始，请求顺利时逐步增大，最多到设置里的 **最大并发**。
- 遇到限流、拒绝、超时，或者某个请求明显比平时慢（卡住），并发数减半，进入冷却期；进度栏显示“降速冷却中”。
- 冷却期结束后，并发数再次逐步增大。
- 失败的图片会自动重试；全部结束后列出仍然失败的图片。
- 登录失效、API key 错误、模型不存在这类不可恢复的错误，以及连续多张失败时，批量会直接中止并说明原因。
- 点击取消后不再发出新请求。Codex / Claude 正在运行的请求会立即终止；API 请求会等当前这次返回后结束，最长等到单张超时。

> 图片会发送给所选的服务商（OpenAI、Anthropic 或中转站），涉及隐私的数据请先确认。

## 二、SAM 3.1 标注

### 1. 启动服务

在 X-AnyLabeling-Server 仓库（`feat/sam3.1` 分支）里：

```bash
cd ~/Documents/X-AnyLabeling-Server
export SAM31_CHECKPOINT=/path/to/sam3.1_multiplex.pt
scripts/sam31_server.sh build    # 仅第一次，需要本机已有 SAM 3.1 基础镜像
scripts/sam31_server.sh start    # 约 20 秒就绪
scripts/sam31_server.sh status   # 查看状态
scripts/sam31_server.sh logs     # 查看日志
scripts/sam31_server.sh stop     # 停止并释放显存
```

服务只监听 `127.0.0.1:8000`，其他机器访问不到。镜像默认基于本地的 `cgd-sam3:2.10.0-cu128-local`，可用环境变量 `BASE_IMAGE` 指定其他装好 SAM 3.1 版 sam3 的镜像。更多说明见服务端的 [docker/sam31/README.md](https://github.com/YoghourtM/X-AnyLabeling-Server/blob/feat/sam3.1/docker/sam31/README.md)。

### 2. 连接服务

1. 在自动标注栏点击模型按钮，选择 **Remote-Server**。
2. 弹窗里服务地址填 `http://127.0.0.1:8000`，API key 留空。
3. 在模型下拉框里选择 **Segment Anything 3.1**，再在任务下拉框里选择任务。

### 3. 三个任务

**Text prompt（文本提示）**：分割图中某些类别的所有实例。

- 最简单的写法是英文类别名用逗号分隔，例如 `person, car, traffic light`。点击发送后每个实例生成一个多边形，提示词本身就是标签名。
- 标签名和提示词不一样时，写成“标签名: 提示词, 提示词”，条目之间用分号或换行分隔：

  ```text
  tactile_paving: tactile paving, yellow tactile paving; vehicle: car, vehicle, automobile; person
  ```

  冒号前是标签名，冒号后的每个提示词分别发给 SAM，结果都用这个标签。几个提示词找到同一个目标时（掩码 IoU ≥ 0.5），只保留分数最高的一个。同一个提示词自己的结果不会被合并。没有冒号的条目，如上例的 `person`，仍然是提示词即标签名。
- 中英文标点都可以：冒号 `:` `：`、分号 `;` `；`、逗号 `,` `，`。英文句号 `.` 也算逗号，所以提示词里不要带句号。
- 每多一个提示词，每张图多花约 0.05 秒（同一张图第一次请求约 1 秒，主要是编码图片）。
- 合并阈值可以在服务端 `configs/auto_labeling/segment_anything_3_1.yaml` 的 `merge_iou` 修改。
- **置信度** 默认 0.5，漏检时调低。
- 提示词可以点输入框右侧的文件夹图标从 txt 文件加载，每行一个条目，例如每行一个 `标签名: 提示词, 提示词`。
- 支持 `Ctrl+B` 批量：选择范围后确认提示词，弹窗同样可以从文件加载。

**Click / box（点击或框选单个目标）**：

- `Point (q)` 添加正点，`Point (e)` 添加负点，每次点击后立即更新分割结果。
- `+矩形` 画一个框，分割框内的目标。
- `清除 (b)` 清空当前提示，`完成 (f)` 确认当前目标并输入标签名。
- 同一张图第一次点击约 0.3 秒，之后每次约 0.02 秒。

**Example boxes（示例框找相似）**：

- 用 `+矩形` 框出一个或几个样例，`-矩形` 框出不想要的样例，点击 `运行矩形`，分割出图中所有相似的目标。

三个任务都可以用 **掩码精细度** 滑块调节多边形的点数：越精细，点越多。

### 4. 说明

- 默认配置 `detector: shared` 让所有任务共用一份 SAM 3.1 模型，约 5.5 GB 显存。代价是文本提示和示例框的置信度分数比批量流程低约 0.1，例如某张测试图上 `tactile paving` 在阈值 0.5 时一个都找不到；遇到这种情况先调低置信度。
- 显存 16 GB 以上时，可以把服务端 `configs/auto_labeling/segment_anything_3_1.yaml` 里的 `detector` 改成 `image_model`，分数会和批量流程一致，然后运行 `scripts/sam31_server.sh restart`。
- 暂不支持 SAM 3.1 视频跟踪。需要视频跟踪时，继续使用 X-AnyLabeling 自带的 SAM2 视频模型。

## 三、从视频获取图片

VLM 和 SAM 3.1 都按单张图片标注，视频要先拆成图片。拆出的图片放在一个普通文件夹里，按 `Ctrl+B` 批量标注即可。

### 1. 本地视频

按 `Ctrl+O`（文件 → 打开视频）选择视频，然后设置三项：

- **抽帧间隔**：每隔几帧取一张，例如 30 fps 的视频填 30 就是每秒 1 张。
- **文件名前缀**
- **序列长度**：编号的位数。

帧保存在视频旁边的同名文件夹里，完成后自动打开。

> 同名文件夹已存在时，确认覆盖会删除整个文件夹，里面已经保存的标注也会一起删除。想换间隔重新拆帧，先把旧文件夹改名。

### 2. 视频链接（YouTube、B 站等）

需要先安装 yt-dlp 和 ffmpeg：

```bash
conda activate x-anylabeling-cu11
pip install -U "yt-dlp[default,deno]"    # 或在仓库目录运行 pip install -e ".[gpu-cu11,video]"
sudo apt install ffmpeg             # Ubuntu
```

`deno` 是 YouTube 需要的 JavaScript 运行环境，会装进同一个 Python 环境；系统里的 Node.js 版本不低于 22 时也可以代替它。网站改版后，旧版 yt-dlp 会下载失败。遇到问题时先运行上面的 `pip install -U` 更新。

1. 点击 **文件 → 打开视频链接**。
2. 粘贴链接，每行一个，链接后面可以写要下载的时间段（见下面的**下载计划**）。也可以点 **从文件加载链接** 选一个写好的 txt 文件。B 站 App 分享出来的文字（如 `【标题】 https://b23.tv/xxxx`）可以直接粘贴，会自动取出其中的链接。
3. 设置下表中的选项，然后点 **开始**。
4. 进度窗口显示当前是第几个视频、第几段，以及下载和抽帧的进度。可以随时取消，已经处理完的部分会保留。
5. 全部完成后，帧保存目录会自动打开，接着按 `Ctrl+B` 批量标注。如果有下载失败，会列出链接、时间段和原因，例如需要登录、视频已删除、yt-dlp 版本过旧或网络错误。

| 选项 | 说明 |
| --- | --- |
| 帧保存目录 | 所有视频的帧都放在这里，默认是 `~/xanylabeling_data/videos/frames_<时间>` |
| 每秒抽帧数 | 默认 1；0.5 表示每 2 秒取 1 张 |
| 默认时间段 | 可选，写成 `90`、`1:30` 或 `1:02:03`；用于没有单独写时间段的链接，留空则下载整个视频 |
| 最高分辨率 | 默认 1080p；只下载画面，不下载声音 |
| 浏览器登录信息 | 读取所选浏览器里的登录状态，需要先在该浏览器里登录网站。B 站不登录时清晰度受限；YouTube 可能要求验证不是机器人 |
| 代理 | 默认留空，走系统网络。在中国大陆访问 YouTube 需要代理，例如 `http://127.0.0.1:7890` |
| 视频保存目录 | 下载的视频存在这里，默认是 `~/xanylabeling_data/videos`。同一个链接再次运行时不会重复下载 |
| 抽帧后保留视频文件 | 取消勾选后，抽完帧会删除视频 |
| yt-dlp 命令 | 默认留空：优先使用 X-AnyLabeling 所在 Python 环境里的 yt-dlp，其次使用 PATH 中的 |

**下载计划**：每行写一个链接，后面跟一个或多个时间段。可以直接写在链接框里，也可以存成 txt 文件（UTF-8 或 GBK 编码）再加载：

```text
# 盲道素材
https://www.bilibili.com/video/BV1FL4y1g7Pd   0:10-0:30   1:00-1:20
https://www.youtube.com/watch?v=aqz-KE-bpKQ   5:00-        # 从 5:00 到结尾
https://www.youtube.com/watch?v=jNQXAC9IVRw                # 不写时间段
```

- 时间写成秒数、`分:秒` 或 `时:分:秒`，例如 `90`、`1:30`、`1:02:03.5`，中文冒号也可以。
- 时间段写成 `开始-结束`，`-` 也可以写成 `~` 或 `到`，两边可以有空格。不写结束时间（如 `5:00-`）表示到视频结尾。多个时间段之间用空格、逗号或分号隔开。
- 不写时间段的链接使用 **默认时间段**；默认时间段也留空，就下载整个视频。
- 同一个链接写在多行时，各行的时间段合在一起；重叠或首尾相接的时间段合并成一段，例如 `0:10-0:30` 和 `0:25-0:40` 合并成 `0:10-0:40`。
- 整行以 `#` 开头，或 `#` 前面有空格时，`#` 后面的内容是注释。链接前面的文字会被忽略。
- 有写错的行时不会开始下载，而是列出行号和原因，例如 `第 3 行：不是有效的时间段：1:3o-2:00`。
- 每个时间段单独下载，只下这一段。时间段超出视频长度的部分会被忽略；开始时间就已经超出视频长度时，这一段列为失败。

**帧文件名**是 `网站_视频编号_t秒数.jpg`，例如 `bilibili_BV1FL4y1g7Pd_t000020.jpg` 是该视频第 20 秒的画面。每秒多于 1 张时会加上毫秒，例如 `t000010_500`。

**来源记录**：帧保存目录里的 `sources.json` 记录每个视频的链接、标题、作者、授权方式、时间段（每段一条，`start`/`end` 为秒数），以及每张图对应的视频时间，方便以后查数据来源。

- 链接指向播放列表或多 P 视频时，只下载链接对应的那一个视频。
- 同一个视频用相同的时间段和抽帧数再运行一次，会覆盖同名图片，已保存的标注不受影响。

**在脚本里使用**：同样的下载计划也可以在 Python 里执行，设置沿用对话框里保存的那份：

```python
from PyQt6.QtCore import QCoreApplication
from anylabeling.views.labeling.utils import video_download as vd

app = QCoreApplication([])
jobs, problems = vd.parse_plan(vd.read_links_file("plan.txt"))
assert not problems, problems
thread = vd.VideoDownloadThread(jobs, "/path/to/frames", vd.load_settings())
thread.progress_updated.connect(lambda pct, text: print(pct, text.splitlines()[-1]))
thread.finished_all.connect(lambda folder, count, failures: print(count, failures))
thread.run()  # 全部完成后才返回
```

> 请只下载你有权使用的视频。他人视频的抽帧仅供自己训练使用，请勿公开发布。

### 3. 跨帧跟踪

上面两种方式都把视频当成一组互不相关的图片。如果需要同一个目标在各帧里保持同一个编号，请使用官方的 SAM 2 Video（需要安装 `sam2` 包）或 SAM 3 Video（需要 X-AnyLabeling-Server 和 `sam3.pt` 权重）。本 fork 的 SAM 3.1 服务不提供视频跟踪。

## 常见问题

| 现象 | 处理 |
| --- | --- |
| VLM 报未登录或认证失败 | 在终端重新登录 `codex login` / `claude`；或检查 API key |
| 中转站返回 400 | 不支持 JSON Schema 输出时会自动退回普通 JSON 输出；仍然失败时，确认模型支持图片输入 |
| 批量时经常显示“降速冷却中” | 服务商在限流，调低 **最大并发** 或调大冷却时间 |
| 批量看起来像串行 | 并发从 1 开始，每成功一轮翻倍（1→2→4）。Codex 每张约 75 秒时，前两三分钟只有 1–2 个请求，看进度栏的“并发 x/y、进行中 z”即可确认。另外，“发送”按钮只处理当前一张，并发只对 `Ctrl+B` 批量生效 |
| VLM 漏掉某些目标 | 在提示词里补充描述，或在附加说明里写清楚要什么、不要什么 |
| Remote-Server 连接失败 | 运行 `scripts/sam31_server.sh status`；服务停止时先 `start` |
| SAM 3.1 结果太少 | 调低置信度；或者在显存足够时改用 `detector: image_model` |
| SAM 3.1 完全找不到某个类别 | 给同一个标签多写几个提示词。例如灰色盲道只写 `tactile paving` 一个都找不到，写成 `tactile_paving: tactile paving, gray tactile paving, tactile strip` 就能找到（分数 0.53）。可以先把置信度调到 0.1，逐个试提示词看分数，再选用效果好的 |
| 打开视频链接提示需要登录 | 先在浏览器里登录该网站，再在“浏览器登录信息”里选择这个浏览器；提示读取失败时，关闭浏览器再试 |
| 打开视频链接下载失败 | 先运行 `pip install -U "yt-dlp[default,deno]"` 更新 yt-dlp；在中国大陆访问 YouTube 还需要设置代理 |
