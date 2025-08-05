#!/usr/bin/env python3
"""
WebSocket Context Test
실시간 컨텍스트 동기화 테스트
"""
import asyncio
import websockets
import json
import uuid
import sys
import os

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


async def test_websocket_connection():
    """WebSocket 연결 테스트"""
    print("=" * 60)
    print("WebSocket 컨텍스트 동기화 테스트")
    print("=" * 60)

    session_id = f"test_session_{uuid.uuid4()}"
    uri = f"ws://localhost:8000/api/v1/ws/context/{session_id}"

    try:
        async with websockets.connect(uri) as websocket:
            print(f"\n✅ WebSocket 연결 성공: {uri}")

            # 1. 초기 컨텍스트 수신
            initial_msg = await websocket.recv()
            initial_data = json.loads(initial_msg)
            print("\n📥 초기 컨텍스트 수신:")
            print(f"   Type: {initial_data.get('type')}")
            print(f"   Session ID: {initial_data.get('data', {}).get('session_id')}")

            # 2. 멀티 셀 선택 테스트
            print("\n📤 멀티 셀 선택 메시지 전송...")
            cell_selection_msg = {
                "type": "cell_selection",
                "data": {
                    "cells": [
                        {"address": "A1", "sheetName": "Sheet1", "value": 100},
                        {"address": "B1", "sheetName": "Sheet1", "value": 200},
                        {"address": "C1", "sheetName": "Sheet1", "value": "=A1+B1"},
                    ]
                },
                "client_id": str(uuid.uuid4()),
            }
            await websocket.send(json.dumps(cell_selection_msg))

            # 응답 수신
            response = await websocket.recv()
            response_data = json.loads(response)
            print(f"📥 응답 수신: {response_data.get('type')}")

            # 3. 컨텍스트 요청
            print("\n📤 컨텍스트 요청...")
            context_request = {"type": "request_context", "data": {}}
            await websocket.send(json.dumps(context_request))

            response = await websocket.recv()
            response_data = json.loads(response)
            print(f"📥 컨텍스트 응답 수신: {response_data.get('type')}")

            # 4. 사용자 메시지 테스트
            print("\n📤 사용자 메시지 전송...")
            user_msg = {
                "type": "user_message",
                "data": {"message": "선택한 셀들의 합계는 얼마인가요?"},
            }
            await websocket.send(json.dumps(user_msg))

            response = await websocket.recv()
            response_data = json.loads(response)
            print(f"📥 메시지 응답: {response_data.get('type')}")

            # 5. Ping 테스트
            print("\n📤 Ping 전송...")
            ping_msg = {"type": "ping", "data": {}}
            await websocket.send(json.dumps(ping_msg))

            response = await websocket.recv()
            response_data = json.loads(response)
            print(f"📥 Pong 수신: {response_data.get('type')}")

            print("\n✅ 모든 WebSocket 테스트 완료!")

    except Exception as e:
        print(f"\n❌ WebSocket 테스트 실패: {e}")
        import traceback

        traceback.print_exc()


async def test_multiple_clients():
    """여러 클라이언트 동시 연결 테스트"""
    print("\n" + "=" * 60)
    print("다중 클라이언트 동기화 테스트")
    print("=" * 60)

    session_id = f"multi_session_{uuid.uuid4()}"
    uri = f"ws://localhost:8000/api/v1/ws/context/{session_id}"

    async def client_handler(client_name: str):
        """개별 클라이언트 핸들러"""
        try:
            async with websockets.connect(uri) as websocket:
                print(f"\n[{client_name}] 연결됨")

                # 초기 메시지 수신
                await websocket.recv()
                print(f"[{client_name}] 초기 컨텍스트 수신")

                if client_name == "Client1":
                    # Client1이 셀 선택
                    await asyncio.sleep(1)
                    msg = {
                        "type": "cell_selection",
                        "data": {
                            "cells": [
                                {"address": "D1", "sheetName": "Sheet1", "value": 500}
                            ]
                        },
                        "client_id": client_name,
                    }
                    await websocket.send(json.dumps(msg))
                    print(f"[{client_name}] 셀 선택 전송")

                # 모든 클라이언트가 브로드캐스트 수신
                for _ in range(3):
                    try:
                        response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                        data = json.loads(response)
                        print(f"[{client_name}] 브로드캐스트 수신: {data.get('type')}")
                    except asyncio.TimeoutError:
                        break

        except Exception as e:
            print(f"[{client_name}] 오류: {e}")

    # 3개 클라이언트 동시 실행
    await asyncio.gather(
        client_handler("Client1"), client_handler("Client2"), client_handler("Client3")
    )

    print("\n✅ 다중 클라이언트 테스트 완료!")


async def main():
    """메인 테스트 함수"""
    # 1. 단일 클라이언트 테스트
    await test_websocket_connection()

    # 2. 다중 클라이언트 테스트
    await test_multiple_clients()

    print("\n" + "=" * 60)
    print("WebSocket 테스트 완료")
    print("=" * 60)


if __name__ == "__main__":
    # FastAPI 서버가 실행 중이어야 함
    print("⚠️  FastAPI 서버가 localhost:8000에서 실행 중이어야 합니다.")
    print("   실행 명령: uvicorn main:app --reload --port 8000\n")

    asyncio.run(main())
