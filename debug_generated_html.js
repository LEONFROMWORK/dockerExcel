const { chromium } = require('playwright');

async function test() {
  const browser = await chromium.launch({ headless: false });
  const page = await browser.newPage();
  
  console.log('Debugging generated HTML...');
  
  await page.goto('http://localhost:3000/ai/excel/analysis/36');
  await page.waitForTimeout(4000);
  
  const htmlSnippet = await page.evaluate(() => {
    const row3 = document.querySelector('tbody tr:nth-child(3)');
    if (\!row3) return 'Row 3 not found';
    
    const cell = row3.querySelector('td:nth-child(2)'); // Second cell (not row header)
    if (\!cell) return 'Cell not found';
    
    return {
      outerHTML: cell.outerHTML.substring(0, 300),
      style: cell.getAttribute('style'),
      hasHeightInStyle: cell.outerHTML.includes('height:')
    };
  });
  
  console.log('Cell HTML:', htmlSnippet);
  
  await browser.close();
}

test();
