const { chromium } = require('playwright');

async function finalBorderTest() {
  const browser = await chromium.launch({ headless: false });
  const page = await browser.newPage();
  
  try {
    console.log('🎯 최종 테두리 테스트...\n');
    await page.goto('http://localhost:3000/ai/excel/analysis/29');
    await page.waitForTimeout(4000);
    
    // Check border statistics
    const stats = await page.evaluate(() => {
      const cells = document.querySelectorAll('td.data-cell');
      let noBorderCount = 0;
      let customBorderCount = 0;
      let redBorderCount = 0;
      let grayBorderCount = 0;
      const borderColors = {};
      
      cells.forEach(cell => {
        const style = window.getComputedStyle(cell);
        const borders = [
          style.borderTop,
          style.borderRight,
          style.borderBottom,
          style.borderLeft
        ];
        
        const hasNoBorder = borders.every(b => 
          b === 'none' || b === '0px none rgb(0, 0, 0)' || !b
        );
        
        if (hasNoBorder) {
          noBorderCount++;
        } else {
          customBorderCount++;
          
          // Count border colors
          borders.forEach(border => {
            if (border && border !== 'none') {
              const colorMatch = border.match(/rgb\([^)]+\)/);
              if (colorMatch) {
                const color = colorMatch[0];
                borderColors[color] = (borderColors[color] || 0) + 1;
                
                if (color === 'rgb(255, 0, 0)') redBorderCount++;
                if (color === 'rgb(224, 224, 224)' || color === 'rgb(208, 208, 208)') {
                  grayBorderCount++;
                }
              }
            }
          });
        }
      });
      
      return {
        total: cells.length,
        noBorder: noBorderCount,
        withBorder: customBorderCount,
        redBorders: redBorderCount,
        grayBorders: grayBorderCount,
        colorDistribution: borderColors
      };
    });
    
    console.log('📊 테두리 통계:');
    console.log(`총 셀: ${stats.total}`);
    console.log(`테두리 없는 셀: ${stats.noBorder} (${(stats.noBorder/stats.total*100).toFixed(1)}%)`);
    console.log(`테두리 있는 셀: ${stats.withBorder} (${(stats.withBorder/stats.total*100).toFixed(1)}%)`);
    console.log(`빨간색 테두리: ${stats.redBorders}`);
    console.log(`회색 테두리: ${stats.grayBorders}`);
    
    console.log('\n🎨 테두리 색상 분포:');
    Object.entries(stats.colorDistribution)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .forEach(([color, count]) => {
        console.log(`  ${color}: ${count}개`);
      });
    
    // Check specific cells
    const specificCells = ['P13', 'P14', 'F7', 'F8', 'D14', 'D15'];
    console.log('\n🔍 특정 셀 검증:');
    
    for (const cellAddr of specificCells) {
      const result = await page.evaluate((addr) => {
        const col = addr.charCodeAt(0) - 64;
        const row = parseInt(addr.substring(1));
        const index = (row - 1) * 38 + (col - 1);
        
        const cell = document.querySelectorAll('td.data-cell')[index];
        if (!cell) return null;
        
        const style = window.getComputedStyle(cell);
        const hasBorder = [
          style.borderTop,
          style.borderRight,
          style.borderBottom,
          style.borderLeft
        ].some(b => b && b !== 'none' && b !== '0px none rgb(0, 0, 0)');
        
        return {
          text: cell.textContent.trim(),
          hasBorder,
          left: style.borderLeft
        };
      }, cellAddr);
      
      if (result) {
        console.log(`${cellAddr}: "${result.text}" - ${result.hasBorder ? '✅ 테두리 있음' : '❌ 테두리 없음'} (left: ${result.left})`);
      }
    }
    
    console.log('\n✅ 테스트 완료!');
    await page.waitForTimeout(5000);
    
  } catch (error) {
    console.error('오류:', error.message);
  } finally {
    await browser.close();
  }
}

finalBorderTest();