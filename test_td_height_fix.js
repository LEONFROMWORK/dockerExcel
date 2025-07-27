const { chromium } = require('playwright');

async function testTdHeightFix() {
  const browser = await chromium.launch({ headless: false });
  const page = await browser.newPage();
  
  try {
    console.log('🧪 TD 직접 높이 설정 테스트...\n');
    
    await page.goto('http://localhost:3000/ai/excel/analysis/36');
    await page.waitForTimeout(4000);
    
    // Check both TR and TD heights
    const heightComparison = await page.evaluate(() => {
      const results = [];
      const rowsToCheck = [3, 4, 5]; // Problem rows
      
      rowsToCheck.forEach(rowNum => {
        const row = document.querySelector(`tbody tr:nth-child(${rowNum})`);
        if (\!row) return;
        
        const rowStyle = row.getAttribute('style') || '';
        const trHeightMatch = rowStyle.match(/height:\s*(\d+)px/);
        const trSetHeight = trHeightMatch ? parseInt(trHeightMatch[1]) : 0;
        
        // Check first few cells in this row
        const cells = row.querySelectorAll('td');
        const cellData = [];
        
        for (let i = 0; i < Math.min(3, cells.length); i++) {
          const cell = cells[i];
          const cellStyle = cell.getAttribute('style') || '';
          const cellHeightMatch = cellStyle.match(/height:\s*(\d+)px/);
          const cellSetHeight = cellHeightMatch ? parseInt(cellHeightMatch[1]) : 0;
          
          cellData.push({
            index: i,
            setHeight: cellSetHeight,
            actualHeight: cell.offsetHeight,
            content: cell.textContent.trim().substring(0, 15)
          });
        }
        
        results.push({
          rowNumber: rowNum,
          trSetHeight: trSetHeight,
          trActualHeight: row.offsetHeight,
          cellData: cellData
        });
      });
      
      return results;
    });
    
    console.log('📊 TR vs TD 높이 비교:');
    heightComparison.forEach(row => {
      console.log(`\n=== 행 ${row.rowNumber} ===`);
      console.log(`TR 설정 높이: ${row.trSetHeight}px`);
      console.log(`TR 실제 높이: ${row.trActualHeight}px`);
      
      console.log('TD 높이:');
      row.cellData.forEach(cell => {
        if (cell.content || cell.setHeight > 0) {
          console.log(`  셀 ${cell.index}: 설정=${cell.setHeight}px, 실제=${cell.actualHeight}px "${cell.content}"`);
        }
      });
    });
    
    await page.waitForTimeout(3000);
    
  } catch (error) {
    console.error('❌ 테스트 오류:', error.message);
  } finally {
    await browser.close();
  }
}

testTdHeightFix();
