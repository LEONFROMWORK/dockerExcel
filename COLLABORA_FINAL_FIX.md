# Collabora 뷰어 최종 수정 완료 ✅

## 추가로 발견된 문제들과 해결

### 1. URL 중복 문제 ✅ FIXED
**문제**: iframe src에 URL이 중복되어 나타남
```
http://localhost:9980http://localhost:9980/browser/0b27e85/cool.html
```

**원인**: `discovery.action_url`이 이미 전체 URL을 반환하는데 `collaboraHost`를 다시 붙임

**해결**: `/Users/kevin/excel-unified/rails-app/app/javascript/services/collaboraService.js`
```javascript
// action_url이 이미 전체 URL인지 확인
if (actionUrl.startsWith('http')) {
  fullUrl = actionUrl  // 그대로 사용
} else {
  fullUrl = `${collaboraHost}${actionUrl}`  // 경로만 있으면 호스트 추가
}
```

### 2. 읽기 전용 권한 문제 ✅ FIXED
**문제**: `permission=readonly`로 설정되어 편집이 불가능

**원인**: Vue 컴포넌트에서 권한 속성명이 잘못됨 (camelCase vs snake_case)

**해결**: `/Users/kevin/excel-unified/rails-app/app/javascript/domains/excel_ai/components/ExcelCollaboraViewer.vue`
```javascript
// Before (잘못됨):
{
  canWrite: props.editMode,
  canExport: true,
  canPrint: true
}

// After (수정됨):
{
  can_write: props.editMode,
  can_export: true,
  can_print: true
}
```

## 전체 수정 사항 요약

1. **CollaboraDiscoveryService**: 대소문자 구분 문제 수정 ('Calc' → 'calc')
2. **CollaboraController**: 'view' → 'edit' 액션으로 변경
3. **collaboraService.js**: 
   - URL 중복 방지 로직 추가
   - 에러 처리 개선
4. **ExcelCollaboraViewer.vue**: 권한 속성명 수정 (camelCase → snake_case)

## 최종 테스트 결과

✅ Discovery endpoint가 올바른 action URL 반환
✅ WOPI 토큰이 올바른 편집 권한으로 생성
✅ iframe src URL이 정확하게 생성됨
✅ 편집 모드 토글이 정상 작동

## 사용 방법

1. http://localhost:3000/ai/excel/analysis/2 접속
2. Excel 파일이 정상적으로 로드됨
3. "편집 모드" 버튼 클릭하여 편집 활성화
4. 셀 편집 및 저장 가능

---

**상태**: ✅ 완전히 해결됨  
**날짜**: 2025-08-02