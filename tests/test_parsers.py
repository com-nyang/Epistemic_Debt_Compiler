"""
parsers.py 단위 테스트.
RuleBasedClassifier와 ActionClassifier의 감지 정확도를 검증한다.
"""
import pytest

from app.models import RiskLevel, Verdict
from app.parsers import ActionClassifier, RuleBasedClassifier


# ── RuleBasedClassifier ──────────────────────────────────────────────────────

class TestRuleBasedClassifier:

    # ── HEDGE_WEAK ───────────────────────────────────────────────────────────

    def test_hedge_weak_english_might(self, classifier):
        results = classifier.classify("This might be the root cause.")
        ids = [r.rule_id for r in results]
        assert "HEDGE_WEAK" in ids

    def test_hedge_weak_english_possibly(self, classifier):
        results = classifier.classify("The error is possibly in the config.")
        ids = [r.rule_id for r in results]
        assert "HEDGE_WEAK" in ids

    def test_hedge_weak_score(self, classifier):
        results = classifier.classify("It could be a race condition.")
        hedge = next(r for r in results if r.rule_id == "HEDGE_WEAK")
        assert hedge.score == 5
        assert hedge.risk_level == RiskLevel.LOW

    # ── HEDGE_STRONG ─────────────────────────────────────────────────────────

    def test_hedge_strong_english_i_think(self, classifier):
        results = classifier.classify("I think this function is the problem.")
        ids = [r.rule_id for r in results]
        assert "HEDGE_STRONG" in ids

    def test_hedge_strong_english_probably(self, classifier):
        results = classifier.classify("The bug is probably in the auth module.")
        ids = [r.rule_id for r in results]
        assert "HEDGE_STRONG" in ids

    def test_hedge_strong_korean_geot_gat(self, classifier):
        results = classifier.classify("OAuth 문제가 middleware 설정 문제 같습니다.")
        ids = [r.rule_id for r in results]
        assert "HEDGE_STRONG" in ids

    def test_hedge_strong_korean_ama(self, classifier):
        results = classifier.classify("아마 express-session 설정이 원인인 것 같습니다.")
        ids = [r.rule_id for r in results]
        assert "HEDGE_STRONG" in ids

    def test_hedge_strong_korean_boipsida(self, classifier):
        results = classifier.classify("세션이 유실되는 것으로 보입니다.")
        ids = [r.rule_id for r in results]
        assert "HEDGE_STRONG" in ids

    def test_hedge_strong_score(self, classifier):
        results = classifier.classify("I think this is the cause.")
        hedge = next(r for r in results if r.rule_id == "HEDGE_STRONG")
        assert hedge.score == 10
        assert hedge.risk_level == RiskLevel.MEDIUM

    # ── ASSUME_FACT ───────────────────────────────────────────────────────────

    def test_assume_fact_english(self, classifier):
        results = classifier.classify("The root cause is the missing validation.")
        ids = [r.rule_id for r in results]
        assert "ASSUME_FACT" in ids

    def test_assume_fact_korean(self, classifier):
        results = classifier.classify("이게 원인인 것 같습니다. 수정하겠습니다.")
        ids = [r.rule_id for r in results]
        assert "ASSUME_FACT" in ids

    def test_assume_fact_score(self, classifier):
        results = classifier.classify("The bug is in the auth middleware.")
        fact = next((r for r in results if r.rule_id == "ASSUME_FACT"), None)
        assert fact is not None
        assert fact.score == 15

    # ── CLAIM_TEST_PASS ───────────────────────────────────────────────────────

    def test_claim_test_pass_should_work_now(self, classifier):
        results = classifier.classify("This should work now after the fix.")
        ids = [r.rule_id for r in results]
        assert "CLAIM_TEST_PASS" in ids

    def test_claim_test_pass_korean(self, classifier):
        results = classifier.classify("수정 후 테스트가 통과할 것 같습니다.")
        ids = [r.rule_id for r in results]
        assert "CLAIM_TEST_PASS" in ids

    def test_claim_test_pass_score(self, classifier):
        results = classifier.classify("The tests should pass after this change.")
        claim = next(r for r in results if r.rule_id == "CLAIM_TEST_PASS")
        assert claim.score == 20
        assert claim.risk_level == RiskLevel.HIGH

    # ── 클린 텍스트 (부채 없음) ───────────────────────────────────────────────

    def test_clean_factual_english(self, classifier):
        results = classifier.classify("Fixed the null check in validate_token at line 42.")
        assert results == []

    def test_clean_factual_korean(self, classifier):
        results = classifier.classify("auth.py 42번째 줄의 null 검사 로직을 수정했습니다.")
        assert results == []

    def test_empty_string(self, classifier):
        results = classifier.classify("")
        assert results == []

    def test_log_line_no_debt(self, classifier):
        results = classifier.classify("[ERROR] 2026-04-26 10:00:00 Connection refused at port 5432")
        assert results == []

    # ── 복수 규칙 동시 발동 ───────────────────────────────────────────────────

    def test_multiple_rules_fire_in_one_text(self, classifier):
        # HEDGE_STRONG + ASSUME_FACT 동시 감지
        text = "I think the root cause is the missing session cookie."
        results = classifier.classify(text)
        ids = [r.rule_id for r in results]
        assert "HEDGE_STRONG" in ids
        assert "ASSUME_FACT" in ids

    def test_same_rule_fires_only_once(self, classifier):
        # 같은 규칙이 한 텍스트에서 두 번 나와도 1회만 카운트
        text = "I think this is wrong. I think that is also wrong."
        results = classifier.classify(text)
        hedge_matches = [r for r in results if r.rule_id == "HEDGE_STRONG"]
        assert len(hedge_matches) == 1

    def test_claim_matched_text_is_sentence_fragment(self, classifier):
        # 클레임이 전체 텍스트가 아닌 해당 문장을 잘라서 반환하는지 확인
        text = "Analysis complete. I think this is the issue. Let me fix it."
        results = classifier.classify(text)
        hedge = next(r for r in results if r.rule_id == "HEDGE_STRONG")
        assert len(hedge.claim) < len(text)

    def test_ignores_malformed_backtick_fragment(self, classifier):
        results = classifier.classify("rules` 로 보입니다.")
        assert results == []

    def test_ignores_short_broken_assumption_fragment(self, classifier):
        results = classifier.classify("- `원인은 .")
        assert results == []

    def test_balanced_backticks_still_allow_detection(self, classifier):
        results = classifier.classify("원인은 `hatchling` 설정 문제입니다.")
        ids = [r.rule_id for r in results]
        assert "ASSUME_FACT" in ids


# ── ActionClassifier ─────────────────────────────────────────────────────────

class TestActionClassifier:

    # ── EDIT_NO_TEST ─────────────────────────────────────────────────────────

    def test_edit_no_test_fires_when_no_test_run(self, action_classifier):
        results = action_classifier.classify(
            tool="Edit",
            target="src/utils.py",
            command="",
            action_history=[],       # 테스트 기록 없음
            edit_counts={},
        )
        ids = [r.rule_id for r in results]
        assert "EDIT_NO_TEST" in ids

    def test_edit_no_test_skipped_when_test_was_run(self, action_classifier):
        results = action_classifier.classify(
            tool="Edit",
            target="src/utils.py",
            command="",
            action_history=["test"],  # 테스트 실행 기록 있음
            edit_counts={},
        )
        ids = [r.rule_id for r in results]
        assert "EDIT_NO_TEST" not in ids

    def test_edit_no_test_score(self, action_classifier):
        results = action_classifier.classify("Edit", "src/foo.py", "", [], {})
        debt = next(r for r in results if r.rule_id == "EDIT_NO_TEST")
        assert debt.score == 20
        assert debt.risk_level == RiskLevel.HIGH

    # ── HIGH_RISK_FILE ────────────────────────────────────────────────────────

    def test_high_risk_file_auth(self, action_classifier):
        results = action_classifier.classify(
            "Edit", "src/middleware/auth.js", "", ["test"], {}
        )
        ids = [r.rule_id for r in results]
        assert "HIGH_RISK_FILE" in ids

    def test_high_risk_file_config(self, action_classifier):
        results = action_classifier.classify(
            "Edit", "src/config.py", "", ["test"], {}
        )
        ids = [r.rule_id for r in results]
        assert "HIGH_RISK_FILE" in ids

    def test_high_risk_file_dotenv(self, action_classifier):
        results = action_classifier.classify(
            "Edit", ".env.production", "", ["test"], {}
        )
        ids = [r.rule_id for r in results]
        assert "HIGH_RISK_FILE" in ids

    def test_high_risk_file_migration(self, action_classifier):
        results = action_classifier.classify(
            "Edit", "db/migrations/0042_add_user_table.sql", "", ["test"], {}
        )
        ids = [r.rule_id for r in results]
        assert "HIGH_RISK_FILE" in ids

    def test_safe_file_no_high_risk_debt(self, action_classifier):
        results = action_classifier.classify(
            "Edit", "src/utils/string_helpers.py", "", ["test"], {}
        )
        ids = [r.rule_id for r in results]
        assert "HIGH_RISK_FILE" not in ids

    def test_high_risk_file_score(self, action_classifier):
        results = action_classifier.classify(
            "Edit", "src/auth.py", "", ["test"], {}
        )
        debt = next(r for r in results if r.rule_id == "HIGH_RISK_FILE")
        assert debt.score == 25

    # ── DESTRUCTIVE_CMD ───────────────────────────────────────────────────────

    def test_destructive_cmd_rm_rf(self, action_classifier):
        results = action_classifier.classify(
            "Bash", "", "rm -rf ./data/cache", [], {}
        )
        ids = [r.rule_id for r in results]
        assert "DESTRUCTIVE_CMD" in ids

    def test_destructive_cmd_drop_table(self, action_classifier):
        results = action_classifier.classify(
            "Bash", "", "psql -c 'DROP TABLE users;'", [], {}
        )
        ids = [r.rule_id for r in results]
        assert "DESTRUCTIVE_CMD" in ids

    def test_destructive_cmd_git_reset_hard(self, action_classifier):
        results = action_classifier.classify(
            "Bash", "", "git reset --hard HEAD~1", [], {}
        )
        ids = [r.rule_id for r in results]
        assert "DESTRUCTIVE_CMD" in ids

    def test_destructive_cmd_has_force_verdict_block(self, action_classifier):
        results = action_classifier.classify(
            "Bash", "", "rm -rf ./dist", [], {}
        )
        debt = next(r for r in results if r.rule_id == "DESTRUCTIVE_CMD")
        assert debt.force_verdict == Verdict.BLOCK

    def test_safe_bash_no_debt(self, action_classifier):
        results = action_classifier.classify(
            "Bash", "", "grep -n 'redirect_uri' src/middleware/auth.js", ["test"], {}
        )
        assert results == []

    def test_safe_bash_ls(self, action_classifier):
        results = action_classifier.classify(
            "Bash", "", "ls -la src/", [], {}
        )
        assert results == []

    # ── RETRY_SAME_FIX ────────────────────────────────────────────────────────

    def test_retry_same_fix_fires_at_third_edit(self, action_classifier):
        results = action_classifier.classify(
            tool="Edit",
            target="src/auth.py",
            command="",
            action_history=["test"],
            edit_counts={"src/auth.py": 3},  # 3번째 수정
        )
        ids = [r.rule_id for r in results]
        assert "RETRY_SAME_FIX" in ids

    def test_retry_same_fix_does_not_fire_at_second_edit(self, action_classifier):
        results = action_classifier.classify(
            tool="Edit",
            target="src/auth.py",
            command="",
            action_history=["test"],
            edit_counts={"src/auth.py": 2},  # 2번째 수정, 아직 OK
        )
        ids = [r.rule_id for r in results]
        assert "RETRY_SAME_FIX" not in ids

    def test_retry_same_fix_score(self, action_classifier):
        results = action_classifier.classify(
            "Edit", "src/auth.py", "", ["test"], {"src/auth.py": 3}
        )
        debt = next(r for r in results if r.rule_id == "RETRY_SAME_FIX")
        assert debt.score == 15
