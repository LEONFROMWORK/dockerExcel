const { chromium } = require('playwright');

async function validateAllBorders() {
  const browser = await chromium.launch({ headless: false });
  const page = await browser.newPage();
  
  console.log('🚀 전체 테두리 시스템 검증 시작...');
  
  try {
    await page.goto('http://localhost:3000/ai/excel/analysis/29');
    await page.waitForTimeout(3000);
    
    // Extract all border information from the page
    const borderValidation = await page.evaluate(() => {
      const results = {
        totalCells: 0,
        cellsWithBorders: 0,
        borderTypes: {},
        sampleBorders: [],
        issuesFound: []
      };
      
      // Find all data cells
      const dataCells = document.querySelectorAll('td.data-cell');
      results.totalCells = dataCells.length;
      
      dataCells.forEach((cell, index) => {
        const style = cell.getAttribute('style') || '';
        const computedStyle = window.getComputedStyle(cell);
        
        // Check for border styles in inline styles
        const hasBorderInStyle = style.includes('border');
        if (hasBorderInStyle) {
          results.cellsWithBorders++;
          
          // Count border types
          if (style.includes('border-left')) results.borderTypes.left = (results.borderTypes.left || 0) + 1;
          if (style.includes('border-right')) results.borderTypes.right = (results.borderTypes.right || 0) + 1;
          if (style.includes('border-top')) results.borderTypes.top = (results.borderTypes.top || 0) + 1;
          if (style.includes('border-bottom')) results.borderTypes.bottom = (results.borderTypes.bottom || 0) + 1;
          
          // Sample first 10 cells with borders
          if (results.sampleBorders.length < 10) {
            results.sampleBorders.push({
              index,
              cellText: cell.textContent.trim(),
              style: style.substring(0, 200) + (style.length > 200 ? '...' : ''),
              computedBorderLeft: computedStyle.borderLeft,
              computedBorderRight: computedStyle.borderRight,
              computedBorderTop: computedStyle.borderTop,
              computedBorderBottom: computedStyle.borderBottom
            });
          }
        }
        
        // Check for issues
        const hasInlineStyle = style.includes('border');
        const hasComputedBorder = computedStyle.borderLeft !== 'none' || 
                                  computedStyle.borderRight !== 'none' || 
                                  computedStyle.borderTop !== 'none' || 
                                  computedStyle.borderBottom !== 'none';
        
        if (hasInlineStyle && !hasComputedBorder) {
          results.issuesFound.push({
            index,
            issue: 'Has inline border style but computed style shows no border',
            cellText: cell.textContent.trim(),
            style: style.substring(0, 100) + '...'
          });
        }
      });
      
      return results;
    });
    
    console.log('\n📊 전체 테두리 검증 결과:');
    console.log(`총 셀 수: ${borderValidation.totalCells}`);
    console.log(`테두리가 있는 셀 수: ${borderValidation.cellsWithBorders}`);
    console.log(`테두리 적용률: ${(borderValidation.cellsWithBorders / borderValidation.totalCells * 100).toFixed(1)}%`);
    
    console.log('\n📈 테두리 유형별 통계:');
    Object.entries(borderValidation.borderTypes).forEach(([type, count]) => {
      console.log(`  ${type}: ${count}개`);
    });
    
    console.log('\n🔍 테두리 적용 샘플 (처음 10개):');
    borderValidation.sampleBorders.forEach((sample, idx) => {
      console.log(`${idx + 1}. "${sample.cellText}" - ${sample.computedBorderLeft}`);
    });
    
    if (borderValidation.issuesFound.length > 0) {
      console.log('\n⚠️  발견된 문제:');
      borderValidation.issuesFound.forEach((issue, idx) => {
        console.log(`${idx + 1}. ${issue.issue} - "${issue.cellText}"`);
      });
    } else {
      console.log('\n✅ 테두리 시스템 문제 없음!');
    }
    
    // Check specific P13, P14 cells
    const p13p14Check = await page.evaluate(() => {
      const tableRows = document.querySelectorAll('tbody tr');
      const results = {};
      
      const targets = [
        { name: 'P13', rowIndex: 12, colIndex: 16 },
        { name: 'P14', rowIndex: 13, colIndex: 16 }
      ];
      
      targets.forEach(target => {
        if (tableRows[target.rowIndex]) {
          const cells = tableRows[target.rowIndex].querySelectorAll('td');
          if (cells[target.colIndex]) {
            const cell = cells[target.colIndex];
            const computedStyle = window.getComputedStyle(cell);
            results[target.name] = {
              text: cell.textContent.trim(),
              borderLeft: computedStyle.borderLeft,
              borderRight: computedStyle.borderRight,
              borderTop: computedStyle.borderTop,
              borderBottom: computedStyle.borderBottom,
              allBorders: `${computedStyle.borderTop} | ${computedStyle.borderRight} | ${computedStyle.borderBottom} | ${computedStyle.borderLeft}`
            };
          }
        }
      });
      
      return results;
    });
    
    console.log('\n🎯 P13, P14 최종 검증:');
    Object.entries(p13p14Check).forEach(([cell, data]) => {
      console.log(`${cell}: "${data.text}"`);
      console.log(`  전체 테두리: ${data.allBorders}`);
      console.log(`  왼쪽 테두리: ${data.borderLeft}`);
    });
    
    await page.waitForTimeout(2000);
    
  } catch (error) {
    console.error('검증 중 오류:', error.message);
  } finally {
    await browser.close();
  }
}

validateAllBorders();