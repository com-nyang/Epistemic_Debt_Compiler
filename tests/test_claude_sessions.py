"""
claude_sessions.py 단위 테스트.
Claude JSONL을 SessionInput으로 변환하는 경로를 검증한다.
"""
import json

from app.claude_sessions import find_claude_session_file, parse_claude_session_file


class TestFindClaudeSessionFile:

    def test_finds_matching_session_file(self, tmp_path):
        root = tmp_path / "projects"
        target = root / "sample-project"
        target.mkdir(parents=True)
        session_file = target / "22b91bff-bde1-47b9-b7d0-1641ea4ba04c.jsonl"
        session_file.write_text("", encoding="utf-8")

        found = find_claude_session_file("22b91bff-bde1-47b9-b7d0-1641ea4ba04c", sessions_dir=root)
        assert found == session_file


class TestParseClaudeSessionFile:

    def test_parses_assistant_text_actions_and_file_changes(self, tmp_path):
        session_file = tmp_path / "claude.jsonl"
        rows = [
            {
                "type": "permission-mode",
                "permissionMode": "default",
                "sessionId": "claude-123",
            },
            {
                "type": "assistant",
                "timestamp": "2026-04-26T00:18:46.567Z",
                "message": {
                    "role": "assistant",
                    "sessionId": "claude-123",
                    "cwd": "/tmp/project",
                    "content": [
                        {"type": "text", "text": "I think this is the issue."},
                        {
                            "type": "tool_use",
                            "id": "tool-1",
                            "name": "Bash",
                            "input": {"command": "pytest -q"},
                        },
                        {
                            "type": "tool_use",
                            "id": "tool-2",
                            "name": "Edit",
                            "input": {"file_path": "/tmp/project/app/main.py"},
                        },
                    ],
                },
            },
        ]
        session_file.write_text(
            "\n".join(json.dumps(row) for row in rows) + "\n",
            encoding="utf-8",
        )

        session_input = parse_claude_session_file(session_file)

        assert session_input.description == "Claude session claude-123 @ /tmp/project"
        assert session_input.source_id == "claude-123"
        assert [event.type for event in session_input.events] == [
            "message",
            "action",
            "test",
            "file_change",
        ]
        assert session_input.events[0].content == "I think this is the issue."
        assert session_input.events[1].tool == "Bash"
        assert session_input.events[1].command == "pytest -q"
        assert session_input.events[2].exit_code == 0
        assert session_input.events[3].path == "/tmp/project/app/main.py"

