# Local CosyVoice implementation for this PC

## Confirmed machine profile

- GPU: NVIDIA GeForce RTX 4070 12GB
- Driver: 595.97
- CPU threads visible to shell: 16
- Best working Python on this PC: `C:\Users\netsz\AppData\Local\Programs\Python\Python311\python.exe`
- Existing CUDA torch on this PC: `torch 2.5.1+cu121`

## What is already prepared

- Repo cloned to `D:\gpt novel\voice\CosyVoice`
- CPU-only Python 3.10 environment at `D:\gpt novel\voice\.venv`
- Workspace folders created:
  - `D:\gpt novel\voice\refs\raw`
  - `D:\gpt novel\voice\refs\clean`
  - `D:\gpt novel\voice\outputs`
  - `D:\gpt novel\voice\scripts`

## Recommended production path on this machine

Do not keep fighting the CPU-only 3.10 environment.
Use the local Python 3.11 installation that already exposes CUDA on this RTX 4070,
then build a GPU-oriented project venv on top of it.

## Setup steps

1. Run:

```powershell
& "D:\gpt novel\voice\scripts\setup_gpu_env.ps1"
```

2. Activate the GPU environment:

```powershell
& "D:\gpt novel\voice\.venv-gpu\Scripts\Activate.ps1"
```

3. Download one model into `D:\gpt novel\voice\CosyVoice\pretrained_models`

Recommended order:

- First choice: `Fun-CosyVoice3-0.5B`
- Safer fallback: `CosyVoice2-0.5B`

## Reference audio standard

- Length: 8 to 15 seconds
- One speaker only
- No BGM
- No obvious room echo
- Put raw files in `refs\raw`
- Put cleaned files in `refs\clean`
- Keep an exact transcript for each reference clip

## First inference command

```powershell
& "D:\gpt novel\voice\.venv-gpu\Scripts\Activate.ps1"
python "D:\gpt novel\voice\scripts\run_zero_shot.py" `
  --model-dir "D:\gpt novel\voice\CosyVoice\pretrained_models\Fun-CosyVoice3-0.5B" `
  --ref-wav "D:\gpt novel\voice\refs\clean\speaker01.wav" `
  --ref-text "希望你以后能够做得比我还好。" `
  --text "这是本地语音合成流程的第一轮听感测试。" `
  --output "D:\gpt novel\voice\outputs\speaker01_test.wav"
```

## Batch generation command

Put UTF-8 text into a text file. Long paragraphs are automatically split by punctuation and `--max-chars`.

- `D:\gpt novel\voice\scripts\batch_texts_example.txt`

Then run:

```powershell
& "D:\gpt novel\voice\.venv-gpu\Scripts\Activate.ps1"
python "D:\gpt novel\voice\scripts\batch_zero_shot.py" `
  --model-dir "D:\gpt novel\voice\CosyVoice\pretrained_models\Fun-CosyVoice3-0.5B" `
  --ref-wav "D:\gpt novel\voice\refs\clean\speaker01.wav" `
  --ref-text "希望你以后能够做得比我还好。" `
  --input "D:\gpt novel\voice\scripts\batch_texts_example.txt" `
  --output-dir "D:\gpt novel\voice\outputs\batch01" `
  --prefix "speaker01" `
  --merge-output "D:\gpt novel\voice\outputs\batch01\speaker01_full.wav" `
  --silence-secs 0.35 `
  --max-chars 120
```

This will create files like:

- `speaker01_001.wav`
- `speaker01_002.wav`
- `speaker01_003.wav`
- `speaker01_full.wav`

## One-click batch mode

Edit these two files:

- `D:\gpt novel\voice\scripts\batch_config.json`
- `D:\gpt novel\voice\scripts\batch_texts_example.txt`

Then run:

```powershell
& "D:\gpt novel\voice\scripts\run_batch_from_config.ps1"
```

Typical workflow:

- Put your reference wav path in `batch_config.json`
- Put the exact reference transcript in `batch_config.json`
- Put target text in `batch_texts_example.txt`; long text is split automatically
- Set `merged_output` for the complete WAV file
- Run `run_batch_from_config.ps1`

## WebUI production flow

- Desktop shortcut: `C:\Users\netsz\Desktop\Voice WebUI 一键启动.lnk`
- Launch script: `D:\gpt novel\voice\ccwebui\launch.ps1`
- WebUI URL: `http://127.0.0.1:7861`
- TTS generation runs in an isolated Python subprocess by default through `RUN_TTS_IN_SUBPROCESS = True`
- Whisper ASR is lazy-loaded when reference audio is uploaded because `PRELOAD_ASR_ON_START = False`
- WebUI outputs are stored under `D:\gpt novel\voice\ccwebui\outputs`
- CLI batch outputs are stored under the `output_dir` configured in `scripts\batch_config.json`

## Practical defaults for this RTX 4070

- Single inference job at a time
- Start with short sentences
- Use clean prompt audio before doing any advanced tuning
- Prefer Fun-CosyVoice3 only after the model files are fully downloaded
- If model download speed is unstable, use CosyVoice2 first

## Current risk to remember

The cloned 3.10 environment is usable for imports, but it is CPU-only right now.
For actual local TTS on this PC, the `.venv-gpu` path is the one to use.
