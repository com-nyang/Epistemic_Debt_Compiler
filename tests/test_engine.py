"""
engine.py 단위 테스트.
RuleEngine의 텍스트 처리, 액션 처리, 상환, 판정 로직을 검증한다.
"""
import pytest

from app.engine import RuleEngine
from app.models import RiskLevel, Verdict


# ── process_text ──────────────────────────────────────────────────────────────

class TestProcessText:

    def test_hedge_strong_creates_debt_item(self, engine, session):
        events = engine.process_text("I think this is the root cause.", session)
        assert len(events) == 1
        assert events[0].rule_id == "HEDGE_STRONG"
        assert events[0].source == "text"

    def test_session_score_increases_after_text(self, engine, session):
        engine.process_text("I think this is the root cause.", session)
        assert session.debt_score == 10

    def test_multiple_rules_from_one_text(self, engine, session):
        # HEDGE_STRONG + ASSUME_FACT 동시 발생
        events = engine.process_text(
            "I think the root cause is the missing config.", session
        )
        rule_ids = {e.rule_id for e in events}
        assert "HEDGE_STRONG" in rule_ids
        assert "ASSUME_FACT" in rule_ids

    def test_clean_text_creates_no_events(self, engine, session):
        events = engine.process_text(
            "Fixed null check in validate_token at line 42.", session
        )
        assert events == []
        assert session.debt_score == 0

    def test_event_is_persisted_in_registry(self, engine, session, registry):
        events = engine.process_text("I think this is the issue.", session)
        assert len(events) == 1
        stored = registry.get_event(events[0].id)
        assert stored is not None
        assert stored.rule_id == "HEDGE_STRONG"

    def test_session_event_ids_updated(self, engine, session):
        events = engine.process_text("I think this is the issue.", session)
        assert events[0].id in session.event_ids


# ── process_action ────────────────────────────────────────────────────────────

class TestProcessAction:

    def test_edit_no_test_fires_without_test_history(self, engine, session):
        events = engine.process_action("Edit", target="src/utils.py", session=session)
        rule_ids = [e.rule_id for e in events]
        assert "EDIT_NO_TEST" in rule_ids

    def test_edit_no_test_skipped_after_test_run(self, engine, session):
        engine.record_test_run(session, exit_code=0)
        events = engine.process_action("Edit", target="src/utils.py", session=session)
        rule_ids = [e.rule_id for e in events]
        assert "EDIT_NO_TEST" not in rule_ids

    def test_high_risk_file_fires_for_auth_file(self, engine, session):
        engine.record_test_run(session, exit_code=0)
        events = engine.process_action(
            "Edit", target="src/middleware/auth.js", session=session
        )
        rule_ids = [e.rule_id for e in events]
        assert "HIGH_RISK_FILE" in rule_ids

    def test_action_recorded_in_history(self, engine, session):
        engine.process_action("Edit", target="src/utils.py", session=session)
        assert "edit" in session.action_history

    def test_destructive_cmd_fires(self, engine, session):
        events = engine.process_action(
            "Bash", command="rm -rf ./dist", session=session
        )
        rule_ids = [e.rule_id for e in events]
        assert "DESTRUCTIVE_CMD" in rule_ids

    def test_safe_bash_creates_no_events(self, engine, session):
        events = engine.process_action(
            "Bash", command="ls -la src/", session=session
        )
        assert events == []


# ── record_test_run ───────────────────────────────────────────────────────────

class TestRecordTestRun:

    def test_passing_test_sets_has_run_tests(self, engine, session):
        engine.record_test_run(session, exit_code=0)
        assert session.has_run_tests() is True

    def test_failing_test_still_sets_has_run_tests(self, engine, session):
        # 실패한 테스트도 조사 행위이므로 기록되어야 한다
        engine.record_test_run(session, exit_code=1)
        assert session.has_run_tests() is True

    def test_record_test_run_does_not_change_score(self, engine, session):
        engine.record_test_run(session, exit_code=0)
        assert session.debt_score == 0


# ── process_repayment ─────────────────────────────────────────────────────────

class TestProcessRepayment:

    def _add_hedge_debt(self, engine, session):
        events = engine.process_text("I think this is the root cause.", session)
        return events[0]

    def test_repayment_success_reduces_score(self, engine, session):
        event = self._add_hedge_debt(engine, session)
        before = session.debt_score
        result = engine.process_repayment(
            event.id, "GREP_EVIDENCE", "src/auth.py:42", session
        )
        assert result.success is True
        assert session.debt_score < before

    def test_repayment_marks_event_resolved(self, engine, session, registry):
        event = self._add_hedge_debt(engine, session)
        engine.process_repayment(event.id, "GREP_EVIDENCE", "src/auth.py:42", session)
        stored = registry.get_event(event.id)
        assert stored.resolved is True

    def test_repayment_returns_reduced_by_and_new_score(self, engine, session):
        event = self._add_hedge_debt(engine, session)
        result = engine.process_repayment(
            event.id, "GREP_EVIDENCE", "src/auth.py:42", session
        )
        assert result.reduced_by > 0
        assert result.new_score == session.debt_score

    def test_repayment_not_found_returns_failure(self, engine, session):
        result = engine.process_repayment(
            "edc-nonexistent", "GREP_EVIDENCE", "proof", session
        )
        assert result.success is False
        assert "찾을 수 없음" in result.reason

    def test_repayment_already_resolved_returns_failure(self, engine, session):
        event = self._add_hedge_debt(engine, session)
        engine.process_repayment(event.id, "GREP_EVIDENCE", "src/auth.py:42", session)
        result = engine.process_repayment(
            event.id, "GREP_EVIDENCE", "src/auth.py:42", session
        )
        assert result.success is False
        assert "이미 해소" in result.reason

    def test_repayment_unknown_repay_id_returns_failure(self, engine, session):
        event = self._add_hedge_debt(engine, session)
        result = engine.process_repayment(
            event.id, "UNKNOWN_RULE", "proof", session
        )
        assert result.success is False

    def test_repayment_test_pass_with_passing_command(self, engine, session):
        event = self._add_hedge_debt(engine, session)
        result = engine.process_repayment(
            event.id, "TEST_PASS", "exit 0", session, run_command="exit 0"
        )
        assert result.success is True

    def test_repayment_test_pass_with_failing_command(self, engine, session):
        event = self._add_hedge_debt(engine, session)
        result = engine.process_repayment(
            event.id, "TEST_PASS", "exit 1", session, run_command="exit 1"
        )
        assert result.success is False
        assert "테스트 실패" in result.reason

    def test_score_never_goes_below_zero(self, engine, session):
        event = self._add_hedge_debt(engine, session)
        # score is 10 from HEDGE_STRONG; use a high-reduction rule if available
        engine.process_repayment(event.id, "GREP_EVIDENCE", "proof", session)
        # apply a second repay that would exceed remaining score
        event2 = self._add_hedge_debt(engine, session)
        session.debt_score = 0  # force score to 0
        engine.process_repayment(event2.id, "GREP_EVIDENCE", "proof", session)
        assert session.debt_score >= 0


# ── get_verdict ───────────────────────────────────────────────────────────────

class TestGetVerdict:

    def test_allow_when_score_is_zero(self, engine, session):
        result = engine.get_verdict(session)
        assert result.verdict == Verdict.ALLOW
        assert result.score == 0

    def test_allow_at_threshold(self, engine, session):
        session.debt_score = 20
        result = engine.get_verdict(session)
        assert result.verdict == Verdict.ALLOW

    def test_evidence_required_just_above_allow(self, engine, session):
        session.debt_score = 21
        result = engine.get_verdict(session)
        assert result.verdict == Verdict.EVIDENCE_REQUIRED

    def test_evidence_required_at_threshold(self, engine, session):
        session.debt_score = 40
        result = engine.get_verdict(session)
        assert result.verdict == Verdict.EVIDENCE_REQUIRED

    def test_approval_required_just_above_evidence(self, engine, session):
        session.debt_score = 41
        result = engine.get_verdict(session)
        assert result.verdict == Verdict.APPROVAL_REQUIRED

    def test_approval_required_at_threshold(self, engine, session):
        session.debt_score = 70
        result = engine.get_verdict(session)
        assert result.verdict == Verdict.APPROVAL_REQUIRED

    def test_block_above_threshold(self, engine, session):
        session.debt_score = 71
        result = engine.get_verdict(session)
        assert result.verdict == Verdict.BLOCK

    def test_verdict_result_contains_score(self, engine, session):
        session.debt_score = 35
        result = engine.get_verdict(session)
        assert result.score == 35

    def test_allow_verdict_has_no_blocking_ids(self, engine, session):
        result = engine.get_verdict(session)
        assert result.blocking_ids == []


# ── combo rule ────────────────────────────────────────────────────────────────

class TestComboRules:

    def test_hedge_strong_plus_high_risk_file_triggers_approval_required(
        self, engine, session
    ):
        # HEDGE_STRONG (10점) + HIGH_RISK_FILE (25점) → 콤보 룰 → APPROVAL_REQUIRED
        engine.process_text("I think this is the root cause.", session)
        engine.record_test_run(session, exit_code=0)
        engine.process_action("Edit", target="src/middleware/auth.js", session=session)

        result = engine.get_verdict(session)
        assert result.verdict == Verdict.APPROVAL_REQUIRED

    def test_combo_resolved_when_one_debt_repaid(self, engine, session, registry):
        # 부채 중 하나를 해소하면 콤보 조건이 깨진다
        engine.process_text("I think this is the root cause.", session)
        engine.record_test_run(session, exit_code=0)
        action_events = engine.process_action(
            "Edit", target="src/middleware/auth.js", session=session
        )

        high_risk = next(e for e in action_events if e.rule_id == "HIGH_RISK_FILE")
        engine.process_repayment(
            high_risk.id, "GREP_EVIDENCE", "src/auth.js:47", session
        )

        result = engine.get_verdict(session)
        # 콤보 해제 → 점수 기반 판정으로 되돌아감
        assert result.verdict != Verdict.APPROVAL_REQUIRED or result.score > 40


# ── DESTRUCTIVE_CMD force BLOCK ───────────────────────────────────────────────

class TestForcedVerdict:

    def test_destructive_cmd_forces_block(self, engine, session):
        engine.process_action(
            "Bash", command="rm -rf ./dist", session=session
        )
        result = engine.get_verdict(session)
        assert result.verdict == Verdict.BLOCK

    def test_destructive_cmd_block_is_independent_of_score(self, engine, session):
        # 점수가 낮아도 DESTRUCTIVE_CMD가 있으면 BLOCK
        engine.process_action(
            "Bash", command="rm -rf ./dist", session=session
        )
        session.debt_score = 5  # 낮은 점수로 강제 설정
        result = engine.get_verdict(session)
        assert result.verdict == Verdict.BLOCK

    def test_destructive_cmd_block_has_blocking_id(self, engine, session):
        engine.process_action(
            "Bash", command="rm -rf ./dist", session=session
        )
        result = engine.get_verdict(session)
        assert len(result.blocking_ids) == 1
