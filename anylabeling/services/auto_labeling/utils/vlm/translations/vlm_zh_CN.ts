<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="zh_CN">
<context>
    <name>AutoLabelingWidget</name>
    <message>
        <source>VLM Settings</source>
        <translation>VLM 设置</translation>
    </message>
    <message>
        <source>Choose the VLM backend (Codex, Claude, OpenAI API)</source>
        <translation>选择 VLM 后端（Codex、Claude、OpenAI API）</translation>
    </message>
</context>
<context>
    <name>VLMSettingsDialog</name>
    <message>
        <source>VLM Annotator Settings</source>
        <translation>VLM 标注设置</translation>
    </message>
    <message>
        <source>Codex CLI (local login)</source>
        <translation>Codex CLI（本机登录）</translation>
    </message>
    <message>
        <source>Claude CLI (local login)</source>
        <translation>Claude CLI（本机登录）</translation>
    </message>
    <message>
        <source>OpenAI-compatible API</source>
        <translation>OpenAI 兼容 API</translation>
    </message>
    <message>
        <source>Backend</source>
        <translation>后端</translation>
    </message>
    <message>
        <source>Timeout per image</source>
        <translation>单张超时</translation>
    </message>
    <message>
        <source>Max polygon vertices</source>
        <translation>多边形最大顶点数</translation>
    </message>
    <message>
        <source>Max image side sent</source>
        <translation>发送图片最长边</translation>
    </message>
    <message>
        <source>Optional extra instructions appended to every request, e.g. how to split instances or what to ignore</source>
        <translation>可选：附加到每次请求的额外说明，例如如何拆分实例、哪些内容需要忽略</translation>
    </message>
    <message>
        <source>Extra instructions</source>
        <translation>附加说明</translation>
    </message>
    <message>
        <source>Batch (Run All Images)</source>
        <translation>批量（运行所有图片）</translation>
    </message>
    <message>
        <source>Upper limit of parallel requests. Concurrency starts at 1, grows while requests succeed, halves on rejections, timeouts or stalls, then grows again after the cooldown.</source>
        <translation>并发请求上限。并发从 1 开始，请求成功时逐步提升；遇到拒绝、超时或卡顿时减半，冷却结束后再继续提升。</translation>
    </message>
    <message>
        <source>Max concurrency</source>
        <translation>最大并发</translation>
    </message>
    <message>
        <source>Cooldown after back-off</source>
        <translation>降速后冷却时间</translation>
    </message>
    <message>
        <source>Retries per image</source>
        <translation>单张重试次数</translation>
    </message>
    <message>
        <source>Command</source>
        <translation>命令</translation>
    </message>
    <message>
        <source>Model</source>
        <translation>模型</translation>
    </message>
    <message>
        <source>Empty: model from ~/.codex/config.toml</source>
        <translation>留空：使用 ~/.codex/config.toml 中的模型</translation>
    </message>
    <message>
        <source>Reasoning effort</source>
        <translation>推理强度</translation>
    </message>
    <message>
        <source>Base URL</source>
        <translation>接口地址 (Base URL)</translation>
    </message>
    <message>
        <source>API key</source>
        <translation>API 密钥</translation>
    </message>
    <message>
        <source>Empty: use OPENAI_API_KEY</source>
        <translation>留空：使用环境变量 OPENAI_API_KEY</translation>
    </message>
    <message>
        <source>Temperature</source>
        <translation>温度</translation>
    </message>
    <message>
        <source>Uses the /chat/completions endpoint with image input.</source>
        <translation>使用 /chat/completions 接口发送图片。</translation>
    </message>
    <message>
        <source>Save</source>
        <translation>保存</translation>
    </message>
    <message>
        <source>Cancel</source>
        <translation>取消</translation>
    </message>
</context>
<context>
    <name>VLMBatchThread</name>
    <message>
        <source>Progress: {done}/{total}  |  concurrency {window}/{limit}  |  running {running}  |  retries {retries}  |  failed {failed}</source>
        <translation>进度：{done}/{total}  |  并发 {window}/{limit}  |  进行中 {running}  |  重试 {retries}  |  失败 {failed}</translation>
    </message>
    <message>
        <source>  |  backing off</source>
        <translation>  |  降速冷却中</translation>
    </message>
</context>
<context>
    <name>LabelingWidget</name>
    <message>
        <source>VLM batch</source>
        <translation>VLM 批量标注</translation>
    </message>
    <message>
        <source>{count} image(s) could not be labeled:</source>
        <translation>{count} 张图片标注失败：</translation>
    </message>
    <message>
        <source>Batch stopped: {reason}</source>
        <translation>批量已中止：{reason}</translation>
    </message>
</context>
<context>
    <name>PromptFile</name>
    <message>
        <source>Load prompt from file</source>
        <translation>从文件加载提示词</translation>
    </message>
    <message>
        <source>Text files (*.txt);;All files (*)</source>
        <translation>文本文件 (*.txt);;所有文件 (*)</translation>
    </message>
    <message>
        <source>Cannot read {path}: {error}</source>
        <translation>无法读取 {path}：{error}</translation>
    </message>
    <message>
        <source>{path} has no prompt entries.</source>
        <translation>{path} 中没有提示词条目。</translation>
    </message>
    <message>
        <source>Load the prompt from a .txt file: one entry per line, lines starting with # are ignored</source>
        <translation>从 .txt 文件加载提示词：每行一个条目，# 开头的行会被忽略</translation>
    </message>
</context>
<context>
    <name>VideoDownload</name>
    <message>
        <source>Open Video URL</source>
        <translation>打开视频链接</translation>
    </message>
    <message>
        <source>Download videos from YouTube, Bilibili and other sites, then extract frames</source>
        <translation>从 YouTube、B 站等网站下载视频并抽帧</translation>
    </message>
    <message>
        <source>Starting yt-dlp...</source>
        <translation>正在启动 yt-dlp...</translation>
    </message>
    <message>
        <source>Cancel</source>
        <translation>取消</translation>
    </message>
    <message>
        <source>Video {index}/{total}: {url}</source>
        <translation>第 {index}/{total} 个视频：{url}</translation>
    </message>
    <message>
        <source>Downloading {percent}%  {speed}</source>
        <translation>下载中 {percent}%  {speed}</translation>
    </message>
    <message>
        <source>Extracting frames...</source>
        <translation>正在抽帧...</translation>
    </message>
    <message>
        <source>Extracting frames {percent}%</source>
        <translation>抽帧中 {percent}%</translation>
    </message>
    <message>
        <source>{count} frames saved</source>
        <translation>已保存 {count} 帧</translation>
    </message>
    <message>
        <source>{count} download(s) failed:</source>
        <translation>{count} 项下载失败：</translation>
    </message>
    <message>
        <source>Line {line}: no http(s) link</source>
        <translation>第 {line} 行：没有 http(s) 链接</translation>
    </message>
    <message>
        <source>Line {line}: {problem}</source>
        <translation>第 {line} 行：{problem}</translation>
    </message>
    <message>
        <source>not a time range: {text}</source>
        <translation>不是有效的时间段：{text}</translation>
    </message>
    <message>
        <source>the end must be after the start: {text}</source>
        <translation>结束时间必须晚于开始时间：{text}</translation>
    </message>
    <message>
        <source>Section {part}/{parts}: {span}</source>
        <translation>第 {part}/{parts} 段：{span}</translation>
    </message>
    <message>
        <source>The section starts after the video ends ({length}).</source>
        <translation>这一段的开始时间超出了视频长度（{length}）。</translation>
    </message>
    <message>
        <source>yt-dlp not found: {command}</source>
        <translation>找不到 yt-dlp：{command}</translation>
    </message>
    <message>
        <source>yt-dlp is not installed. Install it into the Python that runs X-AnyLabeling: pip install -U "yt-dlp[default,deno]"</source>
        <translation>未安装 yt-dlp。请在运行 X-AnyLabeling 的 Python 环境中安装：pip install -U "yt-dlp[default,deno]"</translation>
    </message>
    <message>
        <source>yt-dlp failed without an error message.</source>
        <translation>yt-dlp 运行失败，但没有给出错误信息。</translation>
    </message>
    <message>
        <source>Cannot read the browser cookies: close that browser and try again, or choose another browser.</source>
        <translation>无法读取浏览器的登录信息：请关闭该浏览器后重试，或换一个浏览器。</translation>
    </message>
    <message>
        <source>The site wants a login: log in to it in your browser, then choose that browser under Browser cookies.</source>
        <translation>网站要求登录：请先在浏览器里登录该网站，再在“浏览器登录信息”中选择这个浏览器。</translation>
    </message>
    <message>
        <source>This link is not a video page yt-dlp supports.</source>
        <translation>这个链接不是 yt-dlp 支持的视频页面。</translation>
    </message>
    <message>
        <source>The page was not found: check the link.</source>
        <translation>页面不存在，请检查链接。</translation>
    </message>
    <message>
        <source>The video is unavailable: removed, private or region-locked.</source>
        <translation>视频无法观看：已删除、仅自己可见或有地区限制。</translation>
    </message>
    <message>
        <source>yt-dlp may be outdated: update it with pip install -U "yt-dlp[default,deno]" and try again.</source>
        <translation>yt-dlp 可能版本过旧：请用 pip install -U "yt-dlp[default,deno]" 更新后重试。</translation>
    </message>
    <message>
        <source>Network error: check the connection, or set a proxy (YouTube needs one in mainland China).</source>
        <translation>网络错误：请检查网络连接，或设置代理（在中国大陆访问 YouTube 需要代理）。</translation>
    </message>
    <message>
        <source>ffmpeg is required: install it and make sure it is on PATH.</source>
        <translation>需要 ffmpeg：请安装并确保它在 PATH 中。</translation>
    </message>
    <message>
        <source>ffmpeg could not extract frames: {error}</source>
        <translation>ffmpeg 抽帧失败：{error}</translation>
    </message>
</context>
<context>
    <name>VideoUrlDialog</name>
    <message>
        <source>Open Video URL</source>
        <translation>打开视频链接</translation>
    </message>
    <message>
        <source>Video links, one per line (YouTube, Bilibili and other sites supported by yt-dlp). Time ranges may follow a link, e.g. 0:10-0:30 1:00-1:20, or 5:00- to the end:</source>
        <translation>视频链接，每行一个（支持 YouTube、B 站等 yt-dlp 支持的网站）。链接后面可以写时间段，例如 0:10-0:30 1:00-1:20，写 5:00- 表示到结尾：</translation>
    </message>
    <message>
        <source>Load links from file...</source>
        <translation>从文件加载链接...</translation>
    </message>
    <message>
        <source>Text files (*.txt);;All files (*)</source>
        <translation>文本文件 (*.txt);;所有文件 (*)</translation>
    </message>
    <message>
        <source>Cannot read {path}: {error}</source>
        <translation>无法读取 {path}：{error}</translation>
    </message>
    <message>
        <source>Frames folder</source>
        <translation>帧保存目录</translation>
    </message>
    <message>
        <source>Frames per second</source>
        <translation>每秒抽帧数</translation>
    </message>
    <message>
        <source>Frames taken per second of video; 0.5 takes one frame every 2 seconds</source>
        <translation>视频每秒取几张图；0.5 表示每 2 秒取 1 张</translation>
    </message>
    <message>
        <source>Default time range</source>
        <translation>默认时间段</translation>
    </message>
    <message>
        <source>to</source>
        <translation>到</translation>
    </message>
    <message>
        <source>video end</source>
        <translation>视频结尾</translation>
    </message>
    <message>
        <source>For links without time ranges of their own, e.g. 90, 1:30 or 1:02:03; empty downloads the whole video</source>
        <translation>用于没有单独写时间段的链接，例如 90、1:30 或 1:02:03；留空则下载整个视频</translation>
    </message>
    <message>
        <source>Max resolution</source>
        <translation>最高分辨率</translation>
    </message>
    <message>
        <source>Best available</source>
        <translation>最高可用</translation>
    </message>
    <message>
        <source>Browser cookies</source>
        <translation>浏览器登录信息</translation>
    </message>
    <message>
        <source>None</source>
        <translation>不使用</translation>
    </message>
    <message>
        <source>Use the login of this browser: Bilibili limits the quality without one, YouTube may ask to confirm you are not a bot</source>
        <translation>使用该浏览器里的登录状态：B 站不登录时清晰度受限，YouTube 可能要求验证不是机器人</translation>
    </message>
    <message>
        <source>Proxy</source>
        <translation>代理</translation>
    </message>
    <message>
        <source>Empty: system network, e.g. http://127.0.0.1:7890</source>
        <translation>留空：使用系统网络，例如 http://127.0.0.1:7890</translation>
    </message>
    <message>
        <source>Video folder</source>
        <translation>视频保存目录</translation>
    </message>
    <message>
        <source>Downloaded videos are kept here, so running the same link again skips the download</source>
        <translation>下载的视频保存在这里，同一个链接再次运行时不会重复下载</translation>
    </message>
    <message>
        <source>Keep videos after extracting frames</source>
        <translation>抽帧后保留视频文件</translation>
    </message>
    <message>
        <source>yt-dlp command</source>
        <translation>yt-dlp 命令</translation>
    </message>
    <message>
        <source>Empty: yt-dlp installed with X-AnyLabeling, else on PATH</source>
        <translation>留空：优先使用 X-AnyLabeling 环境中的 yt-dlp，其次使用 PATH 中的</translation>
    </message>
    <message>
        <source>Only download videos you may use. Frames of other people's videos are for your own training data; do not publish them.</source>
        <translation>请只下载你有权使用的视频。他人视频的抽帧仅供自己训练使用，请勿公开发布。</translation>
    </message>
    <message>
        <source>Start</source>
        <translation>开始</translation>
    </message>
    <message>
        <source>Cancel</source>
        <translation>取消</translation>
    </message>
    <message>
        <source>Browse...</source>
        <translation>浏览...</translation>
    </message>
    <message>
        <source>Choose a folder</source>
        <translation>选择文件夹</translation>
    </message>
    <message>
        <source>Enter at least one video link.</source>
        <translation>请至少输入一个视频链接。</translation>
    </message>
    <message>
        <source>Fix these lines; write time ranges as 1:00-1:30, or 5:00- to the end:</source>
        <translation>请修改以下行；时间段写成 1:00-1:30，或写 5:00- 表示到结尾：</translation>
    </message>
    <message>
        <source>Write times as seconds, m:ss or h:mm:ss, e.g. 1:30.</source>
        <translation>时间请写成秒数、分:秒或时:分:秒，例如 1:30。</translation>
    </message>
    <message>
        <source>The end time must be after the start time.</source>
        <translation>结束时间必须晚于开始时间。</translation>
    </message>
    <message>
        <source>Choose a frames folder.</source>
        <translation>请选择帧保存目录。</translation>
    </message>
</context>
<context>
    <name>Model</name>
    <message>
        <source>Enter the classes to label, e.g. 'tactile_paving: raised guide tiles; crosswalk'</source>
        <translation>请输入要标注的类别，例如 'tactile_paving: 导盲砖; crosswalk'</translation>
    </message>
</context>
</TS>
