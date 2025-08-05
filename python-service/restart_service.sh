#!/bin/bash
# Python 서비스 재시작 스크립트

echo "=== Python 서비스 재시작 ==="

# 기존 프로세스 종료
echo "기존 프로세스 종료 중..."
pkill -f "uvicorn main:app"
sleep 2

# 환경 변수 설정
export OPENROUTER_API_KEY=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

# 서비스 시작
echo "Python 서비스 시작 중..."
cd /Users/kevin/excel-unified/python-service
source venv/bin/activate 2>/dev/null || true
python3 -m uvicorn main:app --reload --port 8000 &

# PID 저장
echo $! > python_service.pid

echo "서비스가 백그라운드에서 시작되었습니다. PID: $(cat python_service.pid)"
echo "로그 확인: tail -f logs/python_service.log"
