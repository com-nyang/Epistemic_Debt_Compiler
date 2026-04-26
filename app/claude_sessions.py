"""
Claude Code 세션(JSONL)을 EDC SessionInput 포맷으로 변환한다.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .codex_sessions import TEST_CMD_RE
from .models import RawEvent, SessionInput


CLAUDE_SESSIONS_DIR = Path.home() / ".claude" / "projects"
PATCH_FILE_RE = re.compile(r"^\*\*\* (?:Add|Update|Delete) File: (.+)$", re.MULTILINE)
FENCED_CODE_RE = re.compile(r"```.*?```", re.DOTALL)
LEADING_BULLET_RE = re.compile(r"^(?:[-*]\s+|\d+\.\s+)")


def find_claude_session_file(session_id: str, sessions_dir: Path = CLAUDE_SESSIONS_DIR) -> Path:
    """세션 ID를 포함하는 Claude JSONL 파일을 찾아 반환한다."""
    matches = sorted(sessions_dir.rglob(f"*{session_id}*.jsonl"))
    if not matches:
        raise FileNotFoundError(f"Claude 세션을 찾을 수 없습니다: {session_id}")
    if len(matches) > 1:
        raise ValueError(
            f"세션 ID가 여러 파일과 매칭됩니다: {session_id} ({len(matches)}개)"
        )
    return matches[0]


def load_claude_session(session_id: str, sessions_dir: Path = CLAUDE_SESSIONS_DIR) -> SessionInput:
    """세션 ID로 Claude 로그를 찾아 SessionInput으로 변환한다."""
    session_file = find_claude_session_file(session_id, sessions_dir=sessions_dir)
    return parse_claude_session_file(session_file)


def parse_claude_session_file(path: Path) -> SessionInput:
    """Claude JSONL 파일을 EDC SessionInput으로 변환한다."""
    events: list[RawEvent] = []
    description: str | None = None
    session_id: str | None = None
    seen: set[tuple] = set()

    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue

        row_type = row.get("type")
        timestamp = row.get("timestamp")

        if row_type == "permission-mode":
            session_id = row.get("sessionId") or session_id
            continue

        if row_type == "assistant":
            msg = row.get("message") or {}
            session_id = msg.get("sessionId") or row.get("sessionId") or session_id
            cwd = msg.get("cwd") or row.get("cwd")
            description = description or _build_description("Claude session", session_id, cwd)
            for raw_event in _parse_assistant_message(msg, timestamp):
                key = _event_key(raw_event)
                if key not in seen:
                    seen.add(key)
                    events.append(raw_event)
            continue

        if row_type == "user":
            msg = row.get("message") or {}
            session_id = msg.get("sessionId") or row.get("sessionId") or session_id
            cwd = msg.get("cwd") or row.get("cwd")
            description = description or _build_description("Claude session", session_id, cwd)
            continue

        if row_type == "session_meta":
            session_id = row.get("sessionId") or row.get("session_id") or session_id
            continue

    if description is None:
        description = f"Claude session import from {path.name}"

    return SessionInput(description=description, events=events, source_id=session_id)


def _build_description(prefix: str, session_id: str | None, cwd: str | None) -> str:
    base = f"{prefix} {session_id}" if session_id else prefix
    return base + (f" @ {cwd}" if cwd else "")


def _event_key(event: RawEvent) -> tuple:
    """동일 import 내에서 중복 이벤트를 제거하기 위한 키."""
    return (
        event.type,
        (event.content or "").strip(),
        event.tool or "",
        event.target or "",
        event.path or "",
        event.command or "",
        event.exit_code if event.exit_code is not None else "",
    )


def _parse_assistant_message(payload: dict, timestamp: str | None) -> list[RawEvent]:
    events: list[RawEvent] = []
    content = payload.get("content")
    if not isinstance(content, list):
        return events

    text_parts: list[str] = []
    for item in content:
        item_type = item.get("type")
        if item_type in {"text", "output_text"} and item.get("text"):
            text_parts.append(item["text"])
            continue
        if item_type == "tool_use":
            events.extend(_parse_tool_use(item, timestamp))

    text = _clean_assistant_text("\n".join(text_parts))
    if text:
        events.insert(0, RawEvent(type="message", content=text, timestamp=timestamp))

    return events


def _parse_tool_use(item: dict, timestamp: str | None) -> list[RawEvent]:
    tool_name = item.get("name") or ""
    tool_input = item.get("input") or {}

    if not tool_name:
        return []

    if tool_name.lower() == "bash":
        command = _shell_command_from_input(tool_input)
        if not command:
            return []
        events = [
            RawEvent(
                type="action",
                tool="Bash",
                command=command,
                timestamp=timestamp,
            )
        ]
        if TEST_CMD_RE.search(command):
            events.append(
                RawEvent(
                    type="test",
                    command=command,
                    exit_code=0,
                    output="Claude session import detected a test command",
                    timestamp=timestamp,
                )
            )
        return events

    if tool_name.lower() in {"edit", "write"}:
        target = (
            tool_input.get("file_path")
            or tool_input.get("path")
            or tool_input.get("target")
            or ""
        )
        if not target:
            return []
        return [
            RawEvent(
                type="file_change",
                path=target,
                timestamp=timestamp,
            )
        ]

    return []


def _shell_command_from_input(tool_input: dict) -> str:
    command = tool_input.get("command") or tool_input.get("shell_command") or ""
    if not command and isinstance(tool_input.get("args"), list):
        command = " ".join(str(arg) for arg in tool_input["args"])
    return str(command).strip()


def _clean_assistant_text(text: str) -> str:
    """예시 명령과 메타 설명 줄을 제거해 분류 노이즈를 줄인다."""
    text = FENCED_CODE_RE.sub("", text)
    lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if _is_example_or_meta_line(line):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def _is_example_or_meta_line(line: str) -> bool:
    normalized = LEADING_BULLET_RE.sub("", line).strip()
    lower = normalized.lower()
    if lower.startswith((
        "예:", "예를 들면", "예를 들어", "정리하면:", "요약하면:", "즉:", "주의:", "참고:",
        "그래서", "핵심은", "이유는", "실전에서는", "가능합니다.", "다만", "즉 ", "즉,"
    )):
        return True
    if line.startswith(("- ", "* ")) and ("예:" in line or "`" in line):
        return True
    if normalized.count("`") >= 2 and len(normalized) < 100:
        return True
    if line.startswith("[Bash]"):
        return True
    return False
