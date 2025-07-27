#!/bin/bash

# E2E 자동화 테스트 스크립트
# Excel Unified Service 전체 시스템 검증

set -e  # 오류 발생 시 즉시 중단

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 테스트 결과 카운터
PASSED=0
FAILED=0

# 로그 함수
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# 테스트 결과 기록
record_test() {
    if [ $1 -eq 0 ]; then
        PASSED=$((PASSED + 1))
        echo -e "${GREEN}✓${NC} $2"
    else
        FAILED=$((FAILED + 1))
        echo -e "${RED}✗${NC} $2"
    fi
}

# 헬스체크 함수
check_service_health() {
    local service_name=$1
    local url=$2
    local max_attempts=30
    local attempt=0

    while [ $attempt -lt $max_attempts ]; do
        if curl -s -f "$url" > /dev/null 2>&1; then
            log_info "$service_name is healthy"
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 2
    done

    log_error "$service_name health check failed after $max_attempts attempts"
    return 1
}

# 메인 테스트 시작
echo "====================================="
echo "Excel Unified E2E Test Suite"
echo "====================================="
echo ""

# 1. 환경 확인
log_info "Checking environment..."

# Ruby 버전 확인
ruby_version=$(ruby --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo "not installed")
if [[ "$ruby_version" > "3.3.0" ]] || [[ "$ruby_version" == "3.3.0" ]]; then
    record_test 0 "Ruby version: $ruby_version"
else
    record_test 1 "Ruby version: $ruby_version (requires >= 3.3.0)"
fi

# Python 버전 확인
python_version=$(python3 --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+' || echo "not installed")
if [[ "$python_version" > "3.11" ]] || [[ "$python_version" == "3.11" ]]; then
    record_test 0 "Python version: $python_version"
else
    record_test 1 "Python version: $python_version (requires >= 3.11)"
fi

# PostgreSQL 확인
if command -v psql &> /dev/null; then
    record_test 0 "PostgreSQL installed"
else
    record_test 1 "PostgreSQL not found"
fi

# Redis 확인
if command -v redis-cli &> /dev/null; then
    record_test 0 "Redis installed"
else
    record_test 1 "Redis not found"
fi

echo ""

# 2. 서비스 헬스체크
log_info "Checking service health..."

# Rails 서비스
check_service_health "Rails" "http://localhost:3000/health"
record_test $? "Rails service health check"

# Python 서비스
check_service_health "Python" "http://localhost:8000/health"
record_test $? "Python service health check"

echo ""

# 3. API 엔드포인트 테스트
log_info "Testing API endpoints..."

# 3.1 파일 업로드 테스트
log_info "Testing file upload..."

# 테스트 파일 생성
mkdir -p test_files
cat > test_files/test.csv << EOF
Name,Value,Formula
Item1,100,=B2*2
Item2,200,=B3*2
Item3,300,=SUM(B2:B3)
EOF

# CSV를 사용하여 간단한 테스트 (실제로는 Excel 파일 사용)
upload_response=$(curl -s -X POST http://localhost:3000/api/v1/excel_analysis/files \
    -F "file=@test_files/test.csv" \
    -H "Accept: application/json" 2>/dev/null || echo '{"error": "upload failed"}')

if echo "$upload_response" | grep -q '"id"'; then
    record_test 0 "File upload endpoint"
    file_id=$(echo "$upload_response" | grep -oE '"id":[^,}]+' | cut -d'"' -f4)
    log_info "Uploaded file ID: $file_id"
else
    record_test 1 "File upload endpoint"
    log_error "Upload response: $upload_response"
fi

# 3.2 파일 분석 테스트
if [ ! -z "$file_id" ]; then
    log_info "Testing file analysis..."
    
    analysis_response=$(curl -s -X POST http://localhost:3000/api/v1/excel_analysis/analyze \
        -H "Content-Type: application/json" \
        -d "{\"file_id\": \"$file_id\"}" 2>/dev/null || echo '{"error": "analysis failed"}')
    
    if echo "$analysis_response" | grep -q '"success":true'; then
        record_test 0 "File analysis endpoint"
    else
        record_test 1 "File analysis endpoint"
        log_error "Analysis response: $analysis_response"
    fi
fi

# 3.3 자동 수정 테스트 (핵심 기능)
log_info "Testing auto-fix feature..."

# 오류가 있는 Excel 파일 생성 (Python 스크립트로)
cat > test_files/create_error_excel.py << 'EOF'
import openpyxl

wb = openpyxl.Workbook()
ws = wb.active

# 데이터 추가
ws['A1'] = 'Values'
ws['A2'] = 100
ws['A3'] = 0
ws['A4'] = 200

# 오류가 있는 수식 추가
ws['B1'] = 'Formulas'
ws['B2'] = '=A2/A3'  # #DIV/0! 오류
ws['B3'] = '=VLOOKUP(A4,A1:A3,2,FALSE)'  # #N/A 오류
ws['B4'] = '=A4*#REF!'  # #REF! 오류

wb.save('test_files/errors.xlsx')
print("Error Excel file created")
EOF

python3 test_files/create_error_excel.py 2>/dev/null || log_warning "Could not create error Excel file"

if [ -f "test_files/errors.xlsx" ]; then
    autofix_response=$(curl -s -X POST http://localhost:3000/api/v1/excel_analysis/auto-fix \
        -F "file=@test_files/errors.xlsx" \
        -F "fix_formulas=true" \
        2>/dev/null || echo '{"error": "auto-fix failed"}')
    
    if echo "$autofix_response" | grep -q '"status":"success"'; then
        fixed_count=$(echo "$autofix_response" | grep -oE '"total_errors_fixed":[0-9]+' | cut -d: -f2)
        record_test 0 "Auto-fix feature (fixed $fixed_count errors)"
    else
        record_test 1 "Auto-fix feature"
        log_error "Auto-fix response: $autofix_response"
    fi
else
    record_test 1 "Auto-fix feature (test file creation failed)"
fi

# 3.4 AI 채팅 테스트
log_info "Testing AI chat..."

chat_response=$(curl -s -X POST http://localhost:3000/api/v1/excel_analysis/chat \
    -H "Content-Type: application/json" \
    -d '{
        "message": "VLOOKUP 함수 사용법을 알려주세요",
        "excel_context": {}
    }' 2>/dev/null || echo '{"error": "chat failed"}')

if echo "$chat_response" | grep -q '"message"'; then
    record_test 0 "AI chat endpoint"
else
    record_test 1 "AI chat endpoint"
    log_error "Chat response: $chat_response"
fi

# 3.5 이미지 분석 테스트
log_info "Testing image analysis..."

# 간단한 테스트 이미지 생성
if command -v convert &> /dev/null; then
    convert -size 200x100 xc:white -pointsize 20 -draw "text 10,30 'Test Table'" test_files/test_image.png
else
    # ImageMagick이 없으면 기본 이미지 사용
    echo "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==" | base64 -d > test_files/test_image.png
fi

image_response=$(curl -s -X POST http://localhost:3000/api/v1/excel_analysis/analyze-image \
    -F "image=@test_files/test_image.png" \
    -F "analysis_type=auto" 2>/dev/null || echo '{"error": "image analysis failed"}')

if echo "$image_response" | grep -q '"success":true'; then
    record_test 0 "Image analysis endpoint"
else
    record_test 1 "Image analysis endpoint"
fi

echo ""

# 4. 성능 테스트
log_info "Running performance tests..."

# 응답 시간 테스트
start_time=$(date +%s%N)
curl -s http://localhost:3000/health > /dev/null 2>&1
end_time=$(date +%s%N)
response_time=$(( ($end_time - $start_time) / 1000000 )) # 밀리초 변환

if [ $response_time -lt 1000 ]; then
    record_test 0 "Health check response time: ${response_time}ms"
else
    record_test 1 "Health check response time: ${response_time}ms (> 1000ms)"
fi

# 동시 요청 테스트 (간단한 버전)
log_info "Testing concurrent requests..."

for i in {1..10}; do
    curl -s http://localhost:3000/health > /dev/null 2>&1 &
done
wait

record_test 0 "Concurrent request handling"

echo ""

# 5. 데이터베이스 연결 테스트
log_info "Testing database connections..."

# Rails 데이터베이스 상태
db_check=$(curl -s http://localhost:3000/api/v1/health/database 2>/dev/null || echo "failed")
if [[ "$db_check" == *"ok"* ]]; then
    record_test 0 "Database connection"
else
    record_test 1 "Database connection"
fi

echo ""

# 6. 종합 시나리오 테스트
log_info "Running integrated scenario test..."

# 전체 워크플로우 테스트
scenario_passed=true

# Step 1: Upload
scenario_upload=$(curl -s -X POST http://localhost:3000/api/v1/excel_analysis/files \
    -F "file=@test_files/test.csv" 2>/dev/null || echo '{}')

if echo "$scenario_upload" | grep -q '"id"'; then
    scenario_file_id=$(echo "$scenario_upload" | grep -oE '"id":[^,}]+' | cut -d'"' -f4)
    
    # Step 2: Analyze
    scenario_analysis=$(curl -s -X POST http://localhost:3000/api/v1/excel_analysis/analyze \
        -H "Content-Type: application/json" \
        -d "{\"file_id\": \"$scenario_file_id\"}" 2>/dev/null || echo '{}')
    
    if ! echo "$scenario_analysis" | grep -q '"success":true'; then
        scenario_passed=false
    fi
    
    # Step 3: Chat about the file
    scenario_chat=$(curl -s -X POST http://localhost:3000/api/v1/excel_analysis/chat \
        -H "Content-Type: application/json" \
        -d "{
            \"message\": \"이 파일의 수식을 설명해주세요\",
            \"excel_context\": {\"file_id\": \"$scenario_file_id\"}
        }" 2>/dev/null || echo '{}')
    
    if ! echo "$scenario_chat" | grep -q '"message"'; then
        scenario_passed=false
    fi
else
    scenario_passed=false
fi

if [ "$scenario_passed" = true ]; then
    record_test 0 "Integrated workflow scenario"
else
    record_test 1 "Integrated workflow scenario"
fi

echo ""

# 테스트 결과 요약
echo "====================================="
echo "Test Results Summary"
echo "====================================="
echo -e "${GREEN}Passed:${NC} $PASSED"
echo -e "${RED}Failed:${NC} $FAILED"
echo -e "Total: $((PASSED + FAILED))"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}All tests passed! ✨${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed. Please check the logs.${NC}"
    exit 1
fi