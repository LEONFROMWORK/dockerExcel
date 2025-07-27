const { chromium } = require('playwright');
const path = require('path');

async function testTextClippingFix() {
  console.log('🔍 텍스트 잘림 수정 테스트 시작...\n');
  
  const browser = await chromium.launch({ headless: false });
  const page = await browser.newPage();
  
  try {
    // 1. Excel AI 페이지로 이동
    await page.goto('http://localhost:3000/ai/excel');
    await page.waitForTimeout(2000);
    
    // 2. 파일 업로드
    const fileInput = await page.locator('input[type="file"]').first();
    await fileInput.setInputFiles('/Users/kevin/Desktop/결산보고_25.2Q.xlsx');
    
    console.log('✅ 파일 업로드 완료');
    
    // 3. 분석 완료 대기
    await page.waitForSelector('.excel-table', { timeout: 30000 });
    console.log('✅ Excel 테이블 렌더링 완료');
    
    await page.waitForTimeout(3000);
    
    // 4. 문제 셀들 확인
    const problemCells = ['F32', 'F33', 'F34', 'F35', 'C44', 'C45', 'C46'];
    
    for (const cellAddress of problemCells) {
      try {
        // 셀 찾기 (행과 열 번호로)
        const cellContent = await page.evaluate((addr) => {
          // 셀 주소를 행과 열로 파싱
          const match = addr.match(/([A-Z]+)(\d+)/);
          if (!match) return null;
          
          const colLetters = match[1];
          const rowNum = parseInt(match[2]);
          
          // 열 문자를 숫자로 변환
          let colNum = 0;
          for (let i = 0; i < colLetters.length; i++) {
            colNum = colNum * 26 + (colLetters.charCodeAt(i) - 64);
          }
          
          // 테이블에서 해당 셀 찾기 (1-based to 0-based)
          const table = document.querySelector('.excel-table');
          if (!table) return null;
          
          const row = table.rows[rowNum]; // 헤더 포함
          if (!row) return null;
          
          const cell = row.cells[colNum]; // 행 헤더 포함
          if (!cell) return null;
          
          return {
            address: addr,
            textContent: cell.textContent?.trim(),
            offsetWidth: cell.offsetWidth,
            scrollWidth: cell.scrollWidth,
            style: window.getComputedStyle(cell),
            overflow: window.getComputedStyle(cell).overflow,
            whiteSpace: window.getComputedStyle(cell).whiteSpace
          };
        }, cellAddress);
        
        if (cellContent) {
          console.log(`\n📱 ${cellAddress} 셀 확인:`);
          console.log(`  텍스트: "${cellContent.textContent}"`);
          console.log(`  너비: ${cellContent.offsetWidth}px (스크롤: ${cellContent.scrollWidth}px)`);
          console.log(`  overflow: ${cellContent.overflow}`);
          console.log(`  white-space: ${cellContent.whiteSpace}`);
          console.log(`  잘림 여부: ${cellContent.scrollWidth > cellContent.offsetWidth ? '❌ 잘림' : '✅ 정상'}`);
          
          // F32, F33은 [object Object] 문제 확인
          if (cellAddress === 'F32' || cellAddress === 'F33') {
            const hasObjectProblem = cellContent.textContent.includes('[object Object]');
            console.log(`  [object Object] 문제: ${hasObjectProblem ? '❌ 발생' : '✅ 해결'}`);
          }
        } else {
          console.log(`\n❌ ${cellAddress} 셀을 찾을 수 없습니다`);
        }
      } catch (error) {
        console.log(`\n❌ ${cellAddress} 셀 확인 중 오류:`, error.message);
      }
    }
    
    // 5. 스크린샷 저장
    await page.screenshot({ 
      path: '/Users/kevin/excel-unified/text_clipping_test_result.png',
      fullPage: true 
    });
    console.log('\n📸 스크린샷 저장 완료: text_clipping_test_result.png');
    
  } catch (error) {
    console.error('❌ 테스트 실행 중 오류:', error);
  } finally {
    await browser.close();
  }
}

// 실행
testTextClippingFix().catch(console.error);