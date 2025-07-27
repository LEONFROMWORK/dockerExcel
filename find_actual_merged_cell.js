const { chromium } = require('playwright');

async function findActualMergedCell() {
  const browser = await chromium.launch({ headless: false });
  const page = await browser.newPage();
  
  try {
    console.log('🔍 병합된 "상반기누적" 셀 찾기...\n');
    await page.goto('http://localhost:3000/ai/excel/analysis/29');
    await page.waitForTimeout(4000);
    
    // Find the exact location by checking visual position
    const mergedCellInfo = await page.evaluate(() => {
      const cells = document.querySelectorAll('td.data-cell');
      const results = [];
      
      // Row 6, columns around J-K-L (10-11-12)
      for (let col = 8; col <= 14; col++) {
        const index = (6 - 1) * 38 + (col - 1);
        const cell = cells[index];
        
        if (cell) {
          const text = cell.textContent.trim();
          const colspan = cell.getAttribute('colspan');
          const style = cell.getAttribute('style') || '';
          const hasRightBorder = style.includes('border-right');
          const rightBorderMatch = style.match(/border-right:\s*([^;]+)/);
          
          results.push({
            col: col,
            colLetter: String.fromCharCode(64 + col),
            address: String.fromCharCode(64 + col) + '6',
            text: text || '(empty)',
            colspan: colspan,
            hasRightBorder: hasRightBorder,
            rightBorder: rightBorderMatch ? rightBorderMatch[1] : null,
            isRedBorder: rightBorderMatch && rightBorderMatch[1].includes('#FF0000')
          });
        }
      }
      
      return results;
    });
    
    console.log('📊 6행의 셀 정보 (H-N 열):');
    mergedCellInfo.forEach(info => {
      console.log(`${info.address}: "${info.text}"`);
      if (info.colspan) {
        console.log(`  병합: colspan=${info.colspan}`);
      }
      if (info.hasRightBorder) {
        console.log(`  오른쪽 테두리: ${info.rightBorder}`);
        if (info.isRedBorder) {
          console.log(`  🔴 빨간색 테두리!`);
        }
      }
      console.log('');
    });
    
    // Check row 7 for the actual merged state
    const row7Info = await page.evaluate(() => {
      const cells = document.querySelectorAll('td.data-cell');
      const results = [];
      
      // Check columns I through M in row 7
      for (let col = 9; col <= 13; col++) {
        const index = (7 - 1) * 38 + (col - 1);
        const cell = cells[index];
        
        if (cell) {
          const text = cell.textContent.trim();
          const style = cell.getAttribute('style') || '';
          
          results.push({
            address: String.fromCharCode(64 + col) + '7',
            text: text || '(empty)',
            hasBorder: style.includes('border-'),
            style: style.substring(0, 150)
          });
        }
      }
      
      return results;
    });
    
    console.log('📋 7행 셀 상태 (I-M 열):');
    row7Info.forEach(info => {
      console.log(`${info.address}: "${info.text}" - 테두리: ${info.hasBorder}`);
    });
    
    // Find cells with thick red borders
    const redBorderCells = await page.evaluate(() => {
      const cells = document.querySelectorAll('td.data-cell');
      const redCells = [];
      
      cells.forEach((cell, idx) => {
        const style = cell.getAttribute('style') || '';
        if (style.includes('4px solid #FF0000')) {
          const row = Math.floor(idx / 38) + 1;
          const col = (idx % 38) + 1;
          const addr = String.fromCharCode(64 + col) + row;
          
          const borders = [];
          if (style.includes('border-top: 4px solid #FF0000')) borders.push('top');
          if (style.includes('border-right: 4px solid #FF0000')) borders.push('right');
          if (style.includes('border-bottom: 4px solid #FF0000')) borders.push('bottom');
          if (style.includes('border-left: 4px solid #FF0000')) borders.push('left');
          
          if (row >= 6 && row <= 8 && col >= 9 && col <= 13) {
            redCells.push({
              address: addr,
              text: cell.textContent.trim() || '(empty)',
              borders: borders
            });
          }
        }
      });
      
      return redCells;
    });
    
    console.log('\n🔴 6-8행, I-M열 범위의 빨간 테두리:');
    redBorderCells.forEach(cell => {
      console.log(`${cell.address}: "${cell.text}" - 빨간 테두리: ${cell.borders.join(', ')}`);
    });
    
    await page.waitForTimeout(3000);
    
  } catch (error) {
    console.error('오류:', error.message);
  } finally {
    await browser.close();
  }
}

findActualMergedCell();