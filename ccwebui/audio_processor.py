"""
音频处理：自动截取最佳片段 + Whisper ASR
"""

from __future__ import annotations

import re
import shutil
import tempfile
import uuid
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf
import whisper

from config import (
    MAX_REF_DURATION_SECS,
    REFS_RAW_DIR,
    TARGET_REF_IDEAL_SECS,
    TARGET_REF_MAX_SECS,
    TARGET_REF_MIN_SECS,
    WHISPER_MODEL,
)

_asr_model = None


def preload_asr_model():
    """启动时预加载 ASR 模型，避免首次上传超时。"""
    global _asr_model
    if _asr_model is None:
        _asr_model = whisper.load_model(WHISPER_MODEL)
    return _asr_model


def _load_asr_model():
    global _asr_model
    if _asr_model is None:
        _asr_model = whisper.load_model(WHISPER_MODEL)
    return _asr_model


def get_audio_duration(path: str) -> float:
    info = sf.info(path)
    return info.duration


def extract_best_segment(path: str) -> tuple[str, float, float]:
    """从长音频中截取最佳片段，返回 (提取段路径, 起始秒, 结束秒)。"""
    y, sr = librosa.load(path, sr=None)
    total_dur = len(y) / sr

    # 备份原始文件
    REFS_RAW_DIR.mkdir(parents=True, exist_ok=True)
    src = Path(path)
    raw_dest = REFS_RAW_DIR / f"{uuid.uuid4().hex[:8]}_{src.name}"
    shutil.copy2(src, raw_dest)

    # 检测语音区间
    intervals = librosa.effects.split(y, top_db=30)
    if len(intervals) == 0:
        # 无语音检测到，取中间段
        start_sample = int((total_dur - TARGET_REF_IDEAL_SECS) / 2 * sr)
        end_sample = start_sample + int(TARGET_REF_IDEAL_SECS * sr)
        return _save_segment(y, sr, max(0, start_sample), min(len(y), end_sample), path)

    # 合并间距 <0.5s 的相邻区间
    merged = _merge_intervals(intervals, sr, gap_threshold=0.5)

    # 对每个合并区间评分
    candidates = []
    for start_s, end_s in merged:
        dur = end_s - start_s
        if dur < 1.0:
            continue
        start_idx = int(start_s * sr)
        end_idx = int(end_s * sr)
        segment = y[start_idx:end_idx]

        # 计算评分
        duration_score = _duration_score(dur)
        rms_cv = _rms_cv(segment)
        mean_rms = np.sqrt(np.mean(segment ** 2))
        score = duration_score * 0.5 + (1 - rms_cv) * 0.3 + min(mean_rms * 10, 1.0) * 0.2
        candidates.append((score, start_s, end_s, dur))

    if not candidates:
        # fallback: 取中间段
        mid = total_dur / 2
        start_s = max(0, mid - TARGET_REF_IDEAL_SECS / 2)
        end_s = min(total_dur, start_s + TARGET_REF_IDEAL_SECS)
        start_idx = int(start_s * sr)
        end_idx = int(end_s * sr)
        return _save_segment(y, sr, start_idx, end_idx, path)

    # 选最佳候选
    candidates.sort(key=lambda x: x[0], reverse=True)
    best = candidates[0]

    # 如果最佳候选在目标范围内，直接用
    if TARGET_REF_MIN_SECS <= best[3] <= TARGET_REF_MAX_SECS:
        start_idx = int(best[1] * sr)
        end_idx = int(best[2] * sr)
        return _save_segment(y, sr, start_idx, end_idx, path)

    # 候选太长：取中心窗口
    if best[3] > TARGET_REF_MAX_SECS:
        center = (best[1] + best[2]) / 2
        half = TARGET_REF_IDEAL_SECS / 2
        start_s = max(best[1], center - half)
        end_s = min(best[2], start_s + TARGET_REF_IDEAL_SECS)
        start_idx = int(start_s * sr)
        end_idx = int(end_s * sr)
        return _save_segment(y, sr, start_idx, end_idx, path)

    # 候选太短：尝试拼接
    total_s = 0.0
    chosen = []
    for score, s, e, d in candidates:
        chosen.append((s, e))
        total_s += d
        if total_s >= TARGET_REF_MIN_SECS:
            break

    if total_s >= TARGET_REF_MIN_SECS:
        all_start = int(chosen[0][0] * sr)
        all_end = int(chosen[-1][1] * sr)
        return _save_segment(y, sr, all_start, all_end, path)

    # 实在拼不够，取最长的
    best = candidates[0]
    start_idx = int(best[1] * sr)
    end_idx = int(best[2] * sr)
    return _save_segment(y, sr, start_idx, end_idx, path)


def _merge_intervals(
    intervals: np.ndarray, sr: int, gap_threshold: float = 0.5
) -> list[tuple[float, float]]:
    """合并间距小于 gap_threshold 秒的相邻语音区间。"""
    if len(intervals) == 0:
        return []
    merged = []
    cur_start = intervals[0][0]
    cur_end = intervals[0][1]
    for s, e in intervals[1:]:
        if (s - cur_end) / sr < gap_threshold:
            cur_end = e
        else:
            merged.append((cur_start / sr, cur_end / sr))
            cur_start = s
            cur_end = e
    merged.append((cur_start / sr, cur_end / sr))
    return merged


def _duration_score(dur: float) -> float:
    """时长评分：越接近 TARGET_REF_IDEAL_SECS 越高。"""
    dist = abs(dur - TARGET_REF_IDEAL_SECS)
    max_dist = TARGET_REF_IDEAL_SECS - TARGET_REF_MIN_SECS
    return max(0, 1 - dist / max_dist)


def _rms_cv(segment: np.ndarray) -> float:
    """RMS 变异系数（越低越稳定）。"""
    frame_len = 2048
    hop = 512
    rms_vals = []
    for i in range(0, len(segment) - frame_len, hop):
        frame = segment[i : i + frame_len]
        rms_vals.append(np.sqrt(np.mean(frame ** 2)))
    if len(rms_vals) < 2:
        return 0.0
    rms_arr = np.array(rms_vals)
    mean = rms_arr.mean()
    if mean < 1e-8:
        return 1.0
    return float(rms_arr.std() / mean)


def _save_segment(
    y: np.ndarray, sr: int, start_idx: int, end_idx: int, orig_path: str
) -> tuple[str, float, float]:
    """提取片段并保存为临时 WAV，返回 (路径, 起始秒, 结束秒)。"""
    segment = y[start_idx:end_idx]
    segment, _ = librosa.effects.trim(segment, top_db=25)

    start_sec = start_idx / sr
    end_sec = end_idx / sr

    tmp_dir = Path(tempfile.gettempdir()) / "ccwebui_extract"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    out_path = str(tmp_dir / f"{uuid.uuid4().hex[:8]}_segment.wav")
    sf.write(out_path, segment, sr)

    return out_path, start_sec, end_sec


def transcribe_audio(path: str) -> str:
    """Whisper ASR，返回识别文本。"""
    model = _load_asr_model()
    # 用 librosa 加载避免 ffmpeg 依赖
    y, _ = librosa.load(path, sr=16000)
    audio = y.astype(np.float32)
    result = model.transcribe(audio, language="zh", initial_prompt="以下是普通话的句子。", word_timestamps=False)
    return result["text"].strip()
