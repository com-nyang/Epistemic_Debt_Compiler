"""
gemini_sessions.py 단위 테스트.
Gemini JSONL을 SessionInput으로 변환하는 경로를 검증한다.
"""
import json

from app.gemini_sessions import find_gemini_session_file, parse_gemini_session_file


class TestFindGeminiSessionFile:

    def test_finds_matching_session_file(self, tmp_path):
        root = tmp_path / ".gemini" / "tmp" / "project-x" / "chats"
        root.mkdir(parents=True)
        session_id = "74890ff3-4821-4249-b3f4-a6c8491edf14"
        session_file = root / "session-2026-04-26T02-48-74890ff3.jsonl"
        session_file.write_text(
            json.dumps({
                "sessionId": session_id,
                "projectHash": "abc",
                "startTime": "2026-04-26T02:48:37.881Z",
                "lastUpdated": "2026-04-26T02:48:37.881Z",
                "kind": "main",
            }) + "\n",
            encoding="utf-8",
        )

        found = find_gemini_session_file(session_id, tmp_dir=tmp_path / ".gemini" / "tmp")
        assert found == session_file


class TestParseGeminiSessionFile:

    def test_parses_user_gemini_and_shell_commands(self, tmp_path):
        session_file = tmp_path / "session.jsonl"
        rows = [
            {
                "sessionId": "74890ff3-4821-4249-b3f4-a6c8491edf14",
                "projectHash": "abc",
                "startTime": "2026-04-26T02:48:37.881Z",
                "lastUpdated": "2026-04-26T02:48:37.881Z",
                "kind": "main",
            },
            {
                "id": "user-1",
                "timestamp": "2026-04-26T02:48:43.924Z",
                "type": "user",
                "content": [{"text": "우리 프로젝트 분석해줘"}],
            },
            {
                "id": "gemini-1",
                "timestamp": "2026-04-26T02:48:46.793Z",
                "type": "gemini",
                "content": "I will begin by analyzing the project structure.",
                "toolCalls": [
                    {
                        "id": "call-1",
                        "name": "run_shell_command",
                        "args": {"command": "pytest -q"},
                        "result": [],
                    }
                ],
            },
        ]
        session_file.write_text(
            "\n".join(json.dumps(row) for row in rows) + "\n",
            encoding="utf-8",
        )

        session_input = parse_gemini_session_file(session_file)

        assert session_input.source_id == "74890ff3-4821-4249-b3f4-a6c8491edf14"
        assert [event.type for event in session_input.events] == ["message", "message", "action", "test"]
        assert session_input.events[0].content == "우리 프로젝트 분석해줘"
        assert session_input.events[1].content == "I will begin by analyzing the project structure."
        assert session_input.events[2].tool == "Bash"
        assert session_input.events[2].command == "pytest -q"
        assert session_input.events[3].exit_code == 0

