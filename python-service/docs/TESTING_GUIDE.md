# Excel Unified Python Service 테스트 가이드

## 개요
이 문서는 Excel Unified Python Service의 테스트 전략과 실행 방법을 설명합니다.

## 테스트 구조

```
tests/
├── test_integrated_error_detector.py      # 기본 통합 오류 감지기 테스트
├── test_integrated_error_detector_enhanced.py  # 향상된 기능 테스트
├── test_integration_flow.py               # 전체 플로우 통합 테스트
├── test_performance.py                    # 성능 테스트
├── test_advanced_vba_analyzer.py          # VBA 분석기 테스트
├── test_ai_failover_service.py            # AI 페일오버 테스트
└── ...
```

## 테스트 카테고리

### 1. 단위 테스트 (Unit Tests)
개별 컴포넌트의 기능을 테스트합니다.

```bash
# 단위 테스트만 실행
pytest -m unit
```

### 2. 통합 테스트 (Integration Tests)
여러 컴포넌트 간의 상호작용을 테스트합니다.

```bash
# 통합 테스트만 실행
pytest -m integration
```

### 3. 성능 테스트 (Performance Tests)
시스템의 성능과 확장성을 테스트합니다.

```bash
# 성능 테스트만 실행
pytest -m performance
```

## 테스트 실행 방법

### 기본 실행
```bash
# 모든 테스트 실행
pytest

# 특정 파일 테스트
pytest tests/test_integrated_error_detector_enhanced.py

# 특정 테스트 함수 실행
pytest tests/test_integration_flow.py::TestIntegrationFlow::test_full_flow_file_upload_to_ai_chat
```

### 커버리지 확인
```bash
# 커버리지 리포트 생성
pytest --cov=app --cov-report=html

# HTML 리포트 확인
open htmlcov/index.html
```

### 병렬 실행
```bash
# pytest-xdist 설치
pip install pytest-xdist

# CPU 코어 수만큼 병렬 실행
pytest -n auto
```

### 상세 출력
```bash
# 상세한 출력과 함께 실행
pytest -v -s

# 실패한 테스트만 재실행
pytest --lf
```

## 주요 테스트 시나리오

### 1. IntegratedErrorDetector 테스트
- 캐시 동작 검증
- 병렬 처리 최적화 확인
- 배치 처리 성능 검증
- 스트리밍 처리 테스트

### 2. 전체 플로우 테스트
- 파일 업로드 → 오류 감지 → AI 채팅
- WebSocket 실시간 업데이트
- Rails-Python 통신 브리지
- 멀티 셀 선택 분석

### 3. 성능 테스트
- 대용량 파일 처리 (100개 시트)
- 동시 요청 처리 (50개 동시 요청)
- 배치 처리 (1000개 셀)
- 캐시 읽기/쓰기 성능

## 테스트 작성 가이드

### 비동기 테스트
```python
import pytest

@pytest.mark.asyncio
async def test_async_function():
    result = await some_async_function()
    assert result == expected_value
```

### 모킹 예제
```python
from unittest.mock import MagicMock, AsyncMock, patch

@pytest.fixture
def mock_service():
    service = MagicMock()
    service.async_method = AsyncMock(return_value="mocked")
    return service

async def test_with_mock(mock_service):
    result = await mock_service.async_method()
    assert result == "mocked"
```

### 성능 측정
```python
import time

async def test_performance():
    start_time = time.time()

    # 테스트할 작업 실행
    await heavy_operation()

    end_time = time.time()
    processing_time = end_time - start_time

    # 성능 기준 확인
    assert processing_time < 5  # 5초 이내
```

## 테스트 환경 설정

### 필수 패키지
```bash
pip install pytest pytest-asyncio pytest-cov pytest-xdist pytest-timeout
```

### 환경 변수
```bash
# 테스트용 환경 변수
export TESTING=true
export DATABASE_URL=postgresql://test:test@localhost/test_db
export REDIS_URL=redis://localhost:6379/1
```

## CI/CD 통합

### GitHub Actions 예제
```yaml
name: Python Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v2

    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install -r requirements-test.txt

    - name: Run tests
      run: |
        pytest --cov=app --cov-report=xml

    - name: Upload coverage
      uses: codecov/codecov-action@v1
```

## 트러블슈팅

### 일반적인 문제

1. **ImportError**: Python 경로 문제
   ```bash
   export PYTHONPATH=$PYTHONPATH:/path/to/python-service
   ```

2. **Async 테스트 실패**: event loop 문제
   ```python
   # pytest.ini에 추가
   asyncio_mode = auto
   ```

3. **메모리 부족**: 대용량 테스트
   ```bash
   # 메모리 제한 증가
   pytest --max-memory=4GB
   ```

## 베스트 프랙티스

1. **격리된 테스트**: 각 테스트는 독립적이어야 함
2. **명확한 이름**: 테스트 이름은 테스트 내용을 명확히 설명
3. **적절한 모킹**: 외부 의존성은 모킹
4. **성능 기준**: 성능 테스트는 명확한 기준 설정
5. **정리 작업**: 테스트 후 리소스 정리

## 테스트 커버리지 목표

- 전체 커버리지: 80% 이상
- 핵심 모듈 커버리지: 90% 이상
- API 엔드포인트: 100% 커버리지

## 연락처

테스트 관련 문의사항이 있으시면 다음으로 연락주세요:
- 이메일: dev@excel-unified.com
- Slack: #excel-unified-testing
