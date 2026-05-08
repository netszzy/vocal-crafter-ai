from __future__ import annotations

import argparse
import sys
from pathlib import Path

from run_zero_shot import load_model, select_device, synthesize_zero_shot

CCWEBUI_DIR = Path(__file__).resolve().parent.parent / "ccwebui"
if str(CCWEBUI_DIR) not in sys.path:
    sys.path.insert(0, str(CCWEBUI_DIR))

from task_manager import MAX_CHARS_PER_SEGMENT, SILENCE_SECS, _merge_audio, _split_text


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Batch zero-shot CosyVoice inference from a text file.")
    parser.add_argument("--model-dir", required=True, help="Path to a downloaded CosyVoice model directory.")
    parser.add_argument("--ref-wav", required=True, help="Reference audio path.")
    parser.add_argument("--ref-text", required=True, help="Transcript for the reference audio.")
    parser.add_argument("--input", required=True, help="UTF-8 text file. One non-empty line becomes one wav.")
    parser.add_argument("--output-dir", required=True, help="Folder for generated wav files.")
    parser.add_argument("--merge-output", help="Optional merged wav path for the full generated audio.")
    parser.add_argument(
        "--silence-secs",
        type=float,
        default=SILENCE_SECS,
        help="Silence duration inserted between merged segments.",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=MAX_CHARS_PER_SEGMENT,
        help="Maximum characters per generated segment after automatic splitting.",
    )
    parser.add_argument(
        "--prefix",
        default="line",
        help="Filename prefix. Outputs look like prefix_001.wav",
    )
    parser.add_argument(
        "--start-index",
        type=int,
        default=1,
        help="Starting index for output numbering.",
    )
    parser.add_argument(
        "--force-cpu",
        action="store_true",
        help="Force CPU inference even if CUDA is available.",
    )
    parser.add_argument(
        "--cv3-prefix",
        default="You are a helpful assistant.<|endofprompt|>",
        help="Prefix used for Fun-CosyVoice3 style prompts.",
    )
    return parser


def load_lines(input_path: Path, max_chars: int) -> list[str]:
    lines = _split_text(input_path.read_text(encoding="utf-8"), max_chars=max_chars)
    if not lines:
        raise RuntimeError("No usable lines found in input text file.")
    return lines


def main() -> None:
    args = build_parser().parse_args()
    model_dir = Path(args.model_dir).resolve()
    ref_wav = Path(args.ref_wav).resolve()
    input_path = Path(args.input).resolve()
    output_dir = Path(args.output_dir).resolve()

    if not model_dir.exists():
        raise FileNotFoundError(f"Model directory not found: {model_dir}")
    if not ref_wav.exists():
        raise FileNotFoundError(f"Reference wav not found: {ref_wav}")
    if not input_path.exists():
        raise FileNotFoundError(f"Input text file not found: {input_path}")

    device = select_device(args.force_cpu)
    model, repo_root = load_model(model_dir)
    lines = load_lines(input_path, max_chars=args.max_chars)
    generated: list[Path] = []

    print(f"repo={repo_root}")
    print(f"device={device}")
    print(f"lines={len(lines)}")

    for offset, text in enumerate(lines, start=args.start_index):
        output = output_dir / f"{args.prefix}_{offset:03d}.wav"
        synthesize_zero_shot(
            model=model,
            model_dir=model_dir,
            ref_wav=ref_wav,
            ref_text=args.ref_text,
            text=text,
            output=output,
            cv3_prefix=args.cv3_prefix,
        )
        generated.append(output)
        print(f"saved={output}")

    if args.merge_output:
        merged = Path(args.merge_output).resolve()
        _merge_audio(generated, merged, getattr(model, "sample_rate", 24000), args.silence_secs)
        print(f"merged={merged}")


if __name__ == "__main__":
    main()
