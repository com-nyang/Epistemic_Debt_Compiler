---
marp: true
theme: default
paginate: true
html: true
backgroundColor: #0f0f0f
color: #e8e8e8
style: |
  section {
    font-family: 'Pretendard', 'Noto Sans KR', sans-serif;
    padding: 40px 56px;
    overflow: hidden;
  }
  h1 {
    font-size: 1.9em;
    font-weight: 800;
    color: #ffffff;
    border-bottom: 3px solid #6c63ff;
    padding-bottom: 10px;
    margin-top: 0;
    margin-bottom: 18px;
  }
  h2 {
    font-size: 1.2em;
    font-weight: 700;
    color: #a78bfa;
    margin-bottom: 8px;
    margin-top: 0;
  }
  h3 {
    font-size: 0.85em;
    font-weight: 600;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-bottom: 6px;
    margin-top: 0;
  }
  p, li {
    font-size: 0.95em;
    line-height: 1.6;
    color: #cbd5e1;
    margin: 4px 0;
  }
  code {
    background: #1e1e2e;
    color: #a78bfa;
    padding: 1px 6px;
    border-radius: 4px;
    font-size: 0.85em;
  }
  pre {
    background: #1e1e2e;
    border-left: 4px solid #6c63ff;
    border-radius: 8px;
    padding: 16px 20px;
    margin: 10px 0;
  }
  pre code {
    background: transparent;
    color: #c0caf5;
    font-size: 0.78em;
    padding: 0;
    line-height: 1.55;
  }
  strong {
    color: #ffffff;
  }
  td strong {
    color: #a78bfa;
  }
  blockquote {
    border-left: 4px solid #6c63ff;
    background: #1e1e2e;
    padding: 12px 20px;
    border-radius: 0 8px 8px 0;
    color: #e2e8f0;
    font-style: normal;
    font-size: 1em;
    margin: 8px 0;
  }
  blockquote p {
    margin: 4px 0;
    font-size: 1em;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 10px;
    font-size: 0.88em;
  }
  th {
    background: #1e1e2e;
    color: #a78bfa;
    padding: 8px 14px;
    font-weight: 700;
    text-align: left;
  }
  td {
    border-bottom: 1px solid #2d2d3a;
    padding: 8px 14px;
    color: #cbd5e1;
  }
  section.title {
    display: flex;
    flex-direction: column;
    justify-content: center;
    text-align: center;
  }
  section.title h1 {
    font-size: 2.6em;
    border-bottom: none;
    color: #a78bfa;
    margin-bottom: 20px;
  }
  section.title h3 {
    font-size: 1em;
    color: #64748b;
    text-transform: none;
    letter-spacing: 0;
  }
  section.title p {
    font-size: 1em;
    color: #475569;
  }
  section.center {
    display: flex;
    flex-direction: column;
    justify-content: center;
  }
---

<!-- _class: title -->

# Epistemic Debt Compiler

### AI 에이전트의 불확실성을 추적하고 제어하는 CLI 게이트키퍼

<br>

**com_nyang** · 2026

---

# AI 에이전트, 이제 직접 코드를 건드립니다

파일을 수정하고, 명령어를 실행하고, 배포 결정까지 내립니다.

그런데 에이전트가 이런 말을 한다면?

<br>

> **"아마 이게 원인인 것 같습니다. 수정해볼게요."**

> **"이렇게 하면 동작할 것 같습니다."**

> **"이 설정이 문제인 것 같으니 바꿔보겠습니다."**

---

# 문제: 추측이 쌓이면

에이전트의 **추측 하나**는 작아 보입니다. 하지만 그 추측 위에 또 추측이 쌓이면 —

```
"아마 여기가 원인" → auth.py 수정
  → "이제 될 것 같음" → 테스트 없이 커밋
    → "배포해도 괜찮을 것 같음" → 프로덕션 반영
```

<br>

개발자에게 주어진 선택지:

- 매 메시지를 직접 읽으며 판단한다
- 에이전트를 믿고 그냥 넘긴다
- 에이전트 자율성을 포기한다

**세 선택지 모두 나쁩니다.**

---

# Epistemic Debt — 인지부채

증거 없이 행동할 때 발생하는 **누적 리스크**입니다.
기술부채처럼 쌓이고, 기술부채처럼 상환할 수 있습니다.

| 유형 | 예시 | 점수 |
|------|------|:----:|
| 약한 추측 | "might", "어쩌면" | +5 |
| 강한 추측 | "I think", "아마" | +10 |
| 근거 없는 확신 | "this will fix" | +20 |
| 테스트 없는 파일 수정 | Edit without test | +20 |
| 고위험 파일 수정 | auth, secret, .env | +25 |
| 파괴적 명령 실행 | `rm -rf`, `DROP TABLE` | **BLOCK** |

---

# 어떻게 동작하나요? — 감지

```bash
$ debt watch --file examples/demo_oauth/session_demo.json

  세션 ID: dc66f9b4 | 이벤트: 3개

  ◑ HEDGE_STRONG   "OAuth callback redirect loop는 middleware 설정 문제 같습니다"
                   점수 +10  ID edc-8c621d
  ◑ HEDGE_STRONG   "아마 express-session의 cookie sameSite 속성이 원인인 것 같습니다"
                   점수 +10  ID edc-e5b851
  ● EDIT_NO_TEST   테스트 실행 없이 파일 수정: src/middleware/auth.js
                   점수 +20  ID edc-1804a6
  ● HIGH_RISK_FILE 고위험 파일 접근: src/middleware/auth.js
                   점수 +25  ID edc-23daa6

  총 인지부채 4건  (score: 65)
```

---

# 어떻게 동작하나요? — 판정

```bash
$ debt judge

  ⛔  판정: APPROVAL_REQUIRED
  추정 표현 + 고위험 파일 동시 발생
```

```bash
$ debt repay edc-1804a6 --code "src/middleware/auth.js:42"
  ✓ 인지부채 해소됨  edc-1804a6  점수 감소 -10  현재 점수 55

$ debt repay edc-8c621d --doc "express-session docs: sameSite cookie fix"
  ✓ 인지부채 해소됨  edc-8c621d  점수 감소 -8   현재 점수 47

$ debt repay edc-e5b851 --doc "express-session docs: sameSite=strict 설정 확인"
  ✓ 인지부채 해소됨  edc-e5b851  점수 감소 -8   현재 점수 39

$ debt repay edc-23daa6 --manual "auth.js 직접 코드 리뷰 완료"
  ✓ 인지부채 해소됨  edc-23daa6  점수 감소 -5   현재 점수 34
```

증거 없이는 에이전트가 앞으로 나아갈 수 없습니다.

---

# 실시간 대시보드

에이전트가 작업하는 동안 부채 누적을 실시간으로 모니터링합니다.

```bash
# 현재 프로젝트의 최신 Claude 세션 모니터링
$ debt dashboard --type claude

# Codex 세션 ID로 직접 연결
$ debt dashboard --type codex 019d04f2-a69e-7ea3-a599-4a1ae3b2ec19

# 에이전트 세션에 직접 연결
$ debt watch-claude --session <session-id>
$ debt watch-codex  --session <session-id>
$ debt watch-gemini --session <session-id>
```

tmux 기반으로 실행되며, 새 부채가 감지될 때마다 화면이 갱신됩니다.

---

# 실시간 Hook 연동

`debt init` 한 번으로 에이전트와 자동 연동됩니다.

```bash
$ debt init
  ✓ .edc/ 초기화 완료
  ✓ Claude / Codex / Gemini hook 등록 완료
```

에이전트가 도구를 호출하는 순간 `debt judge`가 개입합니다.

| 점수 | 판정 | 결과 |
|:----:|------|------|
| ~ 20 | `ALLOW` | 정상 진행 |
| 21 ~ 40 | `EVIDENCE_REQUIRED` | 증거 요청 |
| 41 ~ 70 | `APPROVAL_REQUIRED` | 승인 요청 |
| 70+ | `BLOCK` | **즉시 중단** |

---

# 지원 에이전트 & 차별점

| 에이전트 | 명령어 |
|----------|--------|
| Claude Code | `debt watch-claude --session <id>` |
| OpenAI Codex | `debt watch-codex --session <id>` |
| Google Gemini | `debt watch-gemini --session <id>` |
| 모든 에이전트 | `debt watch --file session.json` |

| 도구 | 언제 | 무엇을 | 결과 |
|------|------|--------|------|
| Lint | 커밋 전 | 코드 문법/스타일 | 리포트 |
| Policy 엔진 | 실행 전 | 허용 규칙 매칭 | 허용/거부 |
| Eval | 실행 후 | 벤치마크 점수 | 리포트 |
| <span style="color:#a78bfa">**EDC (이 프로젝트)**</span> | <span style="color:#a78bfa">**실행 중**</span> | <span style="color:#a78bfa">**추측→행동 근거**</span> | <span style="color:#a78bfa">**실시간 차단**</span> |

---

<!-- _class: title -->

# Thanks

> **에이전트가 스스로 모른다고 한 것들을,**
> **우리가 대신 추적합니다.**

`debt init` → `debt watch` → `debt judge`

![w:180](qr.png)

**github.com/com-nyang/Epistemic_Debt_Compiler**
