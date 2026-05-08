# Voice - AI 长篇语音合成流水线 (Open Source Edition)

本项目是一个基于 `Fun-CosyVoice3-0.5B` 的本地语音生成操作台和流水线，提供了包含 WebUI 和命令行的一键批量处理方案。专门优化了长文本切割、音色复刻以及最终文件合并流程。

## 🌟 核心特性

- **Gradio WebUI 界面**：直观管理音色库，一键粘贴小说长文本进行全自动语音合成。
- **子进程稳定生成**：TTS 推理独立子进程执行，避免阻塞 UI 线程。
- **长文本智能切分与合并**：自动按照标点符号和长度上限切割，推理完毕后无缝拼接成完整音频。
- **ASR 动态按需加载**：只有在提取参考音频文本时加载 Whisper，日常推理不额外占用显存。
- **命令行批处理支持**：通过 `json` 配置和简单的脚本，快速执行批量合成任务。

## 🚀 快速启动

### 1. 环境准备

建议使用 Python 3.10+，并推荐在虚拟环境中安装：

```bash
# 核心依赖 (适配 Windows GPU)
pip install -r requirements-windows-gpu.txt
```

*(请确保您已经安装并配置好了对应的 CUDA 环境以及 `Fun-CosyVoice3` 核心库。如果是从零开始，可以参考 `docs/new-computer-deployment.md`)*

### 2. 启动 WebUI

最推荐的日常使用方式是通过 WebUI：

```bash
# 进入 ccwebui 目录
cd ccwebui

# Windows 一键启动脚本
start.bat
# 或
.\launch.ps1
```

启动后在浏览器打开对应本地端口即可进入操作界面，进行音色录入和长文本合成。

## 💻 命令行批处理流程

如果您需要通过命令行进行自动化处理，核心控制文件位于 `scripts/` 下。

### 1. 配置文件设置

修改 `scripts/batch_config.json`：
- `ref_wav`：参考音频路径 (推荐放到 `refs/clean/`)
- `ref_text`：参考音频对应文本
- `input`：待生成的长文本文件 (如 `scripts/batch_texts_example.txt`)
- `output_dir`：分段临时输出目录
- `merged_output`：最终拼接好的完整 WAV 路径

### 2. 运行脚本

```powershell
# Windows
& ".\scripts\run_batch_from_config.ps1"
```

## 📖 参考音频建议

为了让零样本 (Zero-Shot) 音色复刻更加稳定自然，参考音频请尽量满足：
- **时长**：`8 - 15 秒`
- **纯净度**：单人干声、无背景音乐、无明显混响
- **准确度**：对应的 `ref_text` 必须逐字准确

## 📁 目录结构

- `ccwebui/`：Gradio 网页端界面及所有后端调度逻辑
- `CosyVoice/`：底层模型调用封装层 (请确保包含预训练模型)
- `scripts/`：命令行批处理脚本和配置文件
- `docs/`：详细部署和架构文档
- `outputs/`、`refs/`、`参考音色/`：默认的音频输入输出与参考目录

---
*本项目作为一个本地语音流水线范例，仅包含调度与处理代码，不包含任何使用者私有录音与生成历史数据。*