#!/usr/bin/env python3
"""
표 구조 인식 서비스
Table Structure Detection Service

재무제표에서 표 구조를 자동으로 인식하고 셀 단위로 분할하여
구조화된 데이터로 변환하는 서비스
"""

import cv2
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
import logging
from dataclasses import dataclass
import json
from PIL import Image
import pytesseract

logger = logging.getLogger(__name__)


@dataclass
class TableCell:
    """표 셀 정보"""
    row: int
    col: int
    x: int
    y: int
    width: int
    height: int
    text: str = ""
    confidence: float = 0.0
    is_header: bool = False
    is_merged: bool = False
    merged_cols: int = 1
    merged_rows: int = 1


@dataclass
class TableStructure:
    """표 구조 정보"""
    rows: int
    cols: int
    cells: List[TableCell]
    x: int
    y: int
    width: int
    height: int
    confidence: float = 0.0


class TableStructureDetector:
    """표 구조 인식기"""
    
    def __init__(self):
        """초기화"""
        self.min_line_length = 50
        self.max_line_gap = 10
        self.contour_min_area = 100
        self.header_font_size_ratio = 1.2  # 헤더는 일반 셀보다 1.2배 큰 폰트
        
        logger.info("TableStructureDetector 초기화 완료")
    
    def detect_tables(self, image: np.ndarray) -> List[TableStructure]:
        """이미지에서 표 구조 감지"""
        try:
            # 1. 전처리
            processed_image = self._preprocess_image(image)
            
            # 2. 수직/수평 선 감지
            horizontal_lines, vertical_lines = self._detect_lines(processed_image)
            
            # 3. 선 교차점으로 표 영역 감지
            table_regions = self._find_table_regions(horizontal_lines, vertical_lines, image.shape)
            
            # 4. 각 표 영역에서 셀 구조 분석
            tables = []
            for region in table_regions:
                table_structure = self._analyze_table_structure(
                    image, region, horizontal_lines, vertical_lines
                )
                if table_structure:
                    tables.append(table_structure)
            
            logger.info(f"감지된 표 개수: {len(tables)}")
            return tables
            
        except Exception as e:
            logger.error(f"표 구조 감지 실패: {e}")
            return []
    
    def _preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """이미지 전처리"""
        try:
            # 그레이스케일 변환
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image.copy()
            
            # 가우시안 블러로 노이즈 제거
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            
            # 적응형 임계값으로 이진화
            binary = cv2.adaptiveThreshold(
                blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY_INV, 11, 2
            )
            
            return binary
            
        except Exception as e:
            logger.error(f"이미지 전처리 실패: {e}")
            return image
    
    def _detect_lines(self, binary_image: np.ndarray) -> Tuple[List, List]:
        """수직/수평 선 감지"""
        try:
            height, width = binary_image.shape
            
            # 더 작은 커널 사용 (더 민감하게)
            horizontal_kernel_size = max(width // 50, 15)
            vertical_kernel_size = max(height // 50, 15)
            
            # 수평선 감지를 위한 커널
            horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (horizontal_kernel_size, 1))
            horizontal_lines = cv2.morphologyEx(binary_image, cv2.MORPH_OPEN, horizontal_kernel)
            
            # 수직선 감지를 위한 커널
            vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, vertical_kernel_size))
            vertical_lines = cv2.morphologyEx(binary_image, cv2.MORPH_OPEN, vertical_kernel)
            
            # 더 민감한 HoughLinesP 파라미터
            h_lines = cv2.HoughLinesP(
                horizontal_lines, 1, np.pi/180, threshold=30,
                minLineLength=max(width // 10, 30), maxLineGap=20
            )
            
            v_lines = cv2.HoughLinesP(
                vertical_lines, 1, np.pi/180, threshold=30,
                minLineLength=max(height // 10, 30), maxLineGap=20
            )
            
            # Contour 기반 보조 선 감지
            h_contour_lines = self._detect_lines_by_contour(binary_image, 'horizontal')
            v_contour_lines = self._detect_lines_by_contour(binary_image, 'vertical')
            
            # 선 정보 정리
            h_processed = self._process_lines(h_lines, 'horizontal') if h_lines is not None else []
            v_processed = self._process_lines(v_lines, 'vertical') if v_lines is not None else []
            
            # Contour 기반 결과와 병합
            h_processed.extend(h_contour_lines)
            v_processed.extend(v_contour_lines)
            
            # 중복 제거
            h_processed = self._remove_duplicate_lines(h_processed, 'horizontal')
            v_processed = self._remove_duplicate_lines(v_processed, 'vertical')
            
            logger.info(f"감지된 선: 수평 {len(h_processed)}개, 수직 {len(v_processed)}개")
            return h_processed, v_processed
            
        except Exception as e:
            logger.error(f"선 감지 실패: {e}")
            return [], []
    
    def _process_lines(self, lines: np.ndarray, direction: str) -> List[Dict]:
        """선 정보 처리 및 정리"""
        processed_lines = []
        
        for line in lines:
            x1, y1, x2, y2 = line[0]
            
            if direction == 'horizontal':
                # 수평선: y 좌표가 유사한 선들을 그룹화
                y_avg = (y1 + y2) // 2
                x_start = min(x1, x2)
                x_end = max(x1, x2)
                
                processed_lines.append({
                    'type': 'horizontal',
                    'y': y_avg,
                    'x_start': x_start,
                    'x_end': x_end,
                    'length': x_end - x_start
                })
            else:
                # 수직선: x 좌표가 유사한 선들을 그룹화
                x_avg = (x1 + x2) // 2
                y_start = min(y1, y2)
                y_end = max(y1, y2)
                
                processed_lines.append({
                    'type': 'vertical',
                    'x': x_avg,
                    'y_start': y_start,
                    'y_end': y_end,
                    'length': y_end - y_start
                })
        
        return processed_lines
    
    def _detect_lines_by_contour(self, binary_image: np.ndarray, direction: str) -> List[Dict]:
        """Contour 기반 선 감지 (보조 방법)"""
        try:
            # 컨투어 찾기
            contours, _ = cv2.findContours(binary_image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            lines = []
            height, width = binary_image.shape
            
            for contour in contours:
                # 사각형으로 근사
                x, y, w, h = cv2.boundingRect(contour)
                
                if direction == 'horizontal':
                    # 수평선: 너비가 높이보다 훨씬 큰 경우
                    if w > h * 10 and w > width // 10 and h < 10:
                        lines.append({
                            'type': 'horizontal',
                            'y': y + h // 2,
                            'x_start': x,
                            'x_end': x + w,
                            'length': w
                        })
                else:
                    # 수직선: 높이가 너비보다 훨씬 큰 경우
                    if h > w * 10 and h > height // 10 and w < 10:
                        lines.append({
                            'type': 'vertical',
                            'x': x + w // 2,
                            'y_start': y,
                            'y_end': y + h,
                            'length': h
                        })
            
            return lines
            
        except Exception as e:
            logger.error(f"Contour 기반 선 감지 실패: {e}")
            return []
    
    def _remove_duplicate_lines(self, lines: List[Dict], direction: str) -> List[Dict]:
        """중복된 선 제거"""
        if not lines:
            return []
        
        try:
            # 좌표별로 정렬
            if direction == 'horizontal':
                lines.sort(key=lambda x: x['y'])
                threshold = 10  # y 좌표 차이 임계값
                
                unique_lines = []
                for line in lines:
                    # 비슷한 y 좌표의 선이 있는지 확인
                    is_duplicate = False
                    for existing in unique_lines:
                        if abs(line['y'] - existing['y']) < threshold:
                            # 더 긴 선을 유지
                            if line['length'] > existing['length']:
                                unique_lines.remove(existing)
                                unique_lines.append(line)
                            is_duplicate = True
                            break
                    
                    if not is_duplicate:
                        unique_lines.append(line)
                
                return unique_lines
            
            else:  # vertical
                lines.sort(key=lambda x: x['x'])
                threshold = 10  # x 좌표 차이 임계값
                
                unique_lines = []
                for line in lines:
                    # 비슷한 x 좌표의 선이 있는지 확인
                    is_duplicate = False
                    for existing in unique_lines:
                        if abs(line['x'] - existing['x']) < threshold:
                            # 더 긴 선을 유지
                            if line['length'] > existing['length']:
                                unique_lines.remove(existing)
                                unique_lines.append(line)
                            is_duplicate = True
                            break
                    
                    if not is_duplicate:
                        unique_lines.append(line)
                
                return unique_lines
            
        except Exception as e:
            logger.error(f"중복 선 제거 실패: {e}")
            return lines
    
    def _find_table_regions(self, h_lines: List, v_lines: List, image_shape: Tuple) -> List[Dict]:
        """선 교차점을 기반으로 표 영역 찾기"""
        try:
            if not h_lines or not v_lines:
                return []
            
            height, width = image_shape[:2]
            
            # 선들을 좌표별로 정렬
            h_lines_sorted = sorted(h_lines, key=lambda x: x['y'])
            v_lines_sorted = sorted(v_lines, key=lambda x: x['x'])
            
            # 표 영역 후보 찾기
            table_regions = []
            
            # 최소 3개의 수평선과 3개의 수직선이 있어야 표로 인식
            if len(h_lines_sorted) >= 3 and len(v_lines_sorted) >= 3:
                # 가장 큰 표 영역 찾기
                top_y = h_lines_sorted[0]['y']
                bottom_y = h_lines_sorted[-1]['y']
                left_x = v_lines_sorted[0]['x']
                right_x = v_lines_sorted[-1]['x']
                
                # 표 영역이 유효한 크기인지 확인
                table_width = right_x - left_x
                table_height = bottom_y - top_y
                
                if (table_width > 100 and table_height > 100 and 
                    table_width < width * 0.9 and table_height < height * 0.9):
                    
                    table_regions.append({
                        'x': left_x,
                        'y': top_y,
                        'width': table_width,
                        'height': table_height,
                        'h_lines': h_lines_sorted,
                        'v_lines': v_lines_sorted
                    })
            
            return table_regions
            
        except Exception as e:
            logger.error(f"표 영역 찾기 실패: {e}")
            return []
    
    def _analyze_table_structure(self, image: np.ndarray, region: Dict, 
                                h_lines: List, v_lines: List) -> Optional[TableStructure]:
        """표 구조 분석"""
        try:
            x, y, width, height = region['x'], region['y'], region['width'], region['height']
            
            # 표 영역 내의 선들만 필터링
            table_h_lines = [line for line in h_lines 
                           if y <= line['y'] <= y + height]
            table_v_lines = [line for line in v_lines 
                           if x <= line['x'] <= x + width]
            
            # 행/열 개수 계산
            rows = len(table_h_lines) - 1 if len(table_h_lines) > 1 else 1
            cols = len(table_v_lines) - 1 if len(table_v_lines) > 1 else 1
            
            if rows < 1 or cols < 1:
                return None
            
            # 셀 정보 생성
            cells = self._extract_cells(image, region, table_h_lines, table_v_lines, rows, cols)
            
            # 표 구조 객체 생성
            table_structure = TableStructure(
                rows=rows,
                cols=cols,
                cells=cells,
                x=x,
                y=y,
                width=width,
                height=height,
                confidence=0.8  # 기본 신뢰도
            )
            
            # 헤더 감지
            self._detect_headers(table_structure)
            
            return table_structure
            
        except Exception as e:
            logger.error(f"표 구조 분석 실패: {e}")
            return None
    
    def _extract_cells(self, image: np.ndarray, region: Dict, 
                      h_lines: List, v_lines: List, rows: int, cols: int) -> List[TableCell]:
        """셀 정보 추출"""
        cells = []
        
        try:
            # 선들을 좌표별로 정렬
            h_lines_sorted = sorted(h_lines, key=lambda x: x['y'])
            v_lines_sorted = sorted(v_lines, key=lambda x: x['x'])
            
            # 각 셀에 대해 OCR 수행
            for row in range(rows):
                for col in range(cols):
                    # 셀 경계 계산
                    if row < len(h_lines_sorted) - 1 and col < len(v_lines_sorted) - 1:
                        cell_y = h_lines_sorted[row]['y']
                        cell_height = h_lines_sorted[row + 1]['y'] - cell_y
                        cell_x = v_lines_sorted[col]['x']
                        cell_width = v_lines_sorted[col + 1]['x'] - cell_x
                        
                        # 셀 이미지 추출
                        cell_image = image[cell_y:cell_y + cell_height, 
                                         cell_x:cell_x + cell_width]
                        
                        # OCR 수행
                        cell_text, confidence = self._extract_cell_text(cell_image)
                        
                        # 셀 객체 생성
                        cell = TableCell(
                            row=row,
                            col=col,
                            x=cell_x,
                            y=cell_y,
                            width=cell_width,
                            height=cell_height,
                            text=cell_text,
                            confidence=confidence
                        )
                        
                        cells.append(cell)
            
            return cells
            
        except Exception as e:
            logger.error(f"셀 정보 추출 실패: {e}")
            return []
    
    def _extract_cell_text(self, cell_image: np.ndarray) -> Tuple[str, float]:
        """개별 셀에서 텍스트 추출 (다국어 지원)"""
        try:
            if cell_image.size == 0:
                return "", 0.0
            
            # 이미지가 너무 작으면 확대
            if cell_image.shape[0] < 20 or cell_image.shape[1] < 20:
                scale_factor = max(2, 30 // min(cell_image.shape[:2]))
                cell_image = cv2.resize(cell_image, None, fx=scale_factor, fy=scale_factor)
            
            # 이미지 전처리 개선
            cell_image = self._enhance_cell_image(cell_image)
            
            # PIL 이미지로 변환
            pil_image = Image.fromarray(cell_image)
            
            # 다국어 OCR 수행 - 여러 언어 시도
            best_text = ""
            best_confidence = 0.0
            
            # 언어별 OCR 시도
            languages = ['kor+eng', 'eng', 'kor']  # 한국어+영어, 영어, 한국어 순서로 시도
            
            for lang in languages:
                try:
                    config = f'--psm 8 -l {lang}'
                    text = pytesseract.image_to_string(pil_image, config=config).strip()
                    
                    if text:
                        # 신뢰도 데이터 가져오기
                        data = pytesseract.image_to_data(pil_image, config=config, output_type=pytesseract.Output.DICT)
                        confidences = [int(conf) for conf in data['conf'] if int(conf) > 0]
                        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
                        
                        # 최고 신뢰도 결과 선택
                        if avg_confidence > best_confidence:
                            best_text = text
                            best_confidence = avg_confidence
                            
                except Exception as lang_error:
                    logger.debug(f"언어 {lang} OCR 실패: {lang_error}")
                    continue
            
            return best_text, best_confidence / 100.0
            
        except Exception as e:
            logger.error(f"셀 텍스트 추출 실패: {e}")
            return "", 0.0
    
    def _enhance_cell_image(self, cell_image: np.ndarray) -> np.ndarray:
        """셀 이미지 품질 향상"""
        try:
            # 그레이스케일 변환
            if len(cell_image.shape) == 3:
                gray = cv2.cvtColor(cell_image, cv2.COLOR_BGR2GRAY)
            else:
                gray = cell_image.copy()
            
            # 노이즈 제거
            denoised = cv2.fastNlMeansDenoising(gray)
            
            # 대비 향상
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            enhanced = clahe.apply(denoised)
            
            # 이진화
            _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            return binary
            
        except Exception as e:
            logger.error(f"셀 이미지 향상 실패: {e}")
            return cell_image
    
    def _detect_headers(self, table_structure: TableStructure):
        """헤더 셀 감지"""
        try:
            if not table_structure.cells:
                return
            
            # 첫 번째 행을 헤더로 가정
            first_row_cells = [cell for cell in table_structure.cells if cell.row == 0]
            
            for cell in first_row_cells:
                # 헤더 판단 기준
                is_header = False
                
                # 1. 텍스트가 있고 비어있지 않음
                if cell.text and cell.text.strip():
                    is_header = True
                
                # 2. 첫 번째 행
                if cell.row == 0:
                    is_header = True
                
                # 3. 숫자가 아닌 텍스트 (재무 항목명)
                if cell.text and not cell.text.replace(',', '').replace('.', '').isdigit():
                    is_header = True
                
                cell.is_header = is_header
            
            # 첫 번째 열도 헤더일 가능성 체크
            first_col_cells = [cell for cell in table_structure.cells if cell.col == 0]
            
            for cell in first_col_cells:
                if cell.text and not cell.text.replace(',', '').replace('.', '').isdigit():
                    cell.is_header = True
            
        except Exception as e:
            logger.error(f"헤더 감지 실패: {e}")
    
    def detect_merged_cells(self, table_structure: TableStructure) -> TableStructure:
        """병합된 셀 감지"""
        try:
            # 현재는 단순히 빈 셀들을 체크
            # 추후 더 정교한 알고리즘으로 개선 가능
            
            for cell in table_structure.cells:
                # 빈 셀이고 주변 셀과 경계가 없으면 병합된 셀일 가능성
                if not cell.text.strip():
                    # 주변 셀들과 비교하여 병합 여부 판단
                    # (현재는 기본 구현)
                    pass
            
            return table_structure
            
        except Exception as e:
            logger.error(f"병합 셀 감지 실패: {e}")
            return table_structure
    
    def to_structured_data(self, table_structure: TableStructure) -> Dict[str, Any]:
        """표 구조를 구조화된 데이터로 변환"""
        try:
            # 헤더 추출
            headers = []
            header_cells = [cell for cell in table_structure.cells if cell.is_header and cell.row == 0]
            header_cells.sort(key=lambda x: x.col)
            
            for cell in header_cells:
                headers.append(cell.text)
            
            # 데이터 행 추출
            data_rows = []
            
            for row in range(1, table_structure.rows):  # 첫 번째 행은 헤더이므로 제외
                row_cells = [cell for cell in table_structure.cells if cell.row == row]
                row_cells.sort(key=lambda x: x.col)
                
                row_data = []
                for cell in row_cells:
                    row_data.append({
                        'text': cell.text,
                        'confidence': cell.confidence,
                        'is_numeric': self._is_numeric(cell.text)
                    })
                
                data_rows.append(row_data)
            
            return {
                'table_info': {
                    'rows': table_structure.rows,
                    'cols': table_structure.cols,
                    'x': table_structure.x,
                    'y': table_structure.y,
                    'width': table_structure.width,
                    'height': table_structure.height,
                    'confidence': table_structure.confidence
                },
                'headers': headers,
                'data': data_rows,
                'cells': [
                    {
                        'row': cell.row,
                        'col': cell.col,
                        'text': cell.text,
                        'confidence': cell.confidence,
                        'is_header': cell.is_header,
                        'x': cell.x,
                        'y': cell.y,
                        'width': cell.width,
                        'height': cell.height
                    }
                    for cell in table_structure.cells
                ]
            }
            
        except Exception as e:
            logger.error(f"구조화된 데이터 변환 실패: {e}")
            return {}
    
    def _is_numeric(self, text: str) -> bool:
        """텍스트가 숫자인지 판단"""
        if not text:
            return False
        
        # 쉼표, 소수점, 괄호, 퍼센트 기호 제거 후 숫자 판단
        cleaned = text.replace(',', '').replace('.', '').replace('(', '').replace(')', '').replace('%', '').strip()
        
        try:
            float(cleaned)
            return True
        except ValueError:
            return False
    
    def visualize_table_detection(self, image: np.ndarray, tables: List[TableStructure]) -> np.ndarray:
        """표 감지 결과 시각화"""
        try:
            result_image = image.copy()
            
            for i, table in enumerate(tables):
                # 표 경계 그리기
                cv2.rectangle(result_image, 
                            (table.x, table.y), 
                            (table.x + table.width, table.y + table.height),
                            (0, 255, 0), 2)
                
                # 표 번호 표시
                cv2.putText(result_image, f'Table {i+1}', 
                           (table.x, table.y - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                
                # 셀 경계 그리기
                for cell in table.cells:
                    color = (255, 0, 0) if cell.is_header else (0, 0, 255)
                    cv2.rectangle(result_image,
                                (cell.x, cell.y),
                                (cell.x + cell.width, cell.y + cell.height),
                                color, 1)
            
            return result_image
            
        except Exception as e:
            logger.error(f"시각화 실패: {e}")
            return image


# 전역 인스턴스
table_detector = TableStructureDetector()