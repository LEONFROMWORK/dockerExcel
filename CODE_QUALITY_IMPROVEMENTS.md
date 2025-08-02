# Collabora 통합 코드 품질 개선 사항

## 즉시 적용된 보안 개선

### 1. 환경변수 기반 URL 관리
- **수정 전**: `http://localhost:8000` 하드코딩
- **수정 후**: `os.getenv('WOPI_BASE_URL', 'http://localhost:8000')`

### 2. 권한 검증 강화
- **수정 전**: `UserCanWrite=True` (항상 쓰기 허용)
- **수정 후**: `UserCanWrite=(token.permission == "write")`

### 3. 파일 업로드 보안
- **파일 크기 제한**: 100MB
- **허용 확장자**: `.xlsx`, `.xls`, `.xlsm`, `.ods`

### 4. PostMessage 보안
- **수정 전**: `event.origin.includes('localhost:9980')`
- **수정 후**: 화이트리스트 기반 엄격한 검증

## 추가 권장 개선사항

### 1. 성능 최적화

#### Redis 연결 풀링
```python
# token_manager.py
class RedisTokenManager(TokenService):
    def __init__(self, redis_url: str, pool_size: int = 10):
        self.pool = redis.ConnectionPool.from_url(
            redis_url,
            max_connections=pool_size,
            decode_responses=True
        )
```

#### 파일 스트리밍 처리
```python
# file_storage.py
async def save_file_content_streaming(self, file_id: str, content_stream):
    file_path = await self.get_file_path(file_id)
    total_size = 0
    
    async with aiofiles.open(file_path, 'wb') as f:
        async for chunk in content_stream:
            if total_size + len(chunk) > self.max_file_size:
                raise ValueError("File size exceeded")
            await f.write(chunk)
            total_size += len(chunk)
```

### 2. 보안 강화

#### JWT 토큰 구현
```python
# token_service.py
import jwt
from datetime import datetime, timedelta

def generate_jwt_token(user_id: str, file_id: str, permission: str) -> str:
    payload = {
        'user_id': user_id,
        'file_id': file_id,
        'permission': permission,
        'exp': datetime.utcnow() + timedelta(hours=24),
        'iat': datetime.utcnow()
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm='HS256')
```

#### CSRF 보호
```javascript
// collaboraService.js
async generateToken(fileData) {
  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content
  
  return apiClient.post('/wopi/token/generate', {
    ...fileData,
    csrf_token: csrfToken
  })
}
```

### 3. 에러 처리 개선

#### 구조화된 에러 응답
```python
# endpoints.py
class WOPIError(HTTPException):
    def __init__(self, status_code: int, error_code: str, message: str):
        super().__init__(
            status_code=status_code,
            detail={
                "error": error_code,
                "message": message,
                "timestamp": datetime.utcnow().isoformat()
            }
        )

@router.exception_handler(WOPIError)
async def wopi_error_handler(request: Request, exc: WOPIError):
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.detail
    )
```

### 4. 로깅 및 모니터링

#### 구조화된 로깅
```python
# logging_config.py
import structlog

logger = structlog.get_logger()

# endpoints.py
logger.info("wopi.token.generated", 
    user_id=request.user_id,
    file_id=request.file_id,
    permission=request.permission
)
```

#### 성능 메트릭
```python
# middleware.py
from prometheus_client import Counter, Histogram

wopi_requests = Counter('wopi_requests_total', 'Total WOPI requests')
wopi_duration = Histogram('wopi_request_duration_seconds', 'WOPI request duration')

@wopi_duration.time()
async def track_request_time(request, call_next):
    wopi_requests.inc()
    response = await call_next(request)
    return response
```

### 5. 테스트 커버리지

#### 단위 테스트
```python
# test_token_manager.py
import pytest
from app.contexts.wopi.infrastructure import RedisTokenManager

@pytest.mark.asyncio
async def test_token_generation():
    manager = RedisTokenManager("redis://localhost")
    token = await manager.generate_token(
        file_id="test123",
        user_id="user1",
        permission="write"
    )
    assert token.access_token is not None
    assert len(token.access_token) == 43  # base64 32 bytes
```

#### 통합 테스트
```javascript
// useCollabora.test.js
import { renderHook } from '@testing-library/vue'
import { useCollabora } from './useCollabora'

test('handles postMessage correctly', async () => {
  const { result } = renderHook(() => useCollabora())
  
  const mockEvent = new MessageEvent('message', {
    origin: 'http://localhost:9980',
    data: { MessageId: 'App_LoadingStatus', Values: { Status: 'Loaded' } }
  })
  
  window.dispatchEvent(mockEvent)
  expect(result.current.state.isReady).toBe(true)
})
```

## 프로덕션 체크리스트

- [ ] 모든 환경변수 설정 (.env.production)
- [ ] SSL/TLS 인증서 설정
- [ ] Rate limiting 구현
- [ ] 로그 수집 시스템 연동
- [ ] 모니터링 대시보드 설정
- [ ] 백업 및 복구 계획
- [ ] 보안 감사 실시
- [ ] 부하 테스트 수행
- [ ] 장애 복구 계획 수립
- [ ] 문서화 완료

## 결론

현재 구현된 코드는 SOLID 원칙을 잘 준수하고 있으며, 기본적인 보안과 성능을 고려하여 작성되었습니다. 위의 개선사항들을 점진적으로 적용하면 프로덕션 환경에서도 안정적으로 운영할 수 있는 시스템이 될 것입니다.