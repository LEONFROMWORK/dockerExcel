#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if .env file exists
if [ ! -f ".env" ]; then
    log_error ".env 파일이 존재하지 않습니다."
    exit 1
fi

# Load environment variables from .env file with error handling
log_info ".env 파일에서 환경변수 로딩 중..."
# Use set -a to export all variables, then source .env, then unset -a
set -a
if source .env 2>/dev/null; then
    log_success "환경변수 로딩 완료"
else
    log_warning ".env 파일 로딩 실패, 기본값 사용"
fi
set +a

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    log_warning "가상환경이 존재하지 않습니다. 새로 생성 중..."
    python3 -m venv venv
    log_success "가상환경 생성 완료"
fi

# Activate virtual environment
log_info "가상환경 활성화 중..."
source venv/bin/activate
if [ $? -eq 0 ]; then
    log_success "가상환경 활성화 완료"
else
    log_error "가상환경 활성화 실패"
    exit 1
fi

# Check if pip is available
if ! command -v pip &> /dev/null; then
    log_error "pip가 설치되지 않았습니다."
    exit 1
fi

# Install/upgrade pip
log_info "pip 업그레이드 중..."
pip install --upgrade pip > /dev/null 2>&1

# Install requirements if needed
log_info "Python 의존성 확인 및 설치 중..."
if ! pip install -r requirements.txt; then
    log_error "의존성 설치 실패"
    exit 1
fi
log_success "의존성 설치 완료"

# Check if main.py exists
if [ ! -f "main.py" ]; then
    log_error "main.py 파일이 존재하지 않습니다."
    exit 1
fi

# Check if port 8000 is available
if lsof -ti:8000 > /dev/null 2>&1; then
    log_warning "포트 8000이 이미 사용 중입니다. 기존 프로세스를 종료합니다."
    kill -9 $(lsof -ti:8000) 2>/dev/null || true
    sleep 2
fi

# Start the Python service with loaded environment variables
log_info "Python FastAPI 서비스 시작 중... (포트 8000)"
uvicorn main:app --reload --port 8000 --host 0.0.0.0
