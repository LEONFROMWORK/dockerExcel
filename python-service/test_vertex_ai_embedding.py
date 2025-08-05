#!/usr/bin/env python3
"""
Vertex AI 임베딩 테스트 스크립트
"""
import asyncio
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set environment variables
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = (
    "/Users/kevin/excel-unified/python-service/google-vertex-ai-key.json"
)
os.environ["GCP_PROJECT_ID"] = "excel-unified"
os.environ["GCP_LOCATION"] = "us-central1"


async def test_vertex_ai_embedding():
    """Vertex AI 임베딩 테스트"""
    print("=== Vertex AI 임베딩 서비스 테스트 ===\n")

    try:
        # Import after environment setup
        from app.services.vertex_ai_embedding_service import (
            get_vertex_ai_embedding_service,
        )

        # 서비스 초기화
        print("1. Vertex AI 서비스 초기화 중...")
        service = get_vertex_ai_embedding_service()
        print("   ✅ 서비스 초기화 성공\n")

        # 단일 임베딩 테스트
        print("2. 단일 텍스트 임베딩 테스트...")
        test_text = "Excel의 VLOOKUP 함수는 테이블에서 값을 검색하는 데 사용됩니다."

        embedding = await service.generate_embedding(test_text)
        print("   ✅ 임베딩 생성 성공")
        print(f"   - 텍스트 길이: {len(test_text)} characters")
        print(f"   - 임베딩 차원: {len(embedding)}")
        print(f"   - 임베딩 샘플: {embedding[:5]}...\n")

        # 배치 임베딩 테스트
        print("3. 배치 임베딩 테스트...")
        test_texts = [
            "Excel에서 피벗 테이블을 만드는 방법",
            "SUMIF 함수로 조건부 합계 구하기",
            "VBA 매크로로 작업 자동화하기",
        ]

        embeddings = await service.generate_embeddings_batch(test_texts)
        print("   ✅ 배치 임베딩 생성 성공")
        print(f"   - 입력 텍스트 수: {len(test_texts)}")
        print(f"   - 생성된 임베딩 수: {len(embeddings)}")
        print(f"   - 각 임베딩 차원: {[len(e) for e in embeddings]}\n")

        # 사용량 통계 확인
        print("4. 사용량 통계...")
        stats = service.get_usage_stats()
        print(f"   - 사용한 문자 수: {stats['monthly_characters']:,} characters")
        print(f"   - 무료 티어 한도: {stats['free_tier_limit']:,} characters")
        print(f"   - 사용률: {stats['usage_percentage']:.2f}%")
        print(f"   - 남은 문자 수: {stats['remaining_characters']:,} characters\n")

        # OpenAI 서비스와의 통합 테스트
        print("5. OpenAI 서비스 통합 테스트...")
        from app.services.openai_service import openai_service

        integration_text = "통합 테스트를 위한 텍스트입니다."
        integration_embedding = await openai_service.generate_embedding(
            integration_text
        )
        print("   ✅ OpenAI 서비스를 통한 Vertex AI 임베딩 성공")
        print(f"   - 임베딩 차원: {len(integration_embedding)}")

    except Exception as e:
        print(f"❌ 오류 발생: {str(e)}")
        import traceback

        traceback.print_exc()

    print("\n=== 테스트 완료 ===")


if __name__ == "__main__":
    asyncio.run(test_vertex_ai_embedding())
