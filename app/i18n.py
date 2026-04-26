from __future__ import annotations

from .config import EDCConfig


STRINGS = {
    "app_title": {
        "ko": "Epistemic Debt Compiler",
        "en": "Epistemic Debt Compiler",
    },
    "app_subtitle": {
        "ko": "AI 에이전트의 불확실한 주장과 위험한 행동을 기록하고, 진행 가능 여부를 판정합니다.",
        "en": "Track uncertain AI-agent claims and risky actions, then decide whether execution should proceed.",
    },
    "usage_steps": {"ko": "사용 순서", "en": "Quick Start"},
    "cmd": {"ko": "명령", "en": "Command"},
    "desc": {"ko": "설명", "en": "Description"},
    "init_help": {"ko": "`.edc/`를 만들고 에이전트 연동을 준비합니다.", "en": "Create `.edc/` and prepare agent integration."},
    "clear_help": {"ko": "`.edc/config.json`을 남기고 런타임 데이터만 비웁니다.", "en": "Keep `.edc/config.json` and clear runtime data only."},
    "watch_help": {"ko": "세션 파일이나 stdin 텍스트를 분석합니다.", "en": "Analyze a session file or stdin text."},
    "watch_claude_help": {"ko": "Claude 출력, 세션 입력, 또는 로컬 세션 로그를 분석합니다.", "en": "Analyze Claude output, session input, or a local session log."},
    "watch_gemini_help": {"ko": "Gemini 출력, 세션 입력, 또는 로컬 세션 로그를 분석합니다.", "en": "Analyze Gemini output, session input, or a local session log."},
    "watch_codex_help": {"ko": "Codex 세션 로그를 읽어 분석합니다.", "en": "Read and analyze a Codex session log."},
    "precise_help": {"ko": "--precise  Gemini 재검토 사용", "en": "--precise  Use Gemini review"},
    "claude_session_help": {"ko": "--session  Claude 세션 ID 지정", "en": "--session  Specify the Claude session ID"},
    "gemini_session_help": {"ko": "--session  Gemini 세션 ID 지정", "en": "--session  Specify the Gemini session ID"},
    "session_help": {"ko": "--session  Codex 세션 ID 지정", "en": "--session  Specify the Codex session ID"},
    "ls_help": {"ko": "현재 세션의 인지부채 목록을 봅니다.", "en": "Show epistemic debt items for the current session."},
    "repay_help": {"ko": "증거를 제출해 특정 인지부채를 해소합니다.", "en": "Resolve a debt item by submitting evidence."},
    "judge_help": {"ko": "현재 점수와 규칙 기준으로 진행 가능 여부를 판정합니다.", "en": "Decide whether execution may proceed from current score and rules."},
    "dashboard_help": {
        "ko": "tmux 기반 실시간 대시보드 실행",
        "en": "Launch tmux-based real-time dashboard"
    },
    "explain_help": {"ko": "특정 인지부채의 문맥과 상환 가이드를 봅니다.", "en": "Show context and repayment guidance for a debt item."},
    "setup_gemini_help": {"ko": "Gemini API 키와 모델을 저장해 정밀 분석을 켭니다.", "en": "Save Gemini API settings for precise analysis."},
    "set_language_help": {"ko": "기본 출력 언어를 저장합니다. (`ko` | `en`)", "en": "Save the default output language. (`ko` | `en`)"},
    "runtime_cleared": {"ko": ".edc/ 런타임 데이터 초기화 완료", "en": ".edc/ runtime data cleared"},
    "preserved_config": {"ko": "보존됨: .edc/config.json", "en": "Kept: .edc/config.json"},
    "init_done": {"ko": ".edc/ 초기화 완료", "en": ".edc/ initialized"},
    "claude_hook_done": {"ko": "Claude Code PreToolUse hook 등록 완료", "en": "Claude Code PreToolUse hook registered"},
    "codex_wrapper_done": {"ko": "Codex 래퍼 생성 완료: {path}", "en": "Codex wrapper created: {path}"},
    "start_watch_hint": {"ko": "이제 `debt watch --file <session.json>` 또는 `debt watch-claude --session <id>` 로 시작하세요.", "en": "Start with `debt watch --file <session.json>` or `debt watch-claude --session <id>`."},
    "language_saved": {"ko": "기본 언어 저장 완료  lang={code}", "en": "Default language saved  lang={code}"},
    "unsupported_language": {"ko": "지원하는 언어는 `ko`, `en` 입니다.", "en": "Supported languages are `ko` and `en`."},
    "gemini_missing_key": {"ko": "Gemini API 키가 없습니다. `debt setup-gemini` 또는 GEMINI_API_KEY를 설정하세요.", "en": "Gemini API key not found. Run `debt setup-gemini` or set GEMINI_API_KEY."},
    "rules_missing": {"ko": "rules.json을 찾을 수 없습니다. 프로젝트 루트에서 실행하세요.", "en": "Could not find rules.json. Run from the project root."},
    "init_required": {"ko": ".edc/ 디렉토리가 없습니다. 먼저 `debt init`을 실행하세요.", "en": ".edc/ is missing. Run `debt init` first."},
    "error": {"ko": "오류:", "en": "Error:"},
    "summary": {"ko": "세션 요약", "en": "Session Summary"},
    "detected_none": {"ko": "감지된 인지부채 없음", "en": "No epistemic debt detected"},
    "well_grounded": {"ko": "에이전트가 근거 있게 행동했습니다.", "en": "The agent acted with sufficient grounding."},
    "total_debt": {"ko": "총 인지부채  {count}건  (점수: {score})", "en": "Total debt  {count} items  (score: {score})"},
    "check_ls": {"ko": "`debt ls` 로 전체 목록 확인", "en": "Use `debt ls` to inspect all items"},
    "check_judge": {"ko": "`debt judge` 로 진행 가능 여부 판정", "en": "Use `debt judge` to decide whether execution may proceed"},
    "claim": {"ko": "클레임", "en": "Claim"},
    "risk": {"ko": "리스크", "en": "Risk"},
    "rule": {"ko": "규칙", "en": "Rule"},
    "score": {"ko": "점수", "en": "Score"},
    "source": {"ko": "출처", "en": "Source"},
    "time": {"ko": "시각", "en": "Time"},
    "session": {"ko": "세션", "en": "Session"},
    "reviewer": {"ko": "검토", "en": "Reviewer"},
    "tool": {"ko": "도구", "en": "Tool"},
    "target": {"ko": "대상", "en": "Target"},
    "command": {"ko": "명령", "en": "Command"},
    "reason": {"ko": "판단 근거", "en": "Reason"},
    "context": {"ko": "대화/문맥", "en": "Context"},
    "summary_panel": {"ko": "요약", "en": "Summary"},
    "reason_panel": {"ko": "판단 근거", "en": "Reason"},
    "repay_panel": {"ko": "상환 방법", "en": "Repayment"},
    "resolved_panel": {"ko": "해소 상태", "en": "Resolution"},
    "registered": {"ko": "등록", "en": "Recorded"},
    "evidence": {"ko": "근거", "en": "Evidence"},
    "method": {"ko": "방법", "en": "Method"},
    "resolved_ok": {"ko": "해소됨", "en": "Resolved"},
    "debt_detected": {"ko": "인지부채 감지", "en": "Debt Detected"},
    "action_debt": {"ko": "행동 인지부채", "en": "Action Debt"},
    "content": {"ko": "내용", "en": "Content"},
    "debt_list_title": {"ko": "최신 인지부채  {count}건  (전체 {total}건)", "en": "Latest debt  {count} items  (Total {total})"},
    "more_items": {"ko": "... 외 {count}건의 부채가 더 있습니다. (`debt ls --all`로 전체 확인)", "en": "... and {count} more items. (Use `debt ls --all` to see all)"},
    "id": {"ko": "ID", "en": "ID"},
    "status": {"ko": "상태", "en": "Status"},
    "resolved": {"ko": "해소", "en": "Resolved"},
    "unresolved": {"ko": "미해소", "en": "Open"},
    "high_blocking": {"ko": "HIGH 부채 {count}건 — 파일 수정/명령 실행이 차단됩니다.", "en": "{count} HIGH debt items — file edits and commands are blocked."},
    "repay_hint": {"ko": "상환 가이드가 필요하면 `debt explain <id>`를 실행하세요.", "en": "For repayment guidance, run `debt explain <id>`."},
    "no_debt": {"ko": "미해소 인지부채  없음 ✓", "en": "No open debt ✓"},
    "explain_title": {"ko": "인지부채  {id}", "en": "Debt  {id}"},
    "already_imported_codex": {"ko": "이미 가져온 Codex 세션입니다: {id}", "en": "Codex session already imported: {id}"},
    "stdin_mode": {"ko": "stdin 모드 — 텍스트를 입력하세요 (Ctrl+D로 종료)", "en": "stdin mode — enter text (Ctrl+D to finish)"},
    "force_override": {"ko": "⚠  강제 진행 — 기록됨", "en": "⚠  Forced override — recorded"},
    "gemini_saved": {"ko": "Gemini 설정 저장 완료  model={model} lang={lang}", "en": "Gemini settings saved  model={model} lang={lang}"},
    "gemini_thinking": {"ko": "Gemini가 인지부채를 분석 중입니다...", "en": "Gemini is analyzing the debt..."},
    "high_risk_reason": {"ko": "config, auth, token, password, deploy 같은 민감 경로 수정은 영향 범위가 커서 고위험으로 분류됩니다.", "en": "Sensitive paths such as config, auth, token, password, and deploy are classified as high risk because their blast radius is large."},
    "destructive_reason": {"ko": "데이터나 작업 상태를 크게 훼손할 수 있는 명령 패턴이라 즉시 차단 대상으로 분류됩니다.", "en": "This command pattern can severely damage data or workspace state, so it is classified for immediate blocking."},
    "edit_no_test_reason": {"ko": "테스트 실행 기록 없이 파일을 수정해 변경 근거가 부족한 상태로 분류됩니다.", "en": "A file was edited without any recorded test execution, so the change is treated as insufficiently validated."},
    "retry_same_fix_reason": {"ko": "같은 파일을 반복 수정하고 있어 원인 검증 없이 시행착오를 반복하는 신호로 분류됩니다.", "en": "The same file has been edited repeatedly, which signals trial-and-error changes without validated root cause."},
}


def current_language() -> str:
    return EDCConfig.load().language


def tr(key: str, lang: str | None = None, **kwargs) -> str:
    resolved_lang = lang or current_language()
    template = STRINGS.get(key, {}).get(resolved_lang) or STRINGS.get(key, {}).get("en") or key
    return template.format(**kwargs)
