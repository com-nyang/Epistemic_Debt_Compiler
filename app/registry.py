"""
.edc/debt.json 파일을 유일한 진실 원본으로 관리하는 레지스트리.

멀티 에이전트 확장 시 이 클래스만 SQLite/Redis 백엔드로 교체하면 된다.
현재 MVP는 단일 JSON 파일을 사용한다.
"""
from __future__ import annotations

from pathlib import Path

from .models import DebtItem, Registry, RiskLevel, Session


EDC_DIR   = Path(".edc")
DEBT_FILE = EDC_DIR / "debt.json"


class DebtRegistry:

    def __init__(self, edc_dir: Path = EDC_DIR) -> None:
        self._path = edc_dir / "debt.json"
        self._data = self._load()

    # ── 초기화 ──────────────────────────────────────────────────────────────

    @staticmethod
    def init(edc_dir: Path = EDC_DIR) -> None:
        """프로젝트에 .edc/ 디렉토리와 빈 레지스트리 파일을 생성한다."""
        edc_dir.mkdir(exist_ok=True)
        debt_file = edc_dir / "debt.json"
        if not debt_file.exists():
            debt_file.write_text(Registry().model_dump_json(indent=2), encoding="utf-8")

    @staticmethod
    def is_initialized(edc_dir: Path = EDC_DIR) -> bool:
        return (edc_dir / "debt.json").exists()

    # ── 세션 관리 ────────────────────────────────────────────────────────────

    def create_session(self, project_root: str) -> Session:
        session = Session(project_root=project_root)
        self._data.sessions[session.id] = session
        self._data.current_session_id   = session.id
        self._save()
        return session

    def current_session(self) -> Session | None:
        sid = self._data.current_session_id
        return self._data.sessions.get(sid) if sid else None

    def get_session(self, session_id: str) -> Session | None:
        return self._data.sessions.get(session_id)

    def save_session(self, session: Session) -> None:
        self._data.sessions[session.id] = session
        self._save()

    # ── 이벤트 관리 ─────────────────────────────────────────────────────────

    def add_event(self, event: DebtItem) -> None:
        self._data.events[event.id] = event
        self._save()

    def get_event(self, event_id: str) -> DebtItem | None:
        return self._data.events.get(event_id)

    def update_event(self, event: DebtItem) -> None:
        self._data.events[event.id] = event
        self._save()

    def get_session_events(
        self,
        session_id:      str,
        unresolved_only: bool = True,
        risk_filter:     RiskLevel | None = None,
    ) -> list[DebtItem]:
        """세션의 이벤트 목록을 반환한다. 필터 조건 적용 가능."""
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

        if risk_filter:
            events = [e for e in events if e.risk_level == risk_filter]

        return events

    def count_edits_by_target(self, session_id: str) -> dict[str, int]:
        """파일별 수정 횟수를 반환한다. RETRY_SAME_FIX 감지에 사용."""
        counts: dict[str, int] = {}
        for event in self.get_session_events(session_id, unresolved_only=False):
            if event.source == "action" and event.target_path:
                counts[event.target_path] = counts.get(event.target_path, 0) + 1
        return counts

    def get_all_events(self) -> list[DebtItem]:
        return list(self._data.events.values())

    # ── IO ──────────────────────────────────────────────────────────────────

    def _load(self) -> Registry:
        if not self._path.exists():
            return Registry()
        try:
            return Registry.model_validate_json(self._path.read_text(encoding="utf-8"))
        except Exception:
            return Registry()

    def _save(self) -> None:
        self._path.parent.mkdir(exist_ok=True)
        self._path.write_text(self._data.model_dump_json(indent=2), encoding="utf-8")
