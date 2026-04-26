#!/usr/bin/env bash
# OAuth redirect loop 시나리오 전체 데모 스크립트
# 실행: bash examples/demo_oauth/run_demo.sh

set -e
DEBT=".venv/bin/python3 debt"
SEP="────────────────────────────────────────────"

echo ""
echo "  Epistemic Debt Compiler — OAuth redirect loop 데모"
echo "  $SEP"
echo ""

# ── 0. 초기화 ──────────────────────────────────────────────────────────────
echo "  [STEP 0] 초기화"
rm -rf .edc
$DEBT init --no-hook
echo ""
read -p "  Enter 키를 눌러 계속하세요..."
echo ""

# ── 1. 나쁜 에이전트 세션 분석 ────────────────────────────────────────────
echo "  [STEP 1] 근거 없는 에이전트 세션 분석"
echo "  $SEP"
$DEBT watch --file examples/demo_oauth/session.json
echo ""
read -p "  Enter 키를 눌러 계속하세요..."
echo ""

# ── 2. 부채 목록 ──────────────────────────────────────────────────────────
echo "  [STEP 2] 인지부채 목록 확인"
echo "  $SEP"
$DEBT ls
echo ""
read -p "  Enter 키를 눌러 계속하세요..."
echo ""

# ── 3. 판정 ───────────────────────────────────────────────────────────────
echo "  [STEP 3] 판정 — APPROVAL_REQUIRED 예상"
echo "  $SEP"
$DEBT judge || true
echo ""
read -p "  Enter 키를 눌러 계속하세요..."
echo ""

# ── 4. 부채 상환 ──────────────────────────────────────────────────────────
echo "  [STEP 4] 인지부채 상환"
echo "  $SEP"

# ASSUME_FACT ID 추출
ASSUME_ID=$($DEBT ls --json 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
ids = [x['id'] for x in data if x['rule_id'] == 'ASSUME_FACT' and not x['resolved']]
print(ids[0] if ids else '')
")

HEDGE_ID=$($DEBT ls --json 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
ids = [x['id'] for x in data if x['rule_id'] == 'HEDGE_STRONG' and not x['resolved']]
print(ids[0] if ids else '')
")

EDIT_ID=$($DEBT ls --json 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
ids = [x['id'] for x in data if x['rule_id'] == 'EDIT_NO_TEST' and not x['resolved']]
print(ids[0] if ids else '')
")

echo "  [4-1] 코드 근거로 ASSUME_FACT 상환: $ASSUME_ID"
$DEBT repay "$ASSUME_ID" --code "src/middleware/auth.js:47"

echo "  [4-2] 문서 근거로 HEDGE_STRONG 상환: $HEDGE_ID"
$DEBT repay "$HEDGE_ID" --doc "RFC 6749 Section 4.1.2: redirect_uri는 authorization request 전 session에 저장되어야 함"

echo "  [4-3] 수동 확인으로 EDIT_NO_TEST 상환: $EDIT_ID"
$DEBT repay "$EDIT_ID" --manual "grep 및 failing test 재현으로 원인 auth.js:47 확인"

read -p "  Enter 키를 눌러 계속하세요..."
echo ""

# ── 5. 재판정 ─────────────────────────────────────────────────────────────
echo "  [STEP 5] 재판정"
echo "  $SEP"
$DEBT judge || true
echo ""
read -p "  Enter 키를 눌러 계속하세요..."
echo ""

# ── 6. 이상적 세션 비교 ───────────────────────────────────────────────────
echo "  [STEP 6] 비교: 이상적 에이전트 세션"
echo "  $SEP"
rm -rf .edc
$DEBT init --no-hook 2>&1 | grep "✓"
$DEBT watch --file examples/demo_oauth/session_repaid.json
$DEBT judge || true

echo ""
echo "  $SEP"
echo "  데모 완료."
echo "  나쁜 에이전트: 215점, 13건  →  APPROVAL_REQUIRED"
echo "  이상적 에이전트:  25점,  1건  →  EVIDENCE_REQUIRED"
echo "  $SEP"
echo ""
