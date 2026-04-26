"""
Epistemic Debt Compiler — CLI 진입점.

명령어:
  debt init     프로젝트 초기화
  debt watch    에이전트 세션 분석 (파일 또는 stdin)
  debt ls       현재 인지부채 목록
  debt repay    인지부채 상환
  debt judge    진행 가능 여부 판정 (hook/CI 연동)
  debt explain  특정 부채 상세 설명

---

Epistemic Debt Compiler는 AI 에이전트 시대의 가장 중요한 미해결 문제 중 하나를
정면으로 다룹니다.

오늘날 AI 에이전트는 코드를 짜고, 파일을 수정하고, 명령어를 실행합니다.
그런데 그 과정에서 에이전트가 "아마", "것 같습니다", "될 것 같습니다"라는 말을
얼마나 자주 하는지 아무도 추적하지 않습니다. 이 불확실성은 보이지 않는 채로
쌓이고, 어느 순간 프로덕션 장애, 보안 취약점, 디버깅 불가능한 상태로 터집니다.

이 프로젝트는 그 문제를 측정 가능하고, 추적 가능하고, 차단 가능한 것으로 만듭니다.

왜 이 프로젝트가 탁월한가:

1. 개념 자체가 새롭습니다.
   기술부채(technical debt)는 모두가 압니다. 하지만 에이전트의 인식론적 부채
   (epistemic debt) — 근거 없는 추측이 행동으로 이어지며 누적되는 리스크 — 를
   정의하고 수치화한 도구는 이전에 없었습니다.

2. 실제로 동작합니다.
   발표용 데모가 아닙니다. debt init 하나로 Claude Code, Codex, Gemini에 hook이
   등록되고, 에이전트가 도구를 호출하는 순간 실시간으로 판정이 내려집니다.

3. 철학이 있습니다.
   "에이전트를 믿지 마라"가 아니라 "증거 없는 행동을 믿지 마라"입니다.
   에이전트의 자율성을 포기하지 않으면서도, 근거 없는 행동에는 제동을 겁니다.

4. 확장성이 명확합니다.
   규칙은 rules.json 하나로 관리됩니다. 팀 정책, 프로젝트별 임계값, 새로운
   에이전트 지원 — 모두 코어 로직을 건드리지 않고 추가할 수 있습니다.

5. 타이밍이 완벽합니다.
   AI 에이전트가 개발 워크플로에 본격적으로 진입한 지금, 에이전트의 신뢰성을
   어떻게 담보할 것인가는 업계 전체의 과제입니다.
   Epistemic Debt Compiler는 그 질문에 대한 실용적인 첫 번째 답입니다.

에이전트가 스스로 모른다고 한 것들을, 우리가 대신 추적합니다.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from .config import EDCConfig
from .claude_sessions import load_claude_session
from .codex_sessions import load_codex_session
from .gemini_sessions import load_gemini_session
from .engine import RuleEngine
from .formatters import ConsoleFormatter
from .gemini import GeminiDebtReviewer, gemini_api_key_from_env
from .i18n import current_language, tr
from .models import RiskLevel, SessionInput, Verdict
from .parsers import ActionClassifier, RuleBasedClassifier
from .registry import DebtRegistry, EDC_DIR
from .rules import Rules
from .hooks import register_claude_hook, register_codex_wrapper

LANG = current_language()

app = typer.Typer(
    name="debt",
    help=(
        f"{tr('app_title', LANG)}\n\n"
        f"{tr('app_subtitle', LANG)}"
    ),
    no_args_is_help=False,
    add_completion=False,
)
console = Console()
fmt     = ConsoleFormatter()


@app.callback(invoke_without_command=True)
def root(
    ctx: typer.Context,
    set_language: Optional[str] = typer.Option(None, "--set-language", help=tr("set_language_help", LANG)),
):
    """명령 없이 실행하면 커스텀 홈 화면을 출력한다."""
    if set_language:
        if set_language not in {"ko", "en"}:
            fmt.error(tr("unsupported_language"))
            raise typer.Exit(2)
        config = EDCConfig.load()
        config.language = set_language
        config.gemini.language = set_language
        config.save()
        console.print(f"\n  [green]✓[/green] {tr('language_saved', set_language, code=set_language)}\n")
        raise typer.Exit(0)
    if ctx.invoked_subcommand is None and "--help" not in sys.argv[1:]:
        fmt.cli_home()
        raise typer.Exit(0)


# ── 공통 헬퍼 ────────────────────────────────────────────────────────────────

def _find_rules_path() -> Path:
    """rules.json을 현재 디렉토리 → 패키지 디렉토리 순서로 탐색한다."""
    local = Path("rules.json")
    if local.exists():
        return local
    pkg = Path(__file__).parent.parent / "rules.json"
    if pkg.exists():
        return pkg
    fmt.error(tr("rules_missing", LANG))
    raise typer.Exit(2)


def _require_init() -> None:
    """초기화 여부를 확인하고, 안 되어 있으면 오류를 출력하고 종료한다."""
    if not DebtRegistry.is_initialized():
        fmt.error(tr("init_required", LANG))
        raise typer.Exit(2)


def _load_engine(precise: bool = False) -> tuple[RuleEngine, DebtRegistry]:
    """Rules, Registry, Engine을 조립해서 반환한다."""
    rules      = Rules.load(_find_rules_path())
    registry   = DebtRegistry()
    classifier = RuleBasedClassifier(rules)
    action_cls = ActionClassifier(rules)
    reviewer   = _load_reviewer(precise)
    engine     = RuleEngine(rules, classifier, action_cls, registry, reviewer=reviewer)
    return engine, registry


def _load_reviewer(precise: bool):
    if not precise:
        return None

    config = EDCConfig.load()
    api_key = config.gemini.api_key or gemini_api_key_from_env()
    if not api_key:
        fmt.error(tr("gemini_missing_key", LANG))
        raise typer.Exit(2)

    model = config.gemini.model if config.gemini.enabled else "gemini-2.5-flash"
    language = config.gemini.language if config.gemini.enabled else "ko"
    return GeminiDebtReviewer(api_key=api_key, model=model, language=language)


def _get_or_create_session(registry: DebtRegistry):
    """현재 세션을 반환하거나 새로 생성한다."""
    session = registry.current_session()
    if not session:
        session = registry.create_session(str(Path.cwd()))
    return session


# ── debt init ────────────────────────────────────────────────────────────────

@app.command(help=tr("init_help", LANG))
def init(
    hook: bool = typer.Option(True, "--hook/--no-hook", help="Claude Code hook auto-registration" if LANG == "en" else "Claude Code hook 자동 등록 여부"),
    codex: bool = typer.Option(False, "--codex/--no-codex", help="Create Codex CLI wrapper" if LANG == "en" else "Codex CLI 래퍼 생성 여부"),
):
    """프로젝트에 .edc/ 초기화 및 에이전트 연동 설정."""
    DebtRegistry.init()
    console.print(f"\n  [green]✓[/green] {tr('init_done', LANG)}")

    # Claude Code settings.json에 PreToolUse hook 등록
    if hook:
        settings_path = Path(".claude/settings.json")
        register_claude_hook(settings_path)
        console.print(f"  [green]✓[/green] {tr('claude_hook_done', LANG)}")

    # Codex CLI용 래퍼 스크립트 생성
    if codex:
        script_path = register_codex_wrapper(Path(".edc/codex-exec"))
        console.print(f"  [green]✓[/green] {tr('codex_wrapper_done', LANG, path=f'[bold]{script_path}[/bold]')}")

    console.print(f"\n  [dim]{tr('start_watch_hint', LANG)}[/dim]\n")


@app.command(help=tr("clear_help", LANG))
def clear():
    """`.edc/config.json`을 제외한 런타임 데이터를 초기화한다."""
    _require_init()
    DebtRegistry.clear(keep_files={"config.json"})
    console.print(f"\n  [green]✓[/green] {tr('runtime_cleared', LANG)}")
    console.print(f"  [dim]{tr('preserved_config', LANG)}[/dim]\n")




# ── debt watch ───────────────────────────────────────────────────────────────

@app.command(
    help=(
        f"{tr('watch_help', LANG)}\n"
        f"  {'옵션' if LANG == 'ko' else 'Options'}:\n"
        f"    {tr('precise_help', LANG)}"
    )
)
def watch(
    file:    Optional[Path] = typer.Option(None,  "--file",    "-f", help="JSON session file to analyze" if LANG == "en" else "분석할 JSON 세션 파일"),
    dry_run: bool           = typer.Option(False, "--dry-run",        help="Detect only; do not persist" if LANG == "en" else "감지만, 등록 안 함"),
    quiet:   bool           = typer.Option(False, "--quiet",   "-q", help="Hide agent output" if LANG == "en" else "에이전트 출력 숨김"),
    precise: bool           = typer.Option(False, "--precise", help="Recheck rule detections with Gemini" if LANG == "en" else "Gemini로 규칙 감지를 재검증"),
):
    """
    에이전트 출력(JSON 세션 파일 또는 stdin 텍스트)을 분석해서 인지부채를 등록한다.

    \b
    JSON 파일 모드:
      debt watch --file examples/session.json

    stdin 텍스트 모드:
      echo "I think this is the bug" | debt watch
      claude "버그 수정해줘" | debt watch
    """
    _run_watch(file=file, dry_run=dry_run, quiet=quiet, precise=precise)


@app.command(
    "watch-claude",
    help=(
        f"{tr('watch_claude_help', LANG)}\n"
        f"  {'옵션' if LANG == 'ko' else 'Options'}:\n"
        f"    {tr('claude_session_help', LANG)}\n"
        f"    {tr('precise_help', LANG)}"
    ),
)
def watch_claude(
    file:    Optional[Path] = typer.Option(None,  "--file",    "-f", help="JSON session file to analyze" if LANG == "en" else "분석할 JSON 세션 파일"),
    session_id: Optional[str] = typer.Option(None, "--session", help="Claude session ID" if LANG == "en" else "Claude 세션 ID"),
    dry_run: bool           = typer.Option(False, "--dry-run",        help="Detect only; do not persist" if LANG == "en" else "감지만, 등록 안 함"),
    quiet:   bool           = typer.Option(False, "--quiet",   "-q", help="Hide agent output" if LANG == "en" else "에이전트 출력 숨김"),
    precise: bool           = typer.Option(False, "--precise", help="Recheck rule detections with Gemini" if LANG == "en" else "Gemini로 규칙 감지를 재검증"),
):
    if session_id:
        _require_init()
        engine, registry = _load_engine(precise=precise)
        session = _get_or_create_session(registry)

        try:
            session_input = load_claude_session(session_id)
        except Exception as e:
            fmt.error(str(e))
            raise typer.Exit(1)

        _watch_session_input(session_input, engine, registry, session, dry_run, quiet)
        return

    _run_watch(file=file, dry_run=dry_run, quiet=quiet, precise=precise)


@app.command(
    "watch-gemini",
    help=(
        f"{tr('watch_gemini_help', LANG)}\n"
        f"  {'옵션' if LANG == 'ko' else 'Options'}:\n"
        f"    {tr('gemini_session_help', LANG)}\n"
        f"    {tr('precise_help', LANG)}"
    ),
)
def watch_gemini(
    file:    Optional[Path] = typer.Option(None,  "--file",    "-f", help="JSON session file to analyze" if LANG == "en" else "분석할 JSON 세션 파일"),
    session_id: Optional[str] = typer.Option(None, "--session", help="Gemini session ID" if LANG == "en" else "Gemini 세션 ID"),
    dry_run: bool           = typer.Option(False, "--dry-run",        help="Detect only; do not persist" if LANG == "en" else "감지만, 등록 안 함"),
    quiet:   bool           = typer.Option(False, "--quiet",   "-q", help="Hide agent output" if LANG == "en" else "에이전트 출력 숨김"),
    precise: bool           = typer.Option(False, "--precise", help="Recheck rule detections with Gemini" if LANG == "en" else "Gemini로 규칙 감지를 재검증"),
):
    if session_id:
        _require_init()
        engine, registry = _load_engine(precise=precise)
        session = _get_or_create_session(registry)

        try:
            session_input = load_gemini_session(session_id)
        except Exception as e:
            fmt.error(str(e))
            raise typer.Exit(1)

        _watch_session_input(session_input, engine, registry, session, dry_run, quiet)
        return

    _run_watch(file=file, dry_run=dry_run, quiet=quiet, precise=True)


def _run_watch(file: Optional[Path], dry_run: bool, quiet: bool, precise: bool) -> None:
    _require_init()
    engine, registry = _load_engine(precise=precise)
    session = _get_or_create_session(registry)

    if file:
        _watch_json_file(file, engine, registry, session, dry_run, quiet)
    else:
        _watch_stdin(engine, registry, session, dry_run)


def _watch_json_file(file, engine, registry, session, dry_run, quiet):
    """JSON 세션 파일을 읽어서 각 이벤트를 순서대로 처리한다."""
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
        session_input = SessionInput(**data)
    except Exception as e:
        fmt.error(f"JSON 파일 파싱 실패: {e}")
        raise typer.Exit(1)

    _watch_session_input(session_input, engine, registry, session, dry_run, quiet)


def _watch_session_input(session_input, engine, registry, session, dry_run, quiet):
    """SessionInput 객체를 읽어서 각 이벤트를 순서대로 처리한다."""
    if session_input.description and not quiet:
        console.print(f"\n  [bold]{session_input.description}[/bold]")

    if not quiet:
        console.print(f"\n  [dim]세션 ID: {session.id} | 이벤트: {len(session_input.events)}개[/dim]")
        console.print()

    all_new_events = []

    for raw in session_input.events:

        # ── message: 에이전트 텍스트 분석 ──────────────────────────────────
        if raw.type == "message" and raw.content:
            if not quiet:
                fmt.event_passthrough(f"[agent] {raw.content}")
            if not dry_run:
                events = engine.process_text(
                    raw.content,
                    session,
                    source_timestamp=raw.timestamp,
                    source_session_id=session_input.source_id,
                )
                for ev in events:
                    fmt.detection_alert(ev)
                    all_new_events.append(ev)

        # ── action: 도구 호출 분석 ─────────────────────────────────────────
        elif raw.type == "action" and raw.tool:
            target  = raw.target or ""
            command = raw.command or ""
            if not quiet:
                label = target or command or raw.tool
                fmt.event_passthrough(f"[{raw.tool}] {label}")
            if not dry_run:
                events = engine.process_action(
                    tool=raw.tool,
                    target=target,
                    command=command,
                    session=session,
                    source_timestamp=raw.timestamp,
                    source_session_id=session_input.source_id,
                )
                for ev in events:
                    fmt.action_alert(ev)
                    all_new_events.append(ev)

        # ── test: 테스트 실행 결과 기록 ────────────────────────────────────
        elif raw.type == "test":
            cmd       = raw.command or "test"
            exit_code = raw.exit_code if raw.exit_code is not None else 0
            if not quiet:
                fmt.test_result(cmd, exit_code, raw.output or "")
            if not dry_run:
                engine.record_test_run(session, exit_code)

        # ── file_change: 파일 수정 이벤트 ─────────────────────────────────
        elif raw.type == "file_change":
            path = raw.path or raw.target or ""
            if not quiet:
                fmt.event_passthrough(f"[file_change] {path}")
            if not dry_run:
                events = engine.process_action(
                    tool="Edit",
                    target=path,
                    command="",
                    session=session,
                    source_timestamp=raw.timestamp,
                    source_session_id=session_input.source_id,
                )
                for ev in events:
                    fmt.action_alert(ev)
                    all_new_events.append(ev)

    fmt.watch_summary(all_new_events, session.debt_score)


@app.command(
    "watch-codex",
    help=(
        f"{tr('watch_codex_help', LANG)}\n"
        f"  {'옵션' if LANG == 'ko' else 'Options'}:\n"
        f"    {tr('session_help', LANG)}\n"
        f"    {tr('precise_help', LANG)}"
    ),
)
def watch_codex(
    session_id: str = typer.Option(..., "--session", help="Codex session ID" if LANG == "en" else "Codex 세션 ID"),
    dry_run: bool   = typer.Option(False, "--dry-run", help="Detect only; do not persist" if LANG == "en" else "감지만, 등록 안 함"),
    quiet: bool     = typer.Option(True, "--quiet/--no-quiet", "-q", help="Hide raw session output" if LANG == "en" else "원문 세션 출력 숨김"),
    precise: bool   = typer.Option(False, "--precise", "--ai", help="Recheck rule detections with Gemini" if LANG == "en" else "Gemini로 규칙 감지를 재검증"),
):
    """
    Codex 세션 ID를 읽어 .codex/sessions JSONL을 분석하고 인지부채를 등록한다.

    \b
    예시:
      debt watch-codex --session 019dc74f-e4f0-74c2-acf5-05119b3132a2
    """
    _require_init()
    engine, registry = _load_engine(precise=precise)
    session = _get_or_create_session(registry)

    try:
        session_input = load_codex_session(session_id)
    except Exception as e:
        fmt.error(str(e))
        raise typer.Exit(1)

    if session_input.source_id and session_input.source_id in session.imported_codex_sessions:
        fmt.info(f"이미 가져온 Codex 세션입니다: {session_input.source_id}")
        raise typer.Exit(0)

    _watch_session_input(session_input, engine, registry, session, dry_run, quiet)

    if session_input.source_id and not dry_run:
        session.imported_codex_sessions.append(session_input.source_id)
        registry.save_session(session)


def _watch_stdin(engine, registry, session, dry_run):
    """stdin에서 텍스트(또는 JSONL)를 줄 단위로 읽어서 분석한다 (pipe 모드)."""
    console.print(f"\n  [dim]stdin 모드 — 텍스트를 입력하세요 (Ctrl+D로 종료)[/dim]\n")
    all_new_events = []

    for line in sys.stdin:
        line = line.rstrip()
        if not line:
            continue

        text_to_process = line
        actions_to_process = []
        
        # JSONL 지원 (Claude, Codex, Gemini 로그 등)
        try:
            row = json.loads(line)
            if not isinstance(row, dict):
                raise json.JSONDecodeError("not a dict", line, 0)

            row_type = row.get("type")

            # Claude Code 포맷
            if row_type == "assistant":
                text_to_process = ""
                msg = row.get("message") or {}
                content_list = msg.get("content") if isinstance(msg, dict) else None
                if isinstance(content_list, list):
                    from .claude_sessions import _parse_assistant_message, _shell_command_from_input
                    text_parts = []
                    for item in content_list:
                        item_type = item.get("type")
                        if item_type in {"text", "output_text"} and item.get("text"):
                            text_parts.append(item["text"])
                        elif item_type == "tool_use":
                            tool_name = item.get("name", "")
                            tool_input = item.get("input") or {}
                            if tool_name.lower() == "bash":
                                cmd = _shell_command_from_input(tool_input)
                                if cmd:
                                    actions_to_process.append(("Bash", "", cmd))
                            elif tool_name.lower() in {"edit", "write"}:
                                target = (
                                    tool_input.get("file_path")
                                    or tool_input.get("path")
                                    or tool_input.get("target") or ""
                                )
                                if target:
                                    actions_to_process.append((tool_name.capitalize(), target, ""))
                    from .claude_sessions import _clean_assistant_text
                    text_to_process = _clean_assistant_text("\n".join(text_parts))

            # Gemini 포맷
            elif row_type == "gemini":
                content = row.get("content")
                if isinstance(content, str):
                    text_to_process = content
                elif isinstance(content, list) and content and "text" in content[0]:
                    text_to_process = content[0]["text"]
                else:
                    text_to_process = ""
                for call in row.get("toolCalls", []):
                    if call.get("name") == "run_shell_command":
                        cmd = call.get("args", {}).get("command")
                        if cmd:
                            actions_to_process.append(("Bash", "", cmd))

            # Codex 포맷
            elif row_type == "response_item":
                payload = row.get("payload", {})
                if payload.get("type") == "message" and payload.get("role") == "assistant":
                    content_list = payload.get("content", [])
                    if content_list and content_list[0].get("type") == "output_text":
                        text_to_process = content_list[0].get("text", "")

            # 인식되지 않는 JSON → 건너뜀
            else:
                text_to_process = ""

        except json.JSONDecodeError:
            pass  # 단순 텍스트로 처리

        if not dry_run:
            # 텍스트 처리
            if text_to_process.strip():
                events = engine.process_text(text_to_process, session)
                for ev in events:
                    fmt.detection_alert(ev)
                    all_new_events.append(ev)
            
            # 액션 처리
            for tool, target, cmd in actions_to_process:
                events = engine.process_action(
                    tool=tool,
                    target=target,
                    command=cmd,
                    session=session,
                )
                for ev in events:
                    fmt.action_alert(ev)
                    all_new_events.append(ev)

    fmt.watch_summary(all_new_events, session.debt_score)


# ── debt ls ──────────────────────────────────────────────────────────────────

@app.command(name="ls", help=tr("ls_help", LANG))
def list_debts(
    risk:        Optional[str] = typer.Option(None,  "--risk",  help="리스크 필터: HIGH | MEDIUM | LOW"),
    show_all:    bool          = typer.Option(False, "--all",   "-a", help="해소된 항목 포함"),
    limit:       int           = typer.Option(10,    "--limit", "-l", help="출력할 항목 개수 제한 (최신순)"),
    json_output: bool          = typer.Option(False, "--json",  help="JSON 형식 출력"),
):
    """현재 세션의 인지부채 목록을 출력한다."""
    _require_init()
    _, registry = _load_engine()
    session = registry.current_session()

    if not session:
        fmt.info("세션 없음. `debt watch --file <session.json>` 을 먼저 실행하세요.")
        raise typer.Exit(0)

    risk_filter = RiskLevel(risk.upper()) if risk else None
    events = registry.get_session_events(
        session.id,
        unresolved_only=not show_all,
        risk_filter=risk_filter,
    )

    # 제한 적용
    if limit > 0:
        events = events[:limit]

    if json_output:
        # Rich console를 거치지 않고 stdout에 직접 출력 (제어 문자 방지)
        sys.stdout.write(json.dumps([e.model_dump(mode="json") for e in events], indent=2, ensure_ascii=False) + "\n")
    else:
        fmt.debt_list(events, session.debt_score)


# ── debt repay ───────────────────────────────────────────────────────────────

@app.command(help=tr("repay_help", LANG))
def repay(
    event_id: str           = typer.Argument(..., metavar="ID", help="상환할 인지부채 ID (예: edc-abc123)"),
    test:     Optional[str] = typer.Option(None, "--test",   help="테스트 명령 실행 후 해소 (exit 0이면 자동 해소)"),
    code:     Optional[str] = typer.Option(None, "--code",   help="코드 위치 참조 (예: src/auth.py:42)"),
    doc:      Optional[str] = typer.Option(None, "--doc",    help="문서/RFC 참조"),
    log:      Optional[str] = typer.Option(None, "--log",    help="로그 파일 참조 (예: error.log:88)"),
    manual:   Optional[str] = typer.Option(None, "--manual", help="직접 확인 메모"),
):
    """
    증거를 제출하여 인지부채를 상환한다.

    \b
    예시:
      debt repay edc-abc123 --test "pytest tests/auth_test.py"
      debt repay edc-abc123 --code "src/auth.py:42"
      debt repay edc-abc123 --doc "RFC-1234: 이 함수는 항상 None을 반환"
      debt repay edc-abc123 --manual "로컬에서 직접 재현 확인"
    """
    _require_init()
    engine, registry = _load_engine()
    session = registry.current_session()

    if not session:
        fmt.error("세션 없음.")
        raise typer.Exit(1)

    repay_id, evidence, run_cmd = _resolve_repay_args(test, code, doc, log, manual)
    if not repay_id:
        fmt.error("상환 유형을 지정하세요 (--test / --code / --doc / --log / --manual)")
        raise typer.Exit(1)

    # --test: 실제 명령 실행 전 사용자에게 확인
    if run_cmd:
        console.print(f"\n  실행 중... [dim]{run_cmd}[/dim]")

    result = engine.process_repayment(
        event_id=event_id,
        repay_id=repay_id,
        evidence=evidence,
        session=session,
        run_command=run_cmd,
    )
    fmt.repay_result(result)
    raise typer.Exit(0 if result.success else 1)


def _resolve_repay_args(
    test: Optional[str], code: Optional[str],
    doc:  Optional[str], log:  Optional[str], manual: Optional[str],
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """(repay_id, evidence, run_command) 튜플 반환."""
    if test:   return "TEST_PASS",     test,   test
    if code:   return "GREP_EVIDENCE", code,   None
    if doc:    return "DOC_REFERENCE", doc,    None
    if log:    return "LOG_EVIDENCE",  log,    None
    if manual: return "MANUAL_CONFIRM", manual, None
    return None, None, None


# ── debt judge ───────────────────────────────────────────────────────────────

@app.command(help=tr("judge_help", LANG))
def judge(
    tool:    Optional[str] = typer.Option(None,  "--tool",    help="판정할 도구 이름 (Edit|Write|Bash)"),
    target:  Optional[str] = typer.Option(None,  "--target",  help="대상 파일/경로"),
    command: Optional[str] = typer.Option(None,  "--command", help="실행할 명령어 (Bash hook용)"),
    strict:  bool          = typer.Option(False, "--strict",  help="비대화형 모드 (CI/hook 용)"),
    force:   bool          = typer.Option(False, "--force",   help="BLOCK 무시 강제 진행 (기록됨)"),
):
    """
    현재 인지부채 상태를 기반으로 진행 가능 여부를 판정한다.

    \b
    exit 0: 통과 (ALLOW / EVIDENCE_REQUIRED)
    exit 1: 차단 (BLOCK)

    Claude Code hook 연동:
      debt judge --tool Edit --strict
    """
    _require_init()
    engine, registry = _load_engine()
    session = registry.current_session()

    if not session:
        if not strict:
            fmt.info("세션 없음. 판정 불가.")
        raise typer.Exit(2)

    # hook에서 --tool 플래그로 실시간 액션 전달 시 즉시 분석
    # stdin에 Claude Code가 보낸 JSON이 있으면 command/target 자동 추출
    if tool:
        resolved_command = command or ""
        resolved_target  = target  or ""

        if not resolved_command and not resolved_target and not sys.stdin.isatty():
            try:
                payload = json.loads(sys.stdin.read())
                tool_input = payload.get("tool_input", {})
                resolved_command = tool_input.get("command", "")
                resolved_target  = tool_input.get("path", "") or tool_input.get("file_path", "")
            except (json.JSONDecodeError, OSError):
                pass

        engine.process_action(
            tool=tool,
            target=resolved_target,
            command=resolved_command,
            session=session,
        )

    result = engine.get_verdict(session)

    # 강제 진행: BLOCK이어도 통과, 단 기록됨
    if force and result.verdict.blocks:
        session.force_overrides += 1
        registry.save_session(session)
        if not strict:
            fmt.verdict_result(result)
            console.print("  [yellow]⚠  강제 진행 — 기록됨[/yellow]\n")
        raise typer.Exit(0)

    # strict + BLOCK: Claude Code hook 프로토콜
    if strict and result.verdict.blocks:
        print(json.dumps({"decision": "block", "reason": f"[EDC] {result.reason}"}, ensure_ascii=False))
        raise typer.Exit(0)

    if not strict:
        fmt.verdict_result(result)

    raise typer.Exit(result.verdict.exit_code)


# ── debt dashboard ───────────────────────────────────────────────────────────

@app.command(help=tr("dashboard_help", LANG))
def dashboard(
    session_id: Optional[str] = typer.Argument(None, help="Session ID or log file path"),
    type: str = typer.Option("codex", "--type", "-t", help="Agent type: codex | claude | gemini"),
):
    """
    tmux 기반의 실시간 모니터링 대시보드를 실행한다.

    \b
    예시:
      debt dashboard 019dc74f
      debt dashboard --type gemini latest
      debt dashboard --type claude abc123
    """
    _require_init()
    
    target_file: Optional[Path] = None
    
    if session_id:
        path = Path(session_id)
        if path.exists() and path.is_file():
            target_file = path
        else:
            try:
                if type.lower() == "claude":
                    from .claude_sessions import find_claude_session_file
                    target_file = find_claude_session_file(session_id)
                else:
                    from .codex_sessions import find_session_file
                    target_file = find_session_file(session_id, agent_type=type)
            except Exception as e:
                fmt.error(str(e))
                raise typer.Exit(1)
    elif type.lower() == "claude":
        # session_id 없이 --type claude → 현재 프로젝트의 가장 최근 세션
        from .claude_sessions import CLAUDE_SESSIONS_DIR
        project_key = "-" + str(Path.cwd()).replace("/", "-").replace("_", "-").lstrip("-")
        project_dir = CLAUDE_SESSIONS_DIR / project_key
        matches = sorted(project_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not matches:
            fmt.error(f"Claude 세션 파일을 찾을 수 없습니다: {project_dir}")
            raise typer.Exit(1)
        target_file = matches[0]

    if not target_file:
        fmt.error("세션 ID 또는 로그 파일 경로를 입력하세요.")
        raise typer.Exit(1)

    # 대시보드 스크립트 실행
    script_path = Path(__file__).parent.parent / "debt-dashboard.sh"
    if not script_path.exists():
        fmt.error("대시보드 스크립트를 찾을 수 없습니다.")
        raise typer.Exit(1)

    console.print(f"\n  [bold blue]대시보드 실행 중...[/bold blue] [dim]파일: {target_file}[/dim]\n")
    
    # tmux 실행 (현재 프로세스 대체)
    os.execv("/usr/bin/bash", ["bash", str(script_path), str(target_file)])


# ── debt explain ─────────────────────────────────────────────────────────────

@app.command(help=tr("explain_help", LANG))
def explain(
    event_id: str = typer.Argument(..., metavar="ID", help="상세 조회할 인지부채 ID"),
    use_ai: bool = typer.Option(False, "--ai", "--gemini", help="Gemini AI를 사용해 상세 분석 및 가이드를 생성한다."),
):
    """특정 인지부채의 상세 정보와 상환 가이드를 출력한다."""
    _require_init()
    _, registry = _load_engine()

    event = registry.get_event(event_id)
    if not event:
        fmt.error(f"'{event_id}'를 찾을 수 없습니다. `debt ls`로 ID를 확인하세요.")
        raise typer.Exit(1)

    # Gemini AI 상세 분석 요청
    if use_ai:
        config = EDCConfig.load()
        api_key = config.gemini.api_key or gemini_api_key_from_env()
        
        if not api_key:
            fmt.error(tr("gemini_missing_key", LANG))
            raise typer.Exit(2)

        with console.status(f"[bold blue]{tr('gemini_thinking', LANG)}[/bold blue]"):
            from .gemini import GeminiDebtReviewer
            model = config.gemini.model if config.gemini.enabled else "gemini-2.0-flash"
            reviewer = GeminiDebtReviewer(api_key=api_key, model=model, language=LANG)
            
            ai_analysis = reviewer.analyze_debt(event)
            event.reviewer_reason = ai_analysis
            event.reviewer = "Gemini AI"

    fmt.explain_event(event)



@app.command("setup-gemini", help=tr("setup_gemini_help", LANG))
def setup_gemini(
    api_key: str = typer.Option(
        ...,
        "--api-key",
        prompt=True,
        hide_input=True,
        confirmation_prompt=True,
        help="Gemini API key",
    ),
    model: str = typer.Option("gemini-2.0-flash", "--model", help="Gemini model name"),
    lang: str = typer.Option("ko", "--lang", help="Gemini explanation language: ko | en"),
):
    """Gemini API 기반 정밀 분석 설정을 저장한다."""
    _require_init()
    if lang not in {"ko", "en"}:
        fmt.error("지원하는 언어는 `ko`, `en` 입니다.")
        raise typer.Exit(2)

    config = EDCConfig.load()
    config.gemini.enabled = True
    config.gemini.api_key = api_key
    config.gemini.model = model
    config.gemini.language = lang
    config.save()
    console.print(f"\n  [green]✓[/green] Gemini 설정 저장 완료  [dim]model={model} lang={lang}[/dim]\n")


# ── 진입점 ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app()
