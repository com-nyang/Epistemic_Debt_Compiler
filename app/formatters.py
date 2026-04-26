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

    # ── watch: 이벤트 통과 메시지 ──────────────────────────────────────────────

    @staticmethod
    def event_passthrough(content: str) -> None:
        """에이전트 출력을 흐리게 그대로 출력한다."""
        console.print(f"[dim]{content.rstrip()}[/dim]")

    # ── watch: 인지부채 감지 알림 ─────────────────────────────────────────────

    @staticmethod
    def detection_alert(event: DebtItem) -> None:
        color = RISK_COLOR[event.risk_level]
        icon  = RISK_ICON[event.risk_level]

        console.print()
        console.print(f"  [{color}]{icon} 인지부채 감지[/{color}]  [dim]{event.id}[/dim]")
        console.print(f"  [dim]규칙[/dim]    {event.rule_id}")
        console.print(f"  [dim]클레임[/dim]  {event.claim[:80]}")
        console.print(f"  [dim]점수[/dim]    +{event.score}  리스크: [{color}]{event.risk_level.value}[/{color}]")

    # ── watch: 액션 감지 알림 ─────────────────────────────────────────────────

    @staticmethod
    def action_alert(event: DebtItem) -> None:
        color = RISK_COLOR[event.risk_level]
        icon  = RISK_ICON[event.risk_level]

        console.print()
        console.print(f"  [{color}]{icon} 행동 인지부채[/{color}]  [dim]{event.id}[/dim]")
        console.print(f"  [dim]규칙[/dim]    {event.rule_id}")
        console.print(f"  [dim]내용[/dim]    {event.claim}")
        console.print(f"  [dim]점수[/dim]    +{event.score}  리스크: [{color}]{event.risk_level.value}[/{color}]")

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
        console.print()
        console.print(Rule("[dim]세션 요약[/dim]", style="dim"))

        if not events:
            console.print("  [green]감지된 인지부채 없음[/green]  에이전트가 근거 있게 행동했습니다.")
        else:
            high   = sum(1 for e in events if e.risk_level == RiskLevel.HIGH)
            medium = sum(1 for e in events if e.risk_level == RiskLevel.MEDIUM)
            low    = sum(1 for e in events if e.risk_level == RiskLevel.LOW)

            console.print(f"  총 인지부채  [bold]{len(events)}건[/bold]  (점수: {score})")
            if high:   console.print(f"  [red]    HIGH   {high}건[/red]")
            if medium: console.print(f"  [yellow]    MEDIUM {medium}건[/yellow]")
            if low:    console.print(f"  [dim]    LOW    {low}건[/dim]")
            console.print()
            console.print("  [dim]`debt ls` 로 전체 목록 확인[/dim]")
            console.print("  [dim]`debt judge` 로 진행 가능 여부 판정[/dim]")
        console.print()

    # ── ls: 부채 목록 ─────────────────────────────────────────────────────────

    @staticmethod
    def debt_list(events: list[DebtItem], score: int) -> None:
        if not events:
            console.print()
            console.print("  [green]미해소 인지부채  없음 ✓[/green]")
            console.print("  [dim]에이전트가 근거 있게 행동하고 있습니다.[/dim]")
            console.print()
            return

        table = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold dim", padding=(0, 1))
        table.add_column("ID",     style="dim",  min_width=10)
        table.add_column("리스크", min_width=8)
        table.add_column("규칙",   min_width=16)
        table.add_column("클레임", min_width=40)
        table.add_column("상태",   min_width=6)

        for e in events:
            color = RISK_COLOR[e.risk_level]
            icon  = RISK_ICON[e.risk_level]
            status = "[green]해소[/green]" if e.resolved else "[dim]미해소[/dim]"
            table.add_row(
                e.id,
                f"[{color}]{icon} {e.risk_level.value}[/{color}]",
                e.rule_id,
                e.claim[:45] + ("…" if len(e.claim) > 45 else ""),
                status,
            )

        console.print()
        console.print(f"  [bold]인지부채  {len(events)}건[/bold]  [dim](점수: {score})[/dim]")
        console.print(table)

        high_count = sum(1 for e in events if e.risk_level == RiskLevel.HIGH and not e.resolved)
        if high_count:
            console.print(f"  [red]HIGH 부채 {high_count}건 — 파일 수정/명령 실행이 차단됩니다.[/red]")
            console.print(f"  [dim]`debt repay <id> --test <cmd>` 로 상환하세요.[/dim]")
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
        color = RISK_COLOR[event.risk_level]

        console.print()
        console.print(Rule(f"[bold]인지부채  {event.id}[/bold]", style="dim"))
        console.print()
        console.print(f"  [dim]클레임[/dim]    {event.claim}")
        console.print(f"  [dim]리스크[/dim]    [{color}]{event.risk_level.value}[/{color}]")
        console.print(f"  [dim]규칙[/dim]      {event.rule_id}")
        console.print(f"  [dim]점수[/dim]      +{event.score}")
        console.print(f"  [dim]출처[/dim]      {event.source}")

        if event.tool_name:
            console.print(f"  [dim]도구[/dim]      {event.tool_name}")
        if event.target_path:
            console.print(f"  [dim]대상[/dim]      {event.target_path}")
        if event.command:
            console.print(f"  [dim]명령[/dim]      {event.command[:80]}")

        console.print(f"  [dim]등록[/dim]      {event.created_at.strftime('%Y-%m-%d %H:%M:%S')}")

        if event.resolved:
            console.print()
            console.print(f"  [green]✓ 해소됨[/green]  {event.resolved_at.strftime('%Y-%m-%d %H:%M:%S')}")
            console.print(f"  [dim]근거[/dim]      {event.evidence}")
            ev_type = event.evidence_type.value if event.evidence_type else "-"
            console.print(f"  [dim]방법[/dim]      {ev_type}")
        else:
            console.print()
            console.print(f"  [bold]상환 방법[/bold]")
            console.print(f"  [cyan]  debt repay {event.id} --test \"pytest tests/\"[/cyan]")
            console.print(f"  [cyan]  debt repay {event.id} --code \"<파일>:<줄>\"[/cyan]")
            console.print(f"  [cyan]  debt repay {event.id} --manual \"직접 확인\"[/cyan]")

        console.print()

    # ── 공통: 에러 메시지 ─────────────────────────────────────────────────────

    @staticmethod
    def error(message: str) -> None:
        console.print(f"\n  [red]오류:[/red] {message}\n")

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
