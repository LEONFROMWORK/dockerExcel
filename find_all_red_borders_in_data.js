const { chromium } = require('playwright');

async function findAllRedBordersInData() {
  const browser = await chromium.launch({ headless: false });
  const page = await browser.newPage();
  
  // Capture all border-related console messages
  const borderMessages = [];
  page.on('console', msg => {
    const text = msg.text();
    if (text.includes('border') && (text.includes('#FF0000') || text.includes('thick'))) {
      borderMessages.push(text);
    }
  });
  
  try {
    console.log('🔍 Excel 데이터에서 모든 빨간 테두리 찾기...\n');
    await page.goto('http://localhost:3000/ai/excel/analysis/29');
    await page.waitForTimeout(5000);
    
    // Extract console messages about borders
    console.log('📝 빨간/두꺼운 테두리 관련 콘솔 메시지 (처음 20개):');
    borderMessages.slice(0, 20).forEach((msg, idx) => {
      console.log(`${idx + 1}. ${msg}`);
    });
    
    // Check all cells with any borders
    const cellsWithBorders = await page.evaluate(() => {
      const cells = document.querySelectorAll('td');
      const results = [];
      
      cells.forEach((cell, idx) => {
        const style = cell.getAttribute('style') || '';
        if (style.includes('border')) {
          const text = cell.textContent.trim() || '(empty)';
          
          // Get cell position
          const row = cell.parentElement;
          const rowIndex = row ? Array.from(row.parentElement.children).indexOf(row) + 1 : -1;
          
          let colIndex = 0;
          let currentCell = cell;
          while (currentCell.previousSibling) {
            currentCell = currentCell.previousSibling;
            if (currentCell.nodeType === 1) colIndex++;
          }
          colIndex++;
          
          const hasRedBorder = style.includes('#FF0000') || style.includes('255, 0, 0');
          const hasThickBorder = style.includes('4px');
          
          if (hasRedBorder || hasThickBorder) {
            results.push({
              row: rowIndex,
              col: colIndex,
              text: text.substring(0, 30),
              hasRed: hasRedBorder,
              hasThick: hasThickBorder,
              style: style.substring(0, 200)
            });
          }
        }
      });
      
      return results;
    });
    
    console.log(`\n📊 빨간색 또는 두꺼운 테두리가 있는 셀: ${cellsWithBorders.length}개\n`);
    
    // Group by row
    const byRow = {};
    cellsWithBorders.forEach(cell => {
      if (!byRow[cell.row]) byRow[cell.row] = [];
      byRow[cell.row].push(cell);
    });
    
    // Show cells by row
    Object.keys(byRow).sort((a, b) => parseInt(a) - parseInt(b)).forEach(row => {
      console.log(`행 ${row}:`);
      byRow[row].forEach(cell => {
        console.log(`  열 ${cell.col}: "${cell.text}" - ${cell.hasRed ? '빨간색' : ''}${cell.hasThick ? ' 두꺼움' : ''}`);
      });
    });
    
    // Focus on the K-L area (columns 11-12, rows 7-19)
    console.log('\n🎯 K-L 영역 (열 11-12, 행 7-19) 분석:');
    const klAreaCells = cellsWithBorders.filter(cell => 
      cell.col >= 11 && cell.col <= 12 && cell.row >= 7 && cell.row <= 19
    );
    
    if (klAreaCells.length === 0) {
      console.log('K-L 영역에 빨간/두꺼운 테두리가 없습니다.');
    } else {
      klAreaCells.forEach(cell => {
        console.log(`행 ${cell.row}, 열 ${cell.col}: "${cell.text}"`);
      });
    }
    
    await page.waitForTimeout(3000);
    
  } catch (error) {
    console.error('오류:', error.message);
  } finally {
    await browser.close();
  }
}

findAllRedBordersInData();