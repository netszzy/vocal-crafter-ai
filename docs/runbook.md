# Voice Project Runbook

## Standard Startup

Use the desktop shortcut:

```powershell
C:\Users\netsz\Desktop\Voice WebUI 一键启动.lnk
```

The shortcut runs:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "D:\gpt novel\voice\ccwebui\launch.ps1"
```

Expected WebUI URL:

```text
http://127.0.0.1:7861
```

## Manual WebUI Startup

```powershell
cd "D:\gpt novel\voice"
& ".\.venv-gpu\Scripts\python.exe" "ccwebui\app.py"
```

## Batch Generation

Edit:

```text
D:\gpt novel\voice\scripts\batch_config.json
D:\gpt novel\voice\scripts\batch_texts_example.txt
```

Run:

```powershell
& "D:\gpt novel\voice\scripts\run_batch_from_config.ps1"
```

Required config keys:

- `model_dir`
- `ref_wav`
- `ref_text`
- `input`
- `output_dir`
- `merged_output`
- `prefix`
- `start_index`
- `silence_secs`
- `max_chars`
- `force_cpu`
- `cv3_prefix`

## Smoke Tests

Compile check:

```powershell
cd "D:\gpt novel\voice"
& ".\.venv-gpu\Scripts\python.exe" -m compileall -q ccwebui scripts
```

WebUI HTTP check:

```powershell
Invoke-WebRequest "http://127.0.0.1:7861" -UseBasicParsing
Invoke-WebRequest "http://127.0.0.1:7861/gradio_api/info" -UseBasicParsing
```

Single inference check:

```powershell
& ".\.venv-gpu\Scripts\python.exe" "scripts\run_zero_shot.py" `
  --model-dir "D:\gpt novel\voice\CosyVoice\pretrained_models\Fun-CosyVoice3-0.5B" `
  --ref-wav "D:\gpt novel\voice\refs\clean\meili_huainvren_ref.wav" `
  --ref-text "为什么你们会有这样奇怪的要求啊，那我就……你行不行啊，细狗。细狗，你行不行啊。细狗，行不行啊，细狗。" `
  --text "这是本地语音合成流程测试。" `
  --output "D:\gpt novel\voice\outputs\smoke_single.wav"
```

## Operational Notes

- Keep one generation job running at a time on this RTX 4070 12GB machine.
- Use `.venv-gpu`; the `.venv` environment is CPU-oriented and not the production path.
- WebUI generation uses subprocess mode by default through `RUN_TTS_IN_SUBPROCESS = True`.
- Whisper ASR is lazy-loaded through `PRELOAD_ASR_ON_START = False`.
- Output audio and runtime data are ignored by git.

## Troubleshooting

### WebUI starts but generation exits the server

Check `ccwebui/config.py`:

```python
RUN_TTS_IN_SUBPROCESS = True
```

This must stay enabled for the stable WebUI path.

### Uploaded reference audio does not transcribe

Check that `.venv-gpu` can import Whisper:

```powershell
& ".\.venv-gpu\Scripts\python.exe" -c "import whisper; print(whisper.__version__)"
```

### Large audio preview fails

Large files are served through:

```text
/gradio_api/file=<absolute-path>
```

The path must be under one of the `allowed_paths` configured in `app.py`:

- `refs/clean`
- `ccwebui/outputs`

### History deletion does not remove files

History deletion only removes files under:

```text
D:\gpt novel\voice\ccwebui\outputs
```

Records with paths outside that directory are intentionally ignored for deletion safety.
