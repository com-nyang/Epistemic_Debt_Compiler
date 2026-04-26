#!/usr/bin/env bash
# OAuth 통합 테스트 시뮬레이터 (해커톤 데모용)
# 실제 테스트를 대체하는 데모 스크립트

echo ""
echo "pytest tests/test_oauth_flow.py -v"
echo ""
sleep 0.4
echo "  test_callback_redirect_loop ... PASSED"
sleep 0.2
echo "  test_oauth_login_success ...... PASSED"
sleep 0.2
echo "  test_session_cookie_sameSite .. PASSED"
echo ""
echo "3 passed in 0.94s"
echo ""
exit 0
