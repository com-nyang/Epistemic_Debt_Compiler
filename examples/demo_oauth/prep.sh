#!/usr/bin/env bash
# 데모 직전 실행 — 세션 리셋 + 첫 번째 명령 준비 상태로 만들기
set -e
cd "$(dirname "$0")/../.."

echo ""
echo "  Epistemic Debt Compiler — 데모 준비 중..."
rm -rf .edc
.venv/bin/python3 debt init --no-hook 2>&1 | grep "✓"
echo ""
echo "  준비 완료. 아래 명령어로 데모를 시작하세요:"
echo ""
echo "    .venv/bin/python3 debt watch --file examples/demo_oauth/session_demo.json"
echo ""
