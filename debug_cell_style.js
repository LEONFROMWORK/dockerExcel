const { chromium } = require('playwright');

async function test() {
  const browser = await chromium.launch({ headless: false });
  const page = await browser.newPage();
  
  console.log('Debugging cell style...');
  
  await page.goto('http://localhost:3000/ai/excel/analysis/36');
  await page.waitForTimeout(4000);
  
  // Look at console logs from the page
  page.on('console', msg => {
    if (msg.text().includes('cellStyle') || msg.text().includes('height')) {
      console.log('PAGE LOG:', msg.text());
    }
  });
  
  await page.waitForTimeout(2000);
  
  await browser.close();
}

test();
