# Voice Project Architecture

## Purpose

This project provides local voice cloning and long-form text-to-speech generation on Windows.

Primary requirements:

- Register a custom voice from uploaded reference audio and transcript.
- Generate WAV audio using a registered custom voice.
- Generate one complete WAV file from long text.

## Main Components

- `ccwebui/app.py`: Gradio WebUI, user interactions, audio preview, history table.
- `ccwebui/voice_manager.py`: Voice registry persisted in `ccwebui/data/voices.json`.
- `ccwebui/task_manager.py`: Text splitting, generation orchestration, stream merging, history persistence, safe deletion.
- `ccwebui/audio_processor.py`: Reference audio duration check, best-segment extraction, Whisper ASR.
- `scripts/run_zero_shot.py`: Single zero-shot CosyVoice inference.
- `scripts/batch_zero_shot.py`: CLI batch inference, automatic text splitting, optional merged output.
- `scripts/run_batch_from_config.ps1`: One-command batch entry point using `scripts/batch_config.json`.
- `ccwebui/launch.ps1`: WebUI startup script used by the desktop shortcut.

## WebUI Data Flow

1. User uploads reference audio in the WebUI.
2. `app.on_audio_uploaded()` copies the upload to `refs/raw`.
3. `audio_processor` checks duration.
4. Audio longer than 15 seconds is reduced to a best segment.
5. Whisper ASR fills the transcript field for user review.
6. `VoiceManager.add_voice()` copies the final reference WAV into `refs/clean` and stores metadata.
7. User selects a voice and enters target text.
8. `TaskManager.generate()` splits text into stable ordered segments.
9. With `RUN_TTS_IN_SUBPROCESS = True`, generation runs in a separate Python process through `scripts/batch_zero_shot.py`.
10. Segment WAV files are stream-merged into one complete WAV.
11. History is written to `ccwebui/data/history.json`.

## Long Text Strategy

- Default segment size: `MAX_CHARS_PER_SEGMENT = 120`.
- Splitting order:
  - Preserve input line order.
  - Ignore empty lines and lines starting with `#`.
  - Split paragraphs by Chinese and English sentence punctuation.
  - Split overlong sentences at soft punctuation before hard cutting.
- Any failed segment blocks final merge.
- The WebUI reports failure instead of returning an incomplete audio file as a success.

## Stability Strategy

CosyVoice inference was observed to terminate the Gradio server process when executed inside the Gradio queue worker. The production WebUI path therefore uses a subprocess boundary:

- WebUI stays resident and handles UI/API state.
- TTS inference runs in a clean Python subprocess.
- Subprocess success is validated by checking the merged WAV and segment count.
- Subprocess failure returns stderr/stdout detail without writing a successful history record.

ASR is lazy-loaded:

- `PRELOAD_ASR_ON_START = False`.
- Whisper loads only when reference audio is uploaded.
- Normal generation does not keep Whisper resident.

## File Layout

- Voice references: `refs/clean`
- Raw uploads: `refs/raw`
- WebUI runtime data: `ccwebui/data`
- WebUI output tasks: `ccwebui/outputs/{yyyyMMdd_HHmmss}_{voice_id}`
- CLI batch outputs: configured `output_dir` in `scripts/batch_config.json`

Each WebUI task directory contains:

- `input.txt`: generated segment input for subprocess execution.
- `segment_001.wav`, `segment_002.wav`, ...: segment outputs.
- `{safe_voice_name}_full.wav`: complete merged output.

## Safety Boundaries

- User voice names are not used in task directory names.
- File names derived from voice names are cleaned for Windows path safety.
- History deletion only removes:
  - paths in `segment_paths`
  - the record's `merged_path`
  - empty task directory after deletion
- Deletion is constrained to `ccwebui/outputs`.
- Large audio preview uses Gradio file routing instead of base64 when WAV size exceeds 20MB.
