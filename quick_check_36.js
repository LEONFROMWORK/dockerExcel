const { chromium } = require('playwright');

async function quickCheck36() {
  const browser = await chromium.launch({ headless: false });
  const page = await browser.newPage();
  
  try {
    await page.goto('http://localhost:3000/ai/excel/analysis/36');
    await page.waitForTimeout(3000);
    
    // Get Excel rendering info
    const info = await page.evaluate(() => {
      const cells = document.querySelectorAll('td.data-cell');
      const stylesInfo = [];
      
      // Check first 20 cells for styles
      for (let i = 0; i < Math.min(20, cells.length); i++) {
        const cell = cells[i];
        const style = cell.getAttribute('style') || '';
        const text = cell.textContent.trim();
        
        if (text && text.length > 0) {
          stylesInfo.push({
            text: text.substring(0, 15),
            hasStyle: style.length > 0,
            hasBorder: style.includes('border'),
            hasBackground: style.includes('background'),
            hasRed: style.includes('#FF0000') || style.includes('red')
          });
        }
      }
      
      // Check if there are any error messages
      const errorDiv = document.querySelector('.alert-danger, .error');
      const errorText = errorDiv ? errorDiv.textContent.trim() : null;
      
      return {
        totalCells: cells.length,
        stylesInfo: stylesInfo.slice(0, 10),
        hasError: !!errorText,
        errorText: errorText
      };
    });
    
    console.log('\n📊 Excel 36 (사고조사.xlsx) 상태:');
    console.log(`총 셀 개수: ${info.totalCells}`);
    console.log(`오류 여부: ${info.hasError ? '예' : '아니오'}`);
    if (info.hasError) {
      console.log(`오류 내용: ${info.errorText}`);
    }
    
    console.log('\n🎨 셀 스타일 분석:');
    info.stylesInfo.forEach((cell, idx) => {
      console.log(`${idx + 1}. "${cell.text}" - 스타일: ${cell.hasStyle}, 테두리: ${cell.hasBorder}, 배경: ${cell.hasBackground}, 빨강: ${cell.hasRed}`);
    });
    
    await page.waitForTimeout(1000);
    
  } catch (error) {
    console.error('오류:', error.message);
  } finally {
    await browser.close();
  }
}

quickCheck36();