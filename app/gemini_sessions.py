"""
Gemini 로컬 세션(JSONL)을 EDC SessionInput 포맷으로 변환한다.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .codex_sessions import TEST_CMD_RE
from .models import RawEvent, SessionInput


GEMINI_TMP_DIR = Path.home() / ".gemini" / "tmp"
FENCED_CODE_RE = re.compile(r"```.*?```", re.DOTALL)
LEADING_BULLET_RE = re.compile(r"^(?:[-*]\s+|\d+\.\s+)")


def find_gemini_session_file(session_id: str, tmp_dir: Path = GEMINI_TMP_DIR) -> Path:
    """세션 ID를 포함하는 Gemini chat JSONL 파일을 찾아 반환한다."""
    matches: list[Path] = []
    for candidate in tmp_dir.rglob("chats/*.jsonl"):
        try:
            first_line = candidate.read_text(encoding="utf-8").splitlines()[0]
            row = json.loads(first_line)
        except (IndexError, OSError, json.JSONDecodeError):
            continue
        if row.get("sessionId") == session_id:
            matches.append(candidate)

    if not matches:
        raise FileNotFoundError(f"Gemini 세션을 찾을 수 없습니다: {session_id}")
    if len(matches) > 1:
        raise ValueError(
            f"세션 ID가 여러 파일과 매칭됩니다: {session_id} ({len(matches)}개)"
        )
    return matches[0]


def load_gemini_session(session_id: str, tmp_dir: Path = GEMINI_TMP_DIR) -> SessionInput:
    """세션 ID로 Gemini 로그를 찾아 SessionInput으로 변환한다."""
    session_file = find_gemini_session_file(session_id, tmp_dir=tmp_dir)
    return parse_gemini_session_file(session_file)


def parse_gemini_session_file(path: Path) -> SessionInput:
    """Gemini JSONL 파일을 EDC SessionInput으로 변환한다."""
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
        if row_type == "$set":
            continue

        if row_type == "gemini" and session_id is None:
            session_id = row.get("sessionId") or session_id

        if row_type == "user" and session_id is None:
            session_id = row.get("sessionId") or session_id

        if row_type == "gemini":
            if description is None:
                description = _build_description(session_id, path)
            for raw_event in _parse_gemini_row(row):
                key = _event_key(raw_event)
                if key not in seen:
                    seen.add(key)
                    events.append(raw_event)
            continue

        if row_type == "user":
            content = _extract_text(row.get("content"))
            if content:
                raw_event = RawEvent(type="message", content=_clean_text(content), timestamp=row.get("timestamp"))
                if raw_event.content:
                    key = _event_key(raw_event)
                    if key not in seen:
                        seen.add(key)
                        events.append(raw_event)
            continue

        if row.get("sessionId") and session_id is None:
            session_id = row.get("sessionId")

    if description is None:
        description = f"Gemini session import from {path.name}"

    return SessionInput(description=description, events=events, source_id=session_id)


def _build_description(session_id: str | None, path: Path) -> str:
    project = path.parent.parent.name if path.parent.parent else None
    base = f"Gemini session {session_id}" if session_id else "Gemini session"
    return base + (f" @ {project}" if project else "")


def _parse_gemini_row(row: dict) -> list[RawEvent]:
    events: list[RawEvent] = []
    timestamp = row.get("timestamp")
    content = _extract_text(row.get("content"))
    if content:
        cleaned = _clean_text(content)
        if cleaned:
            events.append(RawEvent(type="message", content=cleaned, timestamp=timestamp))

    for tool_call in row.get("toolCalls") or []:
        events.extend(_parse_tool_call(tool_call, timestamp))

    return events


def _parse_tool_call(tool_call: dict, timestamp: str | None) -> list[RawEvent]:
    name = (tool_call.get("name") or "").strip()
    args = tool_call.get("args") or {}
    if not name:
        return []

    lower = name.lower()
    if lower in {"run_shell_command", "shell", "bash"}:
        command = _extract_command(args)
        if not command:
            return []
        events = [RawEvent(type="action", tool="Bash", command=command, timestamp=timestamp)]
        if TEST_CMD_RE.search(command):
            events.append(
                RawEvent(
                    type="test",
                    command=command,
                    exit_code=0,
                    output="Gemini session import detected a test command",
                    timestamp=timestamp,
                )
            )
        return events

    if lower in {"write_file", "edit_file", "replace_file", "apply_patch", "create_file", "delete_file"}:
        target = _extract_target(args)
        if not target:
            return []
        return [RawEvent(type="file_change", path=target, timestamp=timestamp)]

    return []


def _extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("text"):
                    parts.append(str(item["text"]))
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts)
    return ""


def _extract_command(args: dict) -> str:
    command = args.get("command") or args.get("shell_command") or args.get("cmd") or ""
    if not command and isinstance(args.get("args"), list):
        command = " ".join(str(arg) for arg in args["args"])
    return str(command).strip()


def _extract_target(args: dict) -> str:
    return str(
        args.get("file_path")
        or args.get("path")
        or args.get("target")
        or args.get("name")
        or ""
    ).strip()


def _event_key(event: RawEvent) -> tuple:
    return (
        event.type,
        (event.content or "").strip(),
        event.tool or "",
        event.target or "",
        event.path or "",
        event.command or "",
        event.exit_code if event.exit_code is not None else "",
    )


def _clean_text(text: str) -> str:
    text = FENCED_CODE_RE.sub("", text)
    lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if _is_meta_line(line):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def _is_meta_line(line: str) -> bool:
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
