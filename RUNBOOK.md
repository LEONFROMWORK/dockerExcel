# Excel Unified 운영 런북

## 목차
1. [서비스 개요](#서비스-개요)
2. [일상 운영 작업](#일상-운영-작업)
3. [모니터링 체크리스트](#모니터링-체크리스트)
4. [일반적인 이슈 대응](#일반적인-이슈-대응)
5. [긴급 대응 절차](#긴급-대응-절차)
6. [성능 튜닝](#성능-튜닝)
7. [백업 및 복구](#백업-및-복구)
8. [연락처](#연락처)

## 서비스 개요

### 서비스 구성
- **Rails App**: 메인 웹 애플리케이션 (포트 3000)
- **FastAPI**: Python AI/ML 서비스 (포트 8000)
- **PostgreSQL**: 메인 데이터베이스 (포트 5432)
- **Redis**: 캐시 및 큐 (포트 6379)
- **Sidekiq**: 백그라운드 작업 처리
- **Nginx**: 리버스 프록시 (포트 80/443)

### 중요 엔드포인트
- 프로덕션: https://excel-unified.com
- API: https://api.excel-unified.com
- 모니터링: https://monitoring.excel-unified.com
- 로그: https://logs.excel-unified.com

## 일상 운영 작업

### 매일 확인 사항

#### 1. 서비스 헬스체크
```bash
# 모든 서비스 상태 확인
kubectl get pods -n excel-unified

# 헬스체크 엔드포인트
curl https://excel-unified.com/health
curl https://api.excel-unified.com/health
```

#### 2. 리소스 사용량 확인
```bash
# CPU/메모리 사용량
kubectl top pods -n excel-unified

# 디스크 사용량
kubectl exec -n excel-unified postgres-0 -- df -h
```

#### 3. 에러 로그 확인
```bash
# 최근 에러 확인
kubectl logs -n excel-unified -l app=rails --since=24h | grep -i error
kubectl logs -n excel-unified -l app=fastapi --since=24h | grep -i error
```

### 주간 작업

#### 1. 백업 확인
```bash
# 백업 작업 상태 확인
kubectl get cronjobs -n excel-unified
kubectl get jobs -n excel-unified | grep backup
```

#### 2. 성능 리포트 생성
```bash
# Grafana 대시보드에서 주간 리포트 확인
# - 응답 시간 추이
# - 오류율
# - 처리량
```

#### 3. 보안 업데이트 확인
```bash
# 컨테이너 이미지 취약점 스캔
trivy image excel-unified/rails:latest
trivy image excel-unified/fastapi:latest
```

## 모니터링 체크리스트

### 핵심 메트릭

#### 애플리케이션 메트릭
- **응답 시간**: p50 < 200ms, p95 < 500ms, p99 < 1s
- **오류율**: < 0.1%
- **처리량**: > 100 req/s

#### 인프라 메트릭
- **CPU 사용률**: < 70%
- **메모리 사용률**: < 80%
- **디스크 사용률**: < 85%
- **네트워크 대역폭**: < 80%

### 알림 설정
```yaml
# Prometheus 알림 규칙 예시
- alert: HighErrorRate
  expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
  for: 5m
  annotations:
    summary: "High error rate detected"
    
- alert: HighMemoryUsage
  expr: container_memory_usage_bytes / container_spec_memory_limit_bytes > 0.9
  for: 5m
  annotations:
    summary: "High memory usage detected"
```

## 일반적인 이슈 대응

### 1. 서비스 응답 없음

#### 증상
- 웹사이트 접속 불가
- API 응답 없음

#### 대응 절차
```bash
# 1. Pod 상태 확인
kubectl get pods -n excel-unified

# 2. 문제 있는 Pod 재시작
kubectl delete pod -n excel-unified <pod-name>

# 3. 로그 확인
kubectl logs -n excel-unified <pod-name> --previous

# 4. 서비스 상태 확인
kubectl get svc -n excel-unified
kubectl describe svc -n excel-unified nginx-service
```

### 2. 데이터베이스 연결 오류

#### 증상
- "could not connect to server" 에러
- 애플리케이션에서 500 에러 발생

#### 대응 절차
```bash
# 1. PostgreSQL Pod 상태 확인
kubectl get pod -n excel-unified -l app=postgres

# 2. 데이터베이스 연결 테스트
kubectl exec -it -n excel-unified postgres-0 -- psql -U excel_user -c "SELECT 1"

# 3. 연결 수 확인
kubectl exec -it -n excel-unified postgres-0 -- psql -U excel_user -c "SELECT count(*) FROM pg_stat_activity"

# 4. 필요시 연결 종료
kubectl exec -it -n excel-unified postgres-0 -- psql -U excel_user -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle' AND state_change < now() - interval '10 minutes'"
```

### 3. Redis 메모리 부족

#### 증상
- "OOM command not allowed when used memory > 'maxmemory'" 에러
- 캐시 미스율 증가

#### 대응 절차
```bash
# 1. Redis 메모리 사용량 확인
kubectl exec -it -n excel-unified redis-0 -- redis-cli info memory

# 2. 캐시 초기화 (주의!)
kubectl exec -it -n excel-unified redis-0 -- redis-cli FLUSHDB

# 3. 메모리 정책 확인 및 수정
kubectl exec -it -n excel-unified redis-0 -- redis-cli CONFIG GET maxmemory-policy
kubectl exec -it -n excel-unified redis-0 -- redis-cli CONFIG SET maxmemory-policy allkeys-lru
```

### 4. 디스크 공간 부족

#### 증상
- "No space left on device" 에러
- 파일 업로드 실패

#### 대응 절차
```bash
# 1. 디스크 사용량 확인
kubectl exec -n excel-unified <pod-name> -- df -h

# 2. 대용량 파일 찾기
kubectl exec -n excel-unified <pod-name> -- find /app -type f -size +100M

# 3. 오래된 로그 정리
kubectl exec -n excel-unified <pod-name> -- find /app/logs -name "*.log" -mtime +7 -delete

# 4. 업로드 폴더 정리
kubectl exec -n excel-unified <pod-name> -- find /app/uploads -mtime +30 -delete
```

## 긴급 대응 절차

### 전체 서비스 장애

1. **상황 파악**
   ```bash
   # 모든 서비스 상태 확인
   kubectl get all -n excel-unified
   
   # 이벤트 확인
   kubectl get events -n excel-unified --sort-by='.lastTimestamp'
   ```

2. **긴급 복구**
   ```bash
   # 모든 배포 재시작
   kubectl rollout restart deployment -n excel-unified
   
   # 상태 모니터링
   watch kubectl get pods -n excel-unified
   ```

3. **롤백 (필요시)**
   ```bash
   # 이전 버전으로 롤백
   kubectl rollout undo deployment/rails -n excel-unified
   kubectl rollout undo deployment/fastapi -n excel-unified
   ```

4. **관계자 알림**
   - Slack 채널: #excel-unified-incidents
   - 이메일: ops@excel-unified.com

### 데이터 손실 대응

1. **즉시 서비스 중단**
   ```bash
   kubectl scale deployment rails --replicas=0 -n excel-unified
   ```

2. **백업 확인**
   ```bash
   # 최신 백업 찾기
   kubectl exec -n excel-unified backup-pod -- ls -la /backups/
   ```

3. **데이터 복구**
   ```bash
   # 백업에서 복구
   kubectl exec -i -n excel-unified postgres-0 -- psql -U excel_user excel_unified < backup.sql
   ```

## 성능 튜닝

### 애플리케이션 레벨

#### Rails 튜닝
```ruby
# config/environments/production.rb
config.cache_store = :redis_cache_store, {
  url: ENV['REDIS_URL'],
  expires_in: 1.hour,
  namespace: 'rails-cache'
}

# Puma 설정
workers ENV.fetch("WEB_CONCURRENCY") { 4 }
threads_count = ENV.fetch("RAILS_MAX_THREADS") { 5 }
threads threads_count, threads_count
```

#### FastAPI 튜닝
```python
# gunicorn 설정
workers = 4
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50
```

### 데이터베이스 튜닝

#### PostgreSQL 설정
```sql
-- 연결 수 설정
ALTER SYSTEM SET max_connections = 200;

-- 메모리 설정
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';

-- 쿼리 튜닝
ALTER SYSTEM SET work_mem = '4MB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';

-- 설정 적용
SELECT pg_reload_conf();
```

#### 인덱스 최적화
```sql
-- 느린 쿼리 찾기
SELECT query, calls, mean_time, total_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;

-- 인덱스 사용률 확인
SELECT schemaname, tablename, indexname, idx_scan
FROM pg_stat_user_indexes
ORDER BY idx_scan;
```

## 백업 및 복구

### 자동 백업 설정

#### CronJob 생성
```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: postgres-backup
  namespace: excel-unified
spec:
  schedule: "0 2 * * *"  # 매일 새벽 2시
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: postgres-backup
            image: postgres:15
            env:
            - name: PGPASSWORD
              valueFrom:
                secretKeyRef:
                  name: excel-unified-secrets
                  key: db-password
            command:
            - /bin/bash
            - -c
            - |
              DATE=$(date +%Y%m%d_%H%M%S)
              pg_dump -h postgres-service -U excel_user excel_unified > /backup/backup_$DATE.sql
              # S3 업로드 (AWS CLI 필요)
              aws s3 cp /backup/backup_$DATE.sql s3://excel-unified-backups/
              # 30일 이상 된 백업 삭제
              find /backup -name "backup_*.sql" -mtime +30 -delete
```

### 수동 백업
```bash
# 1. 전체 데이터베이스 백업
kubectl exec -n excel-unified postgres-0 -- pg_dump -U excel_user excel_unified > backup_$(date +%Y%m%d_%H%M%S).sql

# 2. 특정 테이블만 백업
kubectl exec -n excel-unified postgres-0 -- pg_dump -U excel_user -t excel_files excel_unified > excel_files_backup.sql

# 3. 백업 압축
gzip backup_*.sql
```

### 복구 절차

#### 전체 복구
```bash
# 1. 서비스 중단
kubectl scale deployment rails sidekiq --replicas=0 -n excel-unified

# 2. 데이터베이스 복구
gunzip -c backup_20240126_020000.sql.gz | kubectl exec -i -n excel-unified postgres-0 -- psql -U excel_user excel_unified

# 3. 서비스 재시작
kubectl scale deployment rails --replicas=3 -n excel-unified
kubectl scale deployment sidekiq --replicas=2 -n excel-unified
```

#### 부분 복구
```bash
# 특정 테이블만 복구
kubectl exec -i -n excel-unified postgres-0 -- psql -U excel_user excel_unified < excel_files_backup.sql
```

## 연락처

### 팀 연락처
- **DevOps 팀**: devops@excel-unified.com
- **개발팀**: dev@excel-unified.com
- **보안팀**: security@excel-unified.com

### 긴급 연락처
- **On-call Engineer**: +82-10-XXXX-XXXX
- **팀 리더**: +82-10-YYYY-YYYY
- **CTO**: +82-10-ZZZZ-ZZZZ

### 외부 지원
- **AWS Support**: https://console.aws.amazon.com/support/
- **OpenAI Support**: support@openai.com

### 중요 링크
- **Status Page**: https://status.excel-unified.com
- **Documentation**: https://docs.excel-unified.com
- **Incident Tracking**: https://jira.excel-unified.com