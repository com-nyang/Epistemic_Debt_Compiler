from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def register_claude_hook(settings_path: Path) -> None:
    """Claude Code settings.json에 PreToolUse hook을 등록한다."""
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


def register_codex_wrapper(script_path: Path) -> Path:
    """
    Codex CLI 비대화형 실행을 debt watch와 연결하는 래퍼를 생성한다.

    참고:
      - 현재 확인 가능한 Codex CLI 표면에는 Claude Code의 PreToolUse와 같은
        명시적 tool hook 설정이 보이지 않는다.
      - 따라서 MVP 연동은 `codex exec` 결과를 debt watch에 자동 전달하는
        방식으로 제공한다.
    """
    script_path.parent.mkdir(exist_ok=True)

    project_root = Path.cwd().resolve()
    debt_entry = (project_root / "debt").resolve()
    python_bin = Path(sys.executable).resolve()

    script = f"""#!/usr/bin/env bash
set -euo pipefail

ROOT="{project_root}"
PYTHON_BIN="{python_bin}"
DEBT_BIN="{debt_entry}"

if ! command -v codex >/dev/null 2>&1; then
  echo "codex CLI를 찾을 수 없습니다." >&2
  exit 127
fi

OUT_FILE="${{TMPDIR:-/tmp}}/edc-codex-last-$$.txt"
cleanup() {{
  rm -f "$OUT_FILE"
}}
trap cleanup EXIT

codex exec -C "$ROOT" -o "$OUT_FILE" "$@"
status=$?

if [ -s "$OUT_FILE" ]; then
  printf '\\n[EDC] Codex 마지막 응답을 분석합니다.\\n' >&2
  "$PYTHON_BIN" "$DEBT_BIN" watch < "$OUT_FILE"
fi

exit "$status"
"""
    script_path.write_text(script, encoding="utf-8")
    os.chmod(script_path, 0o755)
    return script_path
