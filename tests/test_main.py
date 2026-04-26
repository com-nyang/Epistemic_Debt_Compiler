"""
main.py 보조 함수 테스트.
Codex 래퍼 생성 로직이 기대한 실행 파일을 만드는지 검증한다.
"""
from typer.testing import CliRunner

from app.main import app
from pathlib import Path

from app.hooks import register_codex_wrapper
from app.models import SessionInput


runner = CliRunner()


class TestRegisterCodexWrapper:

    def test_creates_executable_wrapper_script(self, tmp_path, monkeypatch):
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / "debt").write_text("#!/usr/bin/env python3\n", encoding="utf-8")

        monkeypatch.chdir(project_root)

        script_path = project_root / ".edc" / "codex-exec"
        created = register_codex_wrapper(script_path)

        assert created == script_path
        assert script_path.exists()
        assert script_path.stat().st_mode & 0o111

        contents = script_path.read_text(encoding="utf-8")
        assert 'codex exec -C "$ROOT" -o "$OUT_FILE" "$@"' in contents
        assert '"$PYTHON_BIN" "$DEBT_BIN" watch < "$OUT_FILE"' in contents
        assert str(project_root) in contents


class TestWatchCodex:

    def test_skips_already_imported_codex_session(self, monkeypatch):
        class FakeRegistry:
            def __init__(self):
                self.session = type("SessionObj", (), {"imported_codex_sessions": ["sess-123"]})()

            def current_session(self):
                return self.session

            def save_session(self, session):
                self.session = session

        fake_registry = FakeRegistry()

        monkeypatch.setattr("app.main.DebtRegistry.is_initialized", lambda: True)
        monkeypatch.setattr("app.main._load_engine", lambda precise=False: (object(), fake_registry))
        monkeypatch.setattr("app.main._get_or_create_session", lambda registry: fake_registry.session)
        monkeypatch.setattr(
            "app.main.load_codex_session",
            lambda session_id: SessionInput(description="x", events=[], source_id="sess-123"),
        )

        result = runner.invoke(app, ["watch-codex", "--session", "sess-123"])
        assert result.exit_code == 0
        assert "이미 가져온 Codex 세션입니다" in result.output


class TestPreciseMode:

    def test_watch_precise_without_api_key_exits(self, monkeypatch, tmp_path):
        edc = tmp_path / ".edc"
        edc.mkdir()
        (edc / "debt.json").write_text('{"events":{},"sessions":{},"current_session_id":null}', encoding="utf-8")

        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

        result = runner.invoke(app, ["watch", "--precise"], input="I think this is the issue.\n")
        assert result.exit_code == 2
        assert "Gemini API 키가 없습니다" in result.output


class TestWatchClaude:

    def test_watch_claude_alias_exists(self):
        result = runner.invoke(app, ["watch-claude", "--help"])
        assert result.exit_code == 0
        assert "watch-claude" in result.output

    def test_watch_claude_session_import(self, monkeypatch, tmp_path):
        edc = tmp_path / ".edc"
        edc.mkdir()
        (edc / "debt.json").write_text('{"events":{},"sessions":{},"current_session_id":null}', encoding="utf-8")

        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("app.main.DebtRegistry.is_initialized", lambda: True)
        monkeypatch.setattr("app.main._load_engine", lambda precise=False: (object(), type("RegistryObj", (), {})()))
        monkeypatch.setattr("app.main._get_or_create_session", lambda registry: type("SessionObj", (), {"id": "sess-1", "debt_score": 0})())

        captured = {}

        def fake_load(session_id):
            captured["session_id"] = session_id
            return SessionInput(description="Claude session", events=[], source_id="claude-123")

        monkeypatch.setattr("app.main.load_claude_session", fake_load)
        monkeypatch.setattr("app.main._watch_session_input", lambda *args, **kwargs: None)

        result = runner.invoke(app, ["watch-claude", "--session", "claude-123"])

        assert result.exit_code == 0
        assert captured["session_id"] == "claude-123"


class TestWatchGemini:

    def test_watch_gemini_alias_exists(self):
        result = runner.invoke(app, ["watch-gemini", "--help"])
        assert result.exit_code == 0
        assert "watch-gemini" in result.output

    def test_watch_gemini_session_import(self, monkeypatch, tmp_path):
        edc = tmp_path / ".edc"
        edc.mkdir()
        (edc / "debt.json").write_text('{"events":{},"sessions":{},"current_session_id":null}', encoding="utf-8")

        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("app.main.DebtRegistry.is_initialized", lambda: True)
        monkeypatch.setattr("app.main._load_engine", lambda precise=False: (object(), type("RegistryObj", (), {})()))
        monkeypatch.setattr("app.main._get_or_create_session", lambda registry: type("SessionObj", (), {"id": "sess-1", "debt_score": 0})())

        captured = {}

        def fake_load(session_id):
            captured["session_id"] = session_id
            return SessionInput(description="Gemini session", events=[], source_id="gemini-123")

        monkeypatch.setattr("app.main.load_gemini_session", fake_load)
        monkeypatch.setattr("app.main._watch_session_input", lambda *args, **kwargs: None)

        result = runner.invoke(app, ["watch-gemini", "--session", "gemini-123"])

        assert result.exit_code == 0
        assert captured["session_id"] == "gemini-123"


class TestClear:

    def test_clear_keeps_config_and_resets_runtime_data(self, tmp_path, monkeypatch):
        edc = tmp_path / ".edc"
        edc.mkdir()
        (edc / "debt.json").write_text(
            '{"events":{"edc-1":{"id":"edc-1","session_id":"sess","rule_id":"HEDGE_STRONG",'
            '"claim":"x","risk_level":"MEDIUM","score":10,"source":"text","resolved":false,'
            '"evidence":null,"evidence_type":null,"created_at":"2026-04-26T00:00:00",'
            '"resolved_at":null}},"sessions":{},"current_session_id":null}',
            encoding="utf-8",
        )
        (edc / "config.json").write_text('{"gemini":{"enabled":true,"api_key":"secret","model":"gemini-2.5-flash"}}', encoding="utf-8")
        (edc / "codex-exec").write_text("#!/usr/bin/env bash\n", encoding="utf-8")

        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["clear"])

        assert result.exit_code == 0
        assert "런타임 데이터 초기화 완료" in result.output
        assert (edc / "config.json").exists()
        assert not (edc / "codex-exec").exists()

        debt_json = (edc / "debt.json").read_text(encoding="utf-8")
        assert '"events": {}' in debt_json
        assert '"sessions": {}' in debt_json
