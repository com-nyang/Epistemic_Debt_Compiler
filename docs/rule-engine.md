# Rule Engine 설계 — Epistemic Debt Compiler

**버전:** 0.1 (MVP)

---

## 설계 원칙

- 점수는 단순 정수 누적, 임계값으로 판정
- 규칙은 외부 JSON 파일로 관리 (코드 수정 없이 튜닝 가능)
- 이벤트 처리기는 인터페이스로 추상화 → LLM 분류기 교체 가능
- HIGH 단일 이벤트는 점수와 무관하게 즉시 판정 가능 (overriding rule)

---

## 1. 점수 모델 개요

```
debt_score = Σ(debt_events) - Σ(repay_events)
debt_score = max(0, debt_score)   # 음수 없음

verdict = thresholds[debt_score]
```

단, 특정 이벤트는 점수와 무관하게 판정을 강제한다 (`force_verdict` 필드).

---

## 2. Debt 발생 이벤트

### 2.1 언어 패턴 (Text Analysis)

에이전트 자연어 출력에서 감지하는 패턴.

| ID | 설명 | 패턴 예시 | 점수 |
|---|---|---|---|
| `HEDGE_WEAK` | 약한 추측 표현 | `might`, `could be`, `아마`, `것 같` | +5 |
| `HEDGE_STRONG` | 강한 추측 단정 | `I think the root cause is`, `원인인 것 같습니다` | +10 |
| `ASSUME_FACT` | 추정을 사실처럼 단정 | `The bug is caused by`, `이게 원인입니다` (근거 없음) | +15 |
| `CLAIM_TEST_PASS` | 테스트 실행 없이 통과 주장 | `This should pass`, `이제 잘 동작할 것입니다` | +20 |
| `SCOPE_CREEP` | 요청 범위 밖 파일 수정 언급 | (대상 외 파일명 등장) | +10 |

### 2.2 행동 패턴 (Action Analysis)

도구 호출(tool use) 자체에서 감지하는 패턴.

| ID | 설명 | 조건 | 점수 | force_verdict |
|---|---|---|---|---|
| `EDIT_NO_TEST` | 테스트 없이 파일 수정 | `Edit/Write` 직전 test runner 실행 없음 | +20 | - |
| `HIGH_RISK_FILE` | 고위험 파일 접근 | 파일명이 risk_patterns 매칭 | +25 | - |
| `DESTRUCTIVE_CMD` | 파괴적 명령 실행 | `rm`, `DROP`, `reset --hard` 등 | +30 | `BLOCK` |
| `RETRY_SAME_FIX` | 동일 수정 반복 | 같은 파일 같은 줄 3회 이상 수정 | +15 | - |
| `SILENT_ASSUMPTION` | 에이전트가 컨텍스트 없이 가정 진행 | 사용자 확인 없이 critical path 수정 | +20 | - |

### 고위험 파일 패턴 (HIGH_RISK_FILE 판정 기준)

```
auth, login, token, credential, password, secret,
migration, schema, seed,
config, settings, env,
payment, billing, invoice,
deploy, dockerfile, ci, workflow
```

---

## 3. Debt 상환 이벤트

### 3.1 강도 기반 분류

| ID | 설명 | 조건 | 점수 감소 |
|---|---|---|---|
| `TEST_PASS` | 테스트 스위트 통과 | exit 0 + 테스트 파일 실행 | -25 |
| `REPRO_FAIL` | 버그 재현 성공 | failing test 작성 + 실행 확인 | -20 |
| `REGRESSION_ADDED` | 회귀 테스트 추가 | 새 테스트 파일/케이스 커밋 | -15 |
| `GREP_EVIDENCE` | 코드에서 직접 근거 확인 | `grep`/`search` 결과 파일:줄 제시 | -10 |
| `LOG_EVIDENCE` | 로그에서 근거 확인 | 로그 파일 줄 참조 | -10 |
| `DOC_REFERENCE` | 공식 문서/RFC 참조 | URL 또는 문서 섹션 제시 | -8 |
| `MANUAL_CONFIRM` | 사용자 직접 확인 | `--manual` 플래그 | -5 |

### 3.2 상환 상한 규칙

- 상환 총합은 현재 `debt_score`를 초과하지 않는다 (0 이하 불가)
- `DESTRUCTIVE_CMD`로 발생한 `BLOCK`은 어떤 상환 이벤트로도 해제 불가 — 사용자 `--force`만 가능

---

## 4. 특수 판정 규칙

점수와 무관하게 판정을 강제하는 규칙.

```
IF event.force_verdict == "BLOCK":
    verdict = BLOCK (점수 무관)

IF HEDGE_STRONG + HIGH_RISK_FILE 동시 발생:
    verdict = min(APPROVAL_REQUIRED, current_verdict)
    # 이미 BLOCK이면 유지

IF debt_score == 0 AND repay_events.count > 0:
    verdict = ALLOW  # 완전 상환
```

---

## 5. 최종 판정 임계값

```
debt_score  0 – 20   →  ALLOW
debt_score 21 – 40   →  EVIDENCE_REQUIRED
debt_score 41 – 70   →  APPROVAL_REQUIRED
debt_score 71+       →  BLOCK
```

### 판정별 동작

| 판정 | CLI 동작 | Hook exit code | 메시지 |
|---|---|---|---|
| `ALLOW` | 통과 | `0` | 부채 없음, 진행 가능 |
| `EVIDENCE_REQUIRED` | 경고 출력, 계속 가능 | `0` | 증거 제출 권장 |
| `APPROVAL_REQUIRED` | 사용자 확인 요청 | `0` (확인 후) / `1` (거부) | 인간 승인 필요 |
| `BLOCK` | 실행 차단 | `1` | 부채 해소 전 진행 불가 |

---

## 6. 규칙 파일

### `rules.json`

```json
{
  "version": "0.1",
  "thresholds": {
    "allow": 20,
    "evidence_required": 40,
    "approval_required": 70,
    "block": 71
  },
  "debt_events": [
    {
      "id": "HEDGE_WEAK",
      "type": "text",
      "patterns": {
        "en": ["might", "could be", "I think", "possibly", "perhaps"],
        "ko": ["것 같", "아마", "~일 수 있", "~인 듯", "보입니다"]
      },
      "score": 5,
      "force_verdict": null
    },
    {
      "id": "HEDGE_STRONG",
      "type": "text",
      "patterns": {
        "en": ["I think the root cause is", "the bug is probably in", "this should be the issue"],
        "ko": ["원인인 것 같습니다", "여기가 문제인 것 같습니다", "이게 원인인 듯합니다"]
      },
      "score": 10,
      "force_verdict": null
    },
    {
      "id": "ASSUME_FACT",
      "type": "text",
      "patterns": {
        "en": ["the root cause is", "this is definitely", "the bug is caused by"],
        "ko": ["원인은", "확실히", "문제는 ~입니다"]
      },
      "score": 15,
      "force_verdict": null,
      "note": "근거 제시 없이 단정. grep_evidence와 함께 오면 무시"
    },
    {
      "id": "CLAIM_TEST_PASS",
      "type": "text",
      "patterns": {
        "en": ["this should work now", "should pass", "tests should be fine"],
        "ko": ["이제 잘 될 것입니다", "동작할 것 같습니다", "테스트를 통과할 것입니다"]
      },
      "score": 20,
      "force_verdict": null
    },
    {
      "id": "EDIT_NO_TEST",
      "type": "action",
      "trigger": ["Edit", "Write"],
      "condition": "no_test_run_in_session",
      "score": 20,
      "force_verdict": null
    },
    {
      "id": "HIGH_RISK_FILE",
      "type": "action",
      "trigger": ["Edit", "Write"],
      "condition": "target_matches_risk_patterns",
      "risk_patterns": [
        "auth", "login", "token", "credential", "password", "secret",
        "migration", "schema", "seed",
        "config", "settings", "\\.env",
        "payment", "billing",
        "deploy", "dockerfile", "\\.github", "workflow"
      ],
      "score": 25,
      "force_verdict": null
    },
    {
      "id": "DESTRUCTIVE_CMD",
      "type": "action",
      "trigger": ["Bash"],
      "condition": "command_matches_destructive_patterns",
      "destructive_patterns": [
        "rm -rf", "DROP TABLE", "DROP DATABASE",
        "git reset --hard", "git clean -f",
        "truncate", "delete from", "format"
      ],
      "score": 30,
      "force_verdict": "BLOCK"
    },
    {
      "id": "RETRY_SAME_FIX",
      "type": "action",
      "trigger": ["Edit"],
      "condition": "same_file_same_lines_count >= 3",
      "score": 15,
      "force_verdict": null
    }
  ],
  "repay_events": [
    {
      "id": "TEST_PASS",
      "type": "test",
      "condition": "exit_code == 0 AND test_file_executed",
      "score_reduction": 25
    },
    {
      "id": "REPRO_FAIL",
      "type": "test",
      "condition": "failing_test_written AND executed",
      "score_reduction": 20
    },
    {
      "id": "REGRESSION_ADDED",
      "type": "action",
      "condition": "new_test_file_or_case_added",
      "score_reduction": 15
    },
    {
      "id": "GREP_EVIDENCE",
      "type": "action",
      "condition": "grep_or_search_with_file_ref",
      "score_reduction": 10
    },
    {
      "id": "LOG_EVIDENCE",
      "type": "manual",
      "condition": "log_file_line_reference_provided",
      "score_reduction": 10
    },
    {
      "id": "DOC_REFERENCE",
      "type": "manual",
      "condition": "url_or_doc_section_provided",
      "score_reduction": 8
    },
    {
      "id": "MANUAL_CONFIRM",
      "type": "manual",
      "condition": "user_provided_note",
      "score_reduction": 5
    }
  ],
  "combo_rules": [
    {
      "id": "HEDGE_PLUS_HIGH_RISK",
      "description": "추정 표현 + 고위험 파일 동시 발생",
      "conditions": ["HEDGE_STRONG", "HIGH_RISK_FILE"],
      "force_verdict": "APPROVAL_REQUIRED"
    }
  ]
}
```

---

## 7. Rule Engine Pseudocode

```python
# ── 인터페이스 ──────────────────────────────────────────────────────────────

class Classifier(Protocol):
    """텍스트 이벤트 분류기. 규칙 기반과 LLM 기반 교체 가능."""
    def classify(self, text: str) -> list[DebtEvent]:
        ...

class RuleBasedClassifier:
    """정규식 패턴 매칭 분류기 (MVP 기본값)."""
    def classify(self, text: str) -> list[DebtEvent]:
        events = []
        for rule in self.rules["debt_events"]:
            if rule["type"] != "text":
                continue
            for lang, patterns in rule["patterns"].items():
                if any(re.search(p, text, re.IGNORECASE) for p in patterns):
                    events.append(DebtEvent(
                        id=rule["id"],
                        score=rule["score"],
                        force_verdict=rule["force_verdict"],
                        matched_text=text
                    ))
                    break  # 같은 규칙 중복 방지
        return events

# LLM 분류기를 붙이려면:
# class LLMClassifier:
#     def classify(self, text: str) -> list[DebtEvent]:
#         response = anthropic.messages.create(...)
#         return parse_debt_events(response)


# ── 핵심 엔진 ───────────────────────────────────────────────────────────────

class RuleEngine:

    def __init__(self, rules: dict, classifier: Classifier):
        self.rules = rules
        self.classifier = classifier
        self.debt_score = 0
        self.debt_items: list[DebtItem] = []
        self.session_actions: list[str] = []   # "test_run", "edit", ...
        self.forced_verdict: str | None = None

    # ── 이벤트 처리 ─────────────────────────────────────────────────────────

    def process_text(self, text: str) -> list[DebtItem]:
        """에이전트 자연어 출력 처리."""
        events = self.classifier.classify(text)
        return [self._apply_debt_event(e) for e in events]

    def process_action(self, tool: str, target: str, command: str = "") -> list[DebtItem]:
        """도구 호출(action) 처리."""
        self.session_actions.append(tool.lower())
        events = []

        for rule in self.rules["debt_events"]:
            if rule["type"] != "action":
                continue
            if tool not in rule["trigger"]:
                continue
            if self._check_action_condition(rule, tool, target, command):
                events.append(DebtEvent(
                    id=rule["id"],
                    score=rule["score"],
                    force_verdict=rule.get("force_verdict")
                ))

        return [self._apply_debt_event(e) for e in events]

    def process_repayment(self, repay_type: str, evidence: str) -> RepayResult:
        """부채 상환 처리."""
        rule = self._find_repay_rule(repay_type)
        if rule is None:
            return RepayResult(success=False, reason="알 수 없는 상환 유형")

        reduction = min(rule["score_reduction"], self.debt_score)
        self.debt_score -= reduction
        return RepayResult(
            success=True,
            reduced_by=reduction,
            new_score=self.debt_score,
            evidence=evidence
        )

    # ── 판정 ────────────────────────────────────────────────────────────────

    def get_verdict(self) -> Verdict:
        # force_verdict 우선 (DESTRUCTIVE_CMD 등)
        if self.forced_verdict == "BLOCK":
            return Verdict(
                decision="BLOCK",
                score=self.debt_score,
                reason="강제 차단 이벤트 발생 (상환 불가)"
            )

        # 콤보 규칙 체크
        combo_verdict = self._check_combo_rules()
        if combo_verdict:
            return combo_verdict

        # 점수 기반 판정
        thresholds = self.rules["thresholds"]
        if self.debt_score <= thresholds["allow"]:
            decision = "ALLOW"
        elif self.debt_score <= thresholds["evidence_required"]:
            decision = "EVIDENCE_REQUIRED"
        elif self.debt_score <= thresholds["approval_required"]:
            decision = "APPROVAL_REQUIRED"
        else:
            decision = "BLOCK"

        return Verdict(
            decision=decision,
            score=self.debt_score,
            items=self.debt_items
        )

    # ── 내부 헬퍼 ───────────────────────────────────────────────────────────

    def _apply_debt_event(self, event: DebtEvent) -> DebtItem:
        self.debt_score += event.score
        if event.force_verdict == "BLOCK":
            self.forced_verdict = "BLOCK"
        item = DebtItem(id=generate_id(), event=event, score=event.score)
        self.debt_items.append(item)
        return item

    def _check_action_condition(self, rule: dict, tool: str, target: str, command: str) -> bool:
        condition = rule["condition"]

        if condition == "no_test_run_in_session":
            return "bash" not in self.session_actions  # 테스트 실행 없음

        if condition == "target_matches_risk_patterns":
            return any(
                re.search(p, target, re.IGNORECASE)
                for p in rule.get("risk_patterns", [])
            )

        if condition == "command_matches_destructive_patterns":
            return any(
                pattern in command
                for pattern in rule.get("destructive_patterns", [])
            )

        if condition == "same_file_same_lines_count >= 3":
            return self._count_same_edits(target) >= 3

        return False

    def _check_combo_rules(self) -> Verdict | None:
        active_ids = {item.event.id for item in self.debt_items}
        for combo in self.rules.get("combo_rules", []):
            if all(cond in active_ids for cond in combo["conditions"]):
                return Verdict(
                    decision=combo["force_verdict"],
                    score=self.debt_score,
                    reason=combo["description"]
                )
        return None

    def _find_repay_rule(self, repay_type: str) -> dict | None:
        for rule in self.rules["repay_events"]:
            if rule["id"] == repay_type:
                return rule
        return None

    def _count_same_edits(self, target: str) -> int:
        return sum(1 for item in self.debt_items if item.target == target)
```

---

## 8. LLM 분류기 확장 포인트

MVP는 `RuleBasedClassifier`를 사용한다. LLM 분류기를 붙이려면 `Classifier` 인터페이스만 구현하면 된다.

```python
class LLMClassifier:
    """Phase 2: 의미론적 불확실성 분류."""

    PROMPT = """
    다음 텍스트에서 인지부채를 감지하세요.
    인지부채 = 근거 없는 추정, 검증 없는 단정, 불확실성 표현.

    텍스트: {text}

    JSON으로 응답:
    {{"events": [{{"id": "HEDGE_STRONG"|"ASSUME_FACT"|..., "matched": "...", "confidence": 0.0-1.0}}]}}
    """

    def classify(self, text: str) -> list[DebtEvent]:
        response = anthropic.messages.create(
            model="claude-haiku-4-5-20251001",  # 빠르고 저렴한 모델
            max_tokens=256,
            messages=[{"role": "user", "content": self.PROMPT.format(text=text)}]
        )
        return self._parse_response(response)
```

**교체 방법:**
```python
# MVP
engine = RuleEngine(rules, classifier=RuleBasedClassifier(rules))

# Phase 2 (한 줄 교체)
engine = RuleEngine(rules, classifier=LLMClassifier())

# 하이브리드 (규칙 기반 우선, 불확실하면 LLM)
engine = RuleEngine(rules, classifier=HybridClassifier(
    primary=RuleBasedClassifier(rules),
    fallback=LLMClassifier(),
    fallback_threshold=0.5
))
```

---

## 9. 동작 예시 (전체 흐름)

```python
engine = RuleEngine(load_rules("rules.json"), RuleBasedClassifier(rules))

# 1. 에이전트 텍스트 처리
items = engine.process_text("validate_token 함수가 원인인 것 같습니다.")
# → HEDGE_STRONG 감지, score +10

# 2. 고위험 파일 수정 행동
items = engine.process_action(tool="Edit", target="src/auth.py")
# → EDIT_NO_TEST +20, HIGH_RISK_FILE +25 → score = 55

# 3. 판정
verdict = engine.get_verdict()
# → APPROVAL_REQUIRED (55점, 콤보 규칙 적용)

# 4. 상환
result = engine.process_repayment("TEST_PASS", evidence="pytest tests/auth_test.py")
# → score = 55 - 25 = 30

# 5. 재판정
verdict = engine.get_verdict()
# → EVIDENCE_REQUIRED (30점)

result = engine.process_repayment("GREP_EVIDENCE", evidence="src/auth.py:42")
# → score = 30 - 10 = 20

verdict = engine.get_verdict()
# → ALLOW (20점)
```
