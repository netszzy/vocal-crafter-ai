# 新电脑从零开始实施文档

本文档面向一台**全新 Windows 电脑**，目标是在最短路径内把本项目跑起来，并具备以下能力：

- 导入参考音频
- 输入文本生成语音
- 批量生成长文本
- 自动合并为一个完整 WAV
- 启动 WebUI

本文档不假设新电脑上已经有 Python、虚拟环境、模型文件或缓存。

---

## 1. 目标目录

建议把项目放在一个**不含中文和空格的目录**，避免第三方工具路径兼容问题。

推荐：

```text
D:\voice
```

如果必须保留当前项目名，也可以用：

```text
D:\gpt novel\voice
```

但从部署稳定性看，短路径更稳。

---

## 2. 前置条件

新电脑需要满足：

- Windows 10/11
- NVIDIA 显卡
- 推荐显存：12GB 或以上
- 已安装最新可用 NVIDIA 驱动
- 网络可访问 GitHub 和 Hugging Face

推荐硬件：

- GPU：RTX 4070 12GB 或更高
- 内存：32GB 或更高
- 磁盘剩余空间：至少 25GB

空间预算大致如下：

- 项目代码与环境：5GB 到 10GB
- 模型目录：约 9GB
- 缓存和输出：按使用量增加

---

## 3. 需要安装的软件

### 必装

1. Git
2. Python 3.11 x64

### 可选

1. ffmpeg
   用于更方便地做音频格式转换和调试，不装也能运行当前主流程
2. PowerShell 7
   当前脚本在系统自带 PowerShell 下也能跑，但 PowerShell 7 更稳定

---

## 4. 安装 Python

下载并安装：

- [Python 3.11](https://www.python.org/downloads/windows/)

安装时必须勾选：

- `Add python.exe to PATH`

安装后验证：

```powershell
python --version
```

预期输出类似：

```text
Python 3.11.x
```

---

## 5. 获取项目代码

在目标目录的父目录执行：

```powershell
git clone --recursive https://github.com/FunAudioLLM/CosyVoice.git
```

但当前项目不是纯上游仓库，还包含额外脚本、WebUI 和配置。  
因此**更推荐直接复制当前整个 `voice` 项目目录**到新电脑。

最稳妥的做法是：

1. 把当前项目目录完整复制到新电脑
2. 在新电脑上重新创建 `.venv-gpu`
3. 重新安装依赖
4. 重新下载或复制模型目录

如果你不是直接拷整个现有目录，而是只拿脚本，至少要保证以下目录存在：

- `CosyVoice`
- `ccwebui`
- `scripts`
- `docs`
- `refs`
- `outputs`

---

## 6. 初始化目录结构

如果目录不完整，至少补齐这些目录：

```text
<project-root>\refs\raw
<project-root>\refs\clean
<project-root>\outputs
<project-root>\scripts
<project-root>\CosyVoice
<project-root>\ccwebui
```

---

## 7. 创建 GPU 虚拟环境

项目根目录假设为：

```text
D:\voice
```

执行：

```powershell
cd D:\voice
python -m venv .venv-gpu
& ".\.venv-gpu\Scripts\Activate.ps1"
python -m pip install --upgrade pip "setuptools<81" wheel
```

如果 PowerShell 阻止脚本执行，先临时放开当前会话：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

---

## 8. 安装 PyTorch CUDA 版本

这是最关键的一步。  
如果这一步装成 CPU 版，后面虽然能跑，但速度会很差。

安装命令：

```powershell
& ".\.venv-gpu\Scripts\Activate.ps1"
python -m pip install torch==2.5.1+cu121 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cu121
```

验证：

```powershell
python -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'cpu')"
```

预期：

- `torch.cuda.is_available()` 输出 `True`
- 能正确显示显卡名

如果这里输出 `False`，不要继续往下做。先排查：

- 驱动是否正常
- 是否装成 CPU 版 torch
- 是否装错 Python 环境

---

## 9. 安装项目依赖

先进入项目根目录并激活环境：

```powershell
cd D:\voice
& ".\.venv-gpu\Scripts\Activate.ps1"
```

安装当前项目依赖：

```powershell
python -m pip install --no-build-isolation openai-whisper==20231117
python -m pip install -r .\requirements-windows-gpu.txt
python -m pip install torchaudio==2.5.1
```

如果你是从当前项目目录完整复制过去，`requirements-windows-gpu.txt` 已经在项目根目录。

验证：

```powershell
python -m pip check
```

说明：

- 如果只出现全局包和系统包的非关键冲突，可以继续
- 但如果 `CosyVoice`、`gradio`、`torchaudio`、`transformers` 相关依赖损坏，需要先修

---

## 10. 初始化 CosyVoice 子模块

进入上游仓库目录：

```powershell
cd D:\voice\CosyVoice
git submodule update --init --recursive
```

这是必做项。  
如果不执行，后面加载模型时会报：

```text
ModuleNotFoundError: No module named 'matcha'
```

---

## 11. 下载模型

推荐模型：

- `Fun-CosyVoice3-0.5B-2512`

下载地址：

- [Hugging Face](https://huggingface.co/FunAudioLLM/Fun-CosyVoice3-0.5B-2512)
- [ModelScope](https://modelscope.cn/models/FunAudioLLM/Fun-CosyVoice3-0.5B-2512)

目标目录：

```text
D:\voice\CosyVoice\pretrained_models\Fun-CosyVoice3-0.5B
```

必须具备的核心文件：

- `campplus.onnx`
- `config.json`
- `configuration.json`
- `cosyvoice3.yaml`
- `flow.decoder.estimator.fp32.onnx`
- `flow.pt`
- `hift.pt`
- `llm.pt`
- `speech_tokenizer_v3.onnx`
- `CosyVoice-BlankEN\model.safetensors`

如果网络慢，优先用支持断点续传的工具整仓下载。

---

## 12. 准备参考音频

把参考音频放到：

```text
D:\voice\refs\clean
```

要求：

- 单人
- 8 到 15 秒
- 干净人声
- 无背景音乐
- 无明显混响
- 有准确逐字文本

---

## 13. 配置批量生成

编辑：

```text
D:\voice\scripts\batch_config.json
```

至少要改这些字段：

- `model_dir`
- `ref_wav`
- `ref_text`
- `input`
- `output_dir`
- `merged_output`

示例：

```json
{
  "model_dir": "D:\\voice\\CosyVoice\\pretrained_models\\Fun-CosyVoice3-0.5B",
  "ref_wav": "D:\\voice\\refs\\clean\\speaker01.wav",
  "ref_text": "这是参考音频的准确文本。",
  "input": "D:\\voice\\scripts\\batch_texts_example.txt",
  "output_dir": "D:\\voice\\outputs\\batch01",
  "merged_output": "D:\\voice\\outputs\\batch01\\speaker01_full.wav",
  "prefix": "speaker01",
  "start_index": 1,
  "silence_secs": 0.35,
  "max_chars": 120,
  "force_cpu": false,
  "cv3_prefix": "You are a helpful assistant.<|endofprompt|>"
}
```

---

## 14. 提交文本并生成

把要生成的文本放到：

```text
D:\voice\scripts\batch_texts_example.txt
```

当前脚本支持：

- 一行一句
- 整段粘贴
- 自动按标点和最大长度切分

执行：

```powershell
cd D:\voice
& ".\scripts\run_batch_from_config.ps1"
```

输出结果：

- 分段音频：`output_dir`
- 合并完整音频：`merged_output`

---

## 15. 启动 WebUI

执行：

```powershell
cd D:\voice
& ".\.venv-gpu\Scripts\python.exe" ".\ccwebui\app.py"
```

或者用启动脚本：

```powershell
& "D:\voice\ccwebui\launch.ps1"
```

默认地址：

```text
http://127.0.0.1:7861
```

如果你要在新电脑上创建桌面快捷方式，可以指向：

```text
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "D:\voice\ccwebui\launch.ps1"
```

---

## 16. 验收检查

至少做这三步：

### 1. CUDA 检查

```powershell
& ".\.venv-gpu\Scripts\Activate.ps1"
python -c "import torch; print(torch.cuda.is_available())"
```

必须输出：

```text
True
```

### 2. 单句推理检查

```powershell
python ".\scripts\run_zero_shot.py" `
  --model-dir "D:\voice\CosyVoice\pretrained_models\Fun-CosyVoice3-0.5B" `
  --ref-wav "D:\voice\refs\clean\speaker01.wav" `
  --ref-text "这是参考音频的准确文本。" `
  --text "这是部署完成后的单句测试。" `
  --output "D:\voice\outputs\smoke_single.wav"
```

### 3. 批量生成检查

```powershell
& ".\scripts\run_batch_from_config.ps1"
```

确认：

- 分段 WAV 生成成功
- `merged_output` 生成成功

---

## 17. 常见失败点

### 1. `torch.cuda.is_available()` 为 `False`

原因通常是：

- 安装了 CPU 版 torch
- 驱动有问题
- 当前命令没跑在 `.venv-gpu`

### 2. `No module named 'matcha'`

原因：

- 没执行 `git submodule update --init --recursive`

### 3. `ModuleNotFoundError: torchaudio`

原因：

- `.venv-gpu` 里没装 `torchaudio`

修复：

```powershell
python -m pip install torchaudio==2.5.1
```

### 4. ONNX 警告里只看到 CPU provider

当前这套流程里：

- 主模型推理走 CUDA
- 某些 ONNX 组件如果没拿到 GPU provider，仍可能回退 CPU

这不会阻塞整个流程，但会影响一部分性能。

### 5. 参考音频效果差

优先检查：

- 音频是否干净
- 时长是否在 8 到 15 秒
- `ref_text` 是否逐字准确
- 目标文本是否太长

---

## 18. 推荐交付方式

如果你要把这个项目交给另一台电脑，建议直接交付：

1. 整个项目目录
2. 本文档
3. 模型目录 `CosyVoice\pretrained_models\Fun-CosyVoice3-0.5B`
4. 一个可用参考音频和对应文本
5. 一个已经填好的 `batch_config.json`

这样新电脑只需要：

1. 安装 Python 3.11
2. 创建 `.venv-gpu`
3. 安装依赖
4. 验证 CUDA
5. 运行脚本

---

## 19. 最短路径总结

新电脑从零开始，最短路径是：

1. 安装 Python 3.11
2. 复制整个项目目录到 `D:\voice`
3. 创建 `.venv-gpu`
4. 安装 `torch==2.5.1+cu121` 和 `torchaudio==2.5.1`
5. 安装 `requirements-windows-gpu.txt`
6. 执行 `git submodule update --init --recursive`
7. 放好模型目录
8. 放好参考音频
9. 改 `batch_config.json`
10. 运行 `scripts\run_batch_from_config.ps1`

