#!/bin/bash
# Docker 서비스 종합 헬스체크 스크립트
# 모든 서비스의 상태를 확인하고 상세한 진단 정보를 제공

set -e

echo "🔍 Docker 서비스 종합 헬스체크 시작..."
echo "=========================================="

# 색상 코드 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 서비스 목록
SERVICES=("postgres" "redis" "rails" "python" "sidekiq" "nginx")
COMPOSE_FILE="docker-compose.prod.yml"

# 전체 상태 추적
HEALTHY_COUNT=0
UNHEALTHY_COUNT=0
TOTAL_SERVICES=${#SERVICES[@]}

# 각 서비스 헬스체크 함수
check_service_health() {
    local service=$1
    local status=$(docker-compose -f $COMPOSE_FILE ps -q $service | xargs docker inspect --format='{{.State.Health.Status}}' 2>/dev/null || echo "no-health-check")
    
    echo -n "📊 $service: "
    case $status in
        "healthy")
            echo -e "${GREEN}✅ HEALTHY${NC}"
            ((HEALTHY_COUNT++))
            ;;
        "unhealthy")
            echo -e "${RED}❌ UNHEALTHY${NC}"
            ((UNHEALTHY_COUNT++))
            show_service_logs $service
            ;;
        "starting")
            echo -e "${YELLOW}⏳ STARTING${NC}"
            ;;
        "no-health-check")
            echo -e "${BLUE}ℹ️  NO HEALTH CHECK${NC}"
            check_service_running $service
            ;;
        *)
            echo -e "${RED}❓ UNKNOWN ($status)${NC}"
            ((UNHEALTHY_COUNT++))
            ;;
    esac
}

# 서비스 실행 상태 확인 (헬스체크가 없는 경우)
check_service_running() {
    local service=$1
    local running=$(docker-compose -f $COMPOSE_FILE ps -q $service | xargs docker inspect --format='{{.State.Running}}' 2>/dev/null || echo "false")
    
    if [ "$running" = "true" ]; then
        echo -e "   ${GREEN}✅ RUNNING${NC}"
        ((HEALTHY_COUNT++))
    else
        echo -e "   ${RED}❌ NOT RUNNING${NC}"
        ((UNHEALTHY_COUNT++))
        show_service_logs $service
    fi
}

# 서비스 로그 출력
show_service_logs() {
    local service=$1
    echo -e "${YELLOW}📋 최근 로그 ($service):${NC}"
    docker-compose -f $COMPOSE_FILE logs --tail=5 $service | sed 's/^/   /'
    echo ""
}

# 네트워크 연결 테스트
test_network_connectivity() {
    echo ""
    echo "🌐 네트워크 연결 테스트"
    echo "------------------------"
    
    # Rails 헬스체크
    if curl -s -f http://localhost/health > /dev/null 2>&1; then
        echo -e "✅ Rails API: ${GREEN}HEALTHY${NC}"
    else
        echo -e "❌ Rails API: ${RED}UNHEALTHY${NC}"
        echo "   - URL: http://localhost/health 연결 실패"
    fi
    
    # Python API 헬스체크
    if curl -s -f http://localhost/api/v1/python/health > /dev/null 2>&1; then
        echo -e "✅ Python API: ${GREEN}HEALTHY${NC}"
    else
        echo -e "❌ Python API: ${RED}UNHEALTHY${NC}"
        echo "   - URL: http://localhost/api/v1/python/health 연결 실패"
    fi
}

# 리소스 사용량 확인
check_resource_usage() {
    echo ""
    echo "💾 리소스 사용량"
    echo "---------------"
    
    # Docker stats (한 번만 실행)
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}" \
        $(docker-compose -f $COMPOSE_FILE ps -q) 2>/dev/null || echo "리소스 정보를 가져올 수 없습니다."
}

# 볼륨 상태 확인
check_volumes() {
    echo ""
    echo "💿 볼륨 상태"
    echo "------------"
    
    local volumes=$(docker-compose -f $COMPOSE_FILE config --volumes 2>/dev/null)
    for volume in $volumes; do
        local size=$(docker system df -v | grep "$volume" | awk '{print $3}' || echo "Unknown")
        echo "📦 $volume: $size"
    done
}

# 메인 헬스체크 실행
echo "🏥 서비스별 헬스체크"
echo "-------------------"

for service in "${SERVICES[@]}"; do
    check_service_health $service
done

# 전체 결과 요약
echo ""
echo "📈 전체 상태 요약"
echo "=================="
echo -e "✅ 정상 서비스: ${GREEN}$HEALTHY_COUNT/$TOTAL_SERVICES${NC}"
echo -e "❌ 비정상 서비스: ${RED}$UNHEALTHY_COUNT/$TOTAL_SERVICES${NC}"

if [ $UNHEALTHY_COUNT -eq 0 ]; then
    echo -e "${GREEN}🎉 모든 서비스가 정상 상태입니다!${NC}"
    EXIT_CODE=0
else
    echo -e "${RED}⚠️  일부 서비스에 문제가 있습니다.${NC}"
    EXIT_CODE=1
fi

# 추가 진단 정보
test_network_connectivity
check_resource_usage
check_volumes

echo ""
echo "🔧 문제 해결 가이드"
echo "==================="
echo "• 서비스 재시작: docker-compose -f $COMPOSE_FILE restart [service_name]"
echo "• 로그 확인: docker-compose -f $COMPOSE_FILE logs -f [service_name]"
echo "• 전체 재시작: docker-compose -f $COMPOSE_FILE down && docker-compose -f $COMPOSE_FILE up -d"
echo "• 상세 상태: docker-compose -f $COMPOSE_FILE ps"

echo ""
echo "헬스체크 완료: $(date)"
exit $EXIT_CODE