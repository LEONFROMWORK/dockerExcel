"""
Excel 수식 분석 API 엔드포인트
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from typing import Dict, Any, List, Optional
import tempfile
import os
import logging
from datetime import datetime
import json

from app.services.analysis import FormulaAnalyzer, FormulaComplexity
from app.services.detection.integrated_error_detector import IntegratedErrorDetector
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

# 서비스 인스턴스
formula_analyzer = FormulaAnalyzer()
error_detector = IntegratedErrorDetector()


@router.post("/analyze-formulas")
async def analyze_excel_formulas(
    file: UploadFile = File(...),
    include_dependencies: bool = Query(True, description="의존성 그래프 포함"),
    include_suggestions: bool = Query(True, description="최적화 제안 포함"),
    complexity_threshold: str = Query("all", description="분석할 복잡도 임계값"),
    session_id: Optional[str] = Query(None, description="WebSocket 세션 ID")
) -> Dict[str, Any]:
    """
    Excel 파일의 모든 수식을 분석
    
    - 수식 복잡도 평가
    - 함수 사용 패턴 분석
    - 의존성 관계 파악
    - 성능 영향 평가
    - 최적화 제안 생성
    """
    
    # 파일 검증
    if not file.filename.lower().endswith(('.xlsx', '.xls')):
        raise HTTPException(
            status_code=400,
            detail="Excel 파일(.xlsx, .xls)만 업로드 가능합니다"
        )
    
    # 임시 파일로 저장
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        logger.info(f"수식 분석 시작: {file.filename}")
        
        # 워크북 분석
        analysis_result = await formula_analyzer.analyze_workbook(tmp_path)
        
        # 응답 데이터 구성
        response_data = {
            "status": "success",
            "filename": file.filename,
            "summary": {
                "total_formulas": analysis_result.total_formulas,
                "complexity_distribution": {
                    k.value: v for k, v in analysis_result.complexity_distribution.items()
                },
                "most_used_functions": [
                    {"function": func, "count": count}
                    for func, count in analysis_result.most_used_functions
                ],
                "volatile_formula_count": len(analysis_result.volatile_formulas),
                "array_formula_count": len(analysis_result.array_formulas),
                "external_reference_count": len(analysis_result.external_references)
            },
            "performance": {
                "bottlenecks": analysis_result.performance_bottlenecks[:10],
                "high_impact_formulas": len([
                    b for b in analysis_result.performance_bottlenecks 
                    if b['impact'] == 'high'
                ])
            },
            "timestamp": datetime.now().isoformat()
        }
        
        # 의존성 그래프 정보
        if include_dependencies and analysis_result.dependency_graph.number_of_nodes() > 0:
            response_data["dependencies"] = {
                "total_nodes": analysis_result.dependency_graph.number_of_nodes(),
                "total_edges": analysis_result.dependency_graph.number_of_edges(),
                "critical_paths": [
                    {
                        "path": path,
                        "length": len(path)
                    }
                    for path in analysis_result.critical_paths[:5]
                ]
            }
        
        # 최적화 제안
        if include_suggestions:
            response_data["optimization"] = {
                "opportunities": analysis_result.optimization_opportunities,
                "total_opportunities": len(analysis_result.optimization_opportunities)
            }
        
        # 특수 수식 목록
        response_data["special_formulas"] = {
            "volatile": analysis_result.volatile_formulas[:10],
            "array": analysis_result.array_formulas[:10],
            "external": analysis_result.external_references[:10]
        }
        
        return response_data
        
    except Exception as e:
        logger.error(f"수식 분석 중 오류: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"수식 분석 중 오류가 발생했습니다: {str(e)}"
        )
    finally:
        # 임시 파일 정리
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.post("/analyze-single-formula")
async def analyze_single_formula(
    formula: str = Query(..., description="분석할 수식 (= 포함)"),
    cell_reference: str = Query("A1", description="셀 참조"),
    sheet_name: str = Query("Sheet1", description="시트 이름")
) -> Dict[str, Any]:
    """
    단일 수식 분석
    """
    
    if not formula.startswith('='):
        formula = '=' + formula
    
    try:
        # 가상 워크시트 컨텍스트에서 분석
        analysis = await formula_analyzer._analyze_formula(
            formula=formula,
            cell=cell_reference,
            sheet=sheet_name,
            worksheet=None  # 단일 수식 분석이므로 워크시트 불필요
        )
        
        return {
            "status": "success",
            "formula": formula,
            "analysis": {
                "complexity": analysis.complexity.value,
                "complexity_score": analysis.complexity_score,
                "functions_used": analysis.functions_used,
                "function_categories": [cat.value for cat in analysis.function_categories],
                "referenced_cells": analysis.referenced_cells,
                "referenced_ranges": analysis.referenced_ranges,
                "is_array_formula": analysis.is_array_formula,
                "is_volatile": analysis.is_volatile,
                "performance_impact": analysis.performance_impact,
                "suggestions": analysis.suggestions
            }
        }
        
    except Exception as e:
        logger.error(f"수식 분석 오류: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"수식 분석 중 오류가 발생했습니다: {str(e)}"
        )


@router.post("/optimize-formulas")
async def optimize_formulas(
    file: UploadFile = File(...),
    optimization_level: str = Query("moderate", regex="^(conservative|moderate|aggressive)$"),
    target_areas: Optional[str] = Query(None, description="최적화 대상 영역 (쉼표 구분)")
) -> Dict[str, Any]:
    """
    수식 최적화 제안 및 적용
    """
    
    # 파일 분석
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        # 수식 분석
        analysis_result = await formula_analyzer.analyze_workbook(tmp_path)
        
        # 최적화 제안 생성
        optimization_plan = []
        
        # 1. VLOOKUP 최적화
        vlookup_optimizations = _generate_vlookup_optimizations(analysis_result)
        optimization_plan.extend(vlookup_optimizations)
        
        # 2. 휘발성 함수 최적화
        volatile_optimizations = _generate_volatile_optimizations(
            analysis_result,
            optimization_level
        )
        optimization_plan.extend(volatile_optimizations)
        
        # 3. 배열 수식 최적화
        array_optimizations = _generate_array_optimizations(analysis_result)
        optimization_plan.extend(array_optimizations)
        
        # 4. 중복 계산 최적화
        duplicate_optimizations = _generate_duplicate_optimizations(analysis_result)
        optimization_plan.extend(duplicate_optimizations)
        
        # 예상 개선 효과 계산
        estimated_improvement = _calculate_improvement_estimate(optimization_plan)
        
        return {
            "status": "success",
            "filename": file.filename,
            "current_state": {
                "total_formulas": analysis_result.total_formulas,
                "high_impact_count": len([
                    b for b in analysis_result.performance_bottlenecks 
                    if b['impact'] == 'high'
                ]),
                "volatile_count": len(analysis_result.volatile_formulas)
            },
            "optimization_plan": optimization_plan[:20],  # 상위 20개
            "estimated_improvement": estimated_improvement,
            "optimization_level": optimization_level,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"수식 최적화 중 오류: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"수식 최적화 중 오류가 발생했습니다: {str(e)}"
        )
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.get("/formula-best-practices")
async def get_formula_best_practices() -> Dict[str, Any]:
    """
    Excel 수식 작성 모범 사례 가이드
    """
    
    return {
        "best_practices": [
            {
                "category": "성능",
                "practices": [
                    {
                        "title": "휘발성 함수 최소화",
                        "description": "NOW(), TODAY(), RAND() 등은 재계산마다 실행되므로 사용 최소화",
                        "example": "대신 정적 날짜 사용 또는 VBA로 업데이트"
                    },
                    {
                        "title": "전체 열/행 참조 피하기",
                        "description": "A:A 대신 A1:A1000처럼 구체적 범위 지정",
                        "example": "=SUM(A1:A1000) instead of =SUM(A:A)"
                    },
                    {
                        "title": "VLOOKUP 대신 INDEX/MATCH",
                        "description": "더 빠르고 유연한 조회 가능",
                        "example": "=INDEX(B:B,MATCH(E1,A:A,0))"
                    }
                ]
            },
            {
                "category": "가독성",
                "practices": [
                    {
                        "title": "명명된 범위 사용",
                        "description": "셀 참조 대신 의미 있는 이름 사용",
                        "example": "=SUM(Sales_2023) instead of =SUM(B2:B365)"
                    },
                    {
                        "title": "복잡한 수식 분할",
                        "description": "중간 계산을 별도 셀에 저장",
                        "example": "여러 단계로 나누어 각 단계별 검증 가능"
                    },
                    {
                        "title": "주석 추가",
                        "description": "복잡한 수식에는 셀 주석으로 설명 추가",
                        "example": "수식의 목적과 로직 설명"
                    }
                ]
            },
            {
                "category": "오류 처리",
                "practices": [
                    {
                        "title": "IFERROR 사용",
                        "description": "오류 발생 시 대체 값 표시",
                        "example": "=IFERROR(A1/B1, 0)"
                    },
                    {
                        "title": "데이터 유효성 검사",
                        "description": "입력 값 제한으로 오류 예방",
                        "example": "드롭다운 목록, 숫자 범위 제한"
                    },
                    {
                        "title": "조건부 계산",
                        "description": "0으로 나누기 등 예외 상황 처리",
                        "example": "=IF(B1=0, \"\", A1/B1)"
                    }
                ]
            }
        ],
        "common_mistakes": [
            {
                "mistake": "순환 참조",
                "impact": "계산 불가 또는 무한 루프",
                "solution": "의존성 체인 확인 및 재설계"
            },
            {
                "mistake": "하드코딩된 값",
                "impact": "유지보수 어려움",
                "solution": "상수는 별도 셀에 저장하고 참조"
            },
            {
                "mistake": "과도한 중첩",
                "impact": "가독성 저하 및 디버깅 어려움",
                "solution": "Helper 열 사용 또는 사용자 정의 함수"
            }
        ],
        "optimization_checklist": [
            "휘발성 함수 사용 검토",
            "불필요한 배열 수식 제거",
            "범위 참조 최적화",
            "중복 계산 제거",
            "조건부 서식 규칙 단순화",
            "외부 링크 최소화",
            "수식 대신 값 붙여넣기 고려"
        ]
    }


@router.post("/dependency-analysis")
async def analyze_formula_dependencies(
    file: UploadFile = File(...),
    target_cell: Optional[str] = Query(None, description="특정 셀의 의존성만 분석"),
    max_depth: int = Query(10, description="최대 의존성 깊이")
) -> Dict[str, Any]:
    """
    수식 의존성 관계 분석
    """
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        # 워크북 분석
        analysis_result = await formula_analyzer.analyze_workbook(tmp_path)
        
        dependency_info = {
            "total_nodes": analysis_result.dependency_graph.number_of_nodes(),
            "total_edges": analysis_result.dependency_graph.number_of_edges(),
            "is_acyclic": nx.is_directed_acyclic_graph(analysis_result.dependency_graph)
        }
        
        # 특정 셀의 의존성 분석
        if target_cell:
            if target_cell in analysis_result.dependency_graph:
                # 선행 셀 (이 셀이 의존하는 셀들)
                predecessors = list(analysis_result.dependency_graph.predecessors(target_cell))
                
                # 후행 셀 (이 셀에 의존하는 셀들)
                successors = list(analysis_result.dependency_graph.successors(target_cell))
                
                dependency_info["target_cell"] = {
                    "cell": target_cell,
                    "depends_on": predecessors[:20],
                    "dependents": successors[:20],
                    "dependency_chain_length": len(nx.ancestors(
                        analysis_result.dependency_graph, target_cell
                    ))
                }
        
        # 중요 노드 식별
        if analysis_result.dependency_graph.number_of_nodes() > 0:
            # 가장 많은 의존성을 가진 노드
            node_degrees = dict(analysis_result.dependency_graph.degree())
            top_nodes = sorted(node_degrees.items(), key=lambda x: x[1], reverse=True)[:10]
            
            dependency_info["key_nodes"] = [
                {
                    "cell": node,
                    "total_connections": degree,
                    "in_degree": analysis_result.dependency_graph.in_degree(node),
                    "out_degree": analysis_result.dependency_graph.out_degree(node)
                }
                for node, degree in top_nodes
            ]
        
        # 순환 참조 검출
        try:
            cycles = list(nx.simple_cycles(analysis_result.dependency_graph))
            dependency_info["circular_references"] = [
                {
                    "cycle": cycle,
                    "length": len(cycle)
                }
                for cycle in cycles[:5]
            ]
        except:
            dependency_info["circular_references"] = []
        
        return {
            "status": "success",
            "filename": file.filename,
            "dependency_analysis": dependency_info,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"의존성 분석 중 오류: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"의존성 분석 중 오류가 발생했습니다: {str(e)}"
        )
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


# 헬퍼 함수들
def _generate_vlookup_optimizations(analysis_result) -> List[Dict[str, Any]]:
    """VLOOKUP 최적화 제안 생성"""
    optimizations = []
    
    for opp in analysis_result.optimization_opportunities:
        if opp['type'] == 'vlookup_optimization':
            optimizations.append({
                'type': 'replace_vlookup',
                'description': 'VLOOKUP을 INDEX/MATCH로 교체',
                'affected_cells': opp.get('cells', []),
                'expected_improvement': '20-30% 조회 성능 향상',
                'priority': 'high',
                'difficulty': 'medium'
            })
    
    return optimizations


def _generate_volatile_optimizations(analysis_result, level: str) -> List[Dict[str, Any]]:
    """휘발성 함수 최적화 제안 생성"""
    optimizations = []
    
    if len(analysis_result.volatile_formulas) > 0:
        if level in ['moderate', 'aggressive']:
            optimizations.append({
                'type': 'reduce_volatile',
                'description': '휘발성 함수를 정적 값 또는 VBA로 대체',
                'affected_cells': analysis_result.volatile_formulas[:10],
                'expected_improvement': '계산 빈도 50% 이상 감소',
                'priority': 'high',
                'difficulty': 'low'
            })
    
    return optimizations


def _generate_array_optimizations(analysis_result) -> List[Dict[str, Any]]:
    """배열 수식 최적화 제안 생성"""
    optimizations = []
    
    if len(analysis_result.array_formulas) > 5:
        optimizations.append({
            'type': 'optimize_arrays',
            'description': '배열 수식을 일반 수식으로 변환',
            'affected_cells': analysis_result.array_formulas[:5],
            'expected_improvement': '메모리 사용량 감소',
            'priority': 'medium',
            'difficulty': 'medium'
        })
    
    return optimizations


def _generate_duplicate_optimizations(analysis_result) -> List[Dict[str, Any]]:
    """중복 계산 최적화 제안 생성"""
    optimizations = []
    
    for opp in analysis_result.optimization_opportunities:
        if opp['type'] == 'duplicate_calculation':
            optimizations.append({
                'type': 'consolidate_calculations',
                'description': '중복 계산을 보조 테이블로 통합',
                'pattern': opp.get('pattern', ''),
                'expected_improvement': '계산 시간 40% 감소',
                'priority': 'medium',
                'difficulty': 'high'
            })
    
    return optimizations


def _calculate_improvement_estimate(optimization_plan: List[Dict[str, Any]]) -> Dict[str, Any]:
    """예상 개선 효과 계산"""
    
    total_score = 0
    for opt in optimization_plan:
        if opt['priority'] == 'high':
            total_score += 3
        elif opt['priority'] == 'medium':
            total_score += 2
        else:
            total_score += 1
    
    # 예상 개선율 (간소화된 계산)
    performance_improvement = min(total_score * 5, 60)  # 최대 60%
    
    return {
        'estimated_performance_gain': f"{performance_improvement}%",
        'calculation_time_reduction': f"{performance_improvement * 0.7:.0f}%",
        'memory_usage_reduction': f"{performance_improvement * 0.3:.0f}%",
        'optimization_count': len(optimization_plan),
        'implementation_effort': 'medium' if len(optimization_plan) > 10 else 'low'
    }


# networkx import 추가
import networkx as nx