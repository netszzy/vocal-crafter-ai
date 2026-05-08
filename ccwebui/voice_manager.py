"""
音色管理：增删改查与持久化
"""

from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from config import VOICES_JSON, REFS_DIR


class VoiceManager:

    def __init__(self) -> None:
        self._voices: list[dict] = []
        self._load()

    def _load(self) -> None:
        VOICES_JSON.parent.mkdir(parents=True, exist_ok=True)
        if VOICES_JSON.exists():
            with open(VOICES_JSON, "r", encoding="utf-8") as f:
                self._voices = json.load(f)
        else:
            self._voices = []
            self._save()

    def _save(self) -> None:
        VOICES_JSON.parent.mkdir(parents=True, exist_ok=True)
        with open(VOICES_JSON, "w", encoding="utf-8") as f:
            json.dump(self._voices, f, ensure_ascii=False, indent=2)

    def list_voices(self) -> list[dict]:
        return [dict(v) for v in self._voices]

    def get_voice(self, voice_id: str) -> Optional[dict]:
        for v in self._voices:
            if v["id"] == voice_id:
                return dict(v)
        return None

    def add_voice(self, name: str, ref_wav_path: str, ref_text: str) -> dict:
        src = Path(ref_wav_path).resolve()
        if not src.exists():
            raise FileNotFoundError(f"参考音频不存在: {src}")

        voice_id = uuid.uuid4().hex[:8]
        dest = REFS_DIR / f"{voice_id}_{src.name}"
        REFS_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)

        voice = {
            "id": voice_id,
            "name": name.strip(),
            "ref_wav": str(dest),
            "ref_text": ref_text.strip(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._voices.append(voice)
        self._save()
        return dict(voice)

    def update_voice(
        self, voice_id: str, name: Optional[str] = None, ref_text: Optional[str] = None
    ) -> Optional[dict]:
        for v in self._voices:
            if v["id"] == voice_id:
                if name is not None:
                    v["name"] = name.strip()
                if ref_text is not None:
                    v["ref_text"] = ref_text.strip()
                self._save()
                return dict(v)
        return None

    def delete_voice(self, voice_id: str) -> bool:
        before = len(self._voices)
        self._voices = [v for v in self._voices if v["id"] != voice_id]
        if len(self._voices) < before:
            self._save()
            return True
        return False

    def get_choices(self) -> list[tuple[str, str]]:
        """Gradio Dropdown 用: (显示名, 值)"""
        return [(v["name"], v["id"]) for v in self._voices]

    def get_name_map(self) -> dict[str, str]:
        return {v["id"]: v["name"] for v in self._voices}
