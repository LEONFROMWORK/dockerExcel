const ExcelJS = require('exceljs');
const path = require('path');

async function analyzeExcelBordersRaw() {
  console.log('🔍 Excel 파일의 원본 테두리 정보 분석...\n');
  
  const workbook = new ExcelJS.Workbook();
  
  try {
    // Load the Excel file directly
    await workbook.xlsx.readFile('/Users/kevin/excel-unified/rails-app/public/uploads/excel_file/file/29/(공표기준)결산보고_25.2Q.xlsx');
    
    const worksheet = workbook.getWorksheet(1);
    console.log(`워크시트: ${worksheet.name}\n`);
    
    // Analyze workbook styles
    if (workbook._styles) {
      console.log('📚 워크북 스타일 정보:');
      console.log(`- borders 개수: ${workbook._styles.borders?.length || 0}`);
      console.log(`- cellXfs 개수: ${workbook._styles.cellXfs?.length || 0}`);
      console.log(`- cellStyles 개수: ${workbook._styles.cellStyles?.length || 0}`);
      
      // First 10 border definitions
      if (workbook._styles.borders) {
        console.log('\n테두리 정의 (처음 10개):');
        workbook._styles.borders.slice(0, 10).forEach((border, idx) => {
          if (border && (border.top || border.bottom || border.left || border.right)) {
            console.log(`Border[${idx}]:`, JSON.stringify(border, null, 2));
          }
        });
      }
    }
    
    // Sample cells analysis
    console.log('\n📋 샘플 셀 분석:');
    const sampleCells = [
      'A1', 'B1', 'C1',  // First row
      'P13', 'P14',      // Problem cells
      'F7', 'F8', 'F9',  // Red border cells
      'D14', 'D15', 'D16', 'D17'  // More red borders
    ];
    
    sampleCells.forEach(addr => {
      const cell = worksheet.getCell(addr);
      console.log(`\n${addr} 셀:`);
      console.log('- value:', cell.value);
      console.log('- border:', cell.border);
      console.log('- style.border:', cell.style?.border);
      console.log('- _style:', cell._style);
      
      // Check if border is from workbook styles
      if (cell._style?.borderId !== undefined) {
        console.log(`- borderId: ${cell._style.borderId}`);
        if (workbook._styles?.borders?.[cell._style.borderId]) {
          console.log('- workbook border:', workbook._styles.borders[cell._style.borderId]);
        }
      }
    });
    
    // Count cells with no borders
    let noBorderCount = 0;
    let customBorderCount = 0;
    let totalCells = 0;
    
    worksheet.eachRow((row, rowNumber) => {
      row.eachCell((cell, colNumber) => {
        totalCells++;
        
        const hasBorder = cell.border && Object.keys(cell.border).length > 0;
        const hasStyleBorder = cell.style?.border && Object.keys(cell.style.border).length > 0;
        
        if (!hasBorder && !hasStyleBorder) {
          noBorderCount++;
        } else {
          customBorderCount++;
        }
      });
    });
    
    console.log('\n📊 전체 셀 통계:');
    console.log(`총 셀 수: ${totalCells}`);
    console.log(`테두리 없는 셀: ${noBorderCount} (${(noBorderCount/totalCells*100).toFixed(1)}%)`);
    console.log(`테두리 있는 셀: ${customBorderCount} (${(customBorderCount/totalCells*100).toFixed(1)}%)`);
    
    // Check for theme colors
    console.log('\n🎨 테마 색상 분석:');
    if (workbook.model?.theme?.themeElements?.clrScheme) {
      const colorScheme = workbook.model.theme.themeElements.clrScheme;
      console.log('테마 색상:', Object.keys(colorScheme));
    }
    
  } catch (error) {
    console.error('오류:', error.message);
  }
}

analyzeExcelBordersRaw();