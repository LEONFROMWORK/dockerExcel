#!/usr/bin/env python3
"""
AI API 연결 테스트 스크립트
"""
import asyncio
import os
import sys
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

from app.services.ai_failover_service import ai_failover_service
from app.core.config import settings


async def test_ai_connections():
    """AI 연결 테스트"""
    print("=== AI Failover Service 연결 테스트 ===\n")

    # API 키 설정 확인
    print("API 키 설정 상태:")
    print(
        f"  OPENROUTER_API_KEY: {'설정됨' if settings.OPENROUTER_API_KEY else '미설정'}"
    )
    if settings.OPENROUTER_API_KEY:
        print(f"  OPENROUTER_API_KEY 값: {settings.OPENROUTER_API_KEY[:20]}...")
    print()

    # 시스템 상태 확인
    status = ai_failover_service.get_system_status()
    print(f"전체 모델 수: {status['total_models']}")
    print(f"정상 모델 수: {status['healthy_models']}")
    print(f"비정상 모델 수: {status['unhealthy_models']}")
    print()

    # 제공자별 상태
    print("제공자별 상태:")
    for provider, info in status["providers"].items():
        print(
            f"  {provider}: 사용가능={info['available']}, 정상={info['healthy']}, 비정상={info['unhealthy']}"
        )
    print()

    # 사용 가능한 모델 목록
    available_models = ai_failover_service.get_available_models()
    print(f"사용 가능한 모델 ({len(available_models)}개):")
    for model in available_models[:5]:  # 상위 5개만 표시
        print(
            f"  - {model.provider.value}:{model.model_name} (우선순위: {model.priority})"
        )
    print()

    # 간단한 테스트 메시지
    try:
        print("테스트 메시지 전송 중...")
        test_messages = [
            {
                "role": "user",
                "content": "안녕하세요. 이것은 연결 테스트입니다. 간단히 응답해주세요.",
            }
        ]

        response = await ai_failover_service.chat_completion_with_failover(
            messages=test_messages, max_tokens=50, temperature=0.1
        )

        print(f"✅ 응답 성공: {response[:100]}...")

        # 어떤 모델이 사용되었는지 확인
        status_after = ai_failover_service.get_system_status()
        for model_key, model_info in status_after["models"].items():
            if model_info["success_count"] > 0:
                print(f"   사용된 모델: {model_key}")
                break

    except Exception as e:
        print(f"❌ 테스트 실패: {str(e)}")

    print("\n=== 테스트 완료 ===")


if __name__ == "__main__":
    asyncio.run(test_ai_connections())
