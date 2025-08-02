# 셀 일치성 검사 시스템 정리

## 개요

Luckysheet 프론트엔드(0-based 인덱싱)와 Python 백엔드(1-based 인덱싱) 간의 셀 선택 일치성을 검증하는 시스템입니다.

## 파일 구조

### 1. Python 서비스 (백엔드)

#### 📄 `/python-service/app/api/v1/test_cell_consistency.py`
**역할**: 실제 Excel 파일을 읽어서 셀 일치성을 검증하는 API 엔드포인트

**주요 기능**:
- 실제 Excel 파일에서 셀 값 읽기 (openpyxl + pandas)
- 다중 시트 지원 (시트명으로 선택 가능)
- 좌표 변환 검증 (0-based → 1-based)
- 값 일치성 검사
- 상세한 디버그 정보 제공

**API 엔드포인트**: `POST /api/v1/test/test-cell-consistency`

**요청 형식**:
```json
{
  "file_id": "multi_sheet_test.xlsx",
  "sheet_name": "Sheet1",
  "frontend_cell": {
    "address": "A1",
    "row": 0,
    "col": 0,
    "value": "테스트값"
  }
}
```

**응답 형식**:
```json
{
  "address": "A1",
  "row": 1,
  "col": 1,
  "value": "테스트값",
  "match": true,
  "differences": [],
  "debug_info": {
    "frontend_0_based": {"row": 0, "col": 0},
    "python_1_based": {"row": 1, "col": 1},
    "pandas_value": "테스트값",
    "sheet_info": {
      "current_sheet": "Sheet1",
      "available_sheets": ["Sheet1", "Sheet2", "테스트시트"],
      "total_sheets": 3
    },
    "file_used": "multi_sheet_test.xlsx"
  }
}
```

### 2. Rails 서비스 (중계)

#### 📄 `/rails-app/app/controllers/api/v1/excel_unified_controller.rb`
**역할**: 프론트엔드 요청을 받아 Python 서비스로 전달하고 결과를 가공해서 반환

**주요 기능**:
- 프론트엔드 요청 파라미터 변환
- Python 서비스 HTTP 호출
- 응답 데이터 가공 및 포맷팅
- Python 서비스 실패시 시뮬레이션 모드 제공

**API 엔드포인트**: `POST /api/v1/excel-unified/test-cell-consistency`

**메소드**: `test_cell_consistency`

### 3. 프론트엔드 (Vue.js)

#### 📄 `/rails-app/app/javascript/domains/excel_ai/components/CellConsistencyTest.vue`
**역할**: 사용자가 셀을 클릭하면 일치성을 테스트할 수 있는 UI 컴포넌트

**주요 기능**:
- Luckysheet 셀 선택 이벤트 감지
- Rails API 호출
- 결과 시각화 (일치/불일치 표시)
- 디버그 정보 표시

### 4. 설정 파일

#### 📄 `/rails-app/config/routes.rb`
```ruby
# Excel Unified - new integrated interface
scope "excel-unified" do
  post "test-cell-consistency", to: "excel_unified#test_cell_consistency"
end
```

#### 📄 `/python-service/app/api/__init__.py`
```python
from app.api.v1 import test_cell_consistency
router.include_router(test_cell_consistency.router, prefix="/test", tags=["testing"])
```

## 테스트 데이터

### 📄 `/python-service/uploads/multi_sheet_test.xlsx`
**용도**: 다중 시트 일치성 테스트용 Excel 파일

**시트 구성**:
- **Sheet1**: 기본 테스트 데이터
  - A1: "첫번째시트", B1: "Sheet1"
  - A2: "데이터1", B2: 100
  
- **Sheet2**: 두 번째 시트 테스트
  - A1: "두번째시트", B1: "Sheet2"  
  - A2: "데이터2", B2: 200
  
- **테스트시트**: 한글 시트명 테스트
  - A1: "한글시트", B1: "테스트", C1: "추가데이터"
  - A2: "값", B2: 300, C2: "테스트값"

## 검증 완료 사항

### ✅ 단일 시트 테스트
- **파일**: `converted_table_20250726_215046.xlsx`
- **테스트 케이스**:
  - A1: "구분" ↔ "구분" ✅
  - C2: 66 ↔ 66 ✅

### ✅ 다중 시트 테스트
- **파일**: `multi_sheet_test.xlsx`
- **테스트 케이스**:
  - Sheet1/A1: "첫번째시트" ↔ "첫번째시트" ✅
  - Sheet1/B2: 100 ↔ 100 ✅
  - Sheet2/A1: "두번째시트" ↔ "두번째시트" ✅
  - Sheet2/B2: 200 ↔ 200 ✅
  - 테스트시트/C2: "테스트값" ↔ "테스트값" ✅

### ✅ 좌표 변환 검증
| 프론트엔드 (0-based) | 파이썬 (1-based) | 주소 |
|---------------------|------------------|-------|
| row: 0, col: 0 | row: 1, col: 1 | A1 |
| row: 1, col: 1 | row: 2, col: 2 | B2 |
| row: 1, col: 2 | row: 2, col: 3 | C2 |

### ✅ 데이터 타입 지원
- **문자열**: 한글, 영문 완벽 지원
- **숫자**: 정수형 완벽 지원
- **시트명**: 한글 시트명 완벽 지원

## 사용 방법

### 1. 직접 API 호출 (개발/테스트용)
```bash
curl -X POST "http://localhost:8000/api/v1/test/test-cell-consistency" \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "multi_sheet_test.xlsx",
    "sheet_name": "Sheet1",
    "frontend_cell": {
      "address": "A1",
      "row": 0,
      "col": 0,
      "value": "첫번째시트"
    }
  }'
```

### 2. 프론트엔드 UI 사용
1. Excel 파일을 Luckysheet로 열기
2. 셀 클릭
3. 일치성 테스트 버튼 클릭
4. 결과 확인

## 기술적 세부사항

### 좌표 변환 로직
```python
# 프론트엔드 (0-based) → 파이썬 (1-based)
python_row = frontend_row + 1
python_col = frontend_col + 1

# 주소 생성
address = f"{openpyxl.utils.get_column_letter(python_col)}{python_row}"
```

### 시트 선택 로직
```python
# 시트 선택
if request.sheet_name and request.sheet_name in wb.sheetnames:
    ws = wb[request.sheet_name]  # 지정된 시트
else:
    ws = wb.active  # 기본 시트
```

### 값 비교 로직
```python
# openpyxl과 pandas 모두 사용하여 검증
openpyxl_value = ws.cell(row=python_row, column=python_col).value
pandas_value = df.iloc[frontend_row, frontend_col]

# 문자열 변환 후 비교
frontend_str = str(frontend_value) if frontend_value is not None else ""
python_str = str(openpyxl_value) if openpyxl_value is not None else ""
```

## 결론

**모든 테스트 통과**: Luckysheet 프론트엔드와 Python 백엔드가 단일/다중 시트 환경에서 **완벽하게 같은 셀을 인식**하고 있음을 확인했습니다.

이 시스템을 통해 향후 Excel 데이터 처리 시 프론트엔드와 백엔드 간의 셀 참조 일치성을 보장할 수 있습니다.