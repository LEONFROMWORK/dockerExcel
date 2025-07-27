const { chromium } = require('playwright');

async function captureConsoleLogs() {
  const browser = await chromium.launch({ headless: false });
  const page = await browser.newPage();
  
  const allMessages = [];
  page.on('console', msg => {
    const text = msg.text();
    allMessages.push(text);
  });
  
  try {
    console.log('🔍 콘솔 로그 캡처 시작...\n');
    await page.goto('http://localhost:3000/ai/excel/analysis/29');
    await page.waitForTimeout(5000);
    
    // Find messages related to border filtering
    const filterMessages = allMessages.filter(msg => 
      msg.includes('🚫') || 
      msg.includes('border filtered') || 
      msg.includes('default gray') ||
      msg.includes('A1')
    );
    
    console.log('📝 A1 셀 테두리 필터링 메시지:');
    filterMessages.forEach(msg => console.log(msg));
    
    // Look for border source messages
    const borderSourceMessages = allMessages.filter(msg => 
      msg.includes('테두리 소스 검색 결과') ||
      msg.includes('borderSources')
    );
    
    console.log('\n📋 테두리 소스 메시지 (첫 5개):');
    borderSourceMessages.slice(0, 5).forEach(msg => console.log(msg));
    
    // Check specific cells
    const checkResult = await page.evaluate(() => {
      const firstCell = document.querySelector('td.data-cell');
      return {
        hasStyle: firstCell?.hasAttribute('style'),
        style: firstCell?.getAttribute('style')?.substring(0, 200),
        text: firstCell?.textContent?.trim()
      };
    });
    
    console.log('\n🎯 첫 번째 셀 상태:');
    console.log('Has style:', checkResult.hasStyle);
    console.log('Style:', checkResult.style);
    console.log('Text:', checkResult.text);
    
    await page.waitForTimeout(2000);
    
  } catch (error) {
    console.error('오류:', error.message);
  } finally {
    await browser.close();
  }
}

captureConsoleLogs();