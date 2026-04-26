# PRD — Epistemic Debt Compiler

**버전:** 0.1 (해커톤 MVP)
**작성일:** 2026-04-26

---

## 1. 문제 정의

AI 코딩 에이전트는 불확실한 추정을 사실처럼 다루며 행동한다.

> "이 함수가 원인인 것 같습니다. 수정하겠습니다."
> "아마 이 설정 때문일 것입니다. 바꿔볼게요."
> "이렇게 하면 될 것 같습니다."

이 추정들은 개별적으로는 작은 판단이지만, 파이프라인 안에서 **전제로 누적**된다. 에이전트는 자신이 앞서 내린 추정 위에 다음 행동을 쌓고, 이 체인이 길어질수록 전체 작업의 신뢰도는 기하급수적으로 낮아진다.

현재 개발자가 이 문제를 해결하는 방법:
- 에이전트 출력을 전부 읽고 직접 판단한다 (느리다)
- 에이전트를 믿고 넘어간다 (위험하다)
- 에이전트를 아예 사용하지 않는다 (비효율적이다)

**근본 문제:** AI 에이전트에게는 자신의 불확실성을 추적하고 그에 따라 행동을 조절하는 메커니즘이 없다.

---

## 2. 왜 지금 필요한가

### AI 에이전트의 자율성이 빠르게 높아지고 있다

Claude Code, Cursor, Devin 같은 도구들은 이제 단순 코드 제안이 아니라 **실제로 파일을 수정하고 명령을 실행**한다. 에이전트의 자율성이 높아질수록 추정 기반 행동의 파급력도 커진다.

### 멀티 에이전트 환경이 등장하고 있다

CMUX 같은 멀티 에이전트 오케스트레이터에서는 에이전트 A의 추정이 에이전트 B의 입력이 된다. 근거 없는 클레임이 파이프라인 전체에 전파된다.

### 기존 솔루션이 이 문제를 다루지 않는다

- 린터/정적 분석: 코드 품질 검사, 에이전트 추론 품질 검사 불가
- 테스트: 결과 검증, 과정 중 불확실성 추적 불가
- 에이전트 로그: 사후 기록, 실시간 게이트 기능 없음

---

## 3. 대상 사용자

### Primary — AI 헤비 유저 개발자

- Claude Code, Cursor 등을 매일 사용하는 개발자
- 에이전트가 내린 판단을 검토하는 데 피로감을 느낌
- "에이전트가 왜 이렇게 했는지" 추적하고 싶어함

### Secondary — 자동화 파이프라인 운영자

- CI/CD 파이프라인에 AI 에이전트를 통합한 팀
- 에이전트의 고위험 행동에 대한 게이트가 필요한 상황
- 에이전트 행동 감사(audit) 기록이 필요한 팀

### Tertiary — 멀티 에이전트 아키텍처 설계자

- CMUX, CrewAI, AutoGen 등의 멀티 에이전트 환경을 구축하는 개발자
- 에이전트 간 신뢰 체계를 설계해야 하는 상황

---

## 4. 주요 기능

### 4.1 인지부채 감지 (Debt Detection)

에이전트 출력에서 불확실성 언어 패턴을 감지하여 인지부채 항목을 생성한다.

**감지 패턴 (규칙 기반):**

| 언어 | 패턴 예시 |
|---|---|
| 한국어 | `것 같`, `아마`, `~일 수 있`, `~인 듯`, `추측`, `보입니다` |
| 영어 | `I think`, `probably`, `might`, `should work`, `I assume`, `likely`, `seems like` |

**리스크 레벨 분류:**

행동 유형과 불확실성 표현의 조합으로 리스크 레벨을 결정한다.

| 리스크 | 조건 |
|---|---|
| `LOW` | 불확실성 표현 + 설명/조언만 |
| `MEDIUM` | 불확실성 표현 + 코드 제안 |
| `HIGH` | 불확실성 표현 + 파일 수정/명령 실행 예고 |

### 4.2 인지부채 레지스트리 (Debt Registry)

`.edc/debt.json`에 부채 항목을 로컬 저장한다.

```json
{
  "id": "edc-001",
  "session": "2026-04-26T10:00:00Z",
  "claim": "이 함수가 원인인 것 같습니다",
  "risk_level": "HIGH",
  "action_blocked": "Edit: src/auth.py",
  "resolved": false,
  "evidence": null,
  "created_at": "2026-04-26T10:00:05Z",
  "resolved_at": null
}
```

### 4.3 게이트 (Gate)

Claude Code `PreToolUse` hook으로 `Edit`, `Write`, `Bash` 실행 직전에 인터셉트한다.

**게이트 로직:**

```
미해소 HIGH 부채 ≥ 1건  →  BLOCK (exit 1)
미해소 MEDIUM 부채 ≥ 3건  →  WARN + 사용자 확인 요청
미해소 LOW 부채  →  통과 (기록만)
--force 플래그  →  BLOCK 무시 + 강제 진행 로그 기록
```

### 4.4 부채 상환 (Debt Resolution)

다음 증거 유형으로 부채를 해소할 수 있다.

| 상환 유형 | 명령 예시 |
|---|---|
| 테스트 통과 | `edc resolve edc-001 --test "pytest tests/auth_test.py"` |
| 코드 증거 | `edc resolve edc-001 --code "src/auth.py:42"` |
| 문서 근거 | `edc resolve edc-001 --doc "RFC-1234: 이 함수는 항상 None을 반환"` |
| 로그 근거 | `edc resolve edc-001 --log "error.log:line 88"` |
| 수동 확인 | `edc resolve edc-001 --manual "직접 확인함"` |

### 4.5 리포트 (Report)

세션 또는 커밋 단위로 인지부채 현황을 출력한다. PR 머지 전 체크리스트로 활용 가능하다.

---

## 5. CLI 명령어 초안

```bash
# 현재 미해소 부채 목록
edc list
edc list --risk HIGH
edc list --session current

# 부채 상세 조회
edc show <id>

# 부채 상환
edc resolve <id> --test "<command>"
edc resolve <id> --code "<file>:<line>"
edc resolve <id> --doc "<description>"
edc resolve <id> --log "<file>:<line>"
edc resolve <id> --manual "<note>"

# 게이트 상태 확인
edc gate --check

# 리포트 출력
edc report
edc report --session <session-id>
edc report --format json

# 설정
edc init                        # 프로젝트에 .edc/ 초기화
edc config --threshold HIGH=1   # 블록 임계값 설정
edc config --show

# 수동 부채 등록 (에이전트 외 직접 입력)
edc add --claim "이 로직이 맞는지 확실하지 않음" --risk MEDIUM
```

---

## 6. 데모 흐름

### 준비

```bash
edc init
# Claude Code settings.json에 hook 자동 등록
```

### Step 1 — 에이전트가 추정 발언

```
사용자: "인증 버그 수정해줘"
Claude: "auth.py의 validate_token 함수가 원인인 것 같습니다. 수정하겠습니다."
```

### Step 2 — 인지부채 자동 등록

```bash
[EDC] 인지부채 감지됨
  ID: edc-001
  클레임: "원인인 것 같습니다"
  리스크: HIGH (파일 수정 예고)
  상태: 미해소
```

### Step 3 — 게이트 작동

```bash
[EDC] BLOCK: 미해소 HIGH 인지부채 1건
  edc-001: "원인인 것 같습니다" → Edit: auth.py

  해결 방법:
    edc resolve edc-001 --test "pytest tests/"
    edc resolve edc-001 --code "auth.py:88"
    edc gate --force  (강제 진행, 기록됨)
```

### Step 4 — 사용자가 테스트 실행 후 부채 상환

```bash
pytest tests/auth_test.py
# ... PASSED

edc resolve edc-001 --test "pytest tests/auth_test.py"
# [EDC] edc-001 해소됨 (근거: 테스트 통과)
```

### Step 5 — 게이트 재확인 후 진행

```bash
edc gate --check
# [EDC] 게이트 통과: 미해소 HIGH 부채 없음

# Claude가 파일 수정 재시도 → 성공
```

### Step 6 — 리포트

```bash
edc report

# 세션 리포트 2026-04-26
# ─────────────────────────────────────
# 총 인지부채: 3건
#   해소됨:   2건 (테스트 1, 코드 근거 1)
#   미해소:   1건 (MEDIUM)
#   강제진행: 0건
# ─────────────────────────────────────
# 부채 상환율: 66%
```

---

## 7. 구현 우선순위

### Phase 1 — 데모 가능한 최소 (4시간)

- [ ] `edc init` — `.edc/` 디렉토리 및 `debt.json` 초기화
- [ ] `edc list` — 부채 목록 출력
- [ ] `edc resolve` — 부채 해소 (manual 유형만)
- [ ] Claude Code `PreToolUse` hook 연동 — HIGH 부채 시 BLOCK
- [ ] 불확실성 패턴 정규식 감지기

### Phase 2 — 데모 품질 향상 (2시간)

- [ ] `edc report` — 세션 리포트
- [ ] `edc gate --check` — 게이트 상태 CLI
- [ ] `--test` 상환 유형 — 실제 명령 실행 후 exit code 0이면 해소
- [ ] `--force` 플래그 + 강제 진행 로그

### Phase 3 — 있으면 좋은 것 (남은 시간)

- [ ] `edc config` — 임계값 설정
- [ ] `PostToolUse` hook — 행동 완료 후 자동 기록
- [ ] JSON 리포트 출력 (`--format json`)
- [ ] 컬러 터미널 출력

---

## 8. 리스크

### 기술 리스크

| 리스크 | 가능성 | 영향 | 대응 |
|---|---|---|---|
| Claude Code hook API 변경 | 낮음 | 높음 | hook 없이 stdin pipe 방식 fallback 준비 |
| 정규식 감지 false positive 과다 | 중간 | 중간 | 임계값 높게 설정, 데모 스크립트 고정 |
| 한/영 혼용 패턴 누락 | 중간 | 낮음 | 데모는 영어 패턴 중심으로 고정 |
| `.edc/debt.json` 동시성 문제 | 낮음 | 낮음 | 단일 프로세스 데모, 무시 가능 |

### 범위 리스크

| 리스크 | 대응 |
|---|---|
| "LLM으로 더 잘 감지되지 않냐"는 질문 | "Phase 2 계획 있음, MVP는 규칙 기반" 답변 준비 |
| 멀티 에이전트 실제 데모 요구 | 철학/아키텍처 설명으로 대체, 단일 에이전트 데모 충분 |
| "실제 프로덕션에선 어떻게?" 질문 | CI 연동 시나리오(exit code 1) 슬라이드 준비 |

---

## 9. 해커톤용 차별점

### 기술적 차별점

**훅 기반 실시간 인터셉트**
에이전트 행동을 사후 분석하지 않고, 실행 직전에 가로챈다. Claude Code의 `PreToolUse` hook을 활용한 실제 동작 데모가 가능하다.

**행동-불확실성 매핑**
불확실성 표현 감지만으로는 부족하다. EDC는 불확실성 표현과 행동 유형(수정/실행/제안)을 결합하여 리스크 레벨을 결정한다. "아마"라고 말하며 설명하는 건 LOW, "아마"라고 말하며 파일을 수정하는 건 HIGH다.

**부채 상환 프로토콜**
에이전트를 막는 도구가 아니라, 에이전트가 계속 진행하기 위한 경로를 제공한다. 부채는 해소될 수 있고, 해소 방법이 명확하다.

### 철학적 차별점

**"막는다"가 아닌 "의식하게 한다"**
`--force`로 항상 override 가능하다. EDC는 개발자의 자율성을 침해하지 않는다. 단, 강제 진행은 기록된다. 개발자가 위험을 인식하고 선택했다는 증거가 남는다.

**멀티 에이전트 환경 대응 철학**
CMUX 같은 환경에서 에이전트 A의 클레임이 에이전트 B로 전파될 때, EDC 레지스트리가 클레임의 근거 여부를 추적하는 공유 메모리 역할을 할 수 있다. MVP는 단일 에이전트지만, 아키텍처는 멀티 에이전트를 고려한다.

**AI 안전성의 실용적 접근**
"AI를 믿을 수 없다" → "AI를 쓰지 말자"가 아니라, "AI의 불확실성을 가시화하고 구조화하자"는 접근이다. 거버넌스보다 도구, 규제보다 관찰 가능성(observability)에 집중한다.

---

## 부록 — 핵심 파일 구조

```
project/
├── .edc/
│   ├── debt.json          # 인지부채 레지스트리
│   ├── config.json        # 임계값 등 설정
│   └── sessions/          # 세션별 스냅샷
├── .claude/
│   └── settings.json      # PreToolUse hook 등록
└── src/
    └── ...
```

## 부록 — hook 연동 예시

```json
// .claude/settings.json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write|Bash",
        "hooks": [
          {
            "type": "command",
            "command": "edc gate --check --tool $TOOL_NAME"
          }
        ]
      }
    ]
  }
}
```
