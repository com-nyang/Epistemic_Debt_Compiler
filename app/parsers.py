"""
텍스트와 액션을 분석해서 ClassifiedDebt를 반환하는 분류기 레이어.

Classifier Protocol을 구현하면 LLM 기반 분류기로 교체 가능하다.
MVP는 정규식 기반 RuleBasedClassifier를 사용한다.
"""
from __future__ import annotations

import re
from typing import Protocol, runtime_checkable

from .models import ClassifiedDebt, RiskLevel, Verdict
from .rules import ActionRule, Rules, TextRule


# ── Classifier 인터페이스 ─────────────────────────────────────────────────────

@runtime_checkable
class Classifier(Protocol):
    """
    텍스트에서 인지부채 후보를 감지해 반환하는 인터페이스.

    LLM 기반 분류기로 교체하려면 이 Protocol을 구현하면 된다:
        class LLMClassifier:
            def classify(self, text: str) -> list[ClassifiedDebt]: ...
    """
    def classify(self, text: str) -> list[ClassifiedDebt]: ...


# ── 규칙 기반 분류기 (MVP 기본값) ─────────────────────────────────────────────

class RuleBasedClassifier:
    """
    rules.json의 정규식 패턴으로 텍스트를 분류한다.
    같은 규칙은 한 텍스트당 최대 1회만 감지한다.
    """

    def __init__(self, rules: Rules) -> None:
        self._rules = rules.get_text_rules()

    def classify(self, text: str) -> list[ClassifiedDebt]:
        """
        텍스트를 분석하여 인지부채를 분류한다.
        문장별로 가장 점수가 높은 규칙 하나만 적용하여 중복 감지를 방지한다.
        """
        # 1. 텍스트를 문장 단위로 분리 (간단한 구현)
        sentences = re.split(r"[.!?,;\n]", text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 5]
        
        results: list[ClassifiedDebt] = []
        processed_sentences: set[str] = set()

        for sentence in sentences:
            if sentence in processed_sentences:
                continue

            best_match: ClassifiedDebt | None = None
            
            for rule in self._rules:
                if self._sentence_matches_rule(sentence, rule):
                    candidate = ClassifiedDebt(
                        rule_id=rule.id,
                        claim=sentence,
                        score=rule.score,
                        risk_level=RiskLevel(rule.risk_level),
                        force_verdict=Verdict(rule.force_verdict) if rule.force_verdict else None,
                    )
                    
                    # 가장 높은 점수의 규칙을 선택
                    if best_match is None or candidate.score > best_match.score:
                        best_match = candidate

            if best_match:
                results.append(best_match)
                processed_sentences.add(sentence)

        return results

    def _sentence_matches_rule(self, sentence: str, rule: TextRule) -> bool:
        """문장이 규칙의 패턴 중 하나라도 매치되는지 확인."""
        for patterns in rule.patterns.values():
            for pattern in patterns:
                if re.search(pattern, sentence, re.IGNORECASE):
                    return True
        return False

    @staticmethod
    def _extract_sentence(text: str, match_pos: int) -> str | None:
        """매칭 위치 기준으로 가장 가까운 문장을 잘라서 반환한다."""
        # 이전 문장 끝(.!?) 이후부터 시작
        start = 0
        for sep in (".", "!", "?", "\n"):
            idx = text.rfind(sep, 0, match_pos)
            if idx != -1:
                start = max(start, idx + 1)

        # 다음 문장 끝까지
        end = len(text)
        for sep in (".", "!", "?", "\n"):
            idx = text.find(sep, match_pos)
            if idx != -1:
                end = min(end, idx + 1)

        sentence = text[start:end].strip()
        sentence = re.sub(r"^(?:[-*]\s+|\d+\.\s+)", "", sentence).strip()

        # 잘린 markdown 조각은 오탐이 많으므로 버린다.
        if sentence.count("`") % 2 == 1:
            return None

        plain = re.sub(r"[`\W_]+", "", sentence, flags=re.UNICODE)
        if len(plain) < 6:
            return None

        return sentence


# ── 액션 분류기 ───────────────────────────────────────────────────────────────

class ActionClassifier:
    """
    도구 호출(tool use) 자체를 분석해서 인지부채를 감지한다.
    텍스트가 아닌 에이전트의 '행동'을 기준으로 판단한다.
    """

    def __init__(self, rules: Rules) -> None:
        self._rules = rules.get_action_rules()

    def classify(
        self,
        tool:           str,
        target:         str,
        command:        str,
        action_history: list[str],
        edit_counts:    dict[str, int],
    ) -> list[ClassifiedDebt]:
        results: list[ClassifiedDebt] = []

        for rule in self._rules:
            if tool not in rule.trigger:
                continue
            if not self._check_condition(rule, tool, target, command, action_history, edit_counts):
                continue

            results.append(ClassifiedDebt(
                rule_id=rule.id,
                claim=self._describe(rule, tool, target, command),
                score=rule.score,
                risk_level=RiskLevel(rule.risk_level),
                force_verdict=Verdict(rule.force_verdict) if rule.force_verdict else None,
            ))

        return results

    def _check_condition(
        self,
        rule:           ActionRule,
        tool:           str,
        target:         str,
        command:        str,
        action_history: list[str],
        edit_counts:    dict[str, int],
    ) -> bool:
        c = rule.condition

        if c == "no_test_run_in_session":
            # 세션 내 테스트 실행 기록이 없으면 True
            return not any(a in ("test", "pytest", "jest", "npm test") for a in action_history)

        if c == "target_matches_risk_patterns":
            return any(
                re.search(p, target, re.IGNORECASE)
                for p in rule.risk_patterns
            )

        if c == "command_matches_destructive_patterns":
            return any(p in command for p in rule.destructive_patterns)

        if c == "same_file_count_gte_3":
            return edit_counts.get(target, 0) >= 3

        return False

    @staticmethod
    def _describe(rule: ActionRule, tool: str, target: str, command: str) -> str:
        """감지된 행동을 사람이 읽기 좋은 문장으로 설명한다."""
        descriptions = {
            "EDIT_NO_TEST":    f"테스트 실행 없이 파일 수정: {target}",
            "HIGH_RISK_FILE":  f"고위험 파일 접근: {target}",
            "DESTRUCTIVE_CMD": f"파괴적 명령 실행: {command[:60]}",
            "SECURITY_RISK_CMD": f"보안 위협 명령 실행: {command[:60]}",
            "RETRY_SAME_FIX":  f"동일 파일 반복 수정 (3회 이상): {target}",
        }
        return descriptions.get(rule.id, f"{tool} → {target or command}")
