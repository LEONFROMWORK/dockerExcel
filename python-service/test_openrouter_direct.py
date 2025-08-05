#!/usr/bin/env python3
"""
OpenRouter API 직접 테스트
"""
import asyncio
import httpx
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


async def test_openrouter():
    """OpenRouter API 직접 테스트"""
    api_key = os.getenv("OPENROUTER_API_KEY")

    if not api_key:
        print("❌ OPENROUTER_API_KEY가 설정되지 않았습니다.")
        return

    print(f"API Key: {api_key[:20]}...")

    # 1. 모델 목록 확인
    print("\n1. 모델 목록 확인...")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                "https://openrouter.ai/api/v1/models",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                timeout=10.0,
            )

            print(f"   상태 코드: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                models = data.get("data", [])
                print(f"   ✅ 성공! 사용 가능한 모델 수: {len(models)}")

                # 일부 모델 표시
                print("   일부 모델:")
                for model in models[:5]:
                    print(f"     - {model.get('id')}")
            else:
                print(f"   ❌ 실패: {response.text}")

        except Exception as e:
            print(f"   ❌ 오류: {str(e)}")

    # 2. 채팅 완성 테스트
    print("\n2. 채팅 완성 테스트...")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://excel-unified.app",
                    "X-Title": "Excel Unified",
                },
                json={
                    "model": "openai/gpt-3.5-turbo",
                    "messages": [
                        {
                            "role": "user",
                            "content": "Say 'Hello, OpenRouter!' in Korean",
                        }
                    ],
                    "max_tokens": 20,
                },
                timeout=30.0,
            )

            print(f"   상태 코드: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                content = (
                    data.get("choices", [{}])[0].get("message", {}).get("content", "")
                )
                print(f"   ✅ 성공! 응답: {content}")
            else:
                print(f"   ❌ 실패: {response.text}")

        except Exception as e:
            print(f"   ❌ 오류: {str(e)}")


if __name__ == "__main__":
    asyncio.run(test_openrouter())
