# CLI Spec — Epistemic Debt Compiler

**Binary:** `debt`
**버전:** 0.1 (해커톤 MVP)

---

## 설계 원칙

- 명령어는 금융 부채 메타포를 일관되게 유지한다 (`watch`, `repay`, `judge`)
- 파이프(`|`) 친화적으로 설계한다
- 에러는 항상 stderr, 정상 출력은 stdout
- exit code를 hook/CI 연동의 신호로 활용한다
- 색상은 정보 전달용, 없어도 읽힌다 (CI 환경 대응)

---

## 명령어 평가 및 최종 권장

### 원안 검토

| 원안 | 평가 | 권장 |
|---|---|---|
| `debt watch` | 직관적, 파이프 연동에 적합 | **유지** |
| `debt repay` | 부채 메타포와 완벽하게 일치 | **유지** |
| `debt judge` | 독창적이고 기억에 남음. CI에선 `gate`가 더 익숙하지만 해커톤엔 `judge`가 낫다 | **유지** (단, `--strict` 모드로 CI 대응) |
| `debt explain` | 모호함. "설명"인지 "목록"인지 불명확 | **`debt ls`로 교체** |

### 추가 제안

| 추가 | 이유 |
|---|---|
| `debt ls` | 목록 조회는 가장 자주 쓰는 명령. `explain`보다 유닉스 관습에 맞음 |

### 최종 권장 명령어 세트 (5개)

```
debt watch    # 에이전트 출력 감시 → 인지부채 자동 등록
debt ls       # 현재 미해소 인지부채 목록 조회
debt repay    # 증거 제출로 부채 상환
debt judge    # 게이트 판정 (hook/CI 연동 포함)
debt explain  # 특정 부채 상세 설명 (선택적 5번째)
```

> **데모 핵심 3개:** `watch` → `ls` → `repay` → `judge` 순서만으로 전체 흐름 시연 가능

---

## 명령어 상세 스펙

---

### `debt watch`

**목적:** 에이전트 출력을 실시간으로 감시하여 불확실성 표현을 인지부채로 자동 등록한다.

**사용 방법:**

```bash
# 파이프 모드 (권장)
claude "auth 버그 수정해줘" | debt watch

# 파일 모드
debt watch --file agent_output.txt

# 직접 입력 모드 (테스트용)
echo "이 함수가 원인인 것 같습니다." | debt watch
```

**옵션:**

```
--file, -f <path>     파일에서 읽기
--session, -s <name>  세션 이름 지정 (기본: 타임스탬프)
--dry-run             등록하지 않고 감지 결과만 출력
--quiet, -q           감지 알림 없이 원본 출력만 통과
```

**출력 예시 — 정상:**

```
$ claude "auth 버그 수정해줘" | debt watch

[통과] 코드 분석 중...
[통과] 재현 조건을 확인합니다...

⚠  인지부채 감지됨
   ID       edc-001
   클레임   "validate_token 함수가 원인인 것 같습니다"
   리스크   HIGH  (파일 수정 예고 포함)
   상태     미해소

[통과] 해당 함수를 수정하겠습니다...

⚠  인지부채 감지됨
   ID       edc-002
   클레임   "아마 이 설정값이 문제일 것입니다"
   리스크   MEDIUM
   상태     미해소

[통과] 나머지 분석 완료.

─────────────────────────────
세션 요약  2026-04-26 10:15
등록된 부채  2건 (HIGH 1, MEDIUM 1)
`debt ls` 로 전체 목록 확인
─────────────────────────────
```

**출력 예시 — 감지 없음:**

```
$ echo "분석 완료. 이 함수를 수정하겠습니다." | debt watch

[통과] 분석 완료. 이 함수를 수정하겠습니다.

─────────────────────────────
세션 요약  감지된 인지부채 없음 ✓
─────────────────────────────
```

**에러 상황:**

```bash
# .edc/ 디렉토리 없음
$ echo "..." | debt watch
✗ 오류: .edc/ 디렉토리가 없습니다. `debt init` 을 먼저 실행하세요.

# 파일 없음
$ debt watch --file missing.txt
✗ 오류: 파일을 찾을 수 없습니다: missing.txt
```

**exit code:** 항상 0 (감지 실패해도 원본 출력 통과)

---

### `debt ls`

**목적:** 현재 세션 또는 프로젝트의 미해소 인지부채 목록을 출력한다. 가장 자주 사용하는 상태 확인 명령.

**사용 방법:**

```bash
debt ls
debt ls --risk HIGH
debt ls --all          # 해소된 것 포함
debt ls --json         # JSON 출력 (파이프 활용)
```

**옵션:**

```
--risk <level>    리스크 필터 (HIGH | MEDIUM | LOW)
--all, -a         해소된 부채 포함
--json            JSON 형식 출력
--session <id>    특정 세션 필터
```

**출력 예시 — 미해소 부채 있음:**

```
$ debt ls

미해소 인지부채  2건
─────────────────────────────────────────────────────────
 ID        리스크    클레임                               상태
─────────────────────────────────────────────────────────
 edc-001   HIGH  ●  "원인인 것 같습니다"                 미해소
 edc-002   MED   ●  "아마 이 설정값이 문제일 것입니다"   미해소
─────────────────────────────────────────────────────────

HIGH 부채가 있어 다음 파일 수정이 차단됩니다.
`debt repay edc-001` 로 증거를 제출하세요.
```

**출력 예시 — 부채 없음:**

```
$ debt ls

미해소 인지부채  없음 ✓
에이전트가 근거 있게 행동하고 있습니다.
```

**출력 예시 — JSON 모드:**

```bash
$ debt ls --json
[
  {
    "id": "edc-001",
    "risk_level": "HIGH",
    "claim": "원인인 것 같습니다",
    "resolved": false,
    "created_at": "2026-04-26T10:00:05Z"
  }
]
```

**에러 상황:**

```bash
# 알 수 없는 리스크 레벨
$ debt ls --risk CRITICAL
✗ 오류: 알 수 없는 리스크 레벨 'CRITICAL'. 사용 가능: HIGH, MEDIUM, LOW
```

**exit code:** `0` 항상 (목록 자체는 에러가 아님)

---

### `debt repay`

**목적:** 증거를 제출하여 인지부채를 상환한다. 증거 유형에 따라 부채의 위험도를 낮추거나 완전히 해소한다.

**사용 방법:**

```bash
debt repay <id> --test "<command>"
debt repay <id> --code "<file>:<line>"
debt repay <id> --doc "<description>"
debt repay <id> --log "<file>:<line>"
debt repay <id> --manual "<note>"
```

**옵션:**

```
--test <cmd>      테스트 명령 실행, exit 0이면 자동 해소
--code <ref>      코드 위치 참조로 해소
--doc <text>      문서/RFC/주석 근거로 해소
--log <ref>       로그 파일 참조로 해소
--manual <note>   직접 확인 기록으로 해소 (가장 약한 근거)
```

**출력 예시 — 테스트 통과:**

```
$ debt repay edc-001 --test "pytest tests/auth_test.py"

실행 중... pytest tests/auth_test.py

  tests/auth_test.py::test_validate_token PASSED
  tests/auth_test.py::test_invalid_token  PASSED
  2 passed in 0.43s

✓ 인지부채 해소됨
  ID       edc-001
  근거     테스트 통과 (pytest tests/auth_test.py)
  해소 시각  2026-04-26 10:22:31

미해소 HIGH 부채  0건 → 게이트 통과 가능
```

**출력 예시 — 테스트 실패:**

```
$ debt repay edc-001 --test "pytest tests/auth_test.py"

실행 중... pytest tests/auth_test.py

  tests/auth_test.py::test_validate_token FAILED
  1 failed in 0.31s

✗ 부채 해소 실패: 테스트가 통과하지 않았습니다.
  edc-001 은 여전히 미해소 상태입니다.
```

**출력 예시 — 코드 근거:**

```
$ debt repay edc-001 --code "src/auth.py:42"

✓ 인지부채 해소됨
  ID       edc-001
  근거     코드 참조 (src/auth.py:42)
  해소 시각  2026-04-26 10:23:11
```

**출력 예시 — 수동 확인:**

```
$ debt repay edc-002 --manual "로컬에서 직접 재현 후 원인 확인"

⚠  수동 확인으로 해소됩니다. 가장 약한 근거 유형입니다.
✓  인지부채 해소됨 (수동)
   edc-002 → 해소됨
```

**에러 상황:**

```bash
# 존재하지 않는 ID
$ debt repay edc-999 --manual "..."
✗ 오류: 'edc-999' 를 찾을 수 없습니다. `debt ls` 로 ID를 확인하세요.

# 이미 해소된 부채
$ debt repay edc-001 --test "pytest tests/"
⚠  edc-001 은 이미 해소된 부채입니다. (2026-04-26 10:22:31)
```

**exit code:** `0` 성공, `1` 실패 (테스트 불통과 포함)

---

### `debt judge`

**목적:** 현재 인지부채 상태를 기반으로 다음 행동의 진행 가능 여부를 판정한다. Claude Code `PreToolUse` hook의 핵심 연동 지점.

**사용 방법:**

```bash
# 수동 실행
debt judge

# hook 연동 (tool 정보 포함)
debt judge --tool Edit --target src/auth.py

# CI 모드 (대화형 없음)
debt judge --strict
```

**옵션:**

```
--tool <name>     평가 대상 도구 (Edit | Write | Bash)
--target <path>   대상 파일/명령
--strict          비대화형 모드, 항상 exit code로만 응답
--force           HIGH 부채가 있어도 강제 통과 (기록됨)
```

**출력 예시 — 통과:**

```
$ debt judge

판정: 통과 ✓
────────────────────────────
미해소 HIGH    0건
미해소 MEDIUM  1건  (임계값 미만)
미해소 LOW     0건
────────────────────────────
진행하세요.
```

**출력 예시 — 차단:**

```
$ debt judge --tool Edit --target src/auth.py

판정: 차단 ✗
────────────────────────────────────────────────────────────
미해소 HIGH 인지부채  1건 → Edit 차단됨
────────────────────────────────────────────────────────────

 edc-001  HIGH  "validate_token 함수가 원인인 것 같습니다"

다음 중 하나를 실행하세요:

  [1] debt repay edc-001 --test "pytest tests/"
  [2] debt repay edc-001 --code "<파일>:<줄>"
  [3] debt judge --force       (강제 진행, 기록됨)

────────────────────────────────────────────────────────────
```

**출력 예시 — 강제 진행:**

```
$ debt judge --force

⚠  강제 진행 — 미해소 HIGH 부채 1건 무시됨
   이 결정은 기록됩니다: 2026-04-26 10:30:44
판정: 강제 통과 (기록됨)
```

**에러 상황:**

```bash
# .edc/ 없음
$ debt judge
✗ 오류: 초기화되지 않은 프로젝트입니다. `debt init` 을 실행하세요.
```

**exit code:**

| 상황 | exit code |
|---|---|
| 통과 | `0` |
| 차단 (HIGH 부채) | `1` |
| 강제 통과 | `0` (단, 로그에 기록) |
| 초기화 안됨 | `2` |

> **hook 연동 핵심:** exit code `1` → Claude Code가 tool 실행 취소

---

### `debt explain` *(5번째, 선택적)*

**목적:** 특정 인지부채 항목의 상세 정보와 상환 가이드를 출력한다. 왜 이게 문제인지 사람이 읽기 좋은 형태로 설명한다.

**사용 방법:**

```bash
debt explain edc-001
debt explain --session current    # 세션 전체 서사 요약
```

**출력 예시:**

```
$ debt explain edc-001

────────────────────────────────────────────────────────────
인지부채  edc-001
────────────────────────────────────────────────────────────
클레임    "validate_token 함수가 원인인 것 같습니다"
리스크    HIGH
등록 시각  2026-04-26 10:00:05
상태      미해소

발생 맥락
  에이전트가 이 클레임을 근거로 src/auth.py 수정을 예고했습니다.
  "것 같습니다" 표현 + 파일 수정 예고 = HIGH 리스크로 분류됨.

왜 문제인가
  추정 없이 확인된 사실이라면 "이 함수가 원인입니다"라고 했을 것입니다.
  불확실한 전제 위에서 파일이 수정되면 잘못된 수정이 쌓일 수 있습니다.

상환 방법 (강도 순)
  1. 테스트로 원인 확인   debt repay edc-001 --test "pytest tests/auth_test.py"
  2. 코드로 원인 확인     debt repay edc-001 --code "src/auth.py:42"
  3. 직접 확인            debt repay edc-001 --manual "재현 후 원인 확인"
────────────────────────────────────────────────────────────
```

---

## 전체 흐름 요약

```
에이전트 출력
     │
     ▼
debt watch          # 불확실성 감지 → 부채 등록
     │
     ▼
debt ls             # 현재 상태 확인
     │
     ├── 부채 있음
     │      │
     │      ▼
     │   debt repay <id>    # 증거 제출로 상환
     │      │
     │      ▼
     │   debt judge         # 게이트 판정
     │      │
     │      ├── exit 0 → 에이전트 행동 허용
     │      └── exit 1 → 에이전트 행동 차단
     │
     └── 부채 없음
            │
            ▼
         debt judge → exit 0 → 통과
```

---

## hook 연동 설정

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
            "command": "debt judge --tool $TOOL_NAME --strict"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": ".*",
        "hooks": [
          {
            "type": "command",
            "command": "debt watch --file $TOOL_OUTPUT --quiet"
          }
        ]
      }
    ]
  }
}
```

---

## 데모 스크립트 (3분)

```bash
# 1. 초기화
debt init

# 2. 에이전트 실행 + 감시
claude "auth 버그 수정해줘" | debt watch

# 3. 부채 확인
debt ls

# 4. 파일 수정 시도 → 차단 확인
debt judge --tool Edit --target src/auth.py
# → exit 1, 차단 메시지 출력

# 5. 부채 상환
debt repay edc-001 --test "pytest tests/"

# 6. 게이트 재확인 → 통과
debt judge
# → exit 0, 통과
```
