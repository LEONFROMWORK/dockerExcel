#!/usr/bin/env python3
"""
차트/그래프 OCR 서비스
Chart/Graph OCR Detection Service

재무 차트에서 데이터 포인트, 범례, 축 레이블을 자동으로 추출하는 서비스
"""

import cv2
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
import logging
from dataclasses import dataclass
import json
from PIL import Image
import pytesseract
# import matplotlib.pyplot as plt  # 아키텍처 호환성 문제로 주석 처리
# from sklearn.cluster import DBSCAN, KMeans  # 당분간 사용하지 않음
import math

logger = logging.getLogger(__name__)


@dataclass
class DataPoint:
    """차트 데이터 포인트"""
    x: float
    y: float
    value: Optional[float] = None
    label: str = ""
    confidence: float = 0.0


@dataclass
class ChartAxis:
    """차트 축 정보"""
    type: str  # 'x' or 'y'
    min_value: float
    max_value: float
    labels: List[str]
    title: str = ""
    scale_type: str = "linear"  # 'linear' or 'log'


@dataclass
class ChartLegend:
    """차트 범례 정보"""
    items: List[Dict[str, Any]]
    position: str  # 'top', 'bottom', 'left', 'right'
    x: int
    y: int
    width: int
    height: int


@dataclass
class ChartInfo:
    """차트 정보"""
    chart_type: str  # 'line', 'bar', 'pie', 'scatter', 'area'
    title: str
    x_axis: Optional[ChartAxis]
    y_axis: Optional[ChartAxis]
    legend: Optional[ChartLegend]
    data_points: List[DataPoint]
    confidence: float
    x: int
    y: int
    width: int
    height: int


class ChartDetector:
    """차트/그래프 감지 및 데이터 추출"""
    
    def __init__(self):
        """초기화"""
        self.min_chart_size = 100
        self.color_tolerance = 30
        self.line_detection_threshold = 50
        
        logger.info("ChartDetector 초기화 완료")
    
    def detect_charts(self, image: np.ndarray) -> List[ChartInfo]:
        """이미지에서 차트 감지"""
        try:
            # 1. 차트 영역 감지
            chart_regions = self._find_chart_regions(image)
            
            # 2. 각 영역에서 차트 분석
            charts = []
            for i, region in enumerate(chart_regions):
                chart_info = self._analyze_chart(image, region, i)
                if chart_info:
                    charts.append(chart_info)
            
            logger.info(f"감지된 차트 개수: {len(charts)}")
            return charts
            
        except Exception as e:
            logger.error(f"차트 감지 실패: {e}")
            return []
    
    def _find_chart_regions(self, image: np.ndarray) -> List[Dict]:
        """차트 영역 찾기"""
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # 에지 검출
            edges = cv2.Canny(gray, 50, 150, apertureSize=3)
            
            # 컨투어 찾기
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            chart_regions = []
            
            for contour in contours:
                # 사각형으로 근사
                x, y, w, h = cv2.boundingRect(contour)
                
                # 차트 크기 조건 체크
                if (w > self.min_chart_size and h > self.min_chart_size and
                    w < image.shape[1] * 0.9 and h < image.shape[0] * 0.9):
                    
                    # 영역의 복잡도 체크 (선이 많으면 차트일 가능성 높음)
                    roi = edges[y:y+h, x:x+w]
                    line_density = np.sum(roi > 0) / (w * h)
                    
                    if line_density > 0.01:  # 최소 1% 이상 선이 있어야 함
                        chart_regions.append({
                            'x': x, 'y': y, 'width': w, 'height': h,
                            'line_density': line_density
                        })
            
            # 선 밀도 기준으로 정렬 (높은 순)
            chart_regions.sort(key=lambda x: x['line_density'], reverse=True)
            
            return chart_regions[:5]  # 최대 5개 차트만 처리
            
        except Exception as e:
            logger.error(f"차트 영역 찾기 실패: {e}")
            return []
    
    def _analyze_chart(self, image: np.ndarray, region: Dict, chart_id: int) -> Optional[ChartInfo]:
        """개별 차트 분석"""
        try:
            x, y, w, h = region['x'], region['y'], region['width'], region['height']
            
            # 차트 영역 추출
            chart_image = image[y:y+h, x:x+w]
            
            # 차트 타입 감지
            chart_type = self._detect_chart_type(chart_image)
            
            # 제목 추출
            title = self._extract_chart_title(image, x, y, w, h)
            
            # 축 정보 추출
            x_axis, y_axis = self._extract_axes_info(chart_image)
            
            # 범례 추출
            legend = self._extract_legend(chart_image)
            
            # 데이터 포인트 추출
            data_points = self._extract_data_points(chart_image, chart_type, x_axis, y_axis)
            
            # 신뢰도 계산
            confidence = self._calculate_chart_confidence(chart_type, x_axis, y_axis, data_points)
            
            return ChartInfo(
                chart_type=chart_type,
                title=title,
                x_axis=x_axis,
                y_axis=y_axis,
                legend=legend,
                data_points=data_points,
                confidence=confidence,
                x=x, y=y, width=w, height=h
            )
            
        except Exception as e:
            logger.error(f"차트 분석 실패: {e}")
            return None
    
    def _detect_chart_type(self, chart_image: np.ndarray) -> str:
        """차트 타입 감지"""
        try:
            gray = cv2.cvtColor(chart_image, cv2.COLOR_BGR2GRAY)
            
            # 선 감지
            lines = cv2.HoughLinesP(
                cv2.Canny(gray, 50, 150),
                1, np.pi/180, threshold=50,
                minLineLength=30, maxLineGap=10
            )
            
            # 원형 감지 (파이 차트용)
            circles = cv2.HoughCircles(
                gray, cv2.HOUGH_GRADIENT, 1, 20,
                param1=50, param2=30, minRadius=20, maxRadius=100
            )
            
            # 사각형 감지 (바 차트용)
            contours, _ = cv2.findContours(
                cv2.Canny(gray, 50, 150), 
                cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            
            rectangles = 0
            for contour in contours:
                approx = cv2.approxPolyDP(contour, 0.02 * cv2.arcLength(contour, True), True)
                if len(approx) == 4:  # 사각형
                    rectangles += 1
            
            # 판단 로직
            if circles is not None and len(circles[0]) > 0:
                return "pie"
            elif rectangles > 5:
                return "bar"
            elif lines is not None and len(lines) > 10:
                return "line"
            else:
                return "scatter"
                
        except Exception as e:
            logger.error(f"차트 타입 감지 실패: {e}")
            return "unknown"
    
    def _extract_chart_title(self, image: np.ndarray, x: int, y: int, w: int, h: int) -> str:
        """차트 제목 추출"""
        try:
            # 차트 위쪽 영역에서 제목 찾기
            title_region_height = min(50, y)
            if title_region_height < 20:
                return ""
            
            title_region = image[max(0, y-title_region_height):y, x:x+w]
            
            if title_region.size == 0:
                return ""
            
            # OCR로 텍스트 추출
            pil_image = Image.fromarray(title_region)
            title = pytesseract.image_to_string(
                pil_image, config='--psm 8 -l kor+eng'
            ).strip()
            
            return title
            
        except Exception as e:
            logger.error(f"차트 제목 추출 실패: {e}")
            return ""
    
    def _extract_axes_info(self, chart_image: np.ndarray) -> Tuple[Optional[ChartAxis], Optional[ChartAxis]]:
        """축 정보 추출"""
        try:
            height, width = chart_image.shape[:2]
            
            # X축 정보 (차트 하단)
            x_axis_region = chart_image[int(height*0.8):height, 0:width]
            x_labels = self._extract_axis_labels(x_axis_region, 'horizontal')
            
            x_axis = ChartAxis(
                type='x',
                min_value=0.0,
                max_value=float(len(x_labels)) if x_labels else 1.0,
                labels=x_labels,
                title="",
                scale_type="linear"
            ) if x_labels else None
            
            # Y축 정보 (차트 좌측)
            y_axis_region = chart_image[0:int(height*0.8), 0:int(width*0.2)]
            y_labels = self._extract_axis_labels(y_axis_region, 'vertical')
            
            y_axis = ChartAxis(
                type='y',
                min_value=0.0,
                max_value=self._extract_max_value_from_labels(y_labels),
                labels=y_labels,
                title="",
                scale_type="linear"
            ) if y_labels else None
            
            return x_axis, y_axis
            
        except Exception as e:
            logger.error(f"축 정보 추출 실패: {e}")
            return None, None
    
    def _extract_axis_labels(self, axis_region: np.ndarray, orientation: str) -> List[str]:
        """축 레이블 추출"""
        try:
            if axis_region.size == 0:
                return []
            
            # 이미지 전처리
            gray = cv2.cvtColor(axis_region, cv2.COLOR_BGR2GRAY)
            
            # 텍스트 영역 향상
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            pil_image = Image.fromarray(binary)
            
            # OCR 설정
            if orientation == 'vertical':
                # 세로 텍스트는 PSM 5 사용
                config = '--psm 5 -l kor+eng'
            else:
                # 가로 텍스트는 PSM 6 사용
                config = '--psm 6 -l kor+eng'
            
            text = pytesseract.image_to_string(pil_image, config=config).strip()
            
            # 텍스트를 라벨로 분할
            if text:
                labels = [label.strip() for label in text.split('\n') if label.strip()]
                return labels[:10]  # 최대 10개 라벨만
            
            return []
            
        except Exception as e:
            logger.error(f"축 레이블 추출 실패: {e}")
            return []
    
    def _extract_max_value_from_labels(self, labels: List[str]) -> float:
        """레이블에서 최대값 추출"""
        try:
            max_val = 0.0
            
            for label in labels:
                # 숫자 추출 시도
                import re
                numbers = re.findall(r'[\d,]+(?:\.\d+)?', label.replace(',', ''))
                
                for num_str in numbers:
                    try:
                        num = float(num_str)
                        max_val = max(max_val, num)
                    except ValueError:
                        continue
            
            return max_val if max_val > 0 else 100.0
            
        except Exception as e:
            logger.error(f"최대값 추출 실패: {e}")
            return 100.0
    
    def _extract_legend(self, chart_image: np.ndarray) -> Optional[ChartLegend]:
        """범례 추출"""
        try:
            height, width = chart_image.shape[:2]
            
            # 범례는 보통 차트 오른쪽이나 위쪽에 위치
            # 오른쪽 영역 체크
            right_region = chart_image[0:height, int(width*0.7):width]
            
            if right_region.size > 0:
                legend_text = self._extract_text_from_region(right_region)
                
                if legend_text and len(legend_text) > 2:
                    legend_items = []
                    for item in legend_text[:5]:  # 최대 5개 항목
                        legend_items.append({
                            'label': item,
                            'color': 'unknown',  # 색상 감지는 추후 구현
                            'marker': 'unknown'
                        })
                    
                    return ChartLegend(
                        items=legend_items,
                        position='right',
                        x=int(width*0.7), y=0,
                        width=int(width*0.3), height=height
                    )
            
            return None
            
        except Exception as e:
            logger.error(f"범례 추출 실패: {e}")
            return None
    
    def _extract_text_from_region(self, region: np.ndarray) -> List[str]:
        """영역에서 텍스트 추출"""
        try:
            if region.size == 0:
                return []
            
            pil_image = Image.fromarray(region)
            text = pytesseract.image_to_string(
                pil_image, config='--psm 6 -l kor+eng'
            ).strip()
            
            if text:
                return [line.strip() for line in text.split('\n') if line.strip()]
            
            return []
            
        except Exception as e:
            logger.error(f"텍스트 추출 실패: {e}")
            return []
    
    def _extract_data_points(self, chart_image: np.ndarray, chart_type: str, 
                           x_axis: Optional[ChartAxis], y_axis: Optional[ChartAxis]) -> List[DataPoint]:
        """데이터 포인트 추출"""
        try:
            if chart_type == "line":
                return self._extract_line_data_points(chart_image, x_axis, y_axis)
            elif chart_type == "bar":
                return self._extract_bar_data_points(chart_image, x_axis, y_axis)
            elif chart_type == "pie":
                return self._extract_pie_data_points(chart_image)
            elif chart_type == "scatter":
                return self._extract_scatter_data_points(chart_image, x_axis, y_axis)
            else:
                return []
                
        except Exception as e:
            logger.error(f"데이터 포인트 추출 실패: {e}")
            return []
    
    def _extract_line_data_points(self, chart_image: np.ndarray, 
                                x_axis: Optional[ChartAxis], y_axis: Optional[ChartAxis]) -> List[DataPoint]:
        """라인 차트 데이터 포인트 추출"""
        try:
            gray = cv2.cvtColor(chart_image, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)
            
            # 선 감지
            lines = cv2.HoughLinesP(
                edges, 1, np.pi/180, threshold=30,
                minLineLength=20, maxLineGap=5
            )
            
            data_points = []
            
            if lines is not None:
                # 선의 교점들을 데이터 포인트로 간주
                for i, line in enumerate(lines[:20]):  # 최대 20개 선만 처리
                    x1, y1, x2, y2 = line[0]
                    
                    # 선의 중점을 데이터 포인트로 사용
                    mid_x = (x1 + x2) / 2
                    mid_y = (y1 + y2) / 2
                    
                    # 좌표를 실제 값으로 변환
                    actual_x = self._pixel_to_value(mid_x, chart_image.shape[1], x_axis)
                    actual_y = self._pixel_to_value(chart_image.shape[0] - mid_y, chart_image.shape[0], y_axis)
                    
                    data_points.append(DataPoint(
                        x=actual_x,
                        y=actual_y,
                        value=actual_y,
                        confidence=0.6
                    ))
            
            return data_points[:10]  # 최대 10개 포인트
            
        except Exception as e:
            logger.error(f"라인 차트 데이터 포인트 추출 실패: {e}")
            return []
    
    def _extract_bar_data_points(self, chart_image: np.ndarray, 
                               x_axis: Optional[ChartAxis], y_axis: Optional[ChartAxis]) -> List[DataPoint]:
        """바 차트 데이터 포인트 추출"""
        try:
            gray = cv2.cvtColor(chart_image, cv2.COLOR_BGR2GRAY)
            
            # 사각형 감지
            contours, _ = cv2.findContours(
                cv2.Canny(gray, 50, 150), 
                cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            
            data_points = []
            
            for contour in contours:
                # 사각형으로 근사
                approx = cv2.approxPolyDP(contour, 0.02 * cv2.arcLength(contour, True), True)
                
                if len(approx) == 4:  # 사각형
                    x, y, w, h = cv2.boundingRect(contour)
                    
                    # 최소 크기 체크
                    if w > 10 and h > 10:
                        # 바의 중심과 높이를 데이터 포인트로 사용
                        center_x = x + w / 2
                        bar_height = h
                        
                        # 좌표를 실제 값으로 변환
                        actual_x = self._pixel_to_value(center_x, chart_image.shape[1], x_axis)
                        actual_y = self._pixel_to_value(bar_height, chart_image.shape[0], y_axis)
                        
                        data_points.append(DataPoint(
                            x=actual_x,
                            y=actual_y,
                            value=actual_y,
                            confidence=0.7
                        ))
            
            return data_points[:15]  # 최대 15개 바
            
        except Exception as e:
            logger.error(f"바 차트 데이터 포인트 추출 실패: {e}")
            return []
    
    def _extract_pie_data_points(self, chart_image: np.ndarray) -> List[DataPoint]:
        """파이 차트 데이터 포인트 추출"""
        try:
            gray = cv2.cvtColor(chart_image, cv2.COLOR_BGR2GRAY)
            
            # 원형 감지
            circles = cv2.HoughCircles(
                gray, cv2.HOUGH_GRADIENT, 1, 20,
                param1=50, param2=30, minRadius=20, maxRadius=100
            )
            
            data_points = []
            
            if circles is not None:
                circles = np.round(circles[0, :]).astype("int")
                
                for (x, y, r) in circles[:1]:  # 첫 번째 원만 처리
                    # 색상 기반으로 섹션 분할 (간단한 구현)
                    # 실제로는 더 복잡한 알고리즘 필요
                    
                    # 임시로 4개 섹션으로 가정
                    for i in range(4):
                        angle = i * 90
                        data_points.append(DataPoint(
                            x=float(i),
                            y=25.0,  # 임시 값
                            value=25.0,
                            label=f"Section {i+1}",
                            confidence=0.5
                        ))
            
            return data_points
            
        except Exception as e:
            logger.error(f"파이 차트 데이터 포인트 추출 실패: {e}")
            return []
    
    def _extract_scatter_data_points(self, chart_image: np.ndarray, 
                                   x_axis: Optional[ChartAxis], y_axis: Optional[ChartAxis]) -> List[DataPoint]:
        """산점도 데이터 포인트 추출"""
        try:
            gray = cv2.cvtColor(chart_image, cv2.COLOR_BGR2GRAY)
            
            # 작은 원형 마커 감지
            circles = cv2.HoughCircles(
                gray, cv2.HOUGH_GRADIENT, 1, 10,
                param1=50, param2=15, minRadius=2, maxRadius=10
            )
            
            data_points = []
            
            if circles is not None:
                circles = np.round(circles[0, :]).astype("int")
                
                for (x, y, r) in circles[:20]:  # 최대 20개 포인트
                    # 좌표를 실제 값으로 변환
                    actual_x = self._pixel_to_value(x, chart_image.shape[1], x_axis)
                    actual_y = self._pixel_to_value(chart_image.shape[0] - y, chart_image.shape[0], y_axis)
                    
                    data_points.append(DataPoint(
                        x=actual_x,
                        y=actual_y,
                        value=actual_y,
                        confidence=0.8
                    ))
            
            return data_points
            
        except Exception as e:
            logger.error(f"산점도 데이터 포인트 추출 실패: {e}")
            return []
    
    def _pixel_to_value(self, pixel: float, max_pixel: int, axis: Optional[ChartAxis]) -> float:
        """픽셀 좌표를 실제 값으로 변환"""
        try:
            if axis is None:
                return pixel / max_pixel * 100.0  # 기본 스케일
            
            # 선형 스케일링
            ratio = pixel / max_pixel
            return axis.min_value + (axis.max_value - axis.min_value) * ratio
            
        except Exception as e:
            logger.error(f"픽셀-값 변환 실패: {e}")
            return 0.0
    
    def _calculate_chart_confidence(self, chart_type: str, x_axis: Optional[ChartAxis], 
                                  y_axis: Optional[ChartAxis], data_points: List[DataPoint]) -> float:
        """차트 신뢰도 계산"""
        try:
            confidence = 0.0
            
            # 차트 타입이 감지되면 +0.3
            if chart_type != "unknown":
                confidence += 0.3
            
            # X축이 있으면 +0.2
            if x_axis is not None:
                confidence += 0.2
            
            # Y축이 있으면 +0.2
            if y_axis is not None:
                confidence += 0.2
            
            # 데이터 포인트가 있으면 +0.3
            if data_points:
                confidence += 0.3
            
            return min(confidence, 1.0)
            
        except Exception as e:
            logger.error(f"신뢰도 계산 실패: {e}")
            return 0.0
    
    def visualize_chart_detection(self, image: np.ndarray, charts: List[ChartInfo]) -> np.ndarray:
        """차트 감지 결과 시각화"""
        try:
            result_image = image.copy()
            
            for i, chart in enumerate(charts):
                # 차트 경계 그리기
                cv2.rectangle(result_image, 
                            (chart.x, chart.y), 
                            (chart.x + chart.width, chart.y + chart.height),
                            (0, 255, 0), 3)
                
                # 차트 정보 표시
                info_text = f"Chart {i+1}: {chart.chart_type} ({chart.confidence:.2f})"
                cv2.putText(result_image, info_text, 
                           (chart.x, chart.y - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                
                # 데이터 포인트 표시
                for point in chart.data_points:
                    if hasattr(point, 'pixel_x') and hasattr(point, 'pixel_y'):
                        cv2.circle(result_image, 
                                 (int(point.pixel_x), int(point.pixel_y)), 
                                 3, (255, 0, 0), -1)
            
            return result_image
            
        except Exception as e:
            logger.error(f"시각화 실패: {e}")
            return image
    
    def to_structured_data(self, chart: ChartInfo) -> Dict[str, Any]:
        """차트 정보를 구조화된 데이터로 변환"""
        try:
            return {
                "chart_info": {
                    "type": chart.chart_type,
                    "title": chart.title,
                    "confidence": chart.confidence,
                    "position": {
                        "x": chart.x,
                        "y": chart.y,
                        "width": chart.width,
                        "height": chart.height
                    }
                },
                "axes": {
                    "x_axis": {
                        "min_value": chart.x_axis.min_value if chart.x_axis else 0,
                        "max_value": chart.x_axis.max_value if chart.x_axis else 1,
                        "labels": chart.x_axis.labels if chart.x_axis else [],
                        "title": chart.x_axis.title if chart.x_axis else ""
                    } if chart.x_axis else None,
                    "y_axis": {
                        "min_value": chart.y_axis.min_value if chart.y_axis else 0,
                        "max_value": chart.y_axis.max_value if chart.y_axis else 1,
                        "labels": chart.y_axis.labels if chart.y_axis else [],
                        "title": chart.y_axis.title if chart.y_axis else ""
                    } if chart.y_axis else None
                },
                "legend": {
                    "items": chart.legend.items if chart.legend else [],
                    "position": chart.legend.position if chart.legend else ""
                } if chart.legend else None,
                "data_points": [
                    {
                        "x": point.x,
                        "y": point.y,
                        "value": point.value,
                        "label": point.label,
                        "confidence": point.confidence
                    }
                    for point in chart.data_points
                ],
                "summary": {
                    "total_data_points": len(chart.data_points),
                    "has_title": bool(chart.title),
                    "has_x_axis": chart.x_axis is not None,
                    "has_y_axis": chart.y_axis is not None,
                    "has_legend": chart.legend is not None
                }
            }
            
        except Exception as e:
            logger.error(f"구조화된 데이터 변환 실패: {e}")
            return {}


# 전역 인스턴스
chart_detector = ChartDetector()