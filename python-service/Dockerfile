# Multi-stage build for Python service optimization
FROM python:3.11-slim as base

# Python 환경 설정
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ======================
# Build Stage
# ======================
FROM base as build

# 빌드 의존성 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    build-essential \
    libpq-dev \
    pkg-config \
    libhdf5-dev \
    libopencv-dev \
    && rm -rf /var/lib/apt/lists/*

# 가상환경 생성
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# requirements 복사 및 의존성 설치
COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt && \
    # 빌드 아티팩트 정리
    find /opt/venv -name "*.pyc" -delete && \
    find /opt/venv -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true && \
    find /opt/venv -name "*.pyo" -delete

# ======================
# Production Stage
# ======================
FROM base as production

# 런타임 의존성 및 최적화된 OCR 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    procps \
    tesseract-ocr \
    tesseract-ocr-kor \
    tesseract-ocr-eng \
    tesseract-ocr-chi-sim \
    tesseract-ocr-jpn \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# 빌드 단계에서 설치된 Python 패키지 복사 (최적화)
COPY --from=build /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 최종 이미지 크기 최적화
RUN find /opt/venv -name "*.pyc" -delete && \
    find /opt/venv -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true && \
    find /opt/venv -name "*.dist-info" -type d -exec find {} -name "RECORD" -delete \; 2>/dev/null || true

# 작업 디렉토리 설정
WORKDIR /app

# 기존 불필요한 데이터 제거 (용량 절약)
RUN rm -f /usr/share/tesseract-ocr/4.00/tessdata/osd.traineddata \
           /usr/share/tesseract-ocr/4.00/tessdata/equ.traineddata 2>/dev/null || true

# 애플리케이션 코드 복사
COPY --chown=1000:1000 . .

# 보안: 비root 사용자 생성
RUN groupadd --system --gid 1000 appuser && \
    useradd --system --uid 1000 --gid appuser --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app

# 비root 사용자로 전환
USER appuser

# Health check 설정
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 포트 노출
EXPOSE 8000

# 프로덕션 서버 실행 (성능 최적화)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--log-level", "info", "--no-server-header"]