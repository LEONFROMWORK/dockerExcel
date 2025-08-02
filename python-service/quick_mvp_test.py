#!/usr/bin/env python3
"""
빠른 MVP 테스트 - 핵심 기능만 확인
"""

import asyncio
from playwright.async_api import async_playwright

async def quick_test():
    print("🚀 MVP 핵심 테스트 시작")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(viewport={'width': 1200, 'height': 800})
        page = await context.new_page()
        
        try:
            # 페이지 로드
            print("📱 페이지 로드 중...")
            await page.goto("http://localhost:8000/test", timeout=15000)
            
            # 간단한 테스트 실행
            print("🧪 간단한 Excel 테스트 실행...")
            await page.click("button:has-text('간단한 Excel 테스트')")
            
            # 5초 대기 후 상태 확인
            print("⏱️  5초 대기 중...")
            await asyncio.sleep(5)
            
            # Canvas 확인
            await page.click("button:has-text('Canvas 상태 확인')")
            await asyncio.sleep(2)
            
            # 결과 확인
            canvas_status = await page.locator("#canvasStatus").text_content()
            cell_count = await page.locator("#cellCount").text_content()
            
            print(f"📊 Canvas 상태: {canvas_status}")
            print(f"📊 셀 개수: {cell_count}")
            
            # 성공 여부 판단
            if '활성' in canvas_status:
                print("✅ MVP 성공: Canvas가 활성화됨!")
                return True
            else:
                print("❌ MVP 실패: Canvas가 활성화되지 않음")
                return False
                
        except Exception as e:
            print(f"❌ 테스트 실패: {e}")
            return False
        finally:
            await browser.close()

if __name__ == "__main__":
    result = asyncio.run(quick_test())
    if result:
        print("\n🎯 MVP 목표 달성!")
    else:
        print("\n❌ MVP 목표 미달성 - 추가 수정 필요")