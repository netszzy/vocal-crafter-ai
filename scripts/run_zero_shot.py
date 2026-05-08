from __future__ import annotations

import argparse
import sys
from pathlib import Path

import torch
import torchaudio


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run local zero-shot CosyVoice inference.")
    parser.add_argument("--model-dir", required=True, help="Path to a downloaded CosyVoice model directory.")
    parser.add_argument("--ref-wav", required=True, help="Reference audio path (8-15s clean speech recommended).")
    parser.add_argument("--ref-text", required=True, help="Transcript for the reference audio.")
    parser.add_argument("--text", required=True, help="Target text to synthesize.")
    parser.add_argument("--output", required=True, help="Output wav path.")
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


def prepare_paths() -> tuple[Path, Path]:
    script_path = Path(__file__).resolve()
    voice_root = script_path.parent.parent
    repo_root = voice_root / "CosyVoice"
    matcha_root = repo_root / "third_party" / "Matcha-TTS"

    sys.path.insert(0, str(repo_root))
    sys.path.insert(0, str(matcha_root))
    return voice_root, repo_root


def merge_chunks(chunks: list[torch.Tensor]) -> torch.Tensor:
    if not chunks:
        raise RuntimeError("CosyVoice returned no audio chunks.")
    if len(chunks) == 1:
        return chunks[0]
    return torch.cat(chunks, dim=-1)


def resolve_prompt_text(model_dir: Path, ref_text: str, cv3_prefix: str) -> str:
    prompt_text = ref_text
    if "Fun-CosyVoice3" in model_dir.name and "<|endofprompt|>" not in prompt_text:
        prompt_text = f"{cv3_prefix}{prompt_text}"
    return prompt_text


def should_use_cv3_prefix(model_dir: Path, ref_text: str, text: str, cv3_prefix: str) -> bool:
    if "Fun-CosyVoice3" not in model_dir.name:
        return False
    if "<|endofprompt|>" in ref_text:
        return False
    prefixed_prompt = f"{cv3_prefix}{ref_text}"
    # For very short target text, forcing the full instruct prefix can make
    # the prompt much longer than the synthesis text and noticeably hurt quality.
    return len(text.strip()) >= len(prefixed_prompt.strip())


def minimal_cv3_prefix(cv3_prefix: str) -> str:
    if "<|endofprompt|>" in cv3_prefix:
        return cv3_prefix.split("<|endofprompt|>")[0].strip() + "<|endofprompt|>"
    return cv3_prefix


def select_device(force_cpu: bool) -> str:
    if force_cpu:
        return "cpu"
    return "cuda" if torch.cuda.is_available() else "cpu"


def load_model(model_dir: Path):
    _, repo_root = prepare_paths()
    from cosyvoice.cli.cosyvoice import AutoModel

    model = AutoModel(model_dir=str(model_dir))
    return model, repo_root


def synthesize_zero_shot(
    model,
    model_dir: Path,
    ref_wav: Path,
    ref_text: str,
    text: str,
    output: Path,
    cv3_prefix: str,
) -> Path:
    prompt_text = ref_text
    if "Fun-CosyVoice3" in model_dir.name and "<|endofprompt|>" not in ref_text:
        if should_use_cv3_prefix(model_dir, ref_text, text, cv3_prefix):
            prompt_text = resolve_prompt_text(model_dir, ref_text, cv3_prefix)
        else:
            prompt_text = f"{minimal_cv3_prefix(cv3_prefix)}{ref_text}"
    elif should_use_cv3_prefix(model_dir, ref_text, text, cv3_prefix):
        prompt_text = resolve_prompt_text(model_dir, ref_text, cv3_prefix)

    result = model.inference_zero_shot(
        text,
        prompt_text,
        str(ref_wav),
        stream=False,
    )
    chunks = [item["tts_speech"].cpu() for item in result]
    audio = merge_chunks(chunks)
    output.parent.mkdir(parents=True, exist_ok=True)
    torchaudio.save(str(output), audio, model.sample_rate)
    return output


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    model_dir = Path(args.model_dir).resolve()
    ref_wav = Path(args.ref_wav).resolve()
    output = Path(args.output).resolve()

    if not model_dir.exists():
        raise FileNotFoundError(f"Model directory not found: {model_dir}")
    if not ref_wav.exists():
        raise FileNotFoundError(f"Reference wav not found: {ref_wav}")

    device = select_device(args.force_cpu)
    model, repo_root = load_model(model_dir)
    synthesize_zero_shot(
        model=model,
        model_dir=model_dir,
        ref_wav=ref_wav,
        ref_text=args.ref_text,
        text=args.text,
        output=output,
        cv3_prefix=args.cv3_prefix,
    )
    print(f"repo={repo_root}")
    print(f"device={device}")
    print(f"output={output}")


if __name__ == "__main__":
    main()
