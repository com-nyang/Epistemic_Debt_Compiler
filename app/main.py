"""
Epistemic Debt Compiler — CLI 진입점.

명령어:
  debt init     프로젝트 초기화
  debt watch    에이전트 세션 분석 (파일 또는 stdin)
  debt ls       현재 인지부채 목록
  debt repay    인지부채 상환
  debt judge    진행 가능 여부 판정 (hook/CI 연동)
  debt explain  특정 부채 상세 설명
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from .engine import RuleEngine
from .formatters import ConsoleFormatter
from .models import RiskLevel, SessionInput, Verdict
from .parsers import ActionClassifier, RuleBasedClassifier
from .registry import DebtRegistry, EDC_DIR
from .rules import Rules

app = typer.Typer(
    name="debt",
    help="Epistemic Debt Compiler — 근거 없는 에이전트 행동을 추적하고 차단한다.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()
fmt     = ConsoleFormatter()


# ── 공통 헬퍼 ────────────────────────────────────────────────────────────────

def _find_rules_path() -> Path:
    """rules.json을 현재 디렉토리 → 패키지 디렉토리 순서로 탐색한다."""
    local = Path("rules.json")
    if local.exists():
        return local
    pkg = Path(__file__).parent.parent / "rules.json"
    if pkg.exists():
        return pkg
    fmt.error("rules.json을 찾을 수 없습니다. 프로젝트 루트에서 실행하세요.")
    raise typer.Exit(2)


def _require_init() -> None:
    """초기화 여부를 확인하고, 안 되어 있으면 오류를 출력하고 종료한다."""
    if not DebtRegistry.is_initialized():
        fmt.error(".edc/ 디렉토리가 없습니다. 먼저 `debt init`을 실행하세요.")
        raise typer.Exit(2)


def _load_engine() -> tuple[RuleEngine, DebtRegistry]:
    """Rules, Registry, Engine을 조립해서 반환한다."""
    rules      = Rules.load(_find_rules_path())
    registry   = DebtRegistry()
    classifier = RuleBasedClassifier(rules)
    action_cls = ActionClassifier(rules)
    engine     = RuleEngine(rules, classifier, action_cls, registry)
    return engine, registry


def _get_or_create_session(registry: DebtRegistry):
    """현재 세션을 반환하거나 새로 생성한다."""
    session = registry.current_session()
    if not session:
        session = registry.create_session(str(Path.cwd()))
    return session


# ── debt init ────────────────────────────────────────────────────────────────

@app.command()
def init(
    hook: bool = typer.Option(True, "--hook/--no-hook", help="Claude Code hook 자동 등록 여부"),
):
    """프로젝트에 .edc/ 초기화 및 Claude Code hook 설정."""
    DebtRegistry.init()
    console.print("\n  [green]✓[/green] .edc/ 초기화 완료")

    # Claude Code settings.json에 PreToolUse hook 등록
    if hook:
        settings_path = Path(".claude/settings.json")
        _register_claude_hook(settings_path)
        console.print("  [green]✓[/green] Claude Code PreToolUse hook 등록 완료")

    console.print("\n  [dim]이제 `debt watch --file <session.json>` 으로 시작하세요.[/dim]\n")


def _register_claude_hook(settings_path: Path) -> None:
    settings_path.parent.mkdir(exist_ok=True)
    settings = json.loads(settings_path.read_text()) if settings_path.exists() else {}
    hook_cmd = "debt judge --tool $TOOL_NAME --strict"

    hooks = settings.setdefault("hooks", {}).setdefault("PreToolUse", [])
    already = any(
        hook_cmd in str(h)
        for entry in hooks
        for h in entry.get("hooks", [])
    )
    if not already:
        hooks.append({
            "matcher": "Edit|Write|Bash",
            "hooks": [{"type": "command", "command": hook_cmd}]
        })
        settings_path.write_text(json.dumps(settings, indent=2))


# ── debt watch ───────────────────────────────────────────────────────────────

@app.command()
def watch(
    file:    Optional[Path] = typer.Option(None,  "--file",    "-f", help="분석할 JSON 세션 파일"),
    dry_run: bool           = typer.Option(False, "--dry-run",        help="감지만, 등록 안 함"),
    quiet:   bool           = typer.Option(False, "--quiet",   "-q", help="에이전트 출력 숨김"),
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
    _require_init()
    engine, registry = _load_engine()
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

    if session_input.description and not quiet:
        console.print(f"\n  [bold]{session_input.description}[/bold]")

    console.print(f"\n  [dim]세션 ID: {session.id} | 이벤트: {len(session_input.events)}개[/dim]")
    console.print()

    all_new_events = []

    for raw in session_input.events:

        # ── message: 에이전트 텍스트 분석 ──────────────────────────────────
        if raw.type == "message" and raw.content:
            if not quiet:
                fmt.event_passthrough(f"[agent] {raw.content}")
            if not dry_run:
                events = engine.process_text(raw.content, session)
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
                    tool=raw.tool, target=target, command=command, session=session
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
                    tool="Edit", target=path, command="", session=session
                )
                for ev in events:
                    fmt.action_alert(ev)
                    all_new_events.append(ev)

    fmt.watch_summary(all_new_events, session.debt_score)


def _watch_stdin(engine, registry, session, dry_run):
    """stdin에서 텍스트를 줄 단위로 읽어서 분석한다 (pipe 모드)."""
    console.print(f"\n  [dim]stdin 모드 — 텍스트를 입력하세요 (Ctrl+D로 종료)[/dim]\n")
    all_new_events = []

    for line in sys.stdin:
        line = line.rstrip()
        if not line:
            continue

        if not dry_run:
            events = engine.process_text(line, session)
            for ev in events:
                fmt.detection_alert(ev)
                all_new_events.append(ev)

    fmt.watch_summary(all_new_events, session.debt_score)


# ── debt ls ──────────────────────────────────────────────────────────────────

@app.command(name="ls")
def list_debts(
    risk:        Optional[str] = typer.Option(None,  "--risk",  help="리스크 필터: HIGH | MEDIUM | LOW"),
    show_all:    bool          = typer.Option(False, "--all",   "-a", help="해소된 항목 포함"),
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

    if json_output:
        # Rich console를 거치지 않고 stdout에 직접 출력 (제어 문자 방지)
        sys.stdout.write(json.dumps([e.model_dump(mode="json") for e in events], indent=2, ensure_ascii=False) + "\n")
    else:
        fmt.debt_list(events, session.debt_score)


# ── debt repay ───────────────────────────────────────────────────────────────

@app.command()
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

@app.command()
def judge(
    tool:   Optional[str] = typer.Option(None,  "--tool",   help="판정할 도구 이름 (Edit|Write|Bash)"),
    target: Optional[str] = typer.Option(None,  "--target", help="대상 파일/경로"),
    strict: bool          = typer.Option(False, "--strict", help="비대화형 모드 (CI/hook 용)"),
    force:  bool          = typer.Option(False, "--force",  help="BLOCK 무시 강제 진행 (기록됨)"),
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
    if tool:
        engine.process_action(tool=tool, target=target or "", session=session)

    result = engine.get_verdict(session)

    # 강제 진행: BLOCK이어도 통과, 단 기록됨
    if force and result.verdict.blocks:
        session.force_overrides += 1
        registry.save_session(session)
        if not strict:
            fmt.verdict_result(result)
            console.print("  [yellow]⚠  강제 진행 — 기록됨[/yellow]\n")
        raise typer.Exit(0)

    if not strict:
        fmt.verdict_result(result)

    raise typer.Exit(result.verdict.exit_code)


# ── debt explain ─────────────────────────────────────────────────────────────

@app.command()
def explain(
    event_id: str = typer.Argument(..., metavar="ID", help="상세 조회할 인지부채 ID"),
):
    """특정 인지부채의 상세 정보와 상환 가이드를 출력한다."""
    _require_init()
    _, registry = _load_engine()

    event = registry.get_event(event_id)
    if not event:
        fmt.error(f"'{event_id}'를 찾을 수 없습니다. `debt ls`로 ID를 확인하세요.")
        raise typer.Exit(1)

    fmt.explain_event(event)


# ── 진입점 ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app()
