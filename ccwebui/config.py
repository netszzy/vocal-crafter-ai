"""
ccwebui 全局配置
"""

from pathlib import Path

# voice 项目根目录
VOICE_ROOT = Path(__file__).resolve().parent.parent

# CosyVoice 模型目录
MODEL_DIR = VOICE_ROOT / "CosyVoice" / "pretrained_models" / "Fun-CosyVoice3-0.5B"

# 参考音频存储目录
REFS_DIR = VOICE_ROOT / "refs" / "clean"
REFS_RAW_DIR = VOICE_ROOT / "refs" / "raw"

# voice 项目 scripts 目录（用于 import 推理函数）
SCRIPTS_DIR = VOICE_ROOT / "scripts"

# ccwebui 自身路径
WEBUI_ROOT = Path(__file__).resolve().parent
DATA_DIR = WEBUI_ROOT / "data"
OUTPUTS_DIR = WEBUI_ROOT / "outputs"

VOICES_JSON = DATA_DIR / "voices.json"
HISTORY_JSON = DATA_DIR / "history.json"

# 推理参数
CV3_PREFIX = "You are a helpful assistant.<|endofprompt|>"
SILENCE_SECS = 0.35
DEFAULT_SAMPLE_RATE = 24000
RUN_TTS_IN_SUBPROCESS = True

# 自动截取参数
MAX_REF_DURATION_SECS = 15.0
TARGET_REF_MIN_SECS = 8.0
TARGET_REF_MAX_SECS = 15.0
TARGET_REF_IDEAL_SECS = 11.5

# ASR 参数
WHISPER_MODEL = "small"
PRELOAD_ASR_ON_START = False

# Gradio
SERVER_NAME = "127.0.0.1"
SERVER_PORT = 7861
