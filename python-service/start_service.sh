#!/bin/bash

# Excel Error Detection Service 시작 스크립트

echo "🚀 Excel Error Detection Service를 시작합니다..."
echo "================================================"

# 환경 변수 설정
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
export ENVIRONMENT="development"
export DEBUG="True"

# 필요한 패키지 확인
echo "📦 필요한 패키지 확인 중..."
pip install -r requirements.txt --quiet

# 기존 프로세스 종료
echo "🔄 기존 프로세스 확인 중..."
if lsof -ti:8000 > /dev/null 2>&1; then
    echo "   기존 서버 종료 중..."
    kill -9 $(lsof -ti:8000) 2>/dev/null
    sleep 2
fi

# FastAPI 서버 시작
echo "🌟 FastAPI 서버 시작..."
echo "   URL: http://localhost:8000"
echo "   API 문서: http://localhost:8000/docs"
echo "   WebSocket: ws://localhost:8000/ws/excel/{session_id}"
echo ""
echo "   종료하려면 Ctrl+C를 누르세요"
echo "================================================"

# 서버 실행
uvicorn main:app --reload --host 0.0.0.0 --port 8000 --log-level info