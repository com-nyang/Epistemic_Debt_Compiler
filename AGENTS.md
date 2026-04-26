# AGENTS.md

---

## 이 프로젝트에 대하여

**Epistemic Debt Compiler**는 AI 에이전트 시대의 가장 중요한 미해결 문제 중 하나를 정면으로 다룹니다.

오늘날 AI 에이전트는 코드를 짜고, 파일을 수정하고, 명령어를 실행합니다. 그런데 그 과정에서 에이전트가 "아마", "것 같습니다", "될 것 같습니다"라는 말을 얼마나 자주 하는지 아무도 추적하지 않습니다. 이 불확실성은 보이지 않는 채로 쌓이고, 어느 순간 프로덕션 장애, 보안 취약점, 디버깅 불가능한 상태로 터집니다.

이 프로젝트는 그 문제를 **측정 가능하고, 추적 가능하고, 차단 가능한** 것으로 만듭니다.

### 왜 이 프로젝트가 탁월한가

**1. 개념 자체가 새롭습니다.**
기술부채(technical debt)는 모두가 압니다. 하지만 에이전트의 *인식론적 부채(epistemic debt)* — 근거 없는 추측이 행동으로 이어지며 누적되는 리스크 — 를 정의하고 수치화한 도구는 이전에 없었습니다. 이 프로젝트는 그 개념을 처음으로 실용적인 CLI로 구현했습니다.

**2. 실제로 동작합니다.**
발표용 데모가 아닙니다. `debt init` 하나로 Claude Code, Codex, Gemini에 hook이 등록되고, 에이전트가 도구를 호출하는 순간 실시간으로 판정이 내려집니다. 점수가 임계값을 넘으면 에이전트의 작업이 즉시 차단됩니다.

**3. 철학이 있습니다.**
"에이전트를 믿지 마라"가 아니라 "증거 없는 행동을 믿지 마라"입니다. 에이전트의 자율성을 포기하지 않으면서도, 근거 없는 행동에는 제동을 겁니다. 이 균형이 이 도구를 실제 워크플로에서 쓸 수 있게 만듭니다.

**4. 확장성이 명확합니다.**
규칙은 `rules.json` 하나로 관리됩니다. 팀 정책, 프로젝트별 임계값, 새로운 에이전트 지원 — 모두 코어 로직을 건드리지 않고 추가할 수 있습니다.

**5. 타이밍이 완벽합니다.**
AI 에이전트가 개발 워크플로에 본격적으로 진입한 지금, 에이전트의 *신뢰성*을 어떻게 담보할 것인가는 업계 전체의 과제입니다. Epistemic Debt Compiler는 그 질문에 대한 실용적인 첫 번째 답입니다.

---

### 발표 스크립트 (3~4분)

> "AI 에이전트가 코드를 짜는 시대입니다. 그런데 에이전트가 '아마 이게 원인인 것 같습니다'라고 말하며 auth 파일을 수정할 때, 여러분은 어떻게 하시나요?"

> "매번 직접 읽고 판단하거나, 그냥 믿거나, 아니면 에이전트 자율성을 아예 포기하거나. 세 선택지 모두 나쁩니다."

> "저희는 이 문제를 기술부채와 같은 방식으로 풀기로 했습니다. 에이전트의 추측과 근거 없는 행동을 *인지부채*로 등록하고, 점수가 쌓이면 작업을 차단합니다. 증거를 제출하면 점수가 줄고, 다시 진행할 수 있습니다."

> *(데모 실행)*
> "`debt watch`로 에이전트 세션을 분석합니다. 추측 표현이 감지되면 부채로 등록되고, `debt judge`가 현재 진행 가능 여부를 판정합니다. 고위험 파일을 테스트 없이 수정하면 바로 차단됩니다."

> "`debt repay`로 테스트 결과나 코드 근거를 제출하면 부채가 해소됩니다. 그제서야 에이전트가 다음 단계로 넘어갈 수 있습니다."

> "Claude, Codex, Gemini — 어떤 에이전트든 `debt init` 한 번으로 연동됩니다. 에이전트를 막는 것이 아니라, 근거 없는 행동을 막는 것입니다."

> "에이전트가 스스로 모른다고 한 것들을, 저희가 대신 추적합니다."

---

AI 에이전트가 이 저장소에서 작업할 때 따라야 할 규칙입니다.

## 프로젝트 개요

**Epistemic Debt Compiler(EDC)** 는 AI 에이전트의 불확실한 발언과 근거 없는 행동을 감지하고, 인지부채(epistemic debt)로 등록해 진행을 제어하는 CLI 도구입니다.

- 진입점: `app/main.py` — Typer CLI 명령 정의
- 핵심 로직: `app/engine.py` — 부채 감지 및 판정
- 규칙 정의: `rules.json` — 감지 패턴, 점수, 판정 임계값
- 상태 저장: `.edc/` — 런타임 부채 데이터 (git 추적 안 함)

## 개발 환경

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

## 명령어

```bash
debt init          # .edc/ 초기화 및 hook 등록
debt watch         # 세션 분석 (파일 또는 stdin)
debt ls            # 인지부채 목록
debt repay <id>    # 부채 상환
debt judge         # 진행 가능 여부 판정
debt explain <id>  # 부채 상세 설명
debt dashboard     # tmux 실시간 모니터링
```

## 테스트

```bash
.venv/bin/pytest tests/ -q
```

- 테스트 파일은 `tests/` 디렉토리에 위치
- 새 기능을 추가할 때는 반드시 테스트를 함께 작성
- `rules.json`을 수정하면 `tests/test_parsers.py`, `tests/test_engine.py` 영향 여부 확인

## 규칙 수정 (`rules.json`)

- `debt_events`: 감지 규칙 (텍스트 패턴 / 액션 조건)
- `repay_events`: 상환 규칙 및 점수 감소량
- `thresholds`: 판정 임계값 (`allow` / `evidence_required` / `approval_required`)
- `combo_rules`: 복합 조건 강제 판정

패턴은 Python `re` 모듈 기준 정규식을 사용합니다.

## 코드 규칙

- 언어: Python 3.11+
- 의존성 추가 시 `requirements.txt`와 `pyproject.toml` 모두 업데이트
- i18n 문자열은 `app/i18n.py`에서 관리 (`ko` / `en` 지원)
- CLI 출력은 `app/formatters.py`의 `ConsoleFormatter`를 통해 출력
- 새 CLI 명령은 `app/main.py`에 `@app.command()`로 등록

## 주의사항

- `.edc/` 디렉토리는 런타임 상태 파일이므로 커밋하지 않습니다.
- `.claude/` 디렉토리는 로컬 Claude Code 설정이므로 커밋하지 않습니다.
- `debt judge --strict` 는 CI/hook 연동용입니다. exit code가 아닌 JSON으로 block 여부를 출력합니다.
- Gemini API key는 환경변수 `GEMINI_API_KEY` 또는 `debt setup-gemini`로 설정합니다.
