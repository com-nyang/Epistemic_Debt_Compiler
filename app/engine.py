"""
Rule Engine 핵심 로직.

설계 원칙:
  - IO 없음 (파일 읽기/쓰기는 registry 담당)
  - 출력 없음 (출력은 formatter 담당)
  - 순수 로직만 → 단위 테스트 가능
"""
from __future__ import annotations

import subprocess

from .models import (
    ClassifiedDebt, DebtItem, EvidenceType,
    RepayResult, RiskLevel, Session, Verdict, VerdictResult,
)
from .parsers import ActionClassifier, Classifier
from .registry import DebtRegistry
from .rules import Rules


class RuleEngine:

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

    def process_text(self, text: str, session: Session) -> list[DebtItem]:
        """에이전트 자연어 출력을 분석해서 인지부채를 등록한다."""
        classified = self._classifier.classify(text)
        events = []
        for c in classified:
            event = self._make_text_event(c, session)
            self._registry.add_event(event)
            session.add_event(event)
            events.append(event)
        self._registry.save_session(session)
        return events

    # ── 액션 처리 ───────────────────────────────────────────────────────────

    def process_action(
        self,
        tool:    str,
        target:  str    = "",
        command: str    = "",
        session: Session = None,
    ) -> list[DebtItem]:
        """도구 호출(Edit/Write/Bash)을 분석해서 인지부채를 등록한다."""
        session.record_action(tool.lower())

        edit_counts = self._registry.count_edits_by_target(session.id)
        classified  = self._action_classifier.classify(
            tool, target, command, session.action_history, edit_counts
        )

        events = []
        for c in classified:
            event = self._make_action_event(c, session, tool, target, command)
            self._registry.add_event(event)
            session.add_event(event)
            events.append(event)
        self._registry.save_session(session)
        return events

    def record_test_run(self, session: Session, exit_code: int) -> None:
        """
        테스트 실행 결과를 세션에 기록한다. EDIT_NO_TEST 감지 조건에 영향.
        실패한 테스트도 "테스트를 실행했다"는 증거이므로 항상 기록한다.
        (실패 테스트로 버그를 재현하는 것은 올바른 접근이다)
        """
        session.record_action("test")
        self._registry.save_session(session)

    # ── 부채 상환 ───────────────────────────────────────────────────────────

    def process_repayment(
        self,
        event_id:    str,
        repay_id:    str,
        evidence:    str,
        session:     Session,
        run_command: str | None = None,
    ) -> RepayResult:
        """증거를 제출해서 인지부채를 상환한다."""
        event = self._registry.get_event(event_id)
        if event is None:
            return RepayResult(success=False, event_id=event_id, reason="부채를 찾을 수 없음")
        if event.resolved:
            return RepayResult(success=False, event_id=event_id, reason="이미 해소된 부채")

        # TEST_PASS: 실제로 명령을 실행해서 exit code 확인
        if repay_id == "TEST_PASS" and run_command:
            result = subprocess.run(
                run_command, shell=True, capture_output=True, text=True
            )
            if result.returncode != 0:
                stderr_preview = result.stderr[:300] if result.stderr else result.stdout[:300]
                return RepayResult(
                    success=False,
                    event_id=event_id,
                    reason=f"테스트 실패 (exit {result.returncode}):\n{stderr_preview}",
                )
            session.record_action("test")

        repay_rule = self._rules.get_repay_rule(repay_id)
        if repay_rule is None:
            return RepayResult(success=False, event_id=event_id, reason=f"알 수 없는 상환 유형: {repay_id}")

        # 점수 감소: 현재 session score를 초과하지 않음
        reduction          = min(repay_rule.score_reduction, session.debt_score)
        session.debt_score -= reduction

        # 증거 타입 파싱: "TEST_PASS" → "test"
        evidence_type_str = repay_id.lower().split("_")[0]
        try:
            ev_type = EvidenceType(evidence_type_str)
        except ValueError:
            ev_type = EvidenceType.MANUAL

        event.resolve(evidence, ev_type)
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
        """현재 세션 상태를 기반으로 판정을 내린다."""

        # 1순위: force_verdict (DESTRUCTIVE_CMD 등)
        forced = self._check_forced_verdict(session)
        if forced:
            return forced

        # 2순위: 콤보 규칙 (HEDGE_STRONG + HIGH_RISK_FILE 동시 발생 등)
        combo = self._check_combo_rules(session)
        if combo:
            return combo

        # 3순위: 점수 기반 판정
        t     = self._rules.thresholds
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

        blocking_ids = self._get_blocking_ids(session, verdict)
        return VerdictResult(
            verdict=verdict,
            score=score,
            reason=self._verdict_reason(verdict, score),
            blocking_ids=blocking_ids,
            suggestions=self._build_suggestions(blocking_ids),
        )

    # ── 내부 헬퍼 ───────────────────────────────────────────────────────────

    def _make_text_event(self, c: ClassifiedDebt, session: Session) -> DebtItem:
        return DebtItem(
            session_id=session.id,
            rule_id=c.rule_id,
            claim=c.claim,
            risk_level=c.risk_level,
            score=c.score,
            source="text",
        )

    def _make_action_event(
        self, c: ClassifiedDebt, session: Session,
        tool: str, target: str, command: str,
    ) -> DebtItem:
        return DebtItem(
            session_id=session.id,
            rule_id=c.rule_id,
            claim=c.claim,
            risk_level=c.risk_level,
            score=c.score,
            source="action",
            tool_name=tool,
            target_path=target or None,
            command=command or None,
        )

    def _check_forced_verdict(self, session: Session) -> VerdictResult | None:
        """force_verdict가 설정된 미해소 이벤트가 있으면 즉시 BLOCK을 반환한다."""
        events = self._registry.get_session_events(session.id, unresolved_only=True)
        for event in events:
            if event.rule_id == "DESTRUCTIVE_CMD":
                return VerdictResult(
                    verdict=Verdict.BLOCK,
                    score=session.debt_score,
                    reason="파괴적 명령 감지 — 상환 불가, --force로만 진행 가능",
                    blocking_ids=[event.id],
                    suggestions=[f"debt judge --force  (강제 진행, 기록됨)"],
                )
        return None

    def _check_combo_rules(self, session: Session) -> VerdictResult | None:
        """콤보 규칙: 복수 규칙이 동시에 활성화된 경우 판정을 강제한다."""
        active_rule_ids = {
            e.rule_id
            for e in self._registry.get_session_events(session.id, unresolved_only=True)
        }
        for combo in self._rules.combo_rules:
            if all(cond in active_rule_ids for cond in combo.conditions):
                return VerdictResult(
                    verdict=Verdict(combo.force_verdict),
                    score=session.debt_score,
                    reason=combo.description,
                )
        return None

    def _get_blocking_ids(self, session: Session, verdict: Verdict) -> list[str]:
        """판정 원인이 된 미해소 이벤트 ID 목록을 반환한다."""
        if verdict == Verdict.ALLOW:
            return []

        # 판정 레벨에 따라 어떤 리스크 레벨이 차단 원인인지 결정
        risk_filter = {
            Verdict.EVIDENCE_REQUIRED: {RiskLevel.HIGH, RiskLevel.MEDIUM},
            Verdict.APPROVAL_REQUIRED: {RiskLevel.HIGH},
            Verdict.BLOCK:             {RiskLevel.HIGH, RiskLevel.MEDIUM},
        }.get(verdict, set())

        events = self._registry.get_session_events(session.id, unresolved_only=True)
        return [e.id for e in events if e.risk_level in risk_filter][:5]  # 최대 5개

    def _build_suggestions(self, blocking_ids: list[str]) -> list[str]:
        """차단된 부채의 상환 명령 예시를 생성한다."""
        suggestions = []
        for eid in blocking_ids[:3]:
            event = self._registry.get_event(eid)
            if not event:
                continue
            if event.rule_id in ("EDIT_NO_TEST", "CLAIM_TEST_PASS"):
                suggestions.append(f"debt repay {eid} --test \"pytest tests/\"")
            elif event.rule_id in ("HEDGE_STRONG", "ASSUME_FACT"):
                suggestions.append(f"debt repay {eid} --code \"<파일>:<줄>\"")
            else:
                suggestions.append(f"debt repay {eid} --manual \"직접 확인\"")
        return suggestions

    @staticmethod
    def _verdict_reason(verdict: Verdict, score: int) -> str:
        return {
            Verdict.ALLOW:             f"인지부채 없음 (점수: {score})",
            Verdict.EVIDENCE_REQUIRED: f"증거 제출 권장 (점수: {score})",
            Verdict.APPROVAL_REQUIRED: f"승인 필요 (점수: {score})",
            Verdict.BLOCK:             f"차단됨 (점수: {score})",
        }[verdict]
