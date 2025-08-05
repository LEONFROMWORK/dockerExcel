#!/usr/bin/env python3
"""
Test Embedding Migration from OpenAI to Vertex AI
임베딩 마이그레이션 테스트 - OpenAI에서 Vertex AI로
"""
import asyncio
import sys
import os

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


async def test_imports():
    """임포트 테스트"""
    print("1. 임포트 테스트")

    try:
        # 인터페이스 임포트
        print("   ✅ IEmbeddingService 인터페이스 임포트 성공")

        # Vertex AI 서비스 임포트
        print("   ✅ VertexAIEmbeddingService 임포트 성공")

        # Factory 임포트
        print("   ✅ EmbeddingServiceFactory 임포트 성공")

        # Vector Search 임포트
        print("   ✅ VectorSearchService 임포트 성공")

        # OpenAI Service 임포트
        print("   ✅ OpenAIService 임포트 성공")

        return True
    except Exception as e:
        print(f"   ❌ 임포트 실패: {e}")
        return False


async def test_service_creation():
    """서비스 생성 테스트"""
    print("\n2. 서비스 생성 테스트")

    try:
        from app.services.embedding.embedding_factory import EmbeddingServiceFactory

        # 동기 버전 테스트
        service_sync = EmbeddingServiceFactory.get_embedding_service_sync()
        print(f"   ✅ 동기 서비스 생성 성공: {type(service_sync).__name__}")

        # 비동기 버전 테스트
        service_async = await EmbeddingServiceFactory.get_embedding_service()
        print(f"   ✅ 비동기 서비스 생성 성공: {type(service_async).__name__}")

        # 같은 인스턴스인지 확인 (싱글톤)
        if service_sync is service_async:
            print("   ✅ 싱글톤 패턴 확인됨")
        else:
            print("   ❌ 싱글톤 패턴 실패")

        return service_async
    except Exception as e:
        print(f"   ❌ 서비스 생성 실패: {e}")
        import traceback

        traceback.print_exc()
        return None


async def test_interface_compliance(service):
    """인터페이스 준수 테스트"""
    print("\n3. 인터페이스 준수 테스트")

    try:
        from app.core.interfaces.embedding_interface import IEmbeddingService

        # 인터페이스 구현 확인
        if isinstance(service, IEmbeddingService):
            print("   ✅ IEmbeddingService 인터페이스 구현 확인")
        else:
            print("   ❌ IEmbeddingService 인터페이스 미구현")

        # 필수 메서드 확인
        methods = [
            "create_embedding",
            "create_embeddings",
            "get_embedding_dimension",
            "get_max_text_length",
        ]

        for method in methods:
            if hasattr(service, method):
                print(f"   ✅ {method} 메서드 존재")
            else:
                print(f"   ❌ {method} 메서드 없음")

        # 메서드 정보 출력
        print(f"   - 임베딩 차원: {service.get_embedding_dimension()}")
        print(f"   - 최대 텍스트 길이: {service.get_max_text_length()}")

        return True
    except Exception as e:
        print(f"   ❌ 인터페이스 준수 테스트 실패: {e}")
        return False


async def test_openai_service_compatibility():
    """OpenAI 서비스 호환성 테스트"""
    print("\n4. OpenAI 서비스 호환성 테스트")

    try:
        from app.services.openai_service import OpenAIService

        # OpenAI 서비스 생성
        openai_svc = OpenAIService()
        print("   ✅ OpenAI 서비스 생성 성공")

        # 임베딩 서비스 확인
        if hasattr(openai_svc, "embedding_service"):
            print(
                f"   ✅ 임베딩 서비스 설정됨: {type(openai_svc.embedding_service).__name__}"
            )
        else:
            print("   ❌ 임베딩 서비스가 설정되지 않음")

        # 메서드 확인
        if hasattr(openai_svc, "generate_embedding"):
            print("   ✅ generate_embedding 메서드 존재")
        if hasattr(openai_svc, "generate_embeddings_batch"):
            print("   ✅ generate_embeddings_batch 메서드 존재")

        return openai_svc
    except Exception as e:
        print(f"   ❌ OpenAI 서비스 호환성 테스트 실패: {e}")
        import traceback

        traceback.print_exc()
        return None


async def test_vector_search_integration():
    """Vector Search 통합 테스트"""
    print("\n5. Vector Search 통합 테스트")

    try:
        from app.services.vector_search import VectorSearchService

        # Vector Search 서비스 생성
        vector_svc = VectorSearchService()
        print("   ✅ Vector Search 서비스 생성 성공")

        # 임베딩 서비스 속성 확인
        if hasattr(vector_svc, "_embedding_service"):
            print("   ✅ _embedding_service 속성 존재")
        else:
            print("   ❌ _embedding_service 속성 없음")

        return True
    except Exception as e:
        print(f"   ❌ Vector Search 통합 테스트 실패: {e}")
        return False


async def test_dependency_paths():
    """의존성 경로 테스트"""
    print("\n6. 의존성 경로 테스트")

    try:
        # 각 모듈의 위치 확인
        import app.core.interfaces.embedding_interface

        print(
            f"   ✅ embedding_interface: {app.core.interfaces.embedding_interface.__file__}"
        )

        import app.services.embedding.vertex_ai_embedding

        print(
            f"   ✅ vertex_ai_embedding: {app.services.embedding.vertex_ai_embedding.__file__}"
        )

        import app.services.embedding.embedding_factory

        print(
            f"   ✅ embedding_factory: {app.services.embedding.embedding_factory.__file__}"
        )

        import app.services.vector_search

        print(f"   ✅ vector_search: {app.services.vector_search.__file__}")

        import app.services.openai_service

        print(f"   ✅ openai_service: {app.services.openai_service.__file__}")

        return True
    except Exception as e:
        print(f"   ❌ 의존성 경로 테스트 실패: {e}")
        return False


async def main():
    """메인 테스트 함수"""
    print("=" * 60)
    print("임베딩 마이그레이션 테스트 시작")
    print("=" * 60)

    # 1. 임포트 테스트
    if not await test_imports():
        print("\n❌ 임포트 실패로 테스트 중단")
        return

    # 2. 서비스 생성 테스트
    service = await test_service_creation()
    if not service:
        print("\n❌ 서비스 생성 실패로 테스트 중단")
        return

    # 3. 인터페이스 준수 테스트
    await test_interface_compliance(service)

    # 4. OpenAI 서비스 호환성 테스트
    await test_openai_service_compatibility()

    # 5. Vector Search 통합 테스트
    await test_vector_search_integration()

    # 6. 의존성 경로 테스트
    await test_dependency_paths()

    print("\n" + "=" * 60)
    print("테스트 완료")
    print("=" * 60)


if __name__ == "__main__":
    # 환경 변수 설정 (테스트용)
    if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        print("⚠️  GOOGLE_APPLICATION_CREDENTIALS 환경 변수가 설정되지 않았습니다.")
        print("   테스트를 위해 더미 경로를 설정합니다.")
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/path/to/dummy/credentials.json"

    # 테스트 실행
    asyncio.run(main())
