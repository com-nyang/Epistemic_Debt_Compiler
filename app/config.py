"""
.edc/config.json 기반 설정 로더.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel

from .registry import EDC_DIR


CONFIG_FILE = EDC_DIR / "config.json"


class GeminiConfig(BaseModel):
    enabled: bool = False
    api_key: Optional[str] = None
    model: str = "gemini-2.0-flash"
    language: Literal["ko", "en"] = "ko"


class EDCConfig(BaseModel):
    language: Literal["ko", "en"] = "ko"
    gemini: GeminiConfig = GeminiConfig()

    @classmethod
    def load(cls, path: Path = CONFIG_FILE) -> "EDCConfig":
        if not path.exists():
            return cls()
        try:
            return cls.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:
            return cls()

    def save(self, path: Path = CONFIG_FILE) -> None:
        path.parent.mkdir(exist_ok=True)
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")
