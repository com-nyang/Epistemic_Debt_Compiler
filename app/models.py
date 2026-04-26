"""
모든 Pydantic 데이터 모델 정의.
다른 레이어가 참조하는 공유 타입이므로 외부 앱 의존성 없음.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ── 열거형 ──────────────────────────────────────────────────────────────────

class RiskLevel(str, Enum):
    LOW    = "LOW"
    MEDIUM = "MEDIUM"
    HIGH   = "HIGH"


class Verdict(str, Enum):
    ALLOW             = "ALLOW"
    EVIDENCE_REQUIRED = "EVIDENCE_REQUIRED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    BLOCK             = "BLOCK"

    @property
    def exit_code(self) -> int:
        """hook/CI에서 사용할 exit code. BLOCK만 1을 반환한다."""
        return 1 if self == Verdict.BLOCK else 0

    @property
    def blocks(self) -> bool:
        return self == Verdict.BLOCK


class EvidenceType(str, Enum):
    TEST   = "test"
    CODE   = "code"
    DOC    = "doc"
    LOG    = "log"
    MANUAL = "manual"


# ── 인지부채 항목 ────────────────────────────────────────────────────────────

class DebtItem(BaseModel):
    id:          str      = Field(default_factory=lambda: f"edc-{uuid.uuid4().hex[:6]}")
    session_id:  str
    rule_id:     str                        # "HEDGE_STRONG", "HIGH_RISK_FILE" 등
    claim:       str                        # 감지된 텍스트 또는 행동 설명
    risk_level:  RiskLevel
    score:       int
    source:      Literal["text", "action"]

    # 액션 이벤트 전용 (source == "action")
    tool_name:   Optional[str] = None       # "Edit", "Write", "Bash"
    target_path: Optional[str] = None       # "src/auth.py"
    command:     Optional[str] = None       # Bash 명령어

    # 상환 정보
    resolved:      bool                  = False
    evidence:      Optional[str]         = None
    evidence_type: Optional[EvidenceType] = None

    created_at:  datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None

    def resolve(self, evidence: str, evidence_type: EvidenceType) -> None:
        self.resolved      = True
        self.evidence      = evidence
        self.evidence_type = evidence_type
        self.resolved_at   = datetime.utcnow()


# ── 세션 ────────────────────────────────────────────────────────────────────

class Session(BaseModel):
    id:           str      = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    started_at:   datetime = Field(default_factory=datetime.utcnow)
    project_root: str

    debt_score:      int    = 0
    verdict:         Verdict = Verdict.ALLOW

    event_ids:       list[str] = Field(default_factory=list)
    action_history:  list[str] = Field(default_factory=list)  # "edit", "bash", "test" 등
    force_overrides: int       = 0

    def add_event(self, event: DebtItem) -> None:
        self.event_ids.append(event.id)
        self.debt_score += event.score

    def record_action(self, action: str) -> None:
        self.action_history.append(action.lower())

    def has_run_tests(self) -> bool:
        return any(a in ("test", "pytest", "jest", "go test") for a in self.action_history)


# ── 파일 기반 레지스트리 루트 ──────────────────────────────────────────────────

class Registry(BaseModel):
    events:             dict[str, DebtItem] = Field(default_factory=dict)
    sessions:           dict[str, Session]  = Field(default_factory=dict)
    current_session_id: Optional[str]       = None


# ── 엔진 출력 DTO ────────────────────────────────────────────────────────────

class VerdictResult(BaseModel):
    verdict:      Verdict
    score:        int
    reason:       str
    blocking_ids: list[str] = Field(default_factory=list)
    suggestions:  list[str] = Field(default_factory=list)


class RepayResult(BaseModel):
    success:    bool
    event_id:   str
    reduced_by: int = 0
    new_score:  int = 0
    reason:     str = ""


# ── parsers → engine 전달용 DTO ───────────────────────────────────────────────

class ClassifiedDebt(BaseModel):
    rule_id:       str
    claim:         str              # 매칭된 원본 텍스트 발췌
    score:         int
    risk_level:    RiskLevel
    force_verdict: Optional[Verdict] = None


# ── debt watch 입력 포맷 ────────────────────────────────────────────────────

class RawEvent(BaseModel):
    """
    debt watch --file 로 전달되는 JSON 파일의 이벤트 단위.
    type 필드로 분기한다.
    """
    type:      str                  # "message" | "action" | "test" | "file_change"
    content:   Optional[str] = None  # message: 에이전트 텍스트
    tool:      Optional[str] = None  # action: "Edit", "Write", "Bash"
    target:    Optional[str] = None  # action / file_change: 대상 파일
    path:      Optional[str] = None  # file_change 전용 (target 대체)
    command:   Optional[str] = None  # action(Bash) / test: 실행 명령
    exit_code: Optional[int] = None  # test: 0=pass, 1+=fail
    output:    Optional[str] = None  # test: 출력 요약
    timestamp: Optional[str] = None


class SessionInput(BaseModel):
    """debt watch --file 로 전달되는 JSON 파일 전체 구조."""
    description: Optional[str] = None
    events:      list[RawEvent]
