# Excel Unified - AI-Powered Excel Knowledge Platform

통합된 Excel AI 지식 플랫폼 - Excel 문제 해결을 위한 AI 기반 솔루션

## 🚀 프로젝트 개요

Excel Unified는 세 개의 기존 프로젝트를 하나로 통합한 플랫폼입니다:
- **excelapp-rails**: Excel 파일 분석 및 사용자 인터페이스
- **pipedata**: 데이터 수집 및 처리 파이프라인
- **excel-ai-knowledge-generator**: AI 기반 지식 생성 시스템

## 🏗️ 기술 스택

### Backend
- **Rails 8.0.2** - 메인 웹 프레임워크
- **PostgreSQL** with **pgvector** - 데이터베이스 및 벡터 검색
- **FastAPI (Python)** - AI 서비스
- **Devise** - 인증 시스템
- **Active Job** - 비동기 작업 처리

### Frontend
- **Vue.js 3** - UI 프레임워크
- **Vite** - 빌드 도구
- **Pinia** - 상태 관리
- **Tailwind CSS** - 스타일링

### AI/ML
- **OpenAI GPT-4** - AI 상담 및 분석
- **Embeddings** - 의미 기반 검색
- **Langchain** - AI 워크플로우

## 📁 프로젝트 구조

```
excel-unified/
├── rails-app/               # Rails 애플리케이션
│   ├── app/
│   │   ├── domains/        # 도메인별 구조 (DDD)
│   │   │   ├── authentication/
│   │   │   ├── excel_analysis/
│   │   │   ├── knowledge_base/
│   │   │   ├── ai_consultation/
│   │   │   └── data_pipeline/
│   │   └── javascript/     # Vue.js 컴포넌트
│   └── config/
├── python-service/         # FastAPI AI 서비스
│   ├── app/
│   │   ├── api/           # API 엔드포인트
│   │   ├── services/      # 비즈니스 로직
│   │   └── models/        # 데이터 모델
│   └── requirements.txt
└── docs/                  # 문서
```

## 🛠️ 설치 및 실행

### 사전 요구사항
- Ruby 3.x
- Node.js 18+
- Python 3.11+
- PostgreSQL 15+ with pgvector extension
- Redis (선택사항)

### 로컬 개발 환경 설정

1. **저장소 클론**
```bash
git clone <repository-url>
cd excel-unified
```

2. **Rails 앱 설정**
```bash
cd rails-app
bundle install
npm install
cp .env.example .env
# .env 파일에 필요한 환경 변수 설정
bin/rails db:create db:migrate
```

3. **Python 서비스 설정**
```bash
cd ../python-service
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# .env 파일에 OpenAI API 키 등 설정
```

4. **개발 서버 실행**

Rails 앱:
```bash
cd rails-app
bin/dev
```

Python 서비스:
```bash
cd python-service
uvicorn main:app --reload
```

## 🚀 Railway 배포

### 배포 준비

1. **Railway CLI 설치**
```bash
npm install -g @railway/cli
```

2. **Railway 로그인**
```bash
railway login
```

3. **프로젝트 생성**
```bash
railway init
```

### 서비스 배포

1. **PostgreSQL 데이터베이스 추가**
   - Railway 대시보드에서 PostgreSQL 플러그인 추가
   - pgvector extension 활성화

2. **환경 변수 설정**
   - `.env.railway.example` 참고하여 Railway 대시보드에서 환경 변수 설정

3. **배포**
```bash
railway up
```

### Railway 서비스 구조
- **rails-app**: 메인 웹 애플리케이션
- **python-service**: AI 처리 서비스
- **PostgreSQL**: 데이터베이스 (pgvector 포함)
- **Redis**: 캐싱 (선택사항)

## 🔧 주요 기능

### 1. Excel 파일 분석
- 파일 업로드 및 구조 분석
- 수식 오류 검출
- 데이터 품질 검사
- AI 기반 개선 제안

### 2. AI 상담
- 실시간 채팅 인터페이스
- Excel 관련 질문 답변
- 스크린샷 분석
- 맞춤형 솔루션 제공

### 3. 지식 베이스
- 벡터 검색 기능
- Q&A 쌍 관리
- 자동 지식 추출
- 유사 문제 검색

### 4. 데이터 파이프라인 (관리자)
- 웹 스크래핑
- API 데이터 수집
- 스케줄링
- 데이터 처리 워크플로우

## 📊 아키텍처 원칙

- **Vertical Slice Architecture**: 기능별 독립적 구조
- **SOLID Principles**: 객체지향 설계 원칙
- **Domain-Driven Design**: 도메인 중심 설계
- **Repository Pattern**: 데이터 접근 추상화
- **Result Pattern**: 일관된 서비스 응답

## 🔐 보안

- JWT 기반 인증
- Google OAuth 2.0 지원
- Role-based Access Control (RBAC)
- API 키 인증 (서비스 간 통신)

## 📝 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.

## 🤝 기여

기여를 환영합니다! PR을 제출하기 전에 다음을 확인해주세요:
- 코드 스타일 가이드 준수
- 테스트 작성
- 문서 업데이트

## 📞 지원

문제가 있거나 질문이 있으시면 이슈를 생성해주세요.