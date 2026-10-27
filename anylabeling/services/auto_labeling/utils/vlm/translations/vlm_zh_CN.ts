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
    <name>Model</name>
    <message>
        <source>Enter the classes to label, e.g. 'tactile_paving: raised guide tiles; crosswalk'</source>
        <translation>请输入要标注的类别，例如 'tactile_paving: 导盲砖; crosswalk'</translation>
    </message>
</context>
</TS>
