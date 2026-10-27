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

## 一、VLM 标注

### 1. 选择模型

1. 打开图片或图片目录。
2. 按 `Ctrl+A`（或左侧工具栏的“自动标注”）打开自动标注栏。
3. 点击“无模型”按钮，选择 **VLM Annotator (Codex / Claude / OpenAI)**。

### 2. 设置后端

点击自动标注栏上的 **VLM 设置**：

- **后端**：Codex CLI、Claude CLI 或 OpenAI 兼容 API。模型名留空时，Codex 使用 `~/.codex/config.toml` 里的模型，Claude 使用 CLI 默认模型。
- **OpenAI 兼容 API**：Base URL 和 API key 留空时，分别读取环境变量 `OPENAI_BASE_URL` 和 `OPENAI_API_KEY`。
- **单张超时**：默认 600 秒。
- **多边形最大顶点数**：默认 40，类别边界复杂时可以调大。
- **发送图片最长边**：默认 2048 像素，超过时先缩小再发送，返回的坐标会换算回原图。
- **附加说明**：附加到每次请求的额外要求，例如“相邻的导盲砖合并成一个实例”“忽略远处小于 20 像素的目标”。
- **批量**：最大并发、退避后的冷却时间、每张图的重试次数，见[批量标注](#5-批量标注)。

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

模型返回的提示词以外的类别会被丢弃。

### 4. 单张标注

1. 在输出下拉框里选择 **多边形** 或 **矩形**。矩形取多边形的外接框。
2. **标签覆盖** 开关：开启时，新结果替换当前图片已有的标注；关闭时保留已有标注，只追加新结果。
3. 点击 **发送**，等待返回。结果出现后可以像普通标注一样修改，再保存。

### 5. 批量标注

1. 先选好模型和输出方式，按 `Ctrl+B`（或左侧工具栏的“自动运行”）。
2. 选择图片范围，然后输入提示词。
3. 多张图片并发请求，进度栏显示“进度 / 并发 / 运行中 / 重试 / 失败”，每张图完成后立即保存。

并发数像 TCP 拥塞窗口一样自动调整：

- 从 1 开始，请求顺利时逐步增大，最多到设置里的 **最大并发**。
- 遇到限流、拒绝、超时，或者某个请求明显比平时慢（卡住），并发数减半，进入冷却期；进度栏显示“退避中”。
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

- 输入英文类别名，用逗号分隔，例如 `person, car, traffic light`，点击发送，每个实例生成一个多边形，标签就是类别名。
- **置信度** 默认 0.5，漏检时调低。
- 支持 `Ctrl+B` 批量：选择范围后输入同样格式的提示词。

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

## 常见问题

| 现象 | 处理 |
| --- | --- |
| VLM 报未登录或认证失败 | 在终端重新登录 `codex login` / `claude`；或检查 API key |
| 中转站返回 400 | 不支持 JSON Schema 输出时会自动退回普通 JSON 输出；仍然失败时，确认模型支持图片输入 |
| 批量时经常显示“退避中” | 服务商在限流，调低 **最大并发** 或调大冷却时间 |
| VLM 漏掉某些目标 | 在提示词里补充描述，或在附加说明里写清楚要什么、不要什么 |
| Remote-Server 连接失败 | 运行 `scripts/sam31_server.sh status`；服务停止时先 `start` |
| SAM 3.1 结果太少 | 调低置信度；或者在显存足够时改用 `detector: image_model` |
