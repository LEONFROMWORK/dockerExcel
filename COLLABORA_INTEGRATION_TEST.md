# Collabora Online 통합 테스트 가이드

## 1. 서비스 시작

### Docker 서비스 시작
```bash
cd /Users/kevin/excel-unified
docker-compose up -d
```

### 서비스 확인
```bash
# 모든 컨테이너 상태 확인
docker-compose ps

# Collabora 로그 확인
docker logs collabora

# Collabora 접속 테스트
curl http://localhost:9980
# "OK" 응답이 나오면 성공
```

## 2. WOPI 엔드포인트 테스트

### 토큰 생성 테스트
```bash
curl -X POST http://localhost:8000/wopi/token/generate \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "test123",
    "user_id": "user1",
    "user_name": "Test User",
    "permission": "write"
  }'
```

### CheckFileInfo 테스트
```bash
# 위에서 받은 access_token 사용
curl "http://localhost:8000/wopi/files/test123?access_token=YOUR_TOKEN"
```

## 3. Frontend 테스트

### 1. 브라우저에서 접속
```
http://localhost:3000/excel/viewer
```

### 2. Excel 파일 업로드
- "Upload a file" 클릭
- .xlsx 파일 선택
- 업로드 진행 상황 확인

### 3. Collabora 로딩 확인
- iframe이 로드되는지 확인
- Collabora 툴바가 표시되는지 확인
- 문서가 정상적으로 렌더링되는지 확인

## 4. 기능 테스트

### 문서 편집
1. 셀 클릭하여 편집
2. 수식 입력 테스트
3. 서식 적용 테스트

### 저장 기능
1. Save 버튼 클릭
2. 콘솔에서 저장 로그 확인
3. Python 서비스 로그 확인

### PostMessage 통신
1. 브라우저 개발자 도구 콘솔 열기
2. Collabora 메시지 로그 확인
3. 문서 로드 완료 메시지 확인

## 5. 문제 해결

### Collabora 연결 실패
```bash
# Collabora 재시작
docker-compose restart collabora

# 방화벽 확인
sudo lsof -i :9980
```

### CORS 에러
- Rails 서버 재시작 필요
```bash
docker-compose restart rails
```

### 파일 업로드 실패
- Python 서비스 로그 확인
```bash
docker-compose logs python
```

### iframe 로드 실패
- Collabora discovery URL 확인
```bash
curl http://localhost:9980/hosting/discovery
```

## 6. 성능 테스트

### 대용량 파일 테스트
- 10MB 이상 Excel 파일 업로드
- 로딩 시간 측정
- 메모리 사용량 확인

### 동시 접속 테스트
- 여러 브라우저 탭에서 동시 접속
- 편집 충돌 테스트

## 7. 로그 모니터링

### 실시간 로그 확인
```bash
# 모든 서비스 로그
docker-compose logs -f

# 특정 서비스 로그
docker-compose logs -f collabora
docker-compose logs -f python
docker-compose logs -f rails
```

## 8. 테스트 체크리스트

- [ ] Docker 컨테이너 모두 정상 실행
- [ ] Collabora 서비스 응답 확인 (http://localhost:9980)
- [ ] WOPI 토큰 생성 성공
- [ ] CheckFileInfo 엔드포인트 정상 동작
- [ ] Frontend 페이지 로드 성공
- [ ] Excel 파일 업로드 성공
- [ ] Collabora iframe 로드 성공
- [ ] 문서 편집 가능
- [ ] 저장 기능 동작
- [ ] PostMessage 통신 정상

## 9. 프로덕션 준비사항

1. **SSL 인증서 설정**
   - Collabora는 프로덕션에서 HTTPS 필수
   - Let's Encrypt 인증서 설정

2. **환경변수 설정**
   ```bash
   COLLABORA_DOMAIN=your-domain.com
   COLLABORA_USERNAME=admin
   COLLABORA_PASSWORD=secure_password
   ```

3. **보안 설정**
   - WOPI 토큰 만료 시간 조정
   - IP 화이트리스트 설정
   - Rate limiting 설정

4. **모니터링 설정**
   - Prometheus/Grafana 연동
   - 로그 수집 설정
   - 알림 설정