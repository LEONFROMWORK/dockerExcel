const { chromium } = require('playwright');
const ExcelJS = require('exceljs');

async function analyzeTextClipping() {
  console.log('🔍 Excel 텍스트 잘림 문제 분석 시작...\n');
  
  // 1. Excel 파일 직접 분석
  const workbook = new ExcelJS.Workbook();
  
  try {
    await workbook.xlsx.readFile('/Users/kevin/Desktop/결산보고_25.2Q.xlsx');
    console.log('✅ Excel 파일 로드 성공');
  } catch (error) {
    console.error('❌ Excel 파일 로드 실패:', error.message);
    return;
  }
  
  console.log(`📊 총 워크시트 수: ${workbook.worksheets.length}`);
  
  // 모든 워크시트 이름 출력
  console.log('📋 워크시트 목록:');
  workbook.worksheets.forEach((ws, index) => {
    console.log(`  ${index + 1}. ${ws.name} (id: ${ws.id})`);
  });
  
  // 첫 번째 워크시트 가져오기 (0-based indexing)
  const sheet = workbook.worksheets[0];
  if (!sheet) {
    console.log('❌ 첫 번째 워크시트를 찾을 수 없습니다');
    return;
  }
  
  console.log(`\n📋 분석 대상 워크시트: ${sheet.name}`);
  
  const problemCells = ['F32', 'F33', 'F34', 'F35', 'C44', 'C45', 'C46'];
  
  console.log('📊 Excel 원본 셀 정보:');
  problemCells.forEach(address => {
    const cell = sheet.getCell(address);
    const column = sheet.getColumn(cell.col);
    
    console.log(`\n${address} 셀:`);
    console.log(`  값: "${cell.value}"`);
    console.log(`  텍스트: "${cell.text || 'undefined'}"`);
    console.log(`  열 너비: ${column.width || '기본값'}`);
    console.log(`  셀 스타일: ${JSON.stringify(cell.style || {}, null, 2)}`);
    
    if (cell.value && typeof cell.value === 'string') {
      console.log(`  텍스트 길이: ${cell.value.length} 문자`);
    }
  });
  
  // 2. C, F 열 전체 너비 정보 확인
  console.log('\n📏 열 너비 정보:');
  console.log(`C열 너비: ${sheet.getColumn('C').width || '기본값'}`);
  console.log(`F열 너비: ${sheet.getColumn('F').width || '기본값'}`);
  
  // 3. 시트 전체 차원 정보
  const dimensions = sheet.dimensions;
  console.log(`\n📐 시트 차원: ${dimensions?.left || 1}:${dimensions?.top || 1} to ${dimensions?.right || 1}:${dimensions?.bottom || 1}`);
  
  // 4. 모든 열의 너비 분석
  console.log('\n📊 전체 열 너비 분석:');
  for (let col = 1; col <= (dimensions?.right || 10); col++) {
    const column = sheet.getColumn(col);
    const letter = String.fromCharCode(64 + col); // A=65, B=66, etc.
    if (column.width) {
      console.log(`${letter}열: ${column.width} (${Math.round(column.width * 7)}px)`);
    }
  }
}

// 실행
analyzeTextClipping().catch(console.error);