# Railway 배포 가이드

## 🚀 Railway 배포 단계별 가이드

### 1. Railway 계정 및 프로젝트 설정

1. [Railway](https://railway.app) 가입 및 로그인
2. 새 프로젝트 생성
3. GitHub 저장소 연결

### 2. PostgreSQL 데이터베이스 설정

1. Railway 대시보드에서 **New → Database → PostgreSQL** 선택
2. PostgreSQL 서비스 생성 후 Variables 탭에서 DATABASE_URL 확인
3. pgvector extension 활성화:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```

### 3. Rails 애플리케이션 배포

1. **New Service → GitHub Repo** 선택
2. `rails-app` 디렉토리를 Root Directory로 설정
3. 환경 변수 설정:
   ```
   RAILS_ENV=production
   RAILS_MASTER_KEY=<your-master-key>
   RAILS_SERVE_STATIC_FILES=true
   RAILS_LOG_TO_STDOUT=true
   DATABASE_URL=<postgresql-url>
   GOOGLE_OAUTH_CLIENT_ID=<your-client-id>
   GOOGLE_OAUTH_CLIENT_SECRET=<your-client-secret>
   PYTHON_SERVICE_URL=http://python-service.railway.internal:8000
   ```

4. Build Command (자동 감지되지 않는 경우):
   ```bash
   bundle install && npm install && bundle exec rails assets:precompile
   ```

5. Start Command:
   ```bash
   bundle exec rails server -p $PORT -b 0.0.0.0
   ```

### 4. Python AI 서비스 배포

1. **New Service → GitHub Repo** 선택
2. `python-service` 디렉토리를 Root Directory로 설정
3. 환경 변수 설정:
   ```
   ENVIRONMENT=production
   DATABASE_URL=<postgresql-url>
   OPENAI_API_KEY=<your-openai-key>
   RAILS_API_URL=http://rails-app.railway.internal:3000
   ```

4. Start Command:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port $PORT
   ```

### 5. 서비스 간 통신 설정

Railway 내부 네트워크 사용:
- Rails → Python: `http://python-service.railway.internal:8000`
- Python → Rails: `http://rails-app.railway.internal:3000`

### 6. 커스텀 도메인 설정 (선택사항)

1. Rails 서비스의 Settings → Domains
2. Custom Domain 추가
3. DNS 설정 업데이트

### 7. 배포 확인

1. **Health Checks**:
   - Rails: `https://your-app.railway.app/up`
   - Python: `https://your-python-service.railway.app/health`

2. **로그 확인**:
   - Railway 대시보드에서 각 서비스의 Logs 탭 확인

3. **데이터베이스 마이그레이션**:
   ```bash
   railway run bundle exec rails db:migrate
   ```

## 🔧 트러블슈팅

### 문제: Assets 컴파일 실패
**해결책**:
```bash
NODE_OPTIONS=--openssl-legacy-provider bundle exec rails assets:precompile
```

### 문제: 데이터베이스 연결 실패
**해결책**:
- DATABASE_URL 형식 확인
- PostgreSQL 서비스가 실행 중인지 확인
- 내부 네트워크 URL 사용 여부 확인

### 문제: 서비스 간 통신 실패
**해결책**:
- 내부 도메인 이름 확인 (`.railway.internal`)
- 포트 번호 확인
- 환경 변수 설정 확인

## 📊 모니터링

### Railway 메트릭
- CPU 사용량
- 메모리 사용량
- 네트워크 트래픽
- 빌드 시간

### 추천 모니터링 도구
- **Sentry**: 에러 트래킹
- **New Relic**: APM
- **LogDNA**: 로그 관리

## 🔄 CI/CD 설정

### GitHub Actions 워크플로우
```yaml
name: Deploy to Railway

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: railwayapp/deploy-action@v1
        with:
          token: ${{ secrets.RAILWAY_TOKEN }}
```

## 📝 배포 체크리스트

- [ ] 모든 환경 변수 설정 완료
- [ ] 데이터베이스 마이그레이션 실행
- [ ] Assets 빌드 성공
- [ ] Health check 통과
- [ ] 서비스 간 통신 확인
- [ ] SSL 인증서 활성화
- [ ] 로그 모니터링 설정
- [ ] 백업 전략 수립

## 🚨 프로덕션 주의사항

1. **보안**:
   - 모든 시크릿 키를 환경 변수로 관리
   - HTTPS 강제 적용
   - CORS 설정 확인

2. **성능**:
   - 캐싱 전략 구현
   - 데이터베이스 인덱스 최적화
   - CDN 사용 고려

3. **백업**:
   - 정기적인 데이터베이스 백업
   - 파일 스토리지 백업
   - 설정 파일 버전 관리