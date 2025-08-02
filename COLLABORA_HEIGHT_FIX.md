# Collabora 뷰어 세로 크기 100% 문제 해결 ✅

## 문제
Collabora 뷰어가 상위 컨테이너 내에서 세로 방향으로 100% 크기로 표시되지 않음

## 원인
1. CSS 컨테이너 체인에서 높이가 명시적으로 설정되지 않은 부분이 있었음
2. `third-party-container` 클래스에 높이 관련 스타일이 누락됨
3. `excel-viewer-container` 클래스에 스타일 정의가 없었음
4. 로딩/에러 상태 표시 요소들이 `min-height: 400px`로 고정되어 있었음

## 수정 사항

### 1. third-party-container 스타일 개선
```css
.third-party-container {
  /* 기존 스타일 유지 */
  isolation: isolate;
  contain: layout style paint;
  pointer-events: auto;
  
  /* 높이 100% 보장 추가 */
  height: 100%;
  display: flex;
  flex-direction: column;
}
```

### 2. excel-viewer-container 스타일 추가
```css
.excel-viewer-container {
  height: 100%;
  display: flex;
  flex-direction: column;
}
```

### 3. 로딩/에러 상태 높이 수정
```css
.workbook-loading, .workbook-error, .no-workbook-data {
  /* min-height: 400px → height: 100% 변경 */
  height: 100%;
  /* 나머지 스타일 유지 */
}
```

## 컨테이너 구조

```
Right Panel (flex-1)
└── Panel Content (h-full flex flex-col)
    └── Excel Grid (flex-1 relative)
        └── third-party-container (h-full w-full + CSS height: 100%)
            └── excel-viewer-container (h-full + CSS height: 100%)
                └── relative h-full
                    └── ExcelCollaboraViewer (h-full w-full)
                        └── iframe (w-full h-full)
```

## 결과
- Collabora 뷰어가 이제 상위 컨테이너의 전체 높이를 차지함
- Split 모드에서 패널 헤더를 제외한 나머지 공간을 모두 활용
- 로딩/에러 상태도 전체 높이로 표시됨

---

**상태**: ✅ 해결됨  
**날짜**: 2025-08-02