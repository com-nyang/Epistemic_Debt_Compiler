"""
registry.py 단위 테스트.
DebtRegistry의 세션/이벤트 관리와 파일 영속성을 검증한다.
"""
import json
from pathlib import Path

import pytest

from app.models import DebtItem, RiskLevel
from app.registry import DebtRegistry


# ── 초기화 ───────────────────────────────────────────────────────────────────

class TestInit:

    def test_init_creates_directory(self, tmp_path):
        edc = tmp_path / ".edc"
        DebtRegistry.init(edc)
        assert edc.is_dir()

    def test_init_creates_debt_json(self, tmp_path):
        edc = tmp_path / ".edc"
        DebtRegistry.init(edc)
        assert (edc / "debt.json").exists()

    def test_init_file_is_valid_json(self, tmp_path):
        edc = tmp_path / ".edc"
        DebtRegistry.init(edc)
        data = json.loads((edc / "debt.json").read_text())
        assert "events" in data
        assert "sessions" in data

    def test_init_is_idempotent(self, tmp_path):
        edc = tmp_path / ".edc"
        DebtRegistry.init(edc)
        DebtRegistry.init(edc)  # 두 번 호출해도 문제없어야 한다
        assert (edc / "debt.json").exists()

    def test_is_initialized_returns_true_after_init(self, tmp_path):
        edc = tmp_path / ".edc"
        DebtRegistry.init(edc)
        assert DebtRegistry.is_initialized(edc) is True

    def test_is_initialized_returns_false_before_init(self, tmp_path):
        edc = tmp_path / ".edc"
        assert DebtRegistry.is_initialized(edc) is False


# ── 세션 관리 ─────────────────────────────────────────────────────────────────

class TestSession:

    def test_create_session_returns_session(self, registry):
        session = registry.create_session("/project")
        assert session.project_root == "/project"

    def test_create_session_sets_as_current(self, registry):
        session = registry.create_session("/project")
        current = registry.current_session()
        assert current.id == session.id

    def test_current_session_is_none_on_empty_registry(self, tmp_path):
        DebtRegistry.init(tmp_path)
        fresh = DebtRegistry(tmp_path)
        assert fresh.current_session() is None

    def test_session_is_persisted_on_disk(self, tmp_path):
        DebtRegistry.init(tmp_path)
        reg = DebtRegistry(tmp_path)
        session = reg.create_session("/project")

        reloaded = DebtRegistry(tmp_path)
        stored = reloaded.get_session(session.id)
        assert stored is not None
        assert stored.project_root == "/project"

    def test_save_session_updates_persisted_state(self, tmp_path):
        DebtRegistry.init(tmp_path)
        reg = DebtRegistry(tmp_path)
        session = reg.create_session("/project")
        session.debt_score = 42
        reg.save_session(session)

        reloaded = DebtRegistry(tmp_path)
        stored = reloaded.get_session(session.id)
        assert stored.debt_score == 42

    def test_multiple_sessions_can_coexist(self, tmp_path):
        DebtRegistry.init(tmp_path)
        reg = DebtRegistry(tmp_path)
        s1 = reg.create_session("/project-a")
        s2 = reg.create_session("/project-b")
        assert reg.get_session(s1.id) is not None
        assert reg.get_session(s2.id) is not None
        assert s1.id != s2.id


# ── 이벤트 관리 ───────────────────────────────────────────────────────────────

def _make_event(session_id: str, rule_id: str = "HEDGE_STRONG",
                risk_level: RiskLevel = RiskLevel.MEDIUM, score: int = 10) -> DebtItem:
    return DebtItem(
        session_id=session_id,
        rule_id=rule_id,
        claim="테스트 클레임",
        risk_level=risk_level,
        score=score,
        source="text",
    )


class TestEvents:

    def test_add_and_get_event(self, registry, session):
        event = _make_event(session.id)
        registry.add_event(event)
        stored = registry.get_event(event.id)
        assert stored is not None
        assert stored.rule_id == "HEDGE_STRONG"

    def test_get_event_returns_none_for_unknown_id(self, registry):
        assert registry.get_event("edc-doesnotexist") is None

    def test_event_is_persisted_on_disk(self, tmp_path):
        DebtRegistry.init(tmp_path)
        reg = DebtRegistry(tmp_path)
        session = reg.create_session("/project")
        event = _make_event(session.id)
        reg.add_event(event)

        reloaded = DebtRegistry(tmp_path)
        stored = reloaded.get_event(event.id)
        assert stored is not None

    def test_update_event_persists_resolved_state(self, tmp_path):
        from app.models import EvidenceType
        DebtRegistry.init(tmp_path)
        reg = DebtRegistry(tmp_path)
        session = reg.create_session("/project")
        event = _make_event(session.id)
        reg.add_event(event)

        event.resolve("src/auth.py:42", EvidenceType.CODE)
        reg.update_event(event)

        reloaded = DebtRegistry(tmp_path)
        stored = reloaded.get_event(event.id)
        assert stored.resolved is True
        assert stored.evidence == "src/auth.py:42"


# ── get_session_events 필터 ───────────────────────────────────────────────────

class TestGetSessionEvents:

    def test_returns_all_unresolved_by_default(self, registry, session):
        e1 = _make_event(session.id, rule_id="HEDGE_STRONG")
        e2 = _make_event(session.id, rule_id="ASSUME_FACT")
        registry.add_event(e1)
        registry.add_event(e2)
        session.event_ids = [e1.id, e2.id]
        registry.save_session(session)

        events = registry.get_session_events(session.id)
        assert len(events) == 2

    def test_excludes_resolved_when_unresolved_only_true(self, registry, session):
        from app.models import EvidenceType
        e1 = _make_event(session.id)
        e2 = _make_event(session.id, rule_id="ASSUME_FACT")
        registry.add_event(e1)
        registry.add_event(e2)
        session.event_ids = [e1.id, e2.id]
        registry.save_session(session)

        e1.resolve("proof", EvidenceType.CODE)
        registry.update_event(e1)

        events = registry.get_session_events(session.id, unresolved_only=True)
        assert len(events) == 1
        assert events[0].id == e2.id

    def test_includes_resolved_when_flag_is_false(self, registry, session):
        from app.models import EvidenceType
        e = _make_event(session.id)
        registry.add_event(e)
        session.event_ids = [e.id]
        registry.save_session(session)

        e.resolve("proof", EvidenceType.CODE)
        registry.update_event(e)

        events = registry.get_session_events(session.id, unresolved_only=False)
        assert len(events) == 1

    def test_risk_filter_high_only(self, registry, session):
        e_high   = _make_event(session.id, rule_id="HIGH_RISK_FILE", risk_level=RiskLevel.HIGH)
        e_medium = _make_event(session.id, rule_id="HEDGE_STRONG",   risk_level=RiskLevel.MEDIUM)
        registry.add_event(e_high)
        registry.add_event(e_medium)
        session.event_ids = [e_high.id, e_medium.id]
        registry.save_session(session)

        events = registry.get_session_events(session.id, risk_filter=RiskLevel.HIGH)
        assert all(e.risk_level == RiskLevel.HIGH for e in events)
        assert len(events) == 1

    def test_unknown_session_returns_empty(self, registry):
        events = registry.get_session_events("nonexistent-session-id")
        assert events == []


# ── count_edits_by_target ─────────────────────────────────────────────────────

class TestCountEditsByTarget:

    def test_counts_action_events_by_target_path(self, registry, session):
        for _ in range(3):
            event = DebtItem(
                session_id=session.id,
                rule_id="RETRY_SAME_FIX",
                claim="반복 수정",
                risk_level=RiskLevel.HIGH,
                score=15,
                source="action",
                target_path="src/auth.py",
            )
            registry.add_event(event)
            session.event_ids.append(event.id)
        registry.save_session(session)

        counts = registry.count_edits_by_target(session.id)
        assert counts.get("src/auth.py", 0) == 3

    def test_multiple_files_tracked_separately(self, registry, session):
        for path in ["src/auth.py", "src/config.py", "src/auth.py"]:
            event = DebtItem(
                session_id=session.id,
                rule_id="EDIT_NO_TEST",
                claim="test",
                risk_level=RiskLevel.HIGH,
                score=20,
                source="action",
                target_path=path,
            )
            registry.add_event(event)
            session.event_ids.append(event.id)
        registry.save_session(session)

        counts = registry.count_edits_by_target(session.id)
        assert counts["src/auth.py"] == 2
        assert counts["src/config.py"] == 1

    def test_text_events_not_counted(self, registry, session):
        event = DebtItem(
            session_id=session.id,
            rule_id="HEDGE_STRONG",
            claim="I think...",
            risk_level=RiskLevel.MEDIUM,
            score=10,
            source="text",       # text, not action
        )
        registry.add_event(event)
        session.event_ids.append(event.id)
        registry.save_session(session)

        counts = registry.count_edits_by_target(session.id)
        assert counts == {}
