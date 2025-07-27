#!/bin/bash
# 환경 변수 검증 스크립트
# 프로덕션 배포 전 필수 환경 변수들이 모두 설정되었는지 확인

set -e

ENV_FILE=".env.production"
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "🔍 환경 변수 검증 시작..."
echo "========================="

# 필수 환경 변수 목록
REQUIRED_VARS=(
    "POSTGRES_PASSWORD"
    "RAILS_MASTER_KEY"
    "SECRET_KEY_BASE"
    "GOOGLE_OAUTH2_CLIENT_ID"
    "GOOGLE_OAUTH2_CLIENT_SECRET"
    "OPENAI_API_KEY"
)

# 권장 환경 변수 목록
RECOMMENDED_VARS=(
    "OPENROUTER_API_KEY"
    "GRAFANA_PASSWORD"
)

# 환경 변수 파일 존재 확인
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}❌ $ENV_FILE 파일이 존재하지 않습니다.${NC}"
    echo "   템플릿을 복사하여 생성해주세요:"
    echo "   cp .env.production.example .env.production"
    exit 1
fi

echo "✅ $ENV_FILE 파일 발견"
echo ""

# 환경 변수 로드
set -a
source "$ENV_FILE"
set +a

MISSING_REQUIRED=0
MISSING_RECOMMENDED=0

# 필수 환경 변수 검증
echo "🔑 필수 환경 변수 검증"
echo "--------------------"

for var in "${REQUIRED_VARS[@]}"; do
    value="${!var}"
    if [ -z "$value" ] || [[ "$value" == *"your-"* ]] || [[ "$value" == *"your_"* ]]; then
        echo -e "${RED}❌ $var: 설정되지 않음 또는 기본값${NC}"
        ((MISSING_REQUIRED++))
    else
        # 민감한 정보는 마스킹
        masked_value=$(echo "$value" | sed 's/./*/g')
        echo -e "${GREEN}✅ $var: ${masked_value:0:10}...${NC}"
    fi
done

echo ""

# 권장 환경 변수 검증
echo "💡 권장 환경 변수 검증"
echo "--------------------"

for var in "${RECOMMENDED_VARS[@]}"; do
    value="${!var}"
    if [ -z "$value" ] || [[ "$value" == *"your-"* ]] || [[ "$value" == *"your_"* ]]; then
        echo -e "${YELLOW}⚠️  $var: 설정되지 않음 (선택사항)${NC}"
        ((MISSING_RECOMMENDED++))
    else
        masked_value=$(echo "$value" | sed 's/./*/g')
        echo -e "${GREEN}✅ $var: ${masked_value:0:10}...${NC}"
    fi
done

echo ""

# 성능 설정 검증
echo "⚡ 성능 설정 검증"
echo "----------------"

check_numeric_var() {
    local var_name=$1
    local var_value="${!var_name}"
    local min_val=${2:-1}
    local max_val=${3:-999}
    
    if [[ "$var_value" =~ ^[0-9]+$ ]] && [ "$var_value" -ge "$min_val" ] && [ "$var_value" -le "$max_val" ]; then
        echo -e "${GREEN}✅ $var_name: $var_value${NC}"
    else
        echo -e "${YELLOW}⚠️  $var_name: $var_value (권장: $min_val-$max_val)${NC}"
    fi
}

check_numeric_var "WEB_CONCURRENCY" 2 8
check_numeric_var "RAILS_MAX_THREADS" 8 32
check_numeric_var "PUMA_WORKERS" 2 8

echo ""

# 보안 설정 검증
echo "🔒 보안 설정 검증"
echo "----------------"

# SECRET_KEY_BASE 길이 확인
if [ ${#SECRET_KEY_BASE} -ge 64 ]; then
    echo -e "${GREEN}✅ SECRET_KEY_BASE: 충분한 길이 (${#SECRET_KEY_BASE} chars)${NC}"
else
    echo -e "${RED}❌ SECRET_KEY_BASE: 너무 짧음 (${#SECRET_KEY_BASE} chars, 최소 64 chars 필요)${NC}"
    ((MISSING_REQUIRED++))
fi

# 비밀번호 강도 확인 (간단한 체크)
check_password_strength() {
    local var_name=$1
    local password="${!var_name}"
    
    if [ ${#password} -lt 12 ]; then
        echo -e "${YELLOW}⚠️  $var_name: 12자 이상 권장${NC}"
    elif [[ "$password" =~ [A-Z] ]] && [[ "$password" =~ [a-z] ]] && [[ "$password" =~ [0-9] ]]; then
        echo -e "${GREEN}✅ $var_name: 강한 비밀번호${NC}"
    else
        echo -e "${YELLOW}⚠️  $var_name: 대문자, 소문자, 숫자 조합 권장${NC}"
    fi
}

if [ -n "$POSTGRES_PASSWORD" ] && [[ "$POSTGRES_PASSWORD" != *"your-"* ]]; then
    check_password_strength "POSTGRES_PASSWORD"
fi

echo ""

# 결과 요약
echo "📊 검증 결과 요약"
echo "================"

if [ $MISSING_REQUIRED -eq 0 ]; then
    echo -e "${GREEN}✅ 모든 필수 환경 변수가 설정되었습니다!${NC}"
    if [ $MISSING_RECOMMENDED -gt 0 ]; then
        echo -e "${YELLOW}💡 $MISSING_RECOMMENDED개의 권장 환경 변수가 설정되지 않았습니다.${NC}"
    fi
    echo ""
    echo -e "${GREEN}🚀 프로덕션 배포 준비 완료!${NC}"
    exit 0
else
    echo -e "${RED}❌ $MISSING_REQUIRED개의 필수 환경 변수가 누락되었습니다.${NC}"
    echo ""
    echo "🔧 설정 가이드:"
    echo "1. $ENV_FILE 파일을 편집하세요"
    echo "2. 'your-' 접두사가 있는 값들을 실제 값으로 변경하세요"
    echo "3. SECRET_KEY_BASE는 다음 명령으로 생성할 수 있습니다:"
    echo "   openssl rand -hex 64"
    exit 1
fi