const { chromium } = require('playwright');

async function test() {
  const browser = await chromium.launch({ headless: false });
  const page = await browser.newPage();
  
  console.log('Testing TD height...');
  
  await page.goto('http://localhost:3000/ai/excel/analysis/36');
  await page.waitForTimeout(4000);
  
  const results = await page.evaluate(() => {
    const row3 = document.querySelector('tbody tr:nth-child(3)');
    const row4 = document.querySelector('tbody tr:nth-child(4)');
    const row5 = document.querySelector('tbody tr:nth-child(5)');
    
    return {
      row3: {
        trHeight: row3 ? row3.offsetHeight : 0,
        tdHeight: row3 ? row3.querySelector('td').offsetHeight : 0,
        tdStyle: row3 ? row3.querySelector('td').getAttribute('style') : ''
      },
      row4: {
        trHeight: row4 ? row4.offsetHeight : 0,
        tdHeight: row4 ? row4.querySelector('td').offsetHeight : 0,
        tdStyle: row4 ? row4.querySelector('td').getAttribute('style') : ''
      },
      row5: {
        trHeight: row5 ? row5.offsetHeight : 0,
        tdHeight: row5 ? row5.querySelector('td').offsetHeight : 0,
        tdStyle: row5 ? row5.querySelector('td').getAttribute('style') : ''
      }
    };
  });
  
  console.log('Row 3:', results.row3);
  console.log('Row 4:', results.row4);
  console.log('Row 5:', results.row5);
  
  await browser.close();
}

test();
