"""
rules.json 파일을 로드하고 규칙 모델을 정의한다.
코드 변경 없이 rules.json만 수정해서 규칙을 튜닝할 수 있다.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel


# ── 규칙 모델 ────────────────────────────────────────────────────────────────

class TextRule(BaseModel):
    """자연어 텍스트에서 불확실성 표현을 감지하는 규칙."""
    id:            str
    type:          Literal["text"]
    patterns:      dict[str, list[str]]   # {"en": [...], "ko": [...]}
    score:         int
    risk_level:    str = "MEDIUM"
    force_verdict: Optional[str] = None


class ActionRule(BaseModel):
    """도구 호출(Edit, Write, Bash)에서 위험 행동을 감지하는 규칙."""
    id:                   str
    type:                 Literal["action"]
    trigger:              list[str]        # 감지할 tool 이름 목록
    condition:            str              # 판단 조건 식별자
    score:                int
    risk_level:           str = "HIGH"
    force_verdict:        Optional[str] = None
    risk_patterns:        list[str] = []   # HIGH_RISK_FILE 조건에 사용
    destructive_patterns: list[str] = []   # DESTRUCTIVE_CMD 조건에 사용


class RepayRule(BaseModel):
    """부채 상환 방법과 점수 감소량을 정의하는 규칙."""
    id:              str
    type:            str
    score_reduction: int
    description:     str = ""


class ComboRule(BaseModel):
    """복수 규칙이 동시에 활성화될 때 강제 판정을 내리는 규칙."""
    id:            str
    description:   str
    conditions:    list[str]   # 동시에 활성화되어야 하는 rule_id 목록
    force_verdict: str


class Thresholds(BaseModel):
    allow:             int = 20
    evidence_required: int = 40
    approval_required: int = 70


class Rules(BaseModel):
    version:      str
    thresholds:   Thresholds
    debt_events:  list[TextRule | ActionRule]
    repay_events: list[RepayRule]
    combo_rules:  list[ComboRule] = []

    @classmethod
    def load(cls, path: Path) -> "Rules":
        """rules.json을 읽어 Rules 인스턴스를 반환한다."""
        data = json.loads(path.read_text(encoding="utf-8"))

        # type 필드로 TextRule/ActionRule 분기
        parsed_events: list[TextRule | ActionRule] = []
        for e in data["debt_events"]:
            if e["type"] == "text":
                parsed_events.append(TextRule(**e))
            else:
                parsed_events.append(ActionRule(**e))

        data["debt_events"] = parsed_events
        data["repay_events"] = [RepayRule(**r) for r in data["repay_events"]]
        data["combo_rules"]  = [ComboRule(**c) for c in data.get("combo_rules", [])]
        data["thresholds"]   = Thresholds(**data["thresholds"])

        return cls(**data)

    def get_text_rules(self) -> list[TextRule]:
        return [r for r in self.debt_events if isinstance(r, TextRule)]

    def get_action_rules(self) -> list[ActionRule]:
        return [r for r in self.debt_events if isinstance(r, ActionRule)]

    def get_repay_rule(self, repay_id: str) -> Optional[RepayRule]:
        return next((r for r in self.repay_events if r.id == repay_id), None)
