"""
알고리즘 최적화 도구
비효율적인 루프, 중복 연산, 불필요한 메모리 할당 개선
"""

import ast
import logging
import time
import functools
from typing import Dict, Any, List, Optional, Set, Tuple, Callable, Union
from dataclasses import dataclass, field
from pathlib import Path
import inspect
import dis
import re
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class CodeIssue:
    """코드 이슈"""
    issue_type: str
    severity: str  # "low", "medium", "high", "critical"
    line_number: int
    function_name: str
    description: str
    current_code: str
    suggested_fix: str
    performance_impact: str
    complexity_reduction: str


@dataclass
class OptimizationResult:
    """최적화 결과"""
    original_execution_time: float
    optimized_execution_time: float
    performance_improvement: float
    memory_reduction: float
    issues_found: List[CodeIssue]
    optimizations_applied: List[str]
    complexity_improvements: Dict[str, str]


class AlgorithmOptimizer:
    """알고리즘 최적화 분석기"""
    
    def __init__(self):
        self.optimization_patterns = self._load_optimization_patterns()
        self.complexity_analyzers = self._load_complexity_analyzers()
        self.memory_analyzers = self._load_memory_analyzers()
        
    def _load_optimization_patterns(self) -> Dict[str, Dict[str, Any]]:
        """최적화 패턴 로드"""
        return {
            "inefficient_loops": {
                "patterns": [
                    r'for\s+\w+\s+in\s+range\(len\([^)]+\)\)',  # for i in range(len(list))
                    r'for\s+\w+\s+in\s+\w+:\s*if\s+',  # 조건부 루프
                    r'while\s+True:.*break',  # 무한 루프 + break
                ],
                "severity": "medium",
                "fixes": {
                    "enumerate_usage": "enumerate() 사용으로 인덱스 접근 최적화",
                    "list_comprehension": "리스트 컴프리헨션으로 변환",
                    "generator_expression": "제너레이터 표현식 사용",
                    "early_termination": "조기 종료 조건 추가"
                }
            },
            
            "redundant_operations": {
                "patterns": [
                    r'(\w+\([^)]*\))\s*==\s*\1',  # 동일한 함수 호출 비교
                    r'len\([^)]+\)\s*>\s*0',  # len() > 0 대신 bool 사용
                    r'str\([^)]+\)\s*\+\s*str\([^)]+\)',  # 문자열 연결 최적화
                ],
                "severity": "low",
                "fixes": {
                    "cache_function_calls": "함수 호출 결과 캐싱",
                    "boolean_evaluation": "직접적인 불린 평가 사용",
                    "string_formatting": "f-string 또는 join() 사용",
                }
            },
            
            "memory_inefficiency": {
                "patterns": [
                    r'\[\]\s*\+\s*\w+',  # 빈 리스트 + 연산
                    r'\w+\s*\+=\s*\[\w+\]',  # 리스트에 단일 원소 추가
                    r'list\(\w+\)',  # 불필요한 list() 변환
                ],
                "severity": "medium",
                "fixes": {
                    "extend_vs_append": "extend() 또는 append() 사용",
                    "in_place_operations": "인플레이스 연산 사용",
                    "avoid_unnecessary_conversion": "불필요한 타입 변환 제거"
                }
            },
            
            "string_operations": {
                "patterns": [
                    r'(\w+\s*\+\s*){3,}',  # 연속된 문자열 연결
                    r'"\s*"\s*\.\s*join',  # 빈 문자열 join
                    r'str\.replace\([^)]+\)\.replace',  # 연속된 replace
                ],
                "severity": "medium",
                "fixes": {
                    "use_join": "join() 메서드 사용",
                    "f_strings": "f-string 사용",
                    "regex_replacement": "정규표현식 사용",
                    "string_template": "Template 클래스 사용"
                }
            },
            
            "data_structure_inefficiency": {
                "patterns": [
                    r'if\s+\w+\s+in\s+\[',  # 리스트에서 멤버십 테스트
                    r'for\s+\w+\s+in\s+\w+\.keys\(\)',  # dict.keys() 순회
                    r'sorted\([^)]+\)\[0\]',  # 최솟값 찾기위한 정렬
                ],
                "severity": "high",
                "fixes": {
                    "use_set": "set 자료구조 사용",
                    "direct_iteration": "직접 딕셔너리 순회",
                    "min_max_functions": "min()/max() 함수 사용",
                    "collections_usage": "collections 모듈 활용"
                }
            }
        }
    
    def _load_complexity_analyzers(self) -> Dict[str, Callable]:
        """복잡도 분석기 로드"""
        return {
            "cyclomatic_complexity": self._calculate_cyclomatic_complexity,
            "nested_loops": self._analyze_nested_loops,
            "function_length": self._analyze_function_length,
            "parameter_count": self._analyze_parameter_count
        }
    
    def _load_memory_analyzers(self) -> Dict[str, Callable]:
        """메모리 분석기 로드"""
        return {
            "large_data_structures": self._analyze_large_data_structures,
            "object_creation": self._analyze_object_creation,
            "memory_leaks": self._analyze_potential_memory_leaks
        }
    
    def analyze_code(self, source_code: str, function_name: str = None) -> List[CodeIssue]:
        """코드 분석 및 이슈 탐지"""
        issues = []
        
        try:
            # AST 파싱
            tree = ast.parse(source_code)
            
            # 패턴 기반 분석
            pattern_issues = self._analyze_patterns(source_code, function_name)
            issues.extend(pattern_issues)
            
            # AST 기반 분석
            ast_issues = self._analyze_ast(tree, function_name)
            issues.extend(ast_issues)
            
            # 복잡도 분석
            complexity_issues = self._analyze_complexity(tree, function_name)
            issues.extend(complexity_issues)
            
            # 메모리 사용 분석
            memory_issues = self._analyze_memory_usage(tree, function_name)
            issues.extend(memory_issues)
            
        except SyntaxError as e:
            logger.error(f"Syntax error in code analysis: {e}")
            issues.append(CodeIssue(
                issue_type="syntax_error",
                severity="critical",
                line_number=e.lineno or 0,
                function_name=function_name or "unknown",
                description=f"구문 오류: {e.msg}",
                current_code="",
                suggested_fix="구문 오류 수정 필요",
                performance_impact="코드 실행 불가",
                complexity_reduction="N/A"
            ))
        
        return issues
    
    def _analyze_patterns(self, source_code: str, function_name: str = None) -> List[CodeIssue]:
        """패턴 기반 분석"""
        issues = []
        lines = source_code.split('\n')
        
        for pattern_type, pattern_info in self.optimization_patterns.items():
            for i, line in enumerate(lines, 1):
                for pattern in pattern_info["patterns"]:
                    if re.search(pattern, line):
                        # 구체적인 수정 제안 생성
                        suggested_fix = self._generate_fix_suggestion(
                            line, pattern_type, pattern_info
                        )
                        
                        issues.append(CodeIssue(
                            issue_type=pattern_type,
                            severity=pattern_info["severity"],
                            line_number=i,
                            function_name=function_name or "global",
                            description=f"{pattern_type} 패턴 감지",
                            current_code=line.strip(),
                            suggested_fix=suggested_fix,
                            performance_impact=self._estimate_performance_impact(pattern_type),
                            complexity_reduction=self._estimate_complexity_reduction(pattern_type)
                        ))
        
        return issues
    
    def _analyze_ast(self, tree: ast.AST, function_name: str = None) -> List[CodeIssue]:
        """AST 기반 구조적 분석"""
        issues = []
        
        class ASTAnalyzer(ast.NodeVisitor):
            def __init__(self):
                self.current_function = None
                self.issues = []
            
            def visit_FunctionDef(self, node):
                old_function = self.current_function
                self.current_function = node.name
                
                # 함수 길이 분석
                if len(node.body) > 50:
                    self.issues.append(CodeIssue(
                        issue_type="long_function",
                        severity="medium",
                        line_number=node.lineno,
                        function_name=node.name,
                        description=f"함수가 너무 깁니다 ({len(node.body)}줄)",
                        current_code=f"def {node.name}(...): # {len(node.body)} lines",
                        suggested_fix="함수를 더 작은 단위로 분할하세요",
                        performance_impact="가독성 및 유지보수성 저하",
                        complexity_reduction="함수 분할로 복잡도 감소"
                    ))
                
                # 매개변수 개수 분석
                if len(node.args.args) > 7:
                    self.issues.append(CodeIssue(
                        issue_type="too_many_parameters",
                        severity="medium",
                        line_number=node.lineno,
                        function_name=node.name,
                        description=f"매개변수가 너무 많습니다 ({len(node.args.args)}개)",
                        current_code=f"def {node.name}({len(node.args.args)} parameters)",
                        suggested_fix="매개변수를 딕셔너리나 클래스로 그룹화하세요",
                        performance_impact="함수 호출 오버헤드 증가",
                        complexity_reduction="매개변수 그룹화로 복잡도 감소"
                    ))
                
                self.generic_visit(node)
                self.current_function = old_function
            
            def visit_For(self, node):
                # 중첩 루프 감지
                for child in ast.walk(node):
                    if isinstance(child, (ast.For, ast.While)) and child != node:
                        self.issues.append(CodeIssue(
                            issue_type="nested_loops",
                            severity="high",
                            line_number=node.lineno,
                            function_name=self.current_function or "global",
                            description="중첩 루프 감지 - O(n²) 복잡도 가능성",
                            current_code="nested for/while loops",
                            suggested_fix="알고리즘 재설계 또는 데이터 구조 변경 검토",
                            performance_impact="시간 복잡도 증가",
                            complexity_reduction="루프 중첩 제거로 O(n) 달성 가능"
                        ))
                        break
                
                self.generic_visit(node)
            
            def visit_ListComp(self, node):
                # 복잡한 리스트 컴프리헨션 감지
                if len(node.generators) > 1:
                    self.issues.append(CodeIssue(
                        issue_type="complex_comprehension",
                        severity="medium",
                        line_number=node.lineno,
                        function_name=self.current_function or "global",
                        description="복잡한 리스트 컴프리헨션",
                        current_code="complex list comprehension",
                        suggested_fix="일반 루프로 변경하여 가독성 향상",
                        performance_impact="가독성 저하",
                        complexity_reduction="명시적 루프로 이해도 향상"
                    ))
                
                self.generic_visit(node)
        
        analyzer = ASTAnalyzer()
        analyzer.visit(tree)
        issues.extend(analyzer.issues)
        
        return issues
    
    def _analyze_complexity(self, tree: ast.AST, function_name: str = None) -> List[CodeIssue]:
        """복잡도 분석"""
        issues = []
        
        for analyzer_name, analyzer_func in self.complexity_analyzers.items():
            try:
                complexity_issues = analyzer_func(tree, function_name)
                issues.extend(complexity_issues)
            except Exception as e:
                logger.error(f"Complexity analysis failed for {analyzer_name}: {e}")
        
        return issues
    
    def _analyze_memory_usage(self, tree: ast.AST, function_name: str = None) -> List[CodeIssue]:
        """메모리 사용 분석"""
        issues = []
        
        for analyzer_name, analyzer_func in self.memory_analyzers.items():
            try:
                memory_issues = analyzer_func(tree, function_name)
                issues.extend(memory_issues)
            except Exception as e:
                logger.error(f"Memory analysis failed for {analyzer_name}: {e}")
        
        return issues
    
    def _calculate_cyclomatic_complexity(self, tree: ast.AST, function_name: str = None) -> List[CodeIssue]:
        """순환 복잡도 계산"""
        issues = []
        
        class ComplexityCalculator(ast.NodeVisitor):
            def __init__(self):
                self.complexity = 1  # 기본 복잡도
                self.current_function = None
            
            def visit_FunctionDef(self, node):
                old_function = self.current_function
                old_complexity = self.complexity
                
                self.current_function = node.name
                self.complexity = 1
                
                self.generic_visit(node)
                
                if self.complexity > 10:
                    issues.append(CodeIssue(
                        issue_type="high_cyclomatic_complexity",
                        severity="high",
                        line_number=node.lineno,
                        function_name=node.name,
                        description=f"순환 복잡도가 높습니다 ({self.complexity})",
                        current_code=f"def {node.name}(...): # complexity: {self.complexity}",
                        suggested_fix="함수를 더 작은 단위로 분할하세요",
                        performance_impact="테스트 및 유지보수 어려움",
                        complexity_reduction=f"복잡도 {self.complexity} → 목표 <10"
                    ))
                
                self.complexity = old_complexity
                self.current_function = old_function
            
            def visit_If(self, node):
                self.complexity += 1
                self.generic_visit(node)
            
            def visit_While(self, node):
                self.complexity += 1
                self.generic_visit(node)
            
            def visit_For(self, node):
                self.complexity += 1
                self.generic_visit(node)
            
            def visit_ExceptHandler(self, node):
                self.complexity += 1
                self.generic_visit(node)
        
        calculator = ComplexityCalculator()
        calculator.visit(tree)
        
        return issues
    
    def _analyze_nested_loops(self, tree: ast.AST, function_name: str = None) -> List[CodeIssue]:
        """중첩 루프 분석"""
        issues = []
        
        class NestedLoopAnalyzer(ast.NodeVisitor):
            def __init__(self):
                self.loop_depth = 0
                self.max_depth = 0
                self.current_function = None
            
            def visit_FunctionDef(self, node):
                old_function = self.current_function
                old_depth = self.loop_depth
                old_max = self.max_depth
                
                self.current_function = node.name
                self.loop_depth = 0
                self.max_depth = 0
                
                self.generic_visit(node)
                
                if self.max_depth > 3:
                    issues.append(CodeIssue(
                        issue_type="deep_nested_loops",
                        severity="critical",
                        line_number=node.lineno,
                        function_name=node.name,
                        description=f"과도한 루프 중첩 (깊이: {self.max_depth})",
                        current_code=f"nested loops depth: {self.max_depth}",
                        suggested_fix="알고리즘 재설계 또는 데이터 구조 변경",
                        performance_impact=f"시간 복잡도 O(n^{self.max_depth})",
                        complexity_reduction="루프 중첩 제거로 성능 대폭 향상"
                    ))
                
                self.loop_depth = old_depth
                self.max_depth = old_max
                self.current_function = old_function
            
            def visit_For(self, node):
                self.loop_depth += 1
                self.max_depth = max(self.max_depth, self.loop_depth)
                self.generic_visit(node)
                self.loop_depth -= 1
            
            def visit_While(self, node):
                self.loop_depth += 1
                self.max_depth = max(self.max_depth, self.loop_depth)
                self.generic_visit(node)
                self.loop_depth -= 1
        
        analyzer = NestedLoopAnalyzer()
        analyzer.visit(tree)
        
        return issues
    
    def _analyze_function_length(self, tree: ast.AST, function_name: str = None) -> List[CodeIssue]:
        """함수 길이 분석"""
        # 이미 _analyze_ast에서 처리됨
        return []
    
    def _analyze_parameter_count(self, tree: ast.AST, function_name: str = None) -> List[CodeIssue]:
        """매개변수 개수 분석"""
        # 이미 _analyze_ast에서 처리됨
        return []
    
    def _analyze_large_data_structures(self, tree: ast.AST, function_name: str = None) -> List[CodeIssue]:
        """대용량 데이터 구조 분석"""
        issues = []
        
        class DataStructureAnalyzer(ast.NodeVisitor):
            def __init__(self):
                self.current_function = None
            
            def visit_FunctionDef(self, node):
                old_function = self.current_function
                self.current_function = node.name
                self.generic_visit(node)
                self.current_function = old_function
            
            def visit_List(self, node):
                if len(node.elts) > 1000:
                    issues.append(CodeIssue(
                        issue_type="large_literal_list",
                        severity="medium",
                        line_number=node.lineno,
                        function_name=self.current_function or "global",
                        description=f"리터럴 리스트가 큽니다 ({len(node.elts)}개 요소)",
                        current_code=f"[...{len(node.elts)} elements...]",
                        suggested_fix="외부 파일에서 로드하거나 제너레이터 사용",
                        performance_impact="메모리 사용량 증가",
                        complexity_reduction="동적 로딩으로 메모리 효율성 향상"
                    ))
                
                self.generic_visit(node)
        
        analyzer = DataStructureAnalyzer()
        analyzer.visit(tree)
        
        return issues
    
    def _analyze_object_creation(self, tree: ast.AST, function_name: str = None) -> List[CodeIssue]:
        """객체 생성 분석"""
        issues = []
        
        class ObjectCreationAnalyzer(ast.NodeVisitor):
            def __init__(self):
                self.current_function = None
                self.object_creations = defaultdict(int)
            
            def visit_FunctionDef(self, node):
                old_function = self.current_function
                old_creations = self.object_creations
                
                self.current_function = node.name
                self.object_creations = defaultdict(int)
                
                self.generic_visit(node)
                
                # 루프 내 객체 생성 감지
                for obj_type, count in self.object_creations.items():
                    if count > 100:
                        issues.append(CodeIssue(
                            issue_type="excessive_object_creation",
                            severity="medium",
                            line_number=node.lineno,
                            function_name=node.name,
                            description=f"과도한 {obj_type} 객체 생성 ({count}회)",
                            current_code=f"multiple {obj_type}() calls",
                            suggested_fix="객체 재사용 또는 팩토리 패턴 사용",
                            performance_impact="가비지 컬렉션 부하 증가",
                            complexity_reduction="객체 풀링으로 성능 향상"
                        ))
                
                self.object_creations = old_creations
                self.current_function = old_function
            
            def visit_Call(self, node):
                if isinstance(node.func, ast.Name):
                    # 빌트인 타입 생성자 호출 감지
                    if node.func.id in ['list', 'dict', 'set', 'tuple']:
                        self.object_creations[node.func.id] += 1
                
                self.generic_visit(node)
        
        analyzer = ObjectCreationAnalyzer()
        analyzer.visit(tree)
        
        return issues
    
    def _analyze_potential_memory_leaks(self, tree: ast.AST, function_name: str = None) -> List[CodeIssue]:
        """잠재적 메모리 누수 분석"""
        issues = []
        
        class MemoryLeakAnalyzer(ast.NodeVisitor):
            def __init__(self):
                self.current_function = None
                self.global_vars = set()
                self.unclosed_resources = []
            
            def visit_FunctionDef(self, node):
                old_function = self.current_function
                self.current_function = node.name
                self.generic_visit(node)
                self.current_function = old_function
            
            def visit_Global(self, node):
                self.global_vars.update(node.names)
                self.generic_visit(node)
            
            def visit_Call(self, node):
                # 파일 열기 등 리소스 사용 감지
                if (isinstance(node.func, ast.Name) and 
                    node.func.id in ['open', 'urllib.request.urlopen']):
                    self.unclosed_resources.append(node.lineno)
                
                self.generic_visit(node)
            
            def visit_With(self, node):
                # with 문으로 감싸진 리소스는 안전
                # 여기서는 unclosed_resources에서 제거하는 로직이 복잡하므로 생략
                self.generic_visit(node)
        
        analyzer = MemoryLeakAnalyzer()
        analyzer.visit(tree)
        
        # 잠재적 메모리 누수 경고
        for line_no in analyzer.unclosed_resources:
            issues.append(CodeIssue(
                issue_type="potential_resource_leak",
                severity="medium",
                line_number=line_no,
                function_name=function_name or "global",
                description="리소스가 명시적으로 닫히지 않을 수 있습니다",
                current_code="resource opening without explicit closing",
                suggested_fix="with 문 사용으로 자동 리소스 관리",
                performance_impact="메모리 누수 위험",
                complexity_reduction="자동 리소스 관리로 안정성 향상"
            ))
        
        return issues
    
    def _generate_fix_suggestion(self, code_line: str, pattern_type: str, 
                                pattern_info: Dict[str, Any]) -> str:
        """수정 제안 생성"""
        fixes = pattern_info.get("fixes", {})
        
        # 패턴별 구체적인 수정 제안
        if pattern_type == "inefficient_loops":
            if "range(len(" in code_line:
                return "enumerate()를 사용하세요: for i, item in enumerate(items):"
            elif "for" in code_line and "if" in code_line:
                return "리스트 컴프리헨션 사용: [item for item in items if condition]"
        
        elif pattern_type == "redundant_operations":
            if "len(" in code_line and "> 0" in code_line:
                return "직접 불린 평가 사용: if items: 대신 if len(items) > 0:"
            elif "str(" in code_line and "+" in code_line:
                return "f-string 사용: f'{var1}{var2}' 대신 str(var1) + str(var2)"
        
        elif pattern_type == "memory_inefficiency":
            if "+=" in code_line and "[" in code_line:
                return "extend() 사용: list.extend([item]) 대신 list += [item]"
        
        # 기본 제안
        first_fix = next(iter(fixes.values()), "코드 최적화 권장")
        return first_fix
    
    def _estimate_performance_impact(self, pattern_type: str) -> str:
        """성능 영향 추정"""
        impact_map = {
            "inefficient_loops": "루프 성능 15-30% 향상 가능",
            "redundant_operations": "중복 연산 제거로 5-15% 향상",
            "memory_inefficiency": "메모리 사용량 10-25% 감소",
            "string_operations": "문자열 처리 20-40% 향상",
            "data_structure_inefficiency": "데이터 접근 속도 50-200% 향상"
        }
        return impact_map.get(pattern_type, "성능 향상 예상")
    
    def _estimate_complexity_reduction(self, pattern_type: str) -> str:
        """복잡도 감소 추정"""
        reduction_map = {
            "inefficient_loops": "시간 복잡도 개선",
            "redundant_operations": "상수 시간 최적화",
            "memory_inefficiency": "공간 복잡도 개선",
            "string_operations": "선형 시간 달성",
            "data_structure_inefficiency": "O(n) → O(1) 또는 O(log n) 가능"
        }
        return reduction_map.get(pattern_type, "복잡도 개선")
    
    def optimize_function(self, func: Callable, test_data: Any = None) -> OptimizationResult:
        """함수 최적화 및 성능 측정"""
        # 함수 소스 코드 추출
        source_code = inspect.getsource(func)
        function_name = func.__name__
        
        # 코드 분석
        issues = self.analyze_code(source_code, function_name)
        
        # 원본 성능 측정
        original_time, original_memory = self._measure_performance(func, test_data)
        
        # 최적화 제안 적용 (실제 코드 수정은 여기서는 시뮬레이션)
        optimizations_applied = self._simulate_optimizations(issues)
        
        # 예상 성능 계산
        estimated_improvement = self._calculate_estimated_improvement(issues)
        estimated_memory_reduction = self._calculate_estimated_memory_reduction(issues)
        
        return OptimizationResult(
            original_execution_time=original_time,
            optimized_execution_time=original_time * (1 - estimated_improvement),
            performance_improvement=estimated_improvement * 100,
            memory_reduction=estimated_memory_reduction * 100,
            issues_found=issues,
            optimizations_applied=optimizations_applied,
            complexity_improvements=self._generate_complexity_improvements(issues)
        )
    
    def _measure_performance(self, func: Callable, test_data: Any = None) -> Tuple[float, float]:
        """성능 측정"""
        import psutil
        import gc
        
        # 가비지 컬렉션 실행
        gc.collect()
        
        # 메모리 사용량 측정 시작
        process = psutil.Process()
        memory_before = process.memory_info().rss / 1024 / 1024  # MB
        
        # 실행 시간 측정
        start_time = time.perf_counter()
        
        try:
            if test_data is not None:
                if isinstance(test_data, (list, tuple)):
                    func(*test_data)
                elif isinstance(test_data, dict):
                    func(**test_data)
                else:
                    func(test_data)
            else:
                func()
        except Exception as e:
            logger.warning(f"Function execution failed during performance measurement: {e}")
        
        end_time = time.perf_counter()
        execution_time = end_time - start_time
        
        # 메모리 사용량 측정 종료
        memory_after = process.memory_info().rss / 1024 / 1024  # MB
        memory_used = memory_after - memory_before
        
        return execution_time, memory_used
    
    def _simulate_optimizations(self, issues: List[CodeIssue]) -> List[str]:
        """최적화 시뮬레이션"""
        optimizations = []
        
        for issue in issues:
            if issue.severity in ["high", "critical"]:
                optimizations.append(f"{issue.issue_type}: {issue.suggested_fix}")
        
        return optimizations
    
    def _calculate_estimated_improvement(self, issues: List[CodeIssue]) -> float:
        """예상 성능 개선도 계산"""
        improvement_factors = {
            "critical": 0.3,
            "high": 0.2,
            "medium": 0.1,
            "low": 0.05
        }
        
        total_improvement = 0.0
        for issue in issues:
            total_improvement += improvement_factors.get(issue.severity, 0.05)
        
        return min(total_improvement, 0.7)  # 최대 70% 개선
    
    def _calculate_estimated_memory_reduction(self, issues: List[CodeIssue]) -> float:
        """예상 메모리 감소율 계산"""
        memory_reduction = 0.0
        
        for issue in issues:
            if "memory" in issue.issue_type:
                if issue.severity == "critical":
                    memory_reduction += 0.25
                elif issue.severity == "high":
                    memory_reduction += 0.15
                elif issue.severity == "medium":
                    memory_reduction += 0.1
        
        return min(memory_reduction, 0.5)  # 최대 50% 감소
    
    def _generate_complexity_improvements(self, issues: List[CodeIssue]) -> Dict[str, str]:
        """복잡도 개선 사항 생성"""
        improvements = {}
        
        for issue in issues:
            if issue.complexity_reduction and issue.complexity_reduction != "N/A":
                improvements[issue.issue_type] = issue.complexity_reduction
        
        return improvements
    
    def generate_optimization_report(self, issues: List[CodeIssue], 
                                   output_path: Path) -> None:
        """최적화 보고서 생성"""
        try:
            # 심각도별 그룹화
            issues_by_severity = defaultdict(list)
            for issue in issues:
                issues_by_severity[issue.severity].append(issue)
            
            report = {
                "analysis_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "total_issues": len(issues),
                "issues_by_severity": {
                    severity: len(issue_list) 
                    for severity, issue_list in issues_by_severity.items()
                },
                "detailed_issues": [
                    {
                        "issue_type": issue.issue_type,
                        "severity": issue.severity,
                        "line_number": issue.line_number,
                        "function_name": issue.function_name,
                        "description": issue.description,
                        "current_code": issue.current_code,
                        "suggested_fix": issue.suggested_fix,
                        "performance_impact": issue.performance_impact,
                        "complexity_reduction": issue.complexity_reduction
                    }
                    for issue in issues
                ],
                "optimization_priorities": self._generate_optimization_priorities(issues),
                "estimated_total_improvement": f"{self._calculate_estimated_improvement(issues) * 100:.1f}%"
            }
            
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            import json
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Optimization report saved to {output_path}")
            
        except Exception as e:
            logger.error(f"Failed to generate optimization report: {e}")
            raise
    
    def _generate_optimization_priorities(self, issues: List[CodeIssue]) -> List[Dict[str, Any]]:
        """최적화 우선순위 생성"""
        # 심각도와 성능 영향을 기준으로 우선순위 계산
        severity_scores = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        
        prioritized_issues = []
        for issue in issues:
            score = severity_scores.get(issue.severity, 1)
            
            # 성능 영향도에 따른 가중치 추가
            if "50%" in issue.performance_impact or "200%" in issue.performance_impact:
                score += 2
            elif "30%" in issue.performance_impact or "40%" in issue.performance_impact:
                score += 1
            
            prioritized_issues.append({
                "issue": issue.description,
                "function": issue.function_name,
                "priority_score": score,
                "suggested_fix": issue.suggested_fix,
                "impact": issue.performance_impact
            })
        
        # 우선순위 순으로 정렬
        prioritized_issues.sort(key=lambda x: x["priority_score"], reverse=True)
        
        return prioritized_issues[:10]  # 상위 10개만 반환


# 전역 최적화기 인스턴스
_global_optimizer: Optional[AlgorithmOptimizer] = None


def get_algorithm_optimizer() -> AlgorithmOptimizer:
    """글로벌 알고리즘 최적화기 가져오기"""
    global _global_optimizer
    if _global_optimizer is None:
        _global_optimizer = AlgorithmOptimizer()
    return _global_optimizer


def optimize_function(func: Callable, test_data: Any = None) -> OptimizationResult:
    """함수 최적화 (편의 함수)"""
    return get_algorithm_optimizer().optimize_function(func, test_data)


def analyze_code_issues(source_code: str, function_name: str = None) -> List[CodeIssue]:
    """코드 이슈 분석 (편의 함수)"""
    return get_algorithm_optimizer().analyze_code(source_code, function_name)