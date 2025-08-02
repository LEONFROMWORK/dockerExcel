# Excel 고급 포맷팅 렌더링 테스트 가이드

## 테스트 파일 위치
`/Users/kevin/excel-unified/python-service/test_advanced_formatting.xlsx`

## 테스트 내용
- 숫자 포맷: 통화(원), 백분율, 날짜, 시간
- 조건부 서식: 색상 스케일, 값 기반 서식
- 데이터 유효성: 드롭다운 목록, 숫자 범위 제한

## 브라우저 테스트 단계

### 1. 서비스 실행 확인
```bash
# Rails 서버 (포트 3000)
lsof -i :3000 | grep LISTEN

# Python 서비스 (포트 8000)
lsof -i :8000 | grep LISTEN
```

### 2. 브라우저 접속
1. Chrome 또는 Firefox 열기
2. http://localhost:3000 접속
3. 개발자 도구 열기 (F12)
4. Console 탭 선택

### 3. Excel 파일 업로드
1. Excel 파일 업로드 버튼 찾기
2. `test_advanced_formatting.xlsx` 파일 선택
3. 업로드 진행

### 4. 콘솔 로그 확인

#### 예상되는 로그:
```javascript
🎨 Registering advanced formatting plugins...
📊 Registering number formatting plugins...
✅ Number formatting plugins registered
🎯 Registering conditional formatting plugins...
✅ Conditional formatting plugins registered
✔️ Registering data validation plugins...
✅ Data validation plugins registered

🎨 Advanced formatting data: {
  hasConditionalFormats: true,
  conditionalFormatsCount: 2,
  hasDataValidations: true,
  dataValidationsCount: 2
}

📊 Number format styles: {
  totalStyles: 9,
  stylesWithNumFormat: 5,
  sampleNumFormats: [...]
}
```

### 5. 렌더링 확인

#### 확인 포인트:
1. **숫자 포맷**
   - B4: 1,234,567원 (통화 형식)
   - B5: 85.67% (백분율)
   - B6: 2025-08-02 (날짜)
   - B7: 3:53:20 PM (시간)

2. **조건부 서식**
   - B11~B15: 점수에 따른 색상 그라데이션
   - 80점 이상: 파란색 굵은 글씨

3. **데이터 유효성**
   - B18: 드롭다운 목록 (A, B, C, D, F)
   - B19: 0-100 범위 숫자만 입력 가능

### 6. 디버깅 명령

콘솔에서 실행:
```javascript
// Univer 인스턴스 확인
console.log(window.univerInstance)

// 현재 시트 데이터 확인
const sheet = window.univerInstance?.getActiveSheet()
console.log('Active sheet:', sheet)

// 스타일 정보 확인
const styles = window.univerInstance?.getStyles()
console.log('Styles:', styles)

// 조건부 서식 확인
const conditionalFormats = sheet?.getConditionalFormats()
console.log('Conditional formats:', conditionalFormats)
```

## 문제 발생 시 체크리스트

### 플러그인 등록 실패
- [ ] package.json에 플러그인 설치 확인
- [ ] UniverViewer.vue에서 import 확인
- [ ] 플러그인 버전 호환성 확인

### 데이터 전달 문제
- [ ] Python 서비스 로그 확인
- [ ] Network 탭에서 API 응답 확인
- [ ] 데이터 구조 검증

### 렌더링 오류
- [ ] 콘솔 에러 메시지 확인
- [ ] Univer 버전 확인
- [ ] 무료 버전 제약사항 확인

## 추가 테스트 파일

다른 형식 테스트가 필요한 경우:
```bash
cd /Users/kevin/excel-unified/python-service
python3 create_test_excel.py
```

생성된 파일로 추가 테스트 가능