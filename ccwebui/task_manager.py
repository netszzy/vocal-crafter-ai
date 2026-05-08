"""
生成任务：文本拆分、逐段推理、自动合并、历史记录
"""

from __future__ import annotations

import json
import re
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import soundfile as sf

from config import (
    SCRIPTS_DIR,
    MODEL_DIR,
    OUTPUTS_DIR,
    HISTORY_JSON,
    SILENCE_SECS,
    CV3_PREFIX,
    DEFAULT_SAMPLE_RATE,
    RUN_TTS_IN_SUBPROCESS,
)

MAX_CHARS_PER_SEGMENT = 120
GENERATION_RETRIES = 2
SAFE_NAME_MAX_CHARS = 32

# 注入 voice 项目 scripts 路径
_scripts_path = str(SCRIPTS_DIR.resolve())
if _scripts_path not in sys.path:
    sys.path.insert(0, _scripts_path)


def _safe_filename_part(value: str, fallback: str = "voice") -> str:
    """Return a Windows-safe, short filename part for user-facing names."""
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value.strip())
    cleaned = re.sub(r"\s+", "_", cleaned).strip(" ._")
    if not cleaned:
        cleaned = fallback
    return cleaned[:SAFE_NAME_MAX_CHARS]


def _split_long_sentence(sentence: str, max_chars: int) -> list[str]:
    """Split an overlong sentence at softer punctuation before hard cutting."""
    chunks: list[str] = []
    remaining = sentence.strip()
    soft_pattern = re.compile(r"^(.{1,%d}[，,、：:；;])(.+)$" % max_chars, re.S)

    while len(remaining) > max_chars:
        match = soft_pattern.match(remaining)
        if match:
            head = match.group(1).strip()
            remaining = match.group(2).strip()
        else:
            head = remaining[:max_chars].strip()
            remaining = remaining[max_chars:].strip()
        if head:
            chunks.append(head)

    if remaining:
        chunks.append(remaining)
    return chunks


def _split_paragraph(paragraph: str, max_chars: int) -> list[str]:
    """Split one paragraph into ordered TTS-sized segments."""
    normalized = re.sub(r"\s+", " ", paragraph.strip())
    if not normalized:
        return []

    sentences = re.findall(r".+?(?:[。！？!?；;…]+|$)", normalized)
    atomic: list[str] = []
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(sentence) <= max_chars:
            atomic.append(sentence)
        else:
            atomic.extend(_split_long_sentence(sentence, max_chars))

    chunks: list[str] = []
    current = ""
    for sentence in atomic:
        if not current:
            current = sentence
        elif len(current) + len(sentence) <= max_chars:
            current += sentence
        else:
            chunks.append(current)
            current = sentence
    if current:
        chunks.append(current)
    return chunks


def _split_text(text: str, max_chars: int = MAX_CHARS_PER_SEGMENT) -> list[str]:
    """Split text into stable, ordered TTS segments."""
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            lines.extend(_split_paragraph(line, max_chars))
    return lines


def _merge_audio(
    wav_paths: list[Path],
    output_path: Path,
    sample_rate: int,
    silence_secs: float,
) -> Path:
    """Stream-merge wav files with silence between segments."""
    sr: Optional[int] = None
    channels: Optional[int] = None
    subtype: Optional[str] = None

    for p in wav_paths:
        info = sf.info(str(p))
        if sr is None:
            sr = info.samplerate
            channels = info.channels
            subtype = info.subtype
        elif sr != info.samplerate:
            raise RuntimeError(f"采样率不匹配: {p} ({info.samplerate} vs {sr})")
        elif channels != info.channels:
            raise RuntimeError(f"声道数不匹配: {p} ({info.channels} vs {channels})")

    if sr is None or channels is None:
        raise RuntimeError("没有可合并的音频片段")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    silence_frames = int(sr * silence_secs)

    with sf.SoundFile(
        str(output_path),
        mode="w",
        samplerate=sr,
        channels=channels,
        subtype=subtype or "PCM_16",
        format="WAV",
    ) as out_f:
        for i, p in enumerate(wav_paths):
            with sf.SoundFile(str(p), mode="r") as in_f:
                while True:
                    data = in_f.read(frames=sr * 30, dtype="float32", always_2d=True)
                    if len(data) == 0:
                        break
                    out_f.write(data)
            if i < len(wav_paths) - 1 and silence_frames > 0:
                import numpy as np

                out_f.write(np.zeros((silence_frames, channels), dtype="float32"))
    return output_path


class TaskManager:

    def __init__(self) -> None:
        self._model = None
        self._sample_rate = DEFAULT_SAMPLE_RATE
        self._history: list[dict] = []
        self._load_history()

    @property
    def is_model_loaded(self) -> bool:
        return RUN_TTS_IN_SUBPROCESS or self._model is not None

    def load_model(self) -> str:
        if RUN_TTS_IN_SUBPROCESS:
            runner = SCRIPTS_DIR / "batch_zero_shot.py"
            if not MODEL_DIR.exists():
                raise FileNotFoundError(f"模型目录不存在: {MODEL_DIR}")
            if not runner.exists():
                raise FileNotFoundError(f"生成脚本不存在: {runner}")
            self._model = "subprocess"
            return "模型将在独立子进程中按任务加载 | WebUI 服务保持常驻稳定"

        from run_zero_shot import load_model, select_device

        model, _ = load_model(MODEL_DIR)
        self._model = model
        self._sample_rate = getattr(model, "sample_rate", DEFAULT_SAMPLE_RATE)
        device = select_device(force_cpu=False)
        return f"模型已加载 | 设备: {device} | 采样率: {self._sample_rate}Hz"

    def _load_history(self) -> None:
        HISTORY_JSON.parent.mkdir(parents=True, exist_ok=True)
        if HISTORY_JSON.exists():
            try:
                with open(HISTORY_JSON, "r", encoding="utf-8") as f:
                    self._history = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._history = []
        else:
            self._history = []

    def _save_history(self) -> None:
        HISTORY_JSON.parent.mkdir(parents=True, exist_ok=True)
        with open(HISTORY_JSON, "w", encoding="utf-8") as f:
            json.dump(self._history, f, ensure_ascii=False, indent=2)

    def list_history(self, limit: int = 50) -> list[dict]:
        return list(reversed(self._history))[:limit]

    def delete_history(self, record_id: str, delete_files: bool = True) -> bool:
        """根据 ID 删除历史记录"""
        target = None
        search_id = str(record_id)
        for r in self._history:
            if str(r.get("id")) == search_id:
                target = r
                break
        
        if not target:
            print(f"[DEBUG] 删除失败: 未找到 ID 为 {search_id} 的记录")
            return False
        
        print(f"[DEBUG] 正在删除记录: {search_id}")
        
        # 删除文件
        if delete_files:
            merged_path = target.get("merged_path")
            if merged_path:
                p = Path(merged_path).resolve()
                outputs_root = OUTPUTS_DIR.resolve()
                if outputs_root in p.parents and p.exists():
                    try:
                        segment_paths = target.get("segment_paths") or [
                            str(seg) for seg in p.parent.glob("segment_*.wav")
                        ]
                        for raw_path in segment_paths:
                            seg = Path(raw_path).resolve()
                            if outputs_root in seg.parents and seg.exists():
                                seg.unlink()
                        if p.exists():
                            p.unlink()
                        task_dir = p.parent
                        if outputs_root in task_dir.parents and not any(task_dir.iterdir()):
                            task_dir.rmdir()
                    except Exception as e:
                        print(f"[WARN] 删除历史文件失败: {e}")

        self._history.remove(target)
        self._save_history()
        return True

    def generate(
        self,
        voice_id: str,
        voice_name: str,
        ref_wav: str,
        ref_text: str,
        text: str,
        silence_secs: float = SILENCE_SECS,
        progress=None,
    ) -> tuple[Optional[str], str]:
        """
        完整生成流程: 拆分 → 逐段推理 → 合并 → 记录历史
        返回: (合并文件路径, 状态消息)
        """
        if RUN_TTS_IN_SUBPROCESS:
            return self._generate_subprocess(
                voice_id=voice_id,
                voice_name=voice_name,
                ref_wav=ref_wav,
                ref_text=ref_text,
                text=text,
                silence_secs=silence_secs,
                progress=progress,
            )

        if not self.is_model_loaded:
            return None, "模型未加载，请等待初始化完成"

        from run_zero_shot import synthesize_zero_shot, resolve_prompt_text

        lines = _split_text(text)
        if not lines:
            return None, "没有可用的文本内容"

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_voice = _safe_filename_part(voice_name)
        task_id = f"{timestamp}_{voice_id}"
        task_dir = OUTPUTS_DIR / task_id
        task_dir.mkdir(parents=True, exist_ok=True)

        wav_paths: list[Path] = []
        failed_segments: list[str] = []
        total = len(lines)

        for i, line in enumerate(lines):
            if progress is not None:
                progress((i, total), desc=f"生成中 {i + 1}/{total}")

            output_path = task_dir / f"segment_{i + 1:03d}.wav"
            last_error: Optional[Exception] = None
            for attempt in range(1, GENERATION_RETRIES + 2):
                try:
                    synthesize_zero_shot(
                        model=self._model,
                        model_dir=MODEL_DIR,
                        ref_wav=Path(ref_wav),
                        ref_text=ref_text,
                        text=line,
                        output=output_path,
                        cv3_prefix=CV3_PREFIX,
                    )
                    wav_paths.append(output_path)
                    last_error = None
                    break
                except Exception as e:
                    last_error = e
                    print(f"[WARN] 段 {i + 1} 第 {attempt} 次生成失败: {e}")

            if last_error is not None:
                failed_segments.append(f"第 {i + 1} 段: {last_error}")

        if failed_segments:
            return None, "生成失败，未合并：\n" + "\n".join(failed_segments[:5])

        if len(wav_paths) != total:
            return None, f"生成失败，成功段数 {len(wav_paths)}/{total}，未合并不完整音频"

        if not wav_paths:
            return None, "所有段落生成均失败"

        merged_path = task_dir / f"{safe_voice}_full.wav"
        try:
            _merge_audio(wav_paths, merged_path, self._sample_rate, silence_secs)
        except Exception as e:
            return str(wav_paths[-1]), f"合并失败({e})，返回最后一段"

        if progress is not None:
            progress((total, total), desc="合并完成")

        record = {
            "id": timestamp,
            "voice_id": voice_id,
            "voice_name": voice_name,
            "text_preview": text[:80].replace("\n", " "),
            "total_lines": total,
            "success_lines": len(wav_paths),
            "merged_path": str(merged_path),
            "segment_paths": [str(p) for p in wav_paths],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._history.append(record)
        self._save_history()

        status = f"生成完成: {len(wav_paths)}/{total} 段成功，已合并为 {merged_path.name}"
        return str(merged_path), status

    def _generate_subprocess(
        self,
        voice_id: str,
        voice_name: str,
        ref_wav: str,
        ref_text: str,
        text: str,
        silence_secs: float = SILENCE_SECS,
        progress=None,
    ) -> tuple[Optional[str], str]:
        lines = _split_text(text)
        if not lines:
            return None, "没有可用的文本内容"

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_voice = _safe_filename_part(voice_name)
        task_id = f"{timestamp}_{voice_id}"
        task_dir = OUTPUTS_DIR / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        input_path = task_dir / "input.txt"
        merged_path = task_dir / f"{safe_voice}_full.wav"
        input_path.write_text("\n".join(lines), encoding="utf-8")

        if progress is not None:
            progress((0, len(lines)), desc="启动独立生成进程")

        cmd = [
            sys.executable,
            str(SCRIPTS_DIR / "batch_zero_shot.py"),
            "--model-dir",
            str(MODEL_DIR),
            "--ref-wav",
            str(ref_wav),
            "--ref-text",
            ref_text,
            "--input",
            str(input_path),
            "--output-dir",
            str(task_dir),
            "--prefix",
            "segment",
            "--start-index",
            "1",
            "--merge-output",
            str(merged_path),
            "--silence-secs",
            str(silence_secs),
            "--max-chars",
            str(MAX_CHARS_PER_SEGMENT),
            "--cv3-prefix",
            CV3_PREFIX,
        ]
        env = os.environ.copy()
        env.setdefault("PYTHONIOENCODING", "utf-8")
        env.setdefault("PYTHONUTF8", "1")

        result = subprocess.run(
            cmd,
            cwd=str(SCRIPTS_DIR.parent),
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
        )

        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            detail = detail[-1200:] if detail else "子进程没有返回错误详情"
            return None, f"生成失败，未合并：{detail}"

        if not merged_path.exists():
            return None, "生成失败，子进程未输出完整合并文件"

        wav_paths = sorted(task_dir.glob("segment_*.wav"))
        if len(wav_paths) != len(lines):
            return None, f"生成失败，成功段数 {len(wav_paths)}/{len(lines)}，未确认完整性"

        if progress is not None:
            progress((len(lines), len(lines)), desc="合并完成")

        record = {
            "id": timestamp,
            "voice_id": voice_id,
            "voice_name": voice_name,
            "text_preview": text[:80].replace("\n", " "),
            "total_lines": len(lines),
            "success_lines": len(wav_paths),
            "merged_path": str(merged_path),
            "segment_paths": [str(p) for p in wav_paths],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._history.append(record)
        self._save_history()

        status = f"生成完成: {len(wav_paths)}/{len(lines)} 段成功，已合并为 {merged_path.name}"
        return str(merged_path), status
