"""
Rich 기반 터미널 출력 포맷터.

설계 원칙:
  - 데이터만 받아서 출력한다. 로직 없음.
  - 색상은 정보 전달용. 없어도 읽힌다 (CI 환경 대응).
"""
from __future__ import annotations

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from .i18n import current_language, tr
from .models import DebtItem, RepayResult, RiskLevel, Session, Verdict, VerdictResult


console = Console()

# ── 색상/아이콘 매핑 ──────────────────────────────────────────────────────────

RISK_COLOR = {
    RiskLevel.LOW:    "dim",
    RiskLevel.MEDIUM: "yellow",
    RiskLevel.HIGH:   "red",
}

RISK_ICON = {
    RiskLevel.LOW:    "○",
    RiskLevel.MEDIUM: "◑",
    RiskLevel.HIGH:   "●",
}

VERDICT_COLOR = {
    Verdict.ALLOW:             "green",
    Verdict.EVIDENCE_REQUIRED: "yellow",
    Verdict.APPROVAL_REQUIRED: "orange3",
    Verdict.BLOCK:             "red",
}

VERDICT_ICON = {
    Verdict.ALLOW:             "✓",
    Verdict.EVIDENCE_REQUIRED: "⚠",
    Verdict.APPROVAL_REQUIRED: "⛔",
    Verdict.BLOCK:             "✗",
}


class ConsoleFormatter:

    ACTION_RULE_EXPLANATIONS = {
        "HIGH_RISK_FILE": "high_risk_reason",
        "DESTRUCTIVE_CMD": "destructive_reason",
        "EDIT_NO_TEST": "edit_no_test_reason",
        "RETRY_SAME_FIX": "retry_same_fix_reason",
    }

    @staticmethod
    def cli_home() -> None:
        lang = current_language()
        console.print()
        console.print(f"[bold]{tr('app_title', lang)}[/bold]")
        console.print()
        console.print(tr("app_subtitle", lang))

        table = Table(
            box=box.SIMPLE_HEAD,
            show_header=True,
            header_style="bold dim",
            padding=(0, 1),
            expand=False,
        )
        table.add_column(tr("cmd", lang), style="cyan", no_wrap=True)
        table.add_column(tr("desc", lang), style="default")
        rows = [
            ("init", tr("init_help", lang)),
            ("clear", tr("clear_help", lang)),
            ("watch", f"{tr('watch_help', lang)}\n  {tr('precise_help', lang)}"),
            ("watch-claude", f"{tr('watch_claude_help', lang)}\n  {tr('claude_session_help', lang)}\n  {tr('precise_help', lang)}"),
            ("watch-gemini", f"{tr('watch_gemini_help', lang)}\n  {tr('gemini_session_help', lang)}\n  {tr('precise_help', lang)}"),
            ("watch-codex", f"{tr('watch_codex_help', lang)}\n  {tr('session_help', lang)}\n  {tr('precise_help', lang)}"),
            ("ls", tr("ls_help", lang)),
            ("repay", tr("repay_help", lang)),
            ("judge", tr("judge_help", lang)),
            ("explain", tr("explain_help", lang)),
            ("setup-gemini", tr("setup_gemini_help", lang)),
        ]
        for idx, (command, description) in enumerate(rows):
            table.add_row(command, description)
            if idx < len(rows) - 1:
                table.add_row("", "")

        console.print()
        console.print(table)
        console.print()
        console.print(f"[bold]{tr('usage_steps', lang)}[/bold]")
        console.print("1. `debt init`")
        connector = "또는" if lang == "ko" else "or"
        console.print(f"2. `debt watch < input.txt` {connector} `debt watch-claude --session <id>`")
        console.print("3. `debt ls`")
        console.print("4. `debt explain <id>`")
        manual_example = "확인 완료" if lang == "ko" else "confirmed"
        console.print(f"5. `debt repay <id> --manual \"{manual_example}\"`")
        console.print("6. `debt judge`")
        console.print()

    @staticmethod
    def _one_line(text: str, limit: int = 72) -> str:
        """여러 줄 텍스트를 한 줄로 압축하고 너무 길면 말줄임한다."""
        compact = " ".join(text.split())
        return compact[: limit - 1] + "…" if len(compact) > limit else compact

    @staticmethod
    def _event_panel(title: str, body: str, color: str) -> None:
        console.print()
        console.print(
            Panel(
                body,
                title=title,
                border_style=color,
                padding=(0, 1),
            )
        )

    # ── watch: 이벤트 통과 메시지 ──────────────────────────────────────────────

    @staticmethod
    def event_passthrough(content: str) -> None:
        """에이전트 출력을 흐리게 그대로 출력한다."""
        console.print(f"[dim]{content.rstrip()}[/dim]")

    # ── watch: 인지부채 감지 알림 ─────────────────────────────────────────────

    @staticmethod
    def detection_alert(event: DebtItem) -> None:
        lang = current_language()
        color = RISK_COLOR[event.risk_level]
        icon  = RISK_ICON[event.risk_level]
        claim = ConsoleFormatter._one_line(event.claim, limit=84)
        body = (
            f"[dim]{tr('rule', lang)}[/dim]  {event.rule_id}\n"
            f"[dim]{tr('claim', lang)}[/dim]  {claim}\n"
            f"[dim]{tr('score', lang)}[/dim]  +{event.score}    "
            f"[dim]{tr('risk', lang)}[/dim]  [{color}]{event.risk_level.value}[/{color}]\n"
            f"[dim]{tr('id', lang)}[/dim]    {event.id}"
        )
        ConsoleFormatter._event_panel(f"[{color}]{icon} {tr('debt_detected', lang)}[/{color}]", body, color)

    # ── watch: 액션 감지 알림 ─────────────────────────────────────────────────

    @staticmethod
    def action_alert(event: DebtItem) -> None:
        lang = current_language()
        color = RISK_COLOR[event.risk_level]
        icon  = RISK_ICON[event.risk_level]
        claim = ConsoleFormatter._one_line(event.claim, limit=84)
        body = (
            f"[dim]{tr('rule', lang)}[/dim]  {event.rule_id}\n"
            f"[dim]{tr('content', lang)}[/dim]  {claim}\n"
            f"[dim]{tr('score', lang)}[/dim]  +{event.score}    "
            f"[dim]{tr('risk', lang)}[/dim]  [{color}]{event.risk_level.value}[/{color}]\n"
            f"[dim]{tr('id', lang)}[/dim]    {event.id}"
        )
        ConsoleFormatter._event_panel(f"[{color}]{icon} {tr('action_debt', lang)}[/{color}]", body, color)

    # ── watch: 테스트 결과 ────────────────────────────────────────────────────

    @staticmethod
    def test_result(command: str, exit_code: int, output: str = "") -> None:
        if exit_code == 0:
            console.print(f"  [green]✓ 테스트 통과[/green]  [dim]{command}[/dim]")
        else:
            console.print(f"  [red]✗ 테스트 실패[/red]  [dim]{command}[/dim]  (exit {exit_code})")
            if output:
                console.print(f"  [dim]{output[:120]}[/dim]")

    # ── watch: 세션 요약 ──────────────────────────────────────────────────────

    @staticmethod
    def watch_summary(events: list[DebtItem], score: int) -> None:
        lang = current_language()
        console.print()
        console.print(Rule(f"[dim]{tr('summary', lang)}[/dim]", style="dim"))

        if not events:
            console.print(f"  [green]{tr('detected_none', lang)}[/green]  {tr('well_grounded', lang)}")
        else:
            high   = sum(1 for e in events if e.risk_level == RiskLevel.HIGH)
            medium = sum(1 for e in events if e.risk_level == RiskLevel.MEDIUM)
            low    = sum(1 for e in events if e.risk_level == RiskLevel.LOW)

            console.print(f"  {tr('total_debt', lang, count=len(events), score=score)}")
            if high:   console.print(f"  [red]    HIGH   {high}건[/red]")
            if medium: console.print(f"  [yellow]    MEDIUM {medium}건[/yellow]")
            if low:    console.print(f"  [dim]    LOW    {low}건[/dim]")
            console.print()
            console.print(f"  [dim]{tr('check_ls', lang)}[/dim]")
            console.print(f"  [dim]{tr('check_judge', lang)}[/dim]")
        console.print()

    # ── ls: 부채 목록 ─────────────────────────────────────────────────────────

    @staticmethod
    def debt_list(events: list[DebtItem], score: int) -> None:
        lang = current_language()
        if not events:
            console.print()
            console.print(f"  [green]{tr('no_debt', lang)}[/green]")
            console.print(f"  [dim]{tr('well_grounded', lang)}[/dim]")
            console.print()
            return

        # 최신 10개만 표시
        MAX_DISPLAY = 10
        display_events = events[:MAX_DISPLAY]
        remaining_count = len(events) - MAX_DISPLAY

        table = Table(
            box=box.SIMPLE_HEAD,
            show_header=True,
            header_style="bold dim",
            padding=(0, 1),
            expand=False,
        )
        table.add_column(tr("id", lang), style="dim", min_width=10, no_wrap=True)
        table.add_column(tr("risk", lang), min_width=8, no_wrap=True)
        table.add_column(tr("rule", lang), min_width=16, no_wrap=True, overflow="ellipsis")
        table.add_column(tr("claim", lang), min_width=56, max_width=72, overflow="ellipsis")
        table.add_column(tr("status", lang), min_width=6, no_wrap=True)

        for e in reversed(display_events):
            color = RISK_COLOR[e.risk_level]
            icon  = RISK_ICON[e.risk_level]
            status = f"[green]{tr('resolved', lang)}[/green]" if e.resolved else f"[dim]{tr('unresolved', lang)}[/dim]"
            table.add_row(
                e.id,
                f"[{color}]{icon} {e.risk_level.value}[/{color}]",
                e.rule_id,
                ConsoleFormatter._one_line(e.claim, limit=68),
                status,
            )

        console.print()
        console.print(f"  [bold]{tr('debt_list_title', lang, count=len(display_events), total=len(events))}[/bold]  [dim](score: {score})[/dim]")
        console.print(table)

        if remaining_count > 0:
            console.print(f"  [dim]{tr('more_items', lang, count=remaining_count)}[/dim]")

        high_count = sum(1 for e in events if e.risk_level == RiskLevel.HIGH and not e.resolved)
        if high_count:
            console.print(f"  [red]{tr('high_blocking', lang, count=high_count)}[/red]")
            console.print(f"  [dim]{tr('repay_hint', lang)}[/dim]")
        console.print()

    # ── judge: 판정 결과 ──────────────────────────────────────────────────────

    @staticmethod
    def verdict_result(result: VerdictResult) -> None:
        color = VERDICT_COLOR[result.verdict]
        icon  = VERDICT_ICON[result.verdict]

        lines = [result.reason]

        if result.blocking_ids:
            lines.append("")
            lines.append("[dim]차단 원인:[/dim]")
            for bid in result.blocking_ids:
                lines.append(f"  {bid}")

        if result.suggestions:
            lines.append("")
            lines.append("[dim]상환 방법:[/dim]")
            for s in result.suggestions:
                lines.append(f"  [cyan]{s}[/cyan]")

        panel = Panel(
            "\n".join(lines),
            title=Text(f" {icon}  판정: {result.verdict.value} ", style=f"bold {color}"),
            border_style=color,
            padding=(1, 2),
        )
        console.print()
        console.print(panel)
        console.print()

    # ── repay: 상환 결과 ──────────────────────────────────────────────────────

    @staticmethod
    def repay_result(result: RepayResult) -> None:
        console.print()
        if result.success:
            console.print(f"  [green]✓ 인지부채 해소됨[/green]  [dim]{result.event_id}[/dim]")
            console.print(f"  [dim]점수 감소[/dim]  -{result.reduced_by}")
            console.print(f"  [dim]현재 점수[/dim]  {result.new_score}")
        else:
            console.print(f"  [red]✗ 해소 실패[/red]  {result.reason}")
        console.print()

    # ── explain: 부채 상세 설명 ───────────────────────────────────────────────

    @staticmethod
    def explain_event(event: DebtItem) -> None:
        lang = current_language()
        color = RISK_COLOR[event.risk_level]
        fallback_reason = None
        if event.source == "action" and not event.reviewer_reason:
            key = ConsoleFormatter.ACTION_RULE_EXPLANATIONS.get(event.rule_id)
            fallback_reason = tr(key, lang) if key else None

        summary_lines = [
            f"[dim]{tr('claim', lang)}[/dim]  {event.claim}",
            f"[dim]{tr('risk', lang)}[/dim]  [{color}]{event.risk_level.value}[/{color}]    [dim]{tr('rule', lang)}[/dim]  {event.rule_id}    [dim]{tr('score', lang)}[/dim]  +{event.score}",
            f"[dim]{tr('source', lang)}[/dim]  {event.source}",
        ]
        meta_bits = []
        if event.source_timestamp:
            meta_bits.append(f"[dim]{tr('time', lang)}[/dim]  {event.source_timestamp}")
        if event.source_session_id:
            meta_bits.append(f"[dim]{tr('session', lang)}[/dim]  {event.source_session_id}")
        if event.tool_name:
            meta_bits.append(f"[dim]{tr('tool', lang)}[/dim]  {event.tool_name}")
        if event.target_path:
            meta_bits.append(f"[dim]{tr('target', lang)}[/dim]  {event.target_path}")
        if event.command:
            meta_bits.append(f"[dim]{tr('command', lang)}[/dim]  {event.command[:80]}")
        if event.reviewer:
            meta_bits.append(f"[dim]{tr('reviewer', lang)}[/dim]  {event.reviewer}")

        console.print()
        console.print(Rule(f"[bold]{tr('explain_title', lang, id=event.id)}[/bold]", style="dim"))
        console.print()
        console.print(
            Panel(
                "\n".join(summary_lines + meta_bits),
                title=Text(tr("summary_panel", lang), style="bold"),
                border_style=color,
                padding=(0, 1),
            )
        )

        reason = event.reviewer_reason or fallback_reason
        if reason:
            console.print()
            console.print(
                Panel(
                    reason,
                    title=Text(tr("reason_panel", lang), style="bold"),
                    border_style="blue",
                    padding=(0, 1),
                )
            )

        if event.source_context:
            context_lines = event.source_context.splitlines()
            if len(context_lines) > 8:
                display_context = "\n".join(context_lines[:8]) + "\n\n  [dim]... (이하 생략)[/dim]"
            else:
                display_context = event.source_context

            console.print()
            console.print(
                Panel(
                    display_context,
                    title=Text(tr("context", lang), style="bold"),
                    border_style="dim",
                    padding=(0, 1),
                )
            )

        console.print(f"  [dim]{tr('registered', lang)}[/dim]  {event.created_at.strftime('%Y-%m-%d %H:%M:%S')}")

        if event.resolved:
            console.print()
            console.print(
                Panel(
                    (
                        f"[green]✓ {tr('resolved_ok', lang)}[/green]  {event.resolved_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
                        f"[dim]{tr('evidence', lang)}[/dim]  {event.evidence}\n"
                        f"[dim]{tr('method', lang)}[/dim]  {event.evidence_type.value if event.evidence_type else '-'}"
                    ),
                    title=Text(tr("resolved_panel", lang), style="bold green"),
                    border_style="green",
                    padding=(0, 1),
                )
            )
        else:
            console.print()
            repay_methods = (
                f"1. [cyan]debt repay {event.id} --test \"pytest tests/\"[/cyan] (테스트 통과로 증명)\n"
                f"2. [cyan]debt repay {event.id} --code \"src/file.py:42\"[/cyan] (관련 코드 위치 참조)\n"
                f"3. [cyan]debt repay {event.id} --manual \"직접 확인\"[/cyan] (수동 검증 완료)"
            ) if lang == "ko" else (
                f"1. [cyan]debt repay {event.id} --test \"pytest tests/\"[/cyan] (Prove with a passing test)\n"
                f"2. [cyan]debt repay {event.id} --code \"src/file.py:42\"[/cyan] (Reference code location)\n"
                f"3. [cyan]debt repay {event.id} --manual \"Confirmed\"[/cyan] (Manual verification)"
            )
            console.print(
                Panel(
                    repay_methods,
                    title=Text(tr("repay_panel", lang), style="bold"),
                    border_style="cyan",
                    padding=(0, 1),
                )
            )

        console.print()

    # ── 공통: 에러 메시지 ─────────────────────────────────────────────────────

    @staticmethod
    def error(message: str) -> None:
        console.print(f"\n  [red]{tr('error')}[/red] {message}\n")

    @staticmethod
    def info(message: str) -> None:
        console.print(f"\n  [dim]{message}[/dim]\n")

    # ── 세션 리포트 ───────────────────────────────────────────────────────────

    @staticmethod
    def session_report(session: Session, all_events: list[DebtItem]) -> None:
        resolved   = [e for e in all_events if e.resolved]
        unresolved = [e for e in all_events if not e.resolved]
        total      = len(all_events)
        rate       = int(len(resolved) / total * 100) if total else 100

        console.print()
        console.print(Rule("[bold]세션 리포트[/bold]", style="dim"))
        console.print()
        console.print(f"  [dim]세션 ID[/dim]   {session.id}")
        console.print(f"  [dim]시작[/dim]      {session.started_at.strftime('%Y-%m-%d %H:%M')}")
        console.print(f"  [dim]프로젝트[/dim]  {session.project_root}")
        console.print()
        console.print(f"  총 인지부채   [bold]{total}건[/bold]")
        console.print(f"  [green]  해소됨    {len(resolved)}건[/green]")
        console.print(f"  [red]  미해소    {len(unresolved)}건[/red]")
        console.print(f"  강제 진행     {session.force_overrides}회")
        console.print()
        console.print(f"  부채 상환율   [bold]{rate}%[/bold]")
        console.print()
