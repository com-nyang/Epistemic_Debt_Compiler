# Architecture — Epistemic Debt Compiler (Python MVP)

**버전:** 0.1 | 기술 스택: Python 3.11+, Typer, Rich, Pydantic v2

---

## 1. 폴더 구조

```
epistemic_debt_compiler/
├── pyproject.toml
├── rules.json                    # 규칙 정의 (외부 설정, 코드 수정 없이 튜닝)
│
├── app/
│   ├── __init__.py
│   ├── main.py                   # CLI entry point (Typer 앱)
│   ├── models.py                 # Pydantic 데이터 모델 전체
│   ├── rules.py                  # 규칙 파일 로딩 + 규칙 모델
│   ├── engine.py                 # Rule engine 핵심 로직
│   ├── parsers.py                # 텍스트/액션 분류기 (Classifier 인터페이스)
│   ├── registry.py               # DebtRegistry — .edc/debt.json CRUD
│   ├── formatters.py             # Rich 터미널 출력 포맷터
│   └── hooks.py                  # Claude Code / 외부 hook 연동 어댑터
│
├── .edc/                         # 런타임 데이터 (.gitignore 추가)
│   ├── debt.json                 # 인지부채 레지스트리
│   ├── session.json              # 현재 세션 상태
│   └── config.json               # 프로젝트별 설정 오버라이드
│
└── tests/
    ├── test_engine.py
    ├── test_parsers.py
    ├── test_registry.py
    └── fixtures/
        ├── sample_output.txt
        └── rules_test.json
```

---

## 2. 각 파일의 역할

| 파일 | 레이어 | 역할 |
|---|---|---|
| `main.py` | CLI | Typer 명령 정의, 레이어 조립, exit code 제어 |
| `models.py` | Domain | 모든 Pydantic 모델 정의. 의존성 없음 |
| `rules.py` | Config | rules.json 로딩, 규칙 모델 정의 |
| `engine.py` | Core | 점수 계산, 판정 로직. CLI/IO 의존성 없음 |
| `parsers.py` | Infra | Classifier 인터페이스 + 규칙 기반 구현체 |
| `registry.py` | Infra | .edc/debt.json 읽기/쓰기, 세션 관리 |
| `formatters.py` | Presentation | Rich 출력. 데이터만 받아 출력, 로직 없음 |
| `hooks.py` | Adapter | Claude Code / CMUX hook stdin/stdout 처리 |

---

## 3. 핵심 데이터 모델 (`app/models.py`)

```python
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


# ── 열거형 ──────────────────────────────────────────────────────────────────

class RiskLevel(str, Enum):
    LOW    = "LOW"
    MEDIUM = "MEDIUM"
    HIGH   = "HIGH"


class Verdict(str, Enum):
    ALLOW              = "ALLOW"
    EVIDENCE_REQUIRED  = "EVIDENCE_REQUIRED"
    APPROVAL_REQUIRED  = "APPROVAL_REQUIRED"
    BLOCK              = "BLOCK"

    @property
    def exit_code(self) -> int:
        return 1 if self in (Verdict.BLOCK,) else 0

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

class DebtEvent(BaseModel):
    id:             str       = Field(default_factory=lambda: f"edc-{uuid.uuid4().hex[:6]}")
    session_id:     str
    rule_id:        str                      # "HEDGE_STRONG", "HIGH_RISK_FILE" 등
    claim:          str                      # 감지된 원본 텍스트 또는 행동 설명
    risk_level:     RiskLevel
    score:          int
    source:         Literal["text", "action"]

    # 액션 이벤트 전용
    tool_name:      str | None = None        # "Edit", "Write", "Bash"
    target_path:    str | None = None        # "src/auth.py"
    command:        str | None = None        # Bash 명령어

    # 상환 정보
    resolved:       bool             = False
    evidence:       str | None       = None
    evidence_type:  EvidenceType | None = None

    # 타임스탬프
    created_at:     datetime = Field(default_factory=datetime.utcnow)
    resolved_at:    datetime | None = None

    def resolve(self, evidence: str, evidence_type: EvidenceType) -> None:
        self.resolved      = True
        self.evidence      = evidence
        self.evidence_type = evidence_type
        self.resolved_at   = datetime.utcnow()


# ── 세션 ────────────────────────────────────────────────────────────────────

class Session(BaseModel):
    id:              str      = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    started_at:      datetime = Field(default_factory=datetime.utcnow)
    project_root:    str

    debt_score:      int     = 0
    verdict:         Verdict = Verdict.ALLOW

    event_ids:       list[str] = Field(default_factory=list)  # DebtEvent.id 목록
    action_history:  list[str] = Field(default_factory=list)  # "edit", "bash", "test" 등
    force_overrides: int       = 0

    def add_event(self, event: DebtEvent) -> None:
        self.event_ids.append(event.id)
        self.debt_score += event.score

    def record_action(self, tool: str) -> None:
        self.action_history.append(tool.lower())

    def has_run_tests(self) -> bool:
        return "bash" in self.action_history  # 더 정밀한 체크는 registry에서


# ── 레지스트리 (파일 직렬화 루트) ─────────────────────────────────────────────

class Registry(BaseModel):
    events:             dict[str, DebtEvent] = Field(default_factory=dict)
    sessions:           dict[str, Session]   = Field(default_factory=dict)
    current_session_id: str | None           = None


# ── 판정 결과 ────────────────────────────────────────────────────────────────

class VerdictResult(BaseModel):
    verdict:       Verdict
    score:         int
    reason:        str
    blocking_ids:  list[str] = Field(default_factory=list)  # 차단 원인 DebtEvent ID
    suggestions:   list[str] = Field(default_factory=list)  # 상환 방법 제안


# ── 상환 결과 ────────────────────────────────────────────────────────────────

class RepayResult(BaseModel):
    success:     bool
    event_id:    str
    reduced_by:  int  = 0
    new_score:   int  = 0
    reason:      str  = ""


# ── 분류기 출력 (parsers → engine 전달 DTO) ───────────────────────────────────

class ClassifiedDebt(BaseModel):
    rule_id:    str
    claim:      str          # 매칭된 원본 텍스트
    score:      int
    risk_level: RiskLevel
    force_verdict: Verdict | None = None
```

---

## 4. 규칙 모델 (`app/rules.py`)

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel


# ── 규칙 모델 ────────────────────────────────────────────────────────────────

class TextRule(BaseModel):
    id:            str
    type:          Literal["text"]
    patterns:      dict[str, list[str]]   # {"en": [...], "ko": [...]}
    score:         int
    risk_level:    str = "MEDIUM"
    force_verdict: str | None = None


class ActionRule(BaseModel):
    id:                   str
    type:                 Literal["action"]
    trigger:              list[str]          # ["Edit", "Write"]
    condition:            str
    score:                int
    risk_level:           str = "HIGH"
    force_verdict:        str | None = None
    risk_patterns:        list[str] = []
    destructive_patterns: list[str] = []


class RepayRule(BaseModel):
    id:              str
    type:            str
    score_reduction: int
    description:     str = ""


class ComboRule(BaseModel):
    id:            str
    description:   str
    conditions:    list[str]     # 동시에 활성화된 rule_id 목록
    force_verdict: str


class Thresholds(BaseModel):
    allow:              int = 20
    evidence_required:  int = 40
    approval_required:  int = 70
    block:              int = 71


class Rules(BaseModel):
    version:      str
    thresholds:   Thresholds
    debt_events:  list[TextRule | ActionRule]
    repay_events: list[RepayRule]
    combo_rules:  list[ComboRule] = []

    @classmethod
    def load(cls, path: Path = Path("rules.json")) -> "Rules":
        data = json.loads(path.read_text())
        # debt_events discriminated union: type 필드로 분기
        events = []
        for e in data["debt_events"]:
            if e["type"] == "text":
                events.append(TextRule(**e))
            else:
                events.append(ActionRule(**e))
        data["debt_events"] = events
        return cls(**data)

    def get_text_rules(self) -> list[TextRule]:
        return [r for r in self.debt_events if isinstance(r, TextRule)]

    def get_action_rules(self) -> list[ActionRule]:
        return [r for r in self.debt_events if isinstance(r, ActionRule)]

    def get_repay_rule(self, repay_id: str) -> RepayRule | None:
        return next((r for r in self.repay_events if r.id == repay_id), None)
```

---

## 5. 분류기 레이어 (`app/parsers.py`)

```python
from __future__ import annotations

import re
from typing import Protocol, runtime_checkable

from .models import ClassifiedDebt, RiskLevel, Verdict
from .rules import Rules, TextRule


# ── Classifier 인터페이스 (LLM 교체 포인트) ──────────────────────────────────

@runtime_checkable
class Classifier(Protocol):
    def classify(self, text: str) -> list[ClassifiedDebt]:
        """텍스트에서 인지부채 후보를 감지해 반환한다."""
        ...


# ── 규칙 기반 구현 (MVP 기본값) ───────────────────────────────────────────────

class RuleBasedClassifier:

    def __init__(self, rules: Rules) -> None:
        self._rules = rules.get_text_rules()

    def classify(self, text: str) -> list[ClassifiedDebt]:
        results: list[ClassifiedDebt] = []
        matched_ids: set[str] = set()

        for rule in self._rules:
            if rule.id in matched_ids:
                continue
            matched = self._match(text, rule)
            if matched:
                results.append(ClassifiedDebt(
                    rule_id=rule.id,
                    claim=matched,
                    score=rule.score,
                    risk_level=RiskLevel(rule.risk_level),
                    force_verdict=Verdict(rule.force_verdict) if rule.force_verdict else None,
                ))
                matched_ids.add(rule.id)

        return results

    def _match(self, text: str, rule: TextRule) -> str | None:
        """매칭된 원본 텍스트 반환, 없으면 None."""
        for lang_patterns in rule.patterns.values():
            for pattern in lang_patterns:
                m = re.search(pattern, text, re.IGNORECASE)
                if m:
                    # 문장 단위로 잘라서 반환
                    return self._extract_sentence(text, m.start())
        return None

    @staticmethod
    def _extract_sentence(text: str, pos: int) -> str:
        start = max(0, text.rfind(".", 0, pos) + 1)
        end   = text.find(".", pos)
        end   = end + 1 if end != -1 else len(text)
        return text[start:end].strip()


# ── Action 분류기 (도구 호출 분석) ───────────────────────────────────────────

class ActionClassifier:
    """텍스트가 아닌 tool 호출 자체를 분석한다."""

    def __init__(self, rules: Rules) -> None:
        self._rules = rules.get_action_rules()

    def classify(
        self,
        tool: str,
        target: str,
        command: str,
        session_action_history: list[str],
        edit_counts: dict[str, int],
    ) -> list[ClassifiedDebt]:
        results: list[ClassifiedDebt] = []

        for rule in self._rules:
            if tool not in rule.trigger:
                continue
            if self._check_condition(rule, tool, target, command, session_action_history, edit_counts):
                results.append(ClassifiedDebt(
                    rule_id=rule.id,
                    claim=self._describe(rule, tool, target, command),
                    score=rule.score,
                    risk_level=RiskLevel(rule.risk_level),
                    force_verdict=Verdict(rule.force_verdict) if rule.force_verdict else None,
                ))

        return results

    def _check_condition(self, rule, tool, target, command, history, edit_counts) -> bool:
        c = rule.condition
        if c == "no_test_run_in_session":
            return "test" not in history and "pytest" not in history
        if c == "target_matches_risk_patterns":
            return any(re.search(p, target, re.IGNORECASE) for p in rule.risk_patterns)
        if c == "command_matches_destructive_patterns":
            return any(p in command for p in rule.destructive_patterns)
        if c == "same_file_same_lines_count >= 3":
            return edit_counts.get(target, 0) >= 3
        return False

    @staticmethod
    def _describe(rule, tool, target, command) -> str:
        if rule.id == "EDIT_NO_TEST":
            return f"테스트 실행 없이 {target} 수정 시도"
        if rule.id == "HIGH_RISK_FILE":
            return f"고위험 파일 접근: {target}"
        if rule.id == "DESTRUCTIVE_CMD":
            return f"파괴적 명령 실행: {command[:60]}"
        if rule.id == "RETRY_SAME_FIX":
            return f"동일 파일 반복 수정: {target}"
        return f"{tool} → {target or command}"
```

---

## 6. Rule Engine (`app/engine.py`)

```python
from __future__ import annotations

from .models import (
    ClassifiedDebt, DebtEvent, EvidenceType, RepayResult,
    RiskLevel, Session, Verdict, VerdictResult,
)
from .parsers import ActionClassifier, Classifier
from .registry import DebtRegistry
from .rules import Rules


class RuleEngine:
    """
    레이어 계약:
      - IO 없음 (파일 읽기/쓰기는 registry가 담당)
      - 출력 없음 (출력은 formatter가 담당)
      - 순수 로직만
    """

    def __init__(
        self,
        rules:             Rules,
        classifier:        Classifier,
        action_classifier: ActionClassifier,
        registry:          DebtRegistry,
    ) -> None:
        self._rules             = rules
        self._classifier        = classifier
        self._action_classifier = action_classifier
        self._registry          = registry

    # ── 텍스트 처리 ─────────────────────────────────────────────────────────

    def process_text(self, text: str, session: Session) -> list[DebtEvent]:
        classified = self._classifier.classify(text)
        events = []
        for c in classified:
            event = self._make_event(c, session, source="text")
            self._registry.add_event(event)
            session.add_event(event)
            events.append(event)
        self._registry.save_session(session)
        return events

    # ── 액션 처리 ───────────────────────────────────────────────────────────

    def process_action(
        self,
        tool:    str,
        target:  str = "",
        command: str = "",
        session: Session = None,
    ) -> list[DebtEvent]:
        session.record_action(tool)

        edit_counts = self._registry.count_edits_by_target(session.id)
        classified = self._action_classifier.classify(
            tool, target, command, session.action_history, edit_counts
        )

        events = []
        for c in classified:
            event = self._make_event(c, session, source="action",
                                     tool_name=tool, target_path=target, command=command)
            self._registry.add_event(event)
            session.add_event(event)
            events.append(event)
        self._registry.save_session(session)
        return events

    # ── 부채 상환 ───────────────────────────────────────────────────────────

    def process_repayment(
        self,
        event_id:     str,
        repay_id:     str,
        evidence:     str,
        session:      Session,
        run_command:  str | None = None,
    ) -> RepayResult:
        event = self._registry.get_event(event_id)
        if event is None:
            return RepayResult(success=False, event_id=event_id, reason="부채를 찾을 수 없음")
        if event.resolved:
            return RepayResult(success=False, event_id=event_id, reason="이미 해소된 부채")

        # 테스트 실행 유형은 실제로 명령 실행
        if repay_id == "TEST_PASS" and run_command:
            import subprocess
            result = subprocess.run(run_command, shell=True, capture_output=True)
            if result.returncode != 0:
                return RepayResult(
                    success=False,
                    event_id=event_id,
                    reason=f"테스트 실패: {result.stderr.decode()[:200]}"
                )
            session.record_action("test")

        repay_rule = self._rules.get_repay_rule(repay_id)
        if repay_rule is None:
            return RepayResult(success=False, event_id=event_id, reason="알 수 없는 상환 유형")

        reduction = min(repay_rule.score_reduction, session.debt_score)
        session.debt_score -= reduction
        event.resolve(evidence, EvidenceType(repay_id.lower().split("_")[0]))

        self._registry.update_event(event)
        self._registry.save_session(session)

        return RepayResult(
            success=True,
            event_id=event_id,
            reduced_by=reduction,
            new_score=session.debt_score,
        )

    # ── 판정 ────────────────────────────────────────────────────────────────

    def get_verdict(self, session: Session) -> VerdictResult:
        # 1. force_verdict 우선 체크 (DESTRUCTIVE_CMD 등)
        forced = self._check_forced_verdict(session)
        if forced:
            return forced

        # 2. 콤보 규칙 체크
        combo = self._check_combo_rules(session)
        if combo:
            return combo

        # 3. 점수 기반 판정
        t = self._rules.thresholds
        score = session.debt_score
        if score <= t.allow:
            verdict = Verdict.ALLOW
        elif score <= t.evidence_required:
            verdict = Verdict.EVIDENCE_REQUIRED
        elif score <= t.approval_required:
            verdict = Verdict.APPROVAL_REQUIRED
        else:
            verdict = Verdict.BLOCK

        session.verdict = verdict
        self._registry.save_session(session)

        blocking_ids = self._get_blocking_event_ids(session, verdict)
        return VerdictResult(
            verdict=verdict,
            score=score,
            reason=self._verdict_reason(verdict, score),
            blocking_ids=blocking_ids,
            suggestions=self._build_suggestions(blocking_ids),
        )

    # ── 내부 헬퍼 ───────────────────────────────────────────────────────────

    def _make_event(self, c: ClassifiedDebt, session: Session, source: str, **kwargs) -> DebtEvent:
        return DebtEvent(
            session_id=session.id,
            rule_id=c.rule_id,
            claim=c.claim,
            risk_level=c.risk_level,
            score=c.score,
            source=source,
            **kwargs,
        )

    def _check_forced_verdict(self, session: Session) -> VerdictResult | None:
        events = self._registry.get_session_events(session.id, unresolved_only=False)
        for event in events:
            if not event.resolved and event.rule_id == "DESTRUCTIVE_CMD":
                return VerdictResult(
                    verdict=Verdict.BLOCK,
                    score=session.debt_score,
                    reason="파괴적 명령 감지: 상환 불가, --force 필요",
                    blocking_ids=[event.id],
                )
        return None

    def _check_combo_rules(self, session: Session) -> VerdictResult | None:
        active_rule_ids = {
            e.rule_id for e in self._registry.get_session_events(session.id, unresolved_only=True)
        }
        for combo in self._rules.combo_rules:
            if all(cond in active_rule_ids for cond in combo.conditions):
                return VerdictResult(
                    verdict=Verdict(combo.force_verdict),
                    score=session.debt_score,
                    reason=combo.description,
                )
        return None

    def _get_blocking_event_ids(self, session: Session, verdict: Verdict) -> list[str]:
        if verdict == Verdict.ALLOW:
            return []
        events = self._registry.get_session_events(session.id, unresolved_only=True)
        risk_filter = {
            Verdict.EVIDENCE_REQUIRED: {RiskLevel.HIGH, RiskLevel.MEDIUM},
            Verdict.APPROVAL_REQUIRED: {RiskLevel.HIGH},
            Verdict.BLOCK:             {RiskLevel.HIGH},
        }.get(verdict, set())
        return [e.id for e in events if e.risk_level in risk_filter]

    def _build_suggestions(self, blocking_ids: list[str]) -> list[str]:
        return [
            f"debt repay {eid} --test \"pytest tests/\"" for eid in blocking_ids[:3]
        ]

    @staticmethod
    def _verdict_reason(verdict: Verdict, score: int) -> str:
        reasons = {
            Verdict.ALLOW:             f"부채 없음 (점수: {score})",
            Verdict.EVIDENCE_REQUIRED: f"증거 제출 권장 (점수: {score})",
            Verdict.APPROVAL_REQUIRED: f"승인 필요 (점수: {score})",
            Verdict.BLOCK:             f"차단 (점수: {score})",
        }
        return reasons[verdict]
```

---

## 7. 레지스트리 (`app/registry.py`)

```python
from __future__ import annotations

import json
from pathlib import Path

from .models import DebtEvent, Registry, Session


EDC_DIR     = Path(".edc")
DEBT_FILE   = EDC_DIR / "debt.json"
CONFIG_FILE = EDC_DIR / "config.json"


class DebtRegistry:
    """
    .edc/debt.json 파일을 유일한 진실 원본으로 관리한다.
    멀티 에이전트 확장 시 이 클래스만 SQLite/Redis 백엔드로 교체하면 된다.
    """

    def __init__(self, edc_dir: Path = EDC_DIR) -> None:
        self._path = edc_dir / "debt.json"
        self._data: Registry = self._load()

    # ── 초기화 ──────────────────────────────────────────────────────────────

    @staticmethod
    def init(edc_dir: Path = EDC_DIR) -> None:
        edc_dir.mkdir(exist_ok=True)
        debt_file = edc_dir / "debt.json"
        if not debt_file.exists():
            debt_file.write_text(Registry().model_dump_json(indent=2))

    # ── 세션 ────────────────────────────────────────────────────────────────

    def create_session(self, project_root: str) -> Session:
        session = Session(project_root=project_root)
        self._data.sessions[session.id] = session
        self._data.current_session_id = session.id
        self._save()
        return session

    def current_session(self) -> Session | None:
        sid = self._data.current_session_id
        return self._data.sessions.get(sid) if sid else None

    def save_session(self, session: Session) -> None:
        self._data.sessions[session.id] = session
        self._save()

    # ── 이벤트 ──────────────────────────────────────────────────────────────

    def add_event(self, event: DebtEvent) -> None:
        self._data.events[event.id] = event
        self._save()

    def get_event(self, event_id: str) -> DebtEvent | None:
        return self._data.events.get(event_id)

    def update_event(self, event: DebtEvent) -> None:
        self._data.events[event.id] = event
        self._save()

    def get_session_events(
        self,
        session_id: str,
        unresolved_only: bool = True,
    ) -> list[DebtEvent]:
        session = self._data.sessions.get(session_id)
        if not session:
            return []
        events = [
            self._data.events[eid]
            for eid in session.event_ids
            if eid in self._data.events
        ]
        if unresolved_only:
            events = [e for e in events if not e.resolved]
        return events

    def count_edits_by_target(self, session_id: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for event in self.get_session_events(session_id, unresolved_only=False):
            if event.target_path:
                counts[event.target_path] = counts.get(event.target_path, 0) + 1
        return counts

    # ── IO ──────────────────────────────────────────────────────────────────

    def _load(self) -> Registry:
        if not self._path.exists():
            return Registry()
        return Registry.model_validate_json(self._path.read_text())

    def _save(self) -> None:
        self._path.write_text(self._data.model_dump_json(indent=2))
```

---

## 8. 포맷터 (`app/formatters.py`)

```python
from __future__ import annotations

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .models import DebtEvent, RiskLevel, Session, Verdict, VerdictResult

console = Console()


RISK_COLOR = {
    RiskLevel.HIGH:   "red",
    RiskLevel.MEDIUM: "yellow",
    RiskLevel.LOW:    "dim",
}

VERDICT_COLOR = {
    Verdict.ALLOW:             "green",
    Verdict.EVIDENCE_REQUIRED: "yellow",
    Verdict.APPROVAL_REQUIRED: "orange3",
    Verdict.BLOCK:             "red",
}

VERDICT_ICON = {
    Verdict.ALLOW:             "✓",
    Verdict.EVIDENCE_REQUIRED: "⚠",
    Verdict.APPROVAL_REQUIRED: "⛔",
    Verdict.BLOCK:             "✗",
}


class ConsoleFormatter:

    # ── 감지 알림 (watch 중 인라인) ──────────────────────────────────────────

    @staticmethod
    def detection_alert(event: DebtEvent) -> None:
        color = RISK_COLOR[event.risk_level]
        console.print(f"\n[{color}]⚠  인지부채 감지됨[/{color}]")
        console.print(f"   [dim]ID[/dim]      {event.id}")
        console.print(f"   [dim]클레임[/dim]  {event.claim[:80]}")
        console.print(f"   [dim]리스크[/dim]  [{color}]{event.risk_level.value}[/{color}]")
        console.print(f"   [dim]상태[/dim]    미해소\n")

    # ── 부채 목록 (ls) ────────────────────────────────────────────────────────

    @staticmethod
    def debt_list(events: list[DebtEvent]) -> None:
        if not events:
            console.print("\n[green]미해소 인지부채  없음 ✓[/green]")
            console.print("[dim]에이전트가 근거 있게 행동하고 있습니다.[/dim]\n")
            return

        table = Table(box=box.SIMPLE, show_header=True, header_style="bold")
        table.add_column("ID",      style="dim",  width=10)
        table.add_column("리스크",  width=8)
        table.add_column("클레임",  width=50)
        table.add_column("상태",    width=8)

        for e in events:
            color = RISK_COLOR[e.risk_level]
            table.add_row(
                e.id,
                f"[{color}]{e.risk_level.value}[/{color}]",
                e.claim[:48] + ("…" if len(e.claim) > 48 else ""),
                "[dim]미해소[/dim]",
            )

        console.print(f"\n[bold]미해소 인지부채  {len(events)}건[/bold]")
        console.print(table)

        high_count = sum(1 for e in events if e.risk_level == RiskLevel.HIGH)
        if high_count:
            console.print(f"[red]HIGH 부채가 있어 다음 파일 수정이 차단됩니다.[/red]")
            console.print(f"[dim]`debt repay <id>` 로 증거를 제출하세요.[/dim]\n")

    # ── 판정 결과 (judge) ─────────────────────────────────────────────────────

    @staticmethod
    def verdict_result(result: VerdictResult) -> None:
        color = VERDICT_COLOR[result.verdict]
        icon  = VERDICT_ICON[result.verdict]

        title = Text(f"판정: {result.verdict.value}  {icon}", style=f"bold {color}")
        body_lines = [result.reason]

        if result.blocking_ids:
            body_lines.append("")
            for bid in result.blocking_ids:
                body_lines.append(f"  [dim]차단 원인:[/dim] {bid}")

        if result.suggestions:
            body_lines.append("")
            body_lines.append("[dim]상환 방법:[/dim]")
            for s in result.suggestions:
                body_lines.append(f"  {s}")

        panel = Panel(
            "\n".join(body_lines),
            title=title,
            border_style=color,
            padding=(0, 2),
        )
        console.print(panel)

    # ── 상환 결과 (repay) ─────────────────────────────────────────────────────

    @staticmethod
    def repay_result(result) -> None:
        if result.success:
            console.print(f"\n[green]✓  인지부채 해소됨[/green]")
            console.print(f"   [dim]ID[/dim]        {result.event_id}")
            console.print(f"   [dim]점수 감소[/dim]  -{result.reduced_by}")
            console.print(f"   [dim]현재 점수[/dim]  {result.new_score}\n")
        else:
            console.print(f"\n[red]✗  해소 실패:[/red] {result.reason}\n")

    # ── 세션 리포트 ───────────────────────────────────────────────────────────

    @staticmethod
    def session_report(session: Session, events: list[DebtEvent]) -> None:
        resolved   = [e for e in events if e.resolved]
        unresolved = [e for e in events if not e.resolved]
        total      = len(events)
        rate       = int(len(resolved) / total * 100) if total else 100

        console.print(f"\n[bold]세션 리포트[/bold]  {session.id}")
        console.print(f"시작: {session.started_at.strftime('%Y-%m-%d %H:%M')}")
        console.print("─" * 50)
        console.print(f"총 인지부채   {total}건")
        console.print(f"  [green]해소됨[/green]    {len(resolved)}건")
        console.print(f"  [red]미해소[/red]    {len(unresolved)}건")
        console.print(f"부채 상환율   {rate}%")
        console.print("─" * 50 + "\n")
```

---

## 9. CLI 진입점 (`app/main.py`)

```python
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from .engine import RuleEngine
from .formatters import ConsoleFormatter
from .parsers import ActionClassifier, RuleBasedClassifier
from .registry import DebtRegistry, EDC_DIR
from .rules import Rules

app = typer.Typer(
    name="debt",
    help="Epistemic Debt Compiler — 근거 없는 에이전트 행동을 차단한다.",
    no_args_is_help=True,
)
console = Console()
fmt     = ConsoleFormatter()


def _load_engine() -> tuple[RuleEngine, DebtRegistry]:
    rules      = Rules.load(Path("rules.json"))
    registry   = DebtRegistry()
    classifier = RuleBasedClassifier(rules)
    action_cls = ActionClassifier(rules)
    engine     = RuleEngine(rules, classifier, action_cls, registry)
    return engine, registry


# ── debt init ────────────────────────────────────────────────────────────────

@app.command()
def init():
    """프로젝트에 .edc/ 초기화 및 Claude Code hook 등록."""
    DebtRegistry.init()
    console.print("[green]✓[/green] .edc/ 초기화 완료")
    _register_hooks()
    console.print("[green]✓[/green] Claude Code hook 등록 완료")


# ── debt watch ───────────────────────────────────────────────────────────────

@app.command()
def watch(
    file:    Optional[Path] = typer.Option(None, "--file", "-f"),
    dry_run: bool           = typer.Option(False, "--dry-run"),
    quiet:   bool           = typer.Option(False, "--quiet", "-q"),
    session_name: Optional[str] = typer.Option(None, "--session", "-s"),
):
    """에이전트 출력을 감시하여 인지부채를 자동 등록한다. (파이프 모드 지원)"""
    engine, registry = _load_engine()
    session = registry.current_session() or registry.create_session(str(Path.cwd()))

    source = open(file) if file else sys.stdin

    for line in source:
        if not quiet:
            console.print(line, end="")

        events = [] if dry_run else engine.process_text(line, session)
        for event in events:
            fmt.detection_alert(event)

    if source is not sys.stdin:
        source.close()


# ── debt ls ──────────────────────────────────────────────────────────────────

@app.command(name="ls")
def list_debts(
    risk:       Optional[str] = typer.Option(None, "--risk"),
    show_all:   bool          = typer.Option(False, "--all", "-a"),
    json_output: bool         = typer.Option(False, "--json"),
):
    """현재 미해소 인지부채 목록을 출력한다."""
    _, registry = _load_engine()
    session = registry.current_session()
    if not session:
        console.print("[dim]세션 없음. `debt init` 을 실행하세요.[/dim]")
        raise typer.Exit(0)

    events = registry.get_session_events(session.id, unresolved_only=not show_all)
    if risk:
        events = [e for e in events if e.risk_level.value == risk.upper()]

    if json_output:
        import json
        console.print(json.dumps([e.model_dump(mode="json") for e in events], indent=2))
    else:
        fmt.debt_list(events)


# ── debt repay ───────────────────────────────────────────────────────────────

@app.command()
def repay(
    event_id: str                  = typer.Argument(..., metavar="ID"),
    test:     Optional[str]        = typer.Option(None, "--test"),
    code:     Optional[str]        = typer.Option(None, "--code"),
    doc:      Optional[str]        = typer.Option(None, "--doc"),
    log:      Optional[str]        = typer.Option(None, "--log"),
    manual:   Optional[str]        = typer.Option(None, "--manual"),
):
    """증거를 제출하여 인지부채를 상환한다."""
    engine, registry = _load_engine()
    session = registry.current_session()
    if not session:
        console.print("[red]오류:[/red] 세션 없음")
        raise typer.Exit(1)

    repay_id, evidence, run_cmd = _resolve_repay_args(test, code, doc, log, manual)
    if not repay_id:
        console.print("[red]오류:[/red] 상환 유형을 지정하세요 (--test, --code, --doc, --log, --manual)")
        raise typer.Exit(1)

    result = engine.process_repayment(event_id, repay_id, evidence, session, run_command=run_cmd)
    fmt.repay_result(result)
    raise typer.Exit(0 if result.success else 1)


# ── debt judge ───────────────────────────────────────────────────────────────

@app.command()
def judge(
    tool:   Optional[str] = typer.Option(None, "--tool"),
    target: Optional[str] = typer.Option(None, "--target"),
    strict: bool          = typer.Option(False, "--strict"),
    force:  bool          = typer.Option(False, "--force"),
):
    """현재 인지부채 상태를 판정한다. hook/CI 연동 시 exit code가 핵심."""
    engine, registry = _load_engine()
    session = registry.current_session()
    if not session:
        raise typer.Exit(2)  # 초기화 안됨

    if tool:
        engine.process_action(tool, target or "", session=session)

    result = engine.get_verdict(session)

    if force and result.verdict.blocks:
        session.force_overrides += 1
        registry.save_session(session)
        if not strict:
            fmt.verdict_result(result)
            console.print("[yellow]⚠  강제 진행 (기록됨)[/yellow]")
        raise typer.Exit(0)

    if not strict:
        fmt.verdict_result(result)

    raise typer.Exit(result.verdict.exit_code)


# ── debt explain ─────────────────────────────────────────────────────────────

@app.command()
def explain(
    event_id: str = typer.Argument(..., metavar="ID"),
):
    """특정 인지부채의 상세 설명과 상환 가이드를 출력한다."""
    _, registry = _load_engine()
    event = registry.get_event(event_id)
    if not event:
        console.print(f"[red]오류:[/red] '{event_id}' 를 찾을 수 없습니다.")
        raise typer.Exit(1)

    console.print(f"\n[bold]인지부채  {event.id}[/bold]")
    console.print("─" * 60)
    console.print(f"클레임    {event.claim}")
    console.print(f"리스크    {event.risk_level.value}")
    console.print(f"등록      {event.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
    console.print(f"상태      {'해소됨' if event.resolved else '미해소'}")

    if not event.resolved:
        console.print("\n[bold]상환 방법[/bold]")
        console.print(f"  1. debt repay {event.id} --test \"pytest tests/\"")
        console.print(f"  2. debt repay {event.id} --code \"<파일>:<줄>\"")
        console.print(f"  3. debt repay {event.id} --manual \"직접 확인\"")
    console.print()


# ── 내부 헬퍼 ────────────────────────────────────────────────────────────────

def _resolve_repay_args(test, code, doc, log, manual):
    if test:   return "TEST_PASS",    test,   test
    if code:   return "GREP_EVIDENCE", code,  None
    if doc:    return "DOC_REFERENCE", doc,   None
    if log:    return "LOG_EVIDENCE",  log,   None
    if manual: return "MANUAL_CONFIRM", manual, None
    return None, None, None


def _register_hooks():
    """Claude Code settings.json에 PreToolUse hook 자동 등록."""
    import json
    settings_path = Path(".claude/settings.json")
    settings_path.parent.mkdir(exist_ok=True)
    settings = json.loads(settings_path.read_text()) if settings_path.exists() else {}

    hook = {"type": "command", "command": "debt judge --tool $TOOL_NAME --strict"}
    settings.setdefault("hooks", {}).setdefault("PreToolUse", [])
    if not any(h.get("command", "").startswith("debt judge") for h in settings["hooks"]["PreToolUse"]):
        settings["hooks"]["PreToolUse"].append({"matcher": "Edit|Write|Bash", "hooks": [hook]})
        settings_path.write_text(json.dumps(settings, indent=2))
```

---

## 10. Hook 어댑터 (`app/hooks.py`)

```python
"""
Claude Code / CMUX hook stdin 입력 파싱.

Claude Code가 hook을 실행할 때 stdin으로 JSON을 전달한다:
{"tool_name": "Edit", "tool_input": {"file_path": "src/auth.py", ...}}

이 모듈은 그 JSON을 engine.process_action()의 인자로 변환한다.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass


@dataclass
class HookInput:
    tool_name: str
    target:    str
    command:   str


def parse_hook_stdin() -> HookInput | None:
    """stdin에서 Claude Code hook JSON을 읽어 파싱한다."""
    if sys.stdin.isatty():
        return None
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return None

    tool = data.get("tool_name", "")
    inp  = data.get("tool_input", {})

    return HookInput(
        tool_name=tool,
        target=inp.get("file_path") or inp.get("path") or "",
        command=inp.get("command") or "",
    )


# ── 확장 포인트: CMUX Agent 연동 ─────────────────────────────────────────────

class AgentHookAdapter:
    """
    CMUX 또는 다른 멀티 에이전트 오케스트레이터 연동.

    에이전트별로 독립 세션을 생성하고,
    에이전트 ID를 session metadata에 포함시킨다.

    Phase 2 구현 시 이 클래스를 채운다.
    현재는 인터페이스만 정의.
    """

    def receive(self, agent_id: str, payload: dict) -> dict:
        """에이전트로부터 이벤트를 수신한다."""
        raise NotImplementedError

    def broadcast_block(self, agent_id: str, verdict) -> None:
        """차단 판정을 오케스트레이터에 전파한다."""
        raise NotImplementedError
```

---

## 11. 확장 포인트 요약

| 포인트 | 현재 MVP | Phase 2 확장 |
|---|---|---|
| **Classifier** | `RuleBasedClassifier` (정규식) | `LLMClassifier` 교체 (Classifier Protocol 구현만 하면 됨) |
| **DebtRegistry** | `.edc/debt.json` 파일 | `SQLiteRegistry` 또는 `RedisRegistry` (동일 인터페이스) |
| **AgentHookAdapter** | Claude Code stdin hook | CMUX 에이전트별 세션 분리, 차단 전파 |
| **VerdictResult** | exit code 기반 | webhook, Slack 알림, PR comment 연동 |
| **Rules** | `rules.json` 로컬 파일 | 원격 규칙 서버, 팀별 규칙 공유 |

---

## 12. `pyproject.toml`

```toml
[project]
name = "epistemic-debt-compiler"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "typer[all]>=0.12",
    "rich>=13",
    "pydantic>=2",
]

[project.scripts]
debt = "app.main:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

---

## 의존성 흐름

```
main.py (CLI)
  │
  ├── rules.py          (Rules 로드)
  ├── registry.py       (DebtRegistry IO)
  ├── parsers.py        (Classifier / ActionClassifier)
  ├── engine.py         (RuleEngine — 순수 로직)
  ├── formatters.py     (ConsoleFormatter — 출력 전담)
  └── hooks.py          (HookInput 파싱 / 에이전트 어댑터)

models.py ← 모든 레이어가 참조, 역방향 의존 없음
```
