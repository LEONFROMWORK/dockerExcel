const { chromium } = require('playwright');

async function analyzeExcelBorders() {
  const browser = await chromium.launch({ headless: false });
  const page = await browser.newPage();
  
  // Capture all console messages
  const consoleMessages = [];
  page.on('console', msg => {
    const text = msg.text();
    if (text.includes('border check') || text.includes('테두리 소스') || text.includes('P13') || text.includes('P14')) {
      consoleMessages.push(text);
    }
  });
  
  try {
    console.log('🔍 Excel 테두리 데이터 분석...\n');
    
    // Inject debug code after page load
    await page.addInitScript(() => {
      window.debugBorderData = [];
    });
    
    await page.goto('http://localhost:3000/ai/excel/analysis/29');
    await page.waitForTimeout(5000);
    
    // Get captured border data
    const borderData = await page.evaluate(() => window.debugBorderData || []);
    
    console.log('📝 P13, P14 테두리 디버그 로그:');
    consoleMessages.forEach(msg => console.log(msg));
    
    if (borderData.length > 0) {
      console.log('\n📋 캡처된 테두리 데이터:');
      borderData.forEach(data => console.log(data));
    }
    
    // Check the actual rendered result
    const renderedBorders = await page.evaluate(() => {
      const results = {};
      const cellsToCheck = ['P13', 'P14', 'F7', 'D14'];
      
      cellsToCheck.forEach(addr => {
        const col = addr.charCodeAt(0) - 64;
        const row = parseInt(addr.substring(1));
        const index = (row - 1) * 38 + (col - 1);
        
        const cell = document.querySelectorAll('td.data-cell')[index];
        if (cell) {
          const style = window.getComputedStyle(cell);
          const inlineStyle = cell.getAttribute('style');
          
          results[addr] = {
            text: cell.textContent.trim(),
            hasInlineBorder: inlineStyle && inlineStyle.includes('border'),
            computedBorders: {
              top: style.borderTop,
              right: style.borderRight,
              bottom: style.borderBottom,
              left: style.borderLeft
            },
            inlineStyle: inlineStyle ? inlineStyle.substring(0, 200) : null
          };
        }
      });
      
      return results;
    });
    
    console.log('\n🎯 렌더링된 테두리 결과:');
    Object.entries(renderedBorders).forEach(([addr, info]) => {
      console.log(`\n${addr}: "${info.text}"`);
      console.log(`  인라인 테두리: ${info.hasInlineBorder ? '있음' : '없음'}`);
      if (info.inlineStyle) {
        const borderMatch = info.inlineStyle.match(/border[^;]*/g);
        if (borderMatch) {
          console.log(`  인라인 테두리 스타일: ${borderMatch.join('; ')}`);
        }
      }
      console.log('  계산된 테두리:');
      Object.entries(info.computedBorders).forEach(([side, value]) => {
        if (value && value !== 'none' && !value.startsWith('0px')) {
          console.log(`    ${side}: ${value}`);
        }
      });
    });
    
    // Count total cells with/without borders
    const stats = await page.evaluate(() => {
      const cells = document.querySelectorAll('td.data-cell');
      let withBorder = 0;
      let withoutBorder = 0;
      const borderTypes = {};
      
      cells.forEach(cell => {
        const style = cell.getAttribute('style');
        if (style && style.includes('border')) {
          withBorder++;
          
          // Extract border types
          const borderMatches = style.match(/border-[^:]+: [^;]+/g);
          if (borderMatches) {
            borderMatches.forEach(match => {
              const [prop, value] = match.split(': ');
              if (!borderTypes[value]) borderTypes[value] = 0;
              borderTypes[value]++;
            });
          }
        } else {
          withoutBorder++;
        }
      });
      
      return { total: cells.length, withBorder, withoutBorder, borderTypes };
    });
    
    console.log('\n📊 전체 통계:');
    console.log(`총 셀: ${stats.total}`);
    console.log(`인라인 테두리 있음: ${stats.withBorder}`);
    console.log(`인라인 테두리 없음: ${stats.withoutBorder}`);
    
    if (Object.keys(stats.borderTypes).length > 0) {
      console.log('\n테두리 타입 분포 (상위 10개):');
      Object.entries(stats.borderTypes)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 10)
        .forEach(([type, count]) => {
          console.log(`  ${type}: ${count}개`);
        });
    }
    
    await page.waitForTimeout(3000);
    
  } catch (error) {
    console.error('오류:', error.message);
  } finally {
    await browser.close();
  }
}

analyzeExcelBorders();