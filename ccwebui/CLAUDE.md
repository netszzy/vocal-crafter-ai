# ccwebui

基于 CosyVoice 的本地语音克隆合成 WebUI。

## 目录结构

```
ccwebui/
├── app.py              # 主入口，Gradio 界面
├── config.py           # 路径与参数配置
├── voice_manager.py    # 音色增删改查
├── task_manager.py     # 文本拆分、逐段生成、自动合并
├── data/               # 运行时数据（gitignore）
│   ├── voices.json     # 音色注册表
│   └── history.json    # 生成历史
├── outputs/            # 生成的音频文件（gitignore）
└── CLAUDE.md
```

## 运行

```bash
cd D:\gpt novel\voice
.venv-gpu\Scripts\activate
cd ccwebui
python app.py
```

启动后自动加载 CosyVoice 模型，浏览器打开 http://127.0.0.1:7861

## 核心流程

1. 音色管理：上传参考音频 + 填写参考文本 → 注册音色
2. 语音生成：选音色 → 粘贴文本 → 自动按标点和长度切分 → 独立子进程逐段推理 → 流式合并为一个完整 wav
3. 历史记录：查看/回放所有生成结果

## 依赖

- Python 3.10+
- torch CUDA
- soundfile
- gradio >= 4.0
- 依赖 voice 项目的 `.venv-gpu` 环境

## 约定

- 所有路径在 `config.py` 中统一定义，不硬编码
- 音色 ID 使用 uuid hex 前 8 位
- WebUI TTS 默认通过 `RUN_TTS_IN_SUBPROCESS = True` 调用 `scripts/batch_zero_shot.py`，避免 CosyVoice 在 Gradio 队列线程中导致服务退出
- ASR 默认通过 `PRELOAD_ASR_ON_START = False` 懒加载；上传参考音频时才加载 Whisper
- 生成目录按 `{时间戳}_{voice_id}/` 组织，避免用户输入的音色名进入目录名
- 合并文件为 `{安全清洗后的音色名}_full.wav`
- 历史记录保存 `segment_paths`，删除历史时只删除本任务 segment 和 merged 文件，并限制在 `ccwebui/outputs`
- 段间静音默认 0.35 秒
- 单段文本默认最大 120 字，常量为 `MAX_CHARS_PER_SEGMENT`
- 大音频预览超过 20MB 时走 `/gradio_api/file=` 文件路由，避免 base64 占用浏览器内存
