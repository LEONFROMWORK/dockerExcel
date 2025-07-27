#!/bin/bash

# Excel Error Detection System 테스트 실행 스크립트

echo "🧪 Excel Error Detection System 테스트를 시작합니다..."
echo "================================================"

# Python 환경 설정
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# 테스트 커버리지 디렉토리 생성
mkdir -p coverage

# 단위 테스트 실행
echo "📊 단위 테스트 실행 중..."
python -m pytest tests/test_formula_error_detector.py -v --cov=app.services.detection.strategies.formula_error_detector --cov-report=html:coverage/formula_detector

python -m pytest tests/test_integrated_error_detector.py -v --cov=app.services.detection.integrated_error_detector --cov-report=html:coverage/integrated_detector

# 통합 테스트
echo ""
echo "🔗 통합 테스트 실행 중..."
python -m pytest tests/ -v -k "integration" --cov=app --cov-report=html:coverage/integration

# 전체 테스트
echo ""
echo "📋 전체 테스트 실행 중..."
python -m pytest tests/ -v --cov=app --cov-report=html:coverage/all --cov-report=term

# 결과 요약
echo ""
echo "✅ 테스트 완료!"
echo "📁 커버리지 리포트: coverage/ 디렉토리를 확인하세요."

# 테스트 실패 시 종료 코드 반환
if [ $? -ne 0 ]; then
    echo "❌ 일부 테스트가 실패했습니다."
    exit 1
else
    echo "✨ 모든 테스트가 성공했습니다!"
    exit 0
fi