"""
Codex CLI 세션(JSONL)을 EDC SessionInput 포맷으로 변환한다.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .models import RawEvent, SessionInput


CODEX_SESSIONS_DIR = Path.home() / ".codex" / "sessions"
TEST_CMD_RE = re.compile(
    r"\b("
    r"pytest|python\s+-m\s+pytest|"
    r"npm\s+(run\s+)?test|pnpm\s+(run\s+)?test|yarn\s+test|bun\s+test|"
    r"cargo\s+test|go\s+test|jest|vitest|unittest"
    r")\b",
    re.IGNORECASE,
)
PATCH_FILE_RE = re.compile(r"^\*\*\* (?:Add|Update|Delete) File: (.+)$", re.MULTILINE)
FENCED_CODE_RE = re.compile(r"```.*?```", re.DOTALL)
NUMBERED_BULLET_RE = re.compile(r"^\d+\.\s+")
LEADING_BULLET_RE = re.compile(r"^(?:[-*]\s+|\d+\.\s+)")
SELF_TEST_CMD_RE = re.compile(
    r"(^|\s)("
    r"rm\s+-rf\s+\.edc|"
    r"(?:\.venv/bin/python|python)\s+debt\s+(?:init|watch(?:-codex)?|judge|repay|ls|explain)\b|"
    r"debt\s+(?:init|watch(?:-codex)?|judge|repay|ls|explain)\b"
    r")",
    re.IGNORECASE,
)
CODEX_SESSIONS_DIR  = Path.home() / ".codex" / "sessions"
CLAUDE_SESSIONS_DIR = Path.home() / ".claude" / "sessions"
GEMINI_SESSIONS_DIR = Path.home() / ".gemini" / "tmp" / "epistemic-debt-compiler" / "chats"


def find_session_file(session_id: str, agent_type: str = "codex") -> Path:
    """에이전트 타입과 세션 ID를 기반으로 세션 로그 파일을 찾아 반환한다."""
    base_dir = {
        "codex":  CODEX_SESSIONS_DIR,
        "claude": CLAUDE_SESSIONS_DIR,
        "gemini": GEMINI_SESSIONS_DIR,
    }.get(agent_type.lower(), CODEX_SESSIONS_DIR)

    # Gemini는 .json 확장자를 쓰기도 하므로 유연하게 탐색
    pattern = f"*{session_id}*"
    matches = sorted(base_dir.rglob(pattern))

    # jsonl 또는 json 파일 필터링
    matches = [m for m in matches if m.suffix in (".jsonl", ".json") and m.is_file()]

    if not matches:
        raise FileNotFoundError(f"{agent_type} 세션을 찾을 수 없습니다: {session_id} (경로: {base_dir})")
    if len(matches) > 1:
        # 가장 최근 파일을 우선 선택 (정렬되었으므로 마지막 항목)
        return matches[-1]
    return matches[0]


def find_codex_session_file(session_id: str, sessions_dir: Path = CODEX_SESSIONS_DIR) -> Path:
    """하위 호환성을 위해 유지: 세션 ID를 포함하는 Codex JSONL 파일을 찾아 반환한다."""
    return find_session_file(session_id, agent_type="codex")


def load_codex_session(session_id: str, sessions_dir: Path = CODEX_SESSIONS_DIR) -> SessionInput:
    """세션 ID로 Codex 로그를 찾아 SessionInput으로 변환한다."""
    session_file = find_codex_session_file(session_id, sessions_dir=sessions_dir)
    return parse_codex_session_file(session_file)


def parse_codex_session_file(path: Path) -> SessionInput:
    """Codex JSONL 파일을 EDC SessionInput으로 변환한다."""
    events: list[RawEvent] = []
    description: str | None = None
    meta_id: str | None = None
    seen: set[tuple] = set()

    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue

        row_type = row.get("type")
        payload = row.get("payload", {})
        timestamp = row.get("timestamp")

        # Gemini 세션 포맷 지원 (메시지)
        if row_type == "gemini" and "content" in row:
            content = row["content"]
            if isinstance(content, str):
                text = _clean_assistant_text(content)
                if text:
                    raw_event = RawEvent(type="message", content=text, timestamp=timestamp)
                    key = _event_key(raw_event)
                    if key not in seen:
                        seen.add(key)
                        events.append(raw_event)
            
            # Gemini 세션 포맷 지원 (액션/도구 호출)
            if "toolCalls" in row:
                for call in row["toolCalls"]:
                    if call.get("name") == "run_shell_command":
                        args = call.get("args", {})
                        command = args.get("command")
                        if command:
                            raw_event = RawEvent(
                                type="action",
                                tool="Bash",
                                command=command,
                                timestamp=timestamp,
                            )
                            key = _event_key(raw_event)
                            if key not in seen:
                                seen.add(key)
                                events.append(raw_event)
            continue

        if row_type == "session_meta":
            meta_id = payload.get("id")
            cwd = payload.get("cwd")
            description = f"Codex session {meta_id}" + (f" @ {cwd}" if cwd else "")
            continue

        if row_type == "response_item":
            raw_event = _parse_response_item(payload, timestamp)
            if raw_event:
                key = _event_key(raw_event)
                if key not in seen:
                    seen.add(key)
                    events.append(raw_event)
            continue

        if row_type == "event_msg":
            for raw_event in _parse_event_msg(payload, timestamp):
                key = _event_key(raw_event)
                if key not in seen:
                    seen.add(key)
                    events.append(raw_event)
            continue

    if description is None:
        description = f"Codex session import from {path.name}"

    return SessionInput(description=description, events=events, source_id=meta_id)


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


def _parse_response_item(payload: dict, timestamp: str | None) -> RawEvent | None:
    item_type = payload.get("type")

    if item_type == "message" and payload.get("role") == "assistant":
        text_parts = []
        for item in payload.get("content", []):
            if item.get("type") == "output_text" and item.get("text"):
                text_parts.append(item["text"])
        text = _clean_assistant_text("\n".join(text_parts))
        if text:
            return RawEvent(type="message", content=text, timestamp=timestamp)

    return None


def _parse_event_msg(payload: dict, timestamp: str | None) -> list[RawEvent]:
    msg_type = payload.get("type")

    if msg_type == "exec_command_end":
        return _parse_exec_command_end(payload, timestamp)

    if msg_type == "patch_apply_end":
        return _parse_patch_apply_end(payload, timestamp)

    return []


def _parse_exec_command_end(payload: dict, timestamp: str | None) -> list[RawEvent]:
    command_parts = payload.get("command") or []
    command_str = _shell_command_from_parts(command_parts)
    if not command_str or SELF_TEST_CMD_RE.search(command_str):
        return []

    events = [
        RawEvent(
            type="action",
            tool="Bash",
            command=command_str,
            timestamp=timestamp,
        )
    ]

    if TEST_CMD_RE.search(command_str):
        events.append(
            RawEvent(
                type="test",
                command=command_str,
                exit_code=payload.get("exit_code"),
                output=payload.get("aggregated_output") or "",
                timestamp=timestamp,
            )
        )

    return events


def _parse_patch_apply_end(payload: dict, timestamp: str | None) -> list[RawEvent]:
    changes = payload.get("changes") or {}
    if changes:
        return [
            RawEvent(type="file_change", path=path, timestamp=timestamp)
            for path in changes.keys()
        ]

    patch_text = payload.get("input") or ""
    paths = PATCH_FILE_RE.findall(patch_text)
    return [RawEvent(type="file_change", path=path, timestamp=timestamp) for path in paths]


def _shell_command_from_parts(parts: list[str]) -> str:
    if not parts:
        return ""
    if len(parts) >= 3 and parts[1] == "-lc":
        return parts[2]
    return " ".join(parts)


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
    if NUMBERED_BULLET_RE.match(line) and ("예" in line or "`" in line):
        return True
    if line.startswith("[Bash]"):
        return True
    if normalized.startswith(("원하면 ", "원하면", "추가된 핵심은:", "변경 파일:", "검증은 끝냈습니다.")):
        return True
    if normalized.count("`") >= 2 and len(normalized) < 100:
        return True
    return False
