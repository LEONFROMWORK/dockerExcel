#!/usr/bin/env python3
"""
최소 MVP 테스트
"""

import asyncio
from playwright.async_api import async_playwright

async def test_minimal():
    print("🧪 최소 MVP 테스트")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=500)
        context = await browser.new_context(viewport={'width': 1000, 'height': 800})
        page = await context.new_page()
        
        try:
            # 페이지 로드
            await page.goto("http://localhost:8000/minimal")
            
            # 3초 대기 (라이브러리 로드)
            await asyncio.sleep(3)
            
            # 테스트 버튼 클릭
            await page.click("button:has-text('간단한 데이터 렌더링 테스트')")
            
            # 3초 대기 (렌더링)
            await asyncio.sleep(3)
            
            # 상태 확인
            status = await page.locator("#status").text_content()
            canvas_info = await page.locator("#canvas-info").text_content()
            
            print(f"상태: {status}")
            print(f"Canvas: {canvas_info}")
            
            # Canvas 상태 확인 버튼 클릭
            await page.click("button:has-text('Canvas 상태 확인')")
            await asyncio.sleep(1)
            
            canvas_info = await page.locator("#canvas-info").text_content()
            print(f"최종 Canvas: {canvas_info}")
            
            # 성공 여부
            success = 'MVP 성공' in status or '개수: 1' in canvas_info or '개수: 2' in canvas_info
            
            if success:
                print("✅ 최소 MVP 성공!")
                return True
            else:
                print("❌ 최소 MVP 실패")
                return False
                
        except Exception as e:
            print(f"❌ 오류: {e}")
            return False
        finally:
            await browser.close()

if __name__ == "__main__":
    result = asyncio.run(test_minimal())
    print(f"\n🎯 결과: {'성공' if result else '실패'}")