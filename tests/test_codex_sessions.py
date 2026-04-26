"""
codex_sessions.py 단위 테스트.
Codex JSONL을 SessionInput으로 변환하는 경로를 검증한다.
"""
import json

from app.codex_sessions import find_codex_session_file, parse_codex_session_file


class TestFindCodexSessionFile:

    def test_finds_matching_session_file(self, tmp_path):
        root = tmp_path / "sessions"
        target = root / "2026" / "04" / "26"
        target.mkdir(parents=True)
        session_file = target / "rollout-2026-04-26T10-03-15-abc-123.jsonl"
        session_file.write_text("", encoding="utf-8")

        found = find_codex_session_file("abc-123", sessions_dir=root)
        assert found == session_file


class TestParseCodexSessionFile:

    def test_parses_messages_actions_tests_and_file_changes(self, tmp_path):
        session_file = tmp_path / "codex.jsonl"
        rows = [
            {
                "timestamp": "2026-04-26T01:03:21.051Z",
                "type": "session_meta",
                "payload": {
                    "id": "sess-123",
                    "cwd": "/tmp/project",
                },
            },
            {
                "timestamp": "2026-04-26T01:03:46.687Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {"type": "output_text", "text": "I think this is the issue."}
                    ],
                },
            },
            {
                "timestamp": "2026-04-26T01:07:52.254Z",
                "type": "event_msg",
                "payload": {
                    "type": "exec_command_end",
                    "command": ["/bin/bash", "-lc", "pytest -q"],
                    "exit_code": 0,
                    "aggregated_output": "1 passed",
                },
            },
            {
                "timestamp": "2026-04-26T01:07:48.279Z",
                "type": "event_msg",
                "payload": {
                    "type": "patch_apply_end",
                    "changes": {
                        "/tmp/project/app/main.py": {"type": "update"},
                    },
                },
            },
        ]
        session_file.write_text(
            "\n".join(json.dumps(row) for row in rows) + "\n",
            encoding="utf-8",
        )

        session_input = parse_codex_session_file(session_file)

        assert session_input.description == "Codex session sess-123 @ /tmp/project"
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

    def test_removes_fenced_code_blocks_from_assistant_message(self, tmp_path):
        session_file = tmp_path / "codex.jsonl"
        rows = [
            {
                "timestamp": "2026-04-26T01:03:21.051Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {
                            "type": "output_text",
                            "text": "설명입니다.\n```bash\necho \"이 설정이 원인인 것 같습니다.\"\n```\n끝.",
                        }
                    ],
                },
            }
        ]
        session_file.write_text(
            "\n".join(json.dumps(row) for row in rows) + "\n",
            encoding="utf-8",
        )

        session_input = parse_codex_session_file(session_file)

        assert len(session_input.events) == 1
        assert session_input.events[0].content == "설명입니다.\n끝."

    def test_filters_example_and_meta_lines(self, tmp_path):
        session_file = tmp_path / "codex.jsonl"
        rows = [
            {
                "timestamp": "2026-04-26T01:03:21.051Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {
                            "type": "output_text",
                            "text": (
                                "실제 설명입니다.\n"
                                "예: `debt judge`\n"
                                "- 예: `원인은`\n"
                                "원하면 다음으로 더 줄여드리겠습니다.\n"
                                "그래서 단순히 말투만 불확실한 건 낮거나 중간 수준일 수 있습니다.\n"
                                "- 즉, Codex 실행 후 응답 자동 분석까지만 가능합니다.\n"
                                "[Bash] debt ls\n"
                            ),
                        }
                    ],
                },
            }
        ]
        session_file.write_text(
            "\n".join(json.dumps(row) for row in rows) + "\n",
            encoding="utf-8",
        )

        session_input = parse_codex_session_file(session_file)

        assert len(session_input.events) == 1
        assert session_input.events[0].content == "실제 설명입니다."

    def test_ignores_self_test_commands_and_dedupes_events(self, tmp_path):
        session_file = tmp_path / "codex.jsonl"
        rows = [
            {
                "timestamp": "2026-04-26T01:03:21.051Z",
                "type": "event_msg",
                "payload": {
                    "type": "exec_command_end",
                    "command": ["/bin/bash", "-lc", "rm -rf .edc && python debt init --no-hook"],
                    "exit_code": 0,
                    "aggregated_output": "",
                },
            },
            {
                "timestamp": "2026-04-26T01:03:22.051Z",
                "type": "event_msg",
                "payload": {
                    "type": "exec_command_end",
                    "command": ["/bin/bash", "-lc", "pytest -q"],
                    "exit_code": 0,
                    "aggregated_output": "1 passed",
                },
            },
            {
                "timestamp": "2026-04-26T01:03:22.052Z",
                "type": "event_msg",
                "payload": {
                    "type": "exec_command_end",
                    "command": ["/bin/bash", "-lc", "pytest -q"],
                    "exit_code": 0,
                    "aggregated_output": "1 passed",
                },
            },
        ]
        session_file.write_text(
            "\n".join(json.dumps(row) for row in rows) + "\n",
            encoding="utf-8",
        )

        session_input = parse_codex_session_file(session_file)

        assert [event.type for event in session_input.events] == ["action", "test"]
        assert session_input.events[0].command == "pytest -q"
