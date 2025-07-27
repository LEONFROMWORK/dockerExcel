#!/bin/bash
# 모든 서비스 강제 시작

echo "🚀 Excel Unified 모든 서비스 시작 중..."

# 기존 프로세스 종료
echo "기존 프로세스 종료 중..."
pkill -f "rails server" || true
pkill -f "vite" || true
pkill -f "uvicorn" || true
pkill -f "sidekiq" || true

# PostgreSQL과 Redis 확인
if ! pg_isready -h localhost -p 5432 > /dev/null 2>&1; then
    echo "⚠️  PostgreSQL이 실행되지 않았습니다. 시작해주세요."
    exit 1
fi

if ! redis-cli ping > /dev/null 2>&1; then
    echo "⚠️  Redis가 실행되지 않았습니다. 시작해주세요."
    exit 1
fi

# tmux 세션으로 모든 서비스 실행
tmux new-session -d -s excel-unified
tmux send-keys -t excel-unified "cd rails-app && bin/dev" C-m
tmux new-window -t excel-unified -n python
tmux send-keys -t excel-unified:python "cd python-service && uvicorn main:app --reload --port 8000" C-m
tmux new-window -t excel-unified -n sidekiq
tmux send-keys -t excel-unified:sidekiq "cd rails-app && bundle exec sidekiq" C-m

echo "✅ 모든 서비스가 시작되었습니다!"
echo "📍 Rails: http://localhost:3000"
echo "📍 Python API: http://localhost:8000"
echo "📍 Vite: http://localhost:5173"
echo ""
echo "tmux attach -t excel-unified 명령어로 서비스 로그를 확인하세요."