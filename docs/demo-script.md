# 해커톤 데모 스크립트 — Epistemic Debt Compiler

**발표 시간:** 2분 이내
**핵심 메시지:** "We don't stop agents from acting. We stop them from acting without evidence."

---

## 사전 준비 (발표 30초 전)

```bash
# 터미널 폰트 크기 키우기 (관중 가시성)
# 프로젝트 루트로 이동
cd ~/play-ground/Epistemic_Debt_Compiler

# 세션 리셋
rm -rf .edc
.venv/bin/python3 debt init --no-hook
```

터미널에 `debt --help` 출력을 띄워두고 시작.

---

## 타임라인 개요

```
00:00 – 00:10   오프닝 — 문제 제시
00:10 – 00:35   debt watch — 인지부채 감지
00:35 – 00:50   debt judge — 차단 판정
00:50 – 01:25   debt repay ×2 — 증거 상환
01:25 – 01:45   debt judge — ALLOW 판정
01:45 – 02:00   클로징 — 핵심 메시지
```

---

## 상세 스크립트

---

### ❶ [00:00 – 00:10] 오프닝

**💬 대사**

> "AI 에이전트가 코드를 수정할 때, 그 판단이 근거 있는 건지 어떻게 알 수 있을까요?
> Epistemic Debt Compiler는 이걸 추적합니다."

**💻 터미널 액션**

없음. 슬라이드 또는 빈 터미널.

**⭐ 강조 포인트**

"알 수 있을까요?" — 청중에게 질문을 던지며 시선 확보.

---

### ❷ [00:10 – 00:35] `debt watch` — 인지부채 감지

**💬 대사**

> "OAuth redirect loop 버그를 수정하는 에이전트 세션이 있습니다.
> 에이전트가 어떻게 행동했는지 분석해 볼게요."

**💻 터미널 입력**

```
debt watch --file examples/demo_oauth/session_demo.json
```

**📺 예상 출력**

```
  OAuth redirect loop 디버깅 (해커톤 데모용 — 3이벤트 간소화)

  세션 ID: a79e0be0 | 이벤트: 3개

 Google OAuth 로그인 후 /auth/callback에서 redirect loop가...
 OAuth callback redirect loop는 middleware 설정 문제 같습니다.
 아마 express-session의 cookie sameSite 속성이 원인인 것 같습니다.

  ◑ 인지부채 감지  edc-xxxxxx
  규칙    HEDGE_STRONG
  클레임  아마 express-session의 cookie sameSite 속성이 원인인 것 같습니다.
  점수    +10  리스크: MEDIUM

[Edit] src/middleware/auth.js

  ● 행동 인지부채  edc-yyyyyy
  규칙    EDIT_NO_TEST
  내용    테스트 실행 없이 파일 수정: src/middleware/auth.js
  점수    +20  리스크: HIGH

  ● 행동 인지부채  edc-zzzzzz
  규칙    HIGH_RISK_FILE
  내용    고위험 파일 접근: src/middleware/auth.js
  점수    +25  리스크: HIGH

──────────────────── 세션 요약 ────────────────────
  총 인지부채  3건  (점수: 55)
      HIGH   2건
      MEDIUM 1건
```

**💬 출력 보면서 할 말**

> "보시면 에이전트가 '아마', '것 같습니다'라고 말하면서
> 바로 인증 파일을 수정하려고 했습니다.
> 테스트도 없이요.
> 이 세 가지가 인지부채로 잡혔습니다. 총 55점."

**⭐ 강조 포인트**

- `HEDGE_STRONG` — "아마", "것 같습니다" 라는 언어 패턴을 짚어주기
- `EDIT_NO_TEST` + `HIGH_RISK_FILE` — "테스트도 없이 인증 파일을" 강조
- **점수 55점** — 숫자를 명확히 짚기

---

### ❸ [00:35 – 00:50] `debt judge` — 차단 판정

**💬 대사**

> "에이전트가 지금 파일을 수정하려고 합니다.
> 게이트를 통과할 수 있을까요?"

**💻 터미널 입력**

```
debt judge
```

**📺 예상 출력**

```
╭──────────────  ⛔  판정: APPROVAL_REQUIRED  ───────────────╮
│                                                             │
│  추정 표현 + 고위험 파일 동시 발생                          │
│                                                             │
╰─────────────────────────────────────────────────────────────╯
```

**💬 출력 보면서 할 말**

> "APPROVAL_REQUIRED. 통과 못 합니다.
> 에이전트를 막은 게 아닙니다. 근거 없는 행동만 막은 겁니다."

**⭐ 강조 포인트**

- `⛔ APPROVAL_REQUIRED` 박스 전체를 손가락으로 가리키며
- **"에이전트를 막은 게 아닙니다"** — 핵심 메시지 선행 예고

---

### ❹ [00:50 – 01:25] `debt repay` — 증거 상환

**💬 대사**

> "그럼 증거를 제출하면 됩니다. 먼저 테스트를 실행합니다."

**💻 터미널 입력 (1번째 repay)**

```
debt repay edc-yyyyyy --test "bash tests/run_oauth_tests.sh"
```

> *(ID는 앞서 watch 출력에서 EDIT_NO_TEST 항목의 edc-xxxxx를 복사)*

**📺 예상 출력**

```
  실행 중... bash tests/run_oauth_tests.sh

pytest tests/test_oauth_flow.py -v

  test_callback_redirect_loop ... PASSED
  test_oauth_login_success ...... PASSED
  test_session_cookie_sameSite .. PASSED

3 passed in 0.94s

  ✓ 인지부채 해소됨  edc-yyyyyy
  점수 감소  -25
  현재 점수  30
```

**💬 출력 보면서 할 말**

> "테스트 통과. 25점 감소. 지금 30점입니다."

---

**💬 대사 (2번째 repay)**

> "코드에서도 직접 근거를 확인했습니다."

**💻 터미널 입력 (2번째 repay)**

```
debt repay edc-zzzzzz --code "src/middleware/auth.js:47"
```

> *(ID는 HIGH_RISK_FILE 항목의 edc-xxxxx)*

**📺 예상 출력**

```
  ✓ 인지부채 해소됨  edc-zzzzzz
  점수 감소  -10
  현재 점수  20
```

**💬 출력 보면서 할 말**

> "코드 47번째 줄 참조. 10점 추가 감소. 이제 20점."

**⭐ 강조 포인트**

- 1번째 repay: `--test` 플래그와 실제 명령 실행 → "직접 실행해서 확인"
- 2번째 repay: `--code` 플래그 → "코드 위치를 근거로 제출"
- 점수가 **55 → 30 → 20** 으로 줄어드는 흐름을 짧게 읊기

---

### ❺ [01:25 – 01:45] `debt judge` 재실행 — ALLOW

**💬 대사**

> "이제 다시 판정해 보겠습니다."

**💻 터미널 입력**

```
debt judge
```

**📺 예상 출력**

```
╭────────────────────────  ✓  판정: ALLOW  ────────────────────────╮
│                                                                   │
│  인지부채 없음 (점수: 20)                                         │
│                                                                   │
╰───────────────────────────────────────────────────────────────────╯
```

**💬 출력 보면서 할 말**

> "ALLOW. 이제 에이전트가 진행할 수 있습니다.
> 에이전트를 막은 게 아닙니다.
> 증거가 생기자마자, 바로 통과했습니다."

**⭐ 강조 포인트 ★★★**

- `✓ ALLOW` 박스 — 앞의 `⛔ APPROVAL_REQUIRED`와 대비
- **말 속도를 늦추며**: "에이전트를 막은 게 아닙니다. 증거가 생기자마자, 바로 통과했습니다."
- 이 장면이 데모의 클라이맥스

---

### ❻ [01:45 – 02:00] 클로징

**💬 대사**

> "Epistemic Debt Compiler.
>
> AI 에이전트의 '아마', '것 같습니다'를 추적하고,
> 증거가 생길 때까지 고위험 행동을 지연시킵니다.
>
> We don't stop agents from acting.
> We stop them from acting without evidence.
>
> 감사합니다."

**💻 터미널 액션**

없음. 마지막 `✓ ALLOW` 출력이 화면에 남아 있는 채로 마무리.

**⭐ 강조 포인트**

- 영어 핵심 메시지는 천천히, 또렷하게
- "without evidence" — 끊어서 강조

---

## 전체 명령어 요약 (복사용)

```bash
# 0. 준비
rm -rf .edc && .venv/bin/python3 debt init --no-hook

# 1. 에이전트 세션 분석
.venv/bin/python3 debt watch --file examples/demo_oauth/session_demo.json

# 2. 판정 (APPROVAL_REQUIRED 예상)
.venv/bin/python3 debt judge

# 3. 상환 — 테스트 실행
.venv/bin/python3 debt repay <EDIT_NO_TEST_ID> --test "bash tests/run_oauth_tests.sh"

# 4. 상환 — 코드 근거
.venv/bin/python3 debt repay <HIGH_RISK_FILE_ID> --code "src/middleware/auth.js:47"

# 5. 재판정 (ALLOW 예상)
.venv/bin/python3 debt judge
```

> **ID 확인 방법:**
> `debt ls`에서 EDIT_NO_TEST, HIGH_RISK_FILE 항목의 `edc-xxxxxx` 복사

---

## 점수 흐름 요약 (발표자 참고용)

```
watch 직후   55점   APPROVAL_REQUIRED   (추정 + 테스트 없음 + 인증 파일)
repay #1    -25점   테스트 통과 (TEST_PASS)
             30점
repay #2    -10점   코드 근거 (GREP_EVIDENCE)
             20점   ALLOW ✓
```

---

## 예상 질문 & 답변

**Q. 정규식으로 감지하면 false positive가 많지 않나요?**

> "MVP는 규칙 기반입니다. Phase 2에서 Classifier 인터페이스를 LLM으로 교체할 수 있게 설계돼 있습니다. 한 줄 교체입니다."

**Q. 에이전트가 --force로 그냥 넘어가면요?**

> "넘어갈 수 있습니다. 단, 강제 진행은 레지스트리에 기록됩니다. 에이전트를 막는 도구가 아니라, 의식하게 만드는 도구입니다."

**Q. 멀티 에이전트 환경에서는요?**

> "현재 MVP는 단일 에이전트입니다. Registry를 SQLite나 Redis로 교체하면 멀티 에이전트가 동일 부채 레지스트리를 공유할 수 있습니다. CMUX 같은 오케스트레이터와 연동을 고려한 구조입니다."

**Q. CI/CD에 붙일 수 있나요?**

> "네. `debt judge`는 exit code 1을 반환하므로 GitHub Actions나 기타 CI에서 바로 사용할 수 있습니다."
