#!/usr/bin/env bash

# Epistemic Debt Compiler - tmux 실시간 대시보드 스크립트
# 사용법: ./debt-dashboard.sh <세션로그파일_경로>

SESSION_FILE=$1
SESSION_NAME="edc-dashboard"

if [ -z "$SESSION_FILE" ]; then
    echo "사용법: $0 <세션로그파일_경로>"
    echo "예: $0 .codex/sessions/latest.jsonl"
    exit 1
fi

# 절대 경로 설정
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"
DEBT_BIN="$PROJECT_ROOT/debt"

# 기존 세션이 있으면 종료
tmux kill-session -t "$SESSION_NAME" 2>/dev/null

# API 키 확인 및 옵션 설정
WATCH_OPTS="--quiet"
if [ -n "$GEMINI_API_KEY" ] || [ -n "$GOOGLE_API_KEY" ]; then
    WATCH_OPTS="$WATCH_OPTS --precise"
    AI_STATUS="(AI Reviewer Active)"
else
    AI_STATUS="(Rule-based only)"
fi

# 1. 새 tmux 세션 시작
tmux new-session -d -x 160 -y 40 -s "$SESSION_NAME" -n "EDC-Main"

# 2. 화면 분할
tmux split-window -h
tmux split-window -v

# 현재 포커스 기준 (0: 맨 왼쪽, 1: 우상단, 2: 우하단. 만약 1-based라면 1,2,3)
# tmux send-keys에 타겟을 주지 않고, select-pane과 조합
tmux select-layout main-vertical

# Pane 1 (우상단) - 실시간 로그 분석
tmux send-keys "cd $PROJECT_ROOT && source .venv/bin/activate && echo 'Monitoring: $AI_STATUS' && tail -f $SESSION_FILE | $PYTHON_BIN $DEBT_BIN watch $WATCH_OPTS" C-m

# Pane 2 (우하단) - 부채 현황 보드 (기본 10개 최신순 표시)
tmux select-pane -D
tmux send-keys "cd $PROJECT_ROOT && source .venv/bin/activate && watch -n 1 -c $PYTHON_BIN $DEBT_BIN ls" C-m

# Pane 0 (좌측)
tmux select-pane -L
tmux send-keys "cd $PROJECT_ROOT && source .venv/bin/activate" C-m
tmux send-keys "clear" C-m
tmux send-keys "# 여기서 에이전트와 대화하세요" C-m

# 5. 세션 부착
tmux attach-session -t "$SESSION_NAME"
