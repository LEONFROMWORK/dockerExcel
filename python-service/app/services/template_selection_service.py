"""
지능형 Excel 템플릿 선택 서비스
Intelligent Excel Template Selection Service
"""

import json
import logging
import os
import re
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.decomposition import PCA
import asyncio

from ..services.openai_service import openai_service
from ..services.excel_analyzer import excel_analyzer

logger = logging.getLogger(__name__)


class TemplateSelectionService:
    """지능형 템플릿 선택 서비스"""
    
    def __init__(self):
        self.templates_metadata = self._load_templates_metadata()
        self.templates_metadata_i18n = self._load_i18n_metadata()
        self.vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words='english',
            ngram_range=(1, 2)
        )
        self.user_preferences = {}  # 사용자별 선호도 캐시
        
        # 템플릿 텍스트 벡터화 사전 계산
        self._initialize_template_vectors()
    
    def _load_templates_metadata(self) -> Dict[str, Any]:
        """템플릿 메타데이터 로드"""
        
        try:
            metadata_path = os.path.join(
                os.path.dirname(__file__),
                "../templates/excel/metadata.json"
            )
            
            with open(metadata_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"템플릿 메타데이터 로드 실패: {str(e)}")
            return {"templates": {}, "categories": {}}
    
    def _load_i18n_metadata(self) -> Dict[str, Any]:
        """다국어 템플릿 메타데이터 로드"""
        
        try:
            i18n_metadata_path = os.path.join(
                os.path.dirname(__file__),
                "../templates/excel/metadata_i18n.json"
            )
            
            with open(i18n_metadata_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"다국어 메타데이터 로드 실패: {str(e)}")
            # 기본 메타데이터로 폴백
            return self.templates_metadata
    
    def _initialize_template_vectors(self):
        """템플릿 벡터 사전 계산"""
        
        try:
            templates = self.templates_metadata.get("templates", {})
            
            # 모든 템플릿의 텍스트 특성 추출
            template_texts = []
            self.template_ids = []
            
            for template_id, template in templates.items():
                # 템플릿 설명, 트리거 키워드, 카테고리 등을 결합
                text_features = []
                text_features.extend(template.get("triggers", []))
                text_features.append(template.get("name", ""))
                text_features.append(template.get("description", ""))
                text_features.extend(template.get("industry_tags", []))
                
                combined_text = " ".join(text_features).lower()
                template_texts.append(combined_text)
                self.template_ids.append(template_id)
            
            # TF-IDF 벡터화
            if template_texts:
                self.template_vectors = self.vectorizer.fit_transform(template_texts)
                logger.info(f"템플릿 벡터 초기화 완료: {len(self.template_ids)}개 템플릿")
            else:
                self.template_vectors = None
                logger.warning("초기화할 템플릿이 없습니다")
                
        except Exception as e:
            logger.error(f"템플릿 벡터 초기화 실패: {str(e)}")
            self.template_vectors = None
    
    async def recommend_templates(
        self, 
        user_intent: str, 
        excel_file_path: str = None,
        user_id: str = None,
        user_tier: str = "basic",
        max_recommendations: int = 5
    ) -> Dict[str, Any]:
        """템플릿 추천 메인 함수"""
        
        try:
            logger.info(f"템플릿 추천 시작 - 사용자: {user_id}, 티어: {user_tier}")
            
            # 1. 사용자 의도 분석
            intent_analysis = await self._analyze_user_intent(user_intent)
            
            # 2. Excel 파일 분석 (파일이 있는 경우)
            data_analysis = None
            if excel_file_path and os.path.exists(excel_file_path):
                data_analysis = await self._analyze_excel_structure(excel_file_path)
            
            # 3. 사용자 히스토리 고려
            user_history = self._get_user_preferences(user_id) if user_id else {}
            
            # 4. 템플릿 매칭 점수 계산
            scored_templates = self._calculate_template_scores(
                intent_analysis,
                data_analysis,
                user_history,
                user_tier
            )
            
            # 5. 상위 N개 추천
            recommendations = scored_templates[:max_recommendations]
            
            # 6. 추천 결과 구성
            result = {
                "status": "success",
                "user_intent": user_intent,
                "intent_analysis": intent_analysis,
                "data_analysis": data_analysis,
                "recommendations": self._format_recommendations(recommendations),
                "total_candidates": len(scored_templates),
                "user_tier": user_tier,
                "timestamp": datetime.now().isoformat()
            }
            
            # 7. 사용자 선호도 업데이트
            if user_id:
                self._update_user_preferences(user_id, intent_analysis)
            
            logger.info(f"템플릿 추천 완료: {len(recommendations)}개 추천")
            return result
            
        except Exception as e:
            logger.error(f"템플릿 추천 실패: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "recommendations": []
            }
    
    async def _analyze_user_intent(self, user_intent: str) -> Dict[str, Any]:
        """사용자 의도 분석"""
        
        try:
            # 1. 키워드 추출
            keywords = self._extract_keywords(user_intent)
            
            # 2. 카테고리 분류
            category_scores = self._classify_intent_category(user_intent)
            
            # 3. AI 기반 의도 파악
            ai_analysis = await self._get_ai_intent_analysis(user_intent)
            
            # 4. 복잡도 추정
            complexity_estimate = self._estimate_complexity_from_intent(user_intent)
            
            return {
                "raw_intent": user_intent,
                "keywords": keywords,
                "category_scores": category_scores,
                "ai_analysis": ai_analysis,
                "complexity_estimate": complexity_estimate,
                "language": self._detect_language(user_intent)
            }
            
        except Exception as e:
            logger.error(f"사용자 의도 분석 실패: {str(e)}")
            return {
                "raw_intent": user_intent,
                "keywords": [],
                "category_scores": {},
                "complexity_estimate": 5
            }
    
    def _extract_keywords(self, text: str) -> List[str]:
        """키워드 추출"""
        
        # 한국어와 영어 키워드 패턴
        korean_pattern = r'[가-힣]{2,}'
        english_pattern = r'[a-zA-Z]{3,}'
        number_pattern = r'\d+'
        
        korean_keywords = re.findall(korean_pattern, text)
        english_keywords = re.findall(english_pattern, text.lower())
        
        # 불용어 제거
        stopwords = {
            '있는', '하는', '되는', '같은', '위한', '통해', '대한', '관련',
            'the', 'and', 'for', 'with', 'that', 'this', 'from'
        }
        
        keywords = []
        keywords.extend([k for k in korean_keywords if k not in stopwords])
        keywords.extend([k for k in english_keywords if k not in stopwords])
        
        return list(set(keywords))
    
    def _classify_intent_category(self, user_intent: str) -> Dict[str, float]:
        """카테고리별 의도 분류"""
        
        categories = self.templates_metadata.get("categories", {})
        category_scores = {}
        
        # 각 카테고리별 키워드 매칭
        category_keywords = {
            "financial_statements": ["재무", "손익", "매출", "수익", "이익", "비용", "financial", "revenue", "profit"],
            "analytics_dashboard": ["분석", "대시보드", "성과", "실적", "dashboard", "analytics", "performance"],
            "project_management": ["프로젝트", "일정", "계획", "진행", "project", "schedule", "timeline"],
            "hr_management": ["인사", "직원", "성과", "평가", "hr", "employee", "performance"],
            "marketing_reports": ["마케팅", "캠페인", "광고", "marketing", "campaign", "advertising"],
            "inventory_management": ["재고", "입고", "출고", "inventory", "stock", "warehouse"],
            "budget_planning": ["예산", "계획", "배정", "budget", "planning", "allocation"],
            "academic_research": ["연구", "실험", "통계", "research", "experiment", "statistics"]
        }
        
        user_intent_lower = user_intent.lower()
        
        for category, keywords in category_keywords.items():
            score = 0
            for keyword in keywords:
                if keyword in user_intent_lower:
                    score += 1
            
            # 키워드 매칭 비율로 점수 계산
            if keywords:
                category_scores[category] = score / len(keywords)
        
        return category_scores
    
    async def _get_ai_intent_analysis(self, user_intent: str) -> Dict[str, Any]:
        """AI 기반 의도 분석"""
        
        try:
            prompt = f"""
            다음 사용자 요청을 분석하여 Excel 템플릿 추천을 위한 정보를 추출해주세요:
            
            사용자 요청: "{user_intent}"
            
            다음 JSON 형태로 분석해주세요:
            {{
                "primary_purpose": "주요 목적 (한 줄 요약)",
                "business_domain": "비즈니스 도메인 (finance, marketing, hr, project, etc.)",
                "data_type": "예상되는 데이터 유형 (numeric, text, date, mixed)",
                "output_preference": "원하는 결과물 (report, dashboard, tracker, analysis)",
                "urgency": "긴급도 (low, medium, high)",
                "complexity": "복잡도 점수 (1-10)"
            }}
            """
            
            response = await openai_service.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            
            # JSON 파싱 시도
            try:
                import json
                ai_analysis = json.loads(response)
                return ai_analysis
            except json.JSONDecodeError:
                # 파싱 실패시 기본값 반환
                return {
                    "primary_purpose": "Excel 작업",
                    "business_domain": "general",
                    "complexity": 5
                }
                
        except Exception as e:
            logger.warning(f"AI 의도 분석 실패: {str(e)}")
            return {"complexity": 5}
    
    def _estimate_complexity_from_intent(self, user_intent: str) -> int:
        """의도에서 복잡도 추정"""
        
        complexity_indicators = {
            "고급": 3, "복잡한": 3, "상세한": 2, "종합적": 2,
            "advanced": 3, "complex": 3, "comprehensive": 2,
            "간단한": -2, "기본": -1, "simple": -2, "basic": -1,
            "대시보드": 2, "분석": 2, "보고서": 1,
            "dashboard": 2, "analysis": 2, "report": 1
        }
        
        base_complexity = 5
        user_intent_lower = user_intent.lower()
        
        for indicator, score in complexity_indicators.items():
            if indicator in user_intent_lower:
                base_complexity += score
        
        return max(1, min(10, base_complexity))
    
    def _detect_language(self, text: str) -> str:
        """언어 감지"""
        
        korean_chars = len(re.findall(r'[가-힣]', text))
        english_chars = len(re.findall(r'[a-zA-Z]', text))
        
        if korean_chars > english_chars:
            return "ko"
        elif english_chars > 0:
            return "en"
        else:
            return "unknown"
    
    async def _analyze_excel_structure(self, file_path: str) -> Dict[str, Any]:
        """Excel 파일 구조 분석"""
        
        try:
            # 기존 ExcelAnalyzer 활용
            analysis_result = await excel_analyzer.analyze_file(file_path)
            
            # 데이터 구조 특성 추출
            structure_analysis = {
                "total_sheets": analysis_result.get("summary", {}).get("total_sheets", 1),
                "total_columns": 0,
                "total_rows": 0,
                "numeric_columns": 0,
                "text_columns": 0,
                "date_columns": 0,
                "has_formulas": False,
                "has_charts": False,
                "data_density": 0.0
            }
            
            sheets = analysis_result.get("sheets", {})
            for sheet_name, sheet_data in sheets.items():
                if isinstance(sheet_data, dict):
                    cols = sheet_data.get("columns", [])
                    structure_analysis["total_columns"] += len(cols)
                    
                    # 데이터 타입 분석
                    for col_info in sheet_data.get("column_analysis", []):
                        if col_info.get("data_type") == "numeric":
                            structure_analysis["numeric_columns"] += 1
                        elif col_info.get("data_type") == "datetime":
                            structure_analysis["date_columns"] += 1
                        else:
                            structure_analysis["text_columns"] += 1
                    
                    # 수식 존재 여부
                    if sheet_data.get("formula_count", 0) > 0:
                        structure_analysis["has_formulas"] = True
            
            # 데이터 밀도 계산
            total_cells = structure_analysis["total_columns"] * structure_analysis["total_rows"]
            if total_cells > 0:
                filled_cells = analysis_result.get("summary", {}).get("total_cells_with_data", 0)
                structure_analysis["data_density"] = filled_cells / total_cells
            
            return structure_analysis
            
        except Exception as e:
            logger.error(f"Excel 구조 분석 실패: {str(e)}")
            return {}
    
    def _get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """사용자 선호도 조회"""
        
        return self.user_preferences.get(user_id, {
            "preferred_categories": {},
            "complexity_preference": 5,
            "recent_selections": []
        })
    
    def _calculate_template_scores(
        self,
        intent_analysis: Dict[str, Any],
        data_analysis: Optional[Dict[str, Any]],
        user_history: Dict[str, Any],
        user_tier: str
    ) -> List[Dict[str, Any]]:
        """템플릿 매칭 점수 계산"""
        
        templates = self.templates_metadata.get("templates", {})
        weights = self.templates_metadata.get("matching_weights", {
            "text_similarity": 0.4,
            "data_structure": 0.3,
            "user_history": 0.2,
            "complexity_match": 0.1
        })
        
        scored_templates = []
        
        for template_id, template in templates.items():
            # 티어 제한 검사
            if not self._check_tier_permission(template, user_tier):
                continue
            
            # 각 요소별 점수 계산
            text_score = self._calculate_text_similarity_score(
                intent_analysis, template
            )
            
            data_score = self._calculate_data_structure_score(
                data_analysis, template
            ) if data_analysis else 0.5
            
            history_score = self._calculate_user_history_score(
                user_history, template
            )
            
            complexity_score = self._calculate_complexity_match_score(
                intent_analysis.get("complexity_estimate", 5),
                template.get("complexity_score", 5)
            )
            
            # 가중 평균 계산
            total_score = (
                text_score * weights.get("text_similarity", 0.4) +
                data_score * weights.get("data_structure", 0.3) +
                history_score * weights.get("user_history", 0.2) +
                complexity_score * weights.get("complexity_match", 0.1)
            )
            
            scored_templates.append({
                "template_id": template_id,
                "template": template,
                "total_score": total_score,
                "score_breakdown": {
                    "text_similarity": text_score,
                    "data_structure": data_score,
                    "user_history": history_score,
                    "complexity_match": complexity_score
                }
            })
        
        # 점수순 정렬
        scored_templates.sort(key=lambda x: x["total_score"], reverse=True)
        
        return scored_templates
    
    def _check_tier_permission(self, template: Dict[str, Any], user_tier: str) -> bool:
        """티어별 접근 권한 확인"""
        
        tier_restrictions = self.templates_metadata.get("tier_restrictions", {})
        user_tier_info = tier_restrictions.get(user_tier, {})
        
        # 복잡도 제한 확인
        max_complexity = user_tier_info.get("max_complexity", 10)
        template_complexity = template.get("complexity_score", 5)
        
        if template_complexity > max_complexity:
            return False
        
        # 카테고리 제한 확인
        allowed_categories = user_tier_info.get("allowed_categories", ["all"])
        if "all" not in allowed_categories:
            template_category = template.get("category", "")
            if template_category not in allowed_categories:
                return False
        
        return True
    
    def _calculate_text_similarity_score(
        self, 
        intent_analysis: Dict[str, Any], 
        template: Dict[str, Any]
    ) -> float:
        """텍스트 유사도 점수 계산"""
        
        try:
            # 사용자 키워드와 템플릿 트리거 매칭
            user_keywords = set(intent_analysis.get("keywords", []))
            template_triggers = set(template.get("triggers", []))
            
            if not user_keywords or not template_triggers:
                return 0.0
            
            # 교집합 비율 계산
            intersection = user_keywords.intersection(template_triggers)
            union = user_keywords.union(template_triggers)
            
            jaccard_similarity = len(intersection) / len(union) if union else 0.0
            
            # 카테고리 매칭 보너스
            category_scores = intent_analysis.get("category_scores", {})
            template_category = template.get("category", "")
            category_bonus = category_scores.get(template_category, 0.0) * 0.3
            
            return min(1.0, jaccard_similarity + category_bonus)
            
        except Exception as e:
            logger.error(f"텍스트 유사도 계산 실패: {str(e)}")
            return 0.0
    
    def _calculate_data_structure_score(
        self,
        data_analysis: Dict[str, Any],
        template: Dict[str, Any]
    ) -> float:
        """데이터 구조 매칭 점수 계산"""
        
        try:
            requirements = template.get("data_requirements", {})
            score = 0.0
            total_checks = 0
            
            # 숫자 컬럼 수 확인
            if "numeric_columns" in requirements:
                required_numeric = requirements["numeric_columns"]
                actual_numeric = data_analysis.get("numeric_columns", 0)
                
                if isinstance(required_numeric, dict):
                    min_numeric = required_numeric.get("min", 1)
                    if actual_numeric >= min_numeric:
                        score += 1.0
                else:
                    if actual_numeric >= required_numeric:
                        score += 1.0
                total_checks += 1
            
            # 날짜 컬럼 확인
            if "date_column" in requirements:
                required_date = requirements["date_column"]
                actual_date = data_analysis.get("date_columns", 0)
                
                if isinstance(required_date, dict):
                    if required_date.get("required", False) and actual_date > 0:
                        score += 1.0
                    elif not required_date.get("required", False):
                        score += 1.0
                elif required_date and actual_date > 0:
                    score += 1.0
                total_checks += 1
            
            # 최소 행 수 확인
            if "min_rows" in requirements:
                required_rows = requirements["min_rows"]
                actual_rows = data_analysis.get("total_rows", 0)
                
                if actual_rows >= required_rows:
                    score += 1.0
                total_checks += 1
            
            return score / total_checks if total_checks > 0 else 0.5
            
        except Exception as e:
            logger.error(f"데이터 구조 점수 계산 실패: {str(e)}")
            return 0.5
    
    def _calculate_user_history_score(
        self,
        user_history: Dict[str, Any],
        template: Dict[str, Any]
    ) -> float:
        """사용자 히스토리 점수 계산"""
        
        try:
            # 선호 카테고리 확인
            preferred_categories = user_history.get("preferred_categories", {})
            template_category = template.get("category", "")
            
            category_preference = preferred_categories.get(template_category, 0.0)
            
            # 최근 선택 이력 확인
            recent_selections = user_history.get("recent_selections", [])
            template_id = template.get("id", "")
            
            recent_bonus = 0.0
            if template_id in recent_selections:
                # 최근 사용한 템플릿에 보너스
                recent_bonus = 0.2
            
            return min(1.0, category_preference + recent_bonus)
            
        except Exception as e:
            logger.error(f"사용자 히스토리 점수 계산 실패: {str(e)}")
            return 0.0
    
    def _calculate_complexity_match_score(
        self,
        user_complexity: int,
        template_complexity: int
    ) -> float:
        """복잡도 매칭 점수 계산"""
        
        try:
            # 복잡도 차이에 따른 점수 계산
            diff = abs(user_complexity - template_complexity)
            
            if diff == 0:
                return 1.0
            elif diff <= 2:
                return 0.8
            elif diff <= 4:
                return 0.5
            else:
                return 0.2
                
        except Exception as e:
            logger.error(f"복잡도 점수 계산 실패: {str(e)}")
            return 0.5
    
    def _format_recommendations(self, scored_templates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """추천 결과 포맷팅"""
        
        recommendations = []
        
        for item in scored_templates:
            template = item["template"]
            
            recommendation = {
                "template_id": item["template_id"],
                "name": template.get("name", ""),
                "description": template.get("description", ""),
                "category": template.get("category", ""),
                "complexity_score": template.get("complexity_score", 5),
                "recommended_tier": template.get("recommended_tier", "basic"),
                "features": template.get("features", []),
                "match_score": round(item["total_score"], 3),
                "score_breakdown": item["score_breakdown"],
                "preview_image": template.get("preview_image", ""),
                "estimated_time": self._estimate_creation_time(template)
            }
            
            recommendations.append(recommendation)
        
        return recommendations
    
    def _estimate_creation_time(self, template: Dict[str, Any]) -> str:
        """템플릿 생성 예상 시간"""
        
        complexity = template.get("complexity_score", 5)
        
        if complexity <= 3:
            return "5-10분"
        elif complexity <= 6:
            return "10-20분"
        elif complexity <= 8:
            return "20-30분"
        else:
            return "30분 이상"
    
    def _update_user_preferences(self, user_id: str, intent_analysis: Dict[str, Any]):
        """사용자 선호도 업데이트"""
        
        try:
            if user_id not in self.user_preferences:
                self.user_preferences[user_id] = {
                    "preferred_categories": {},
                    "complexity_preference": 5,
                    "recent_selections": []
                }
            
            user_prefs = self.user_preferences[user_id]
            
            # 카테고리 선호도 업데이트
            category_scores = intent_analysis.get("category_scores", {})
            for category, score in category_scores.items():
                if score > 0:
                    current_pref = user_prefs["preferred_categories"].get(category, 0.0)
                    # 지수 평활법으로 업데이트
                    user_prefs["preferred_categories"][category] = 0.7 * current_pref + 0.3 * score
            
            # 복잡도 선호도 업데이트
            complexity = intent_analysis.get("complexity_estimate", 5)
            current_complexity = user_prefs["complexity_preference"]
            user_prefs["complexity_preference"] = 0.8 * current_complexity + 0.2 * complexity
            
        except Exception as e:
            logger.error(f"사용자 선호도 업데이트 실패: {str(e)}")
    
    def get_template_categories(self) -> Dict[str, Any]:
        """템플릿 카테고리 목록 조회"""
        
        return {
            "status": "success",
            "categories": self.templates_metadata.get("categories", {}),
            "total_templates": len(self.templates_metadata.get("templates", {}))
        }
    
    def get_template_by_id(self, template_id: str) -> Dict[str, Any]:
        """템플릿 상세 정보 조회"""
        
        templates = self.templates_metadata.get("templates", {})
        template = templates.get(template_id)
        
        if not template:
            return {
                "status": "error",
                "error": f"템플릿을 찾을 수 없습니다: {template_id}"
            }
        
        return {
            "status": "success",
            "template": template
        }
    
    def get_localized_template_by_id(
        self, 
        template_id: str, 
        language: str = "ko"
    ) -> Dict[str, Any]:
        """언어별 템플릿 상세 정보 조회"""
        
        # 기본 템플릿 정보 가져오기
        base_result = self.get_template_by_id(template_id)
        if base_result["status"] != "success":
            return base_result
        
        base_template = base_result["template"]
        
        # i18n 메타데이터에서 번역 정보 가져오기
        i18n_templates = self.templates_metadata_i18n.get("templates", {})
        i18n_template = i18n_templates.get(template_id, {})
        
        # 번역 정보 추가
        if "translations" in i18n_template and language in i18n_template["translations"]:
            translation = i18n_template["translations"][language]
            localized_template = base_template.copy()
            
            # 번역된 필드들 덮어쓰기
            localized_template.update({
                "localized_name": translation.get("name", base_template.get("name", "")),
                "localized_description": translation.get("description", base_template.get("description", "")),
                "localized_features": translation.get("features", base_template.get("features", [])),
                "original_language": "ko",
                "display_language": language
            })
            
            return {
                "status": "success",
                "template": localized_template
            }
        else:
            # 번역이 없으면 기본 템플릿 반환
            return base_result
    
    def get_localized_categories(self, language: str = "ko") -> Dict[str, Any]:
        """언어별 카테고리 목록 조회"""
        
        try:
            base_categories = self.templates_metadata.get("categories", {})
            i18n_categories = self.templates_metadata_i18n.get("categories", {})
            
            localized_categories = {}
            
            for category_id, category_info in base_categories.items():
                localized_category = category_info.copy()
                
                # i18n 번역 정보 확인
                if category_id in i18n_categories:
                    i18n_category = i18n_categories[category_id]
                    if "translations" in i18n_category and language in i18n_category["translations"]:
                        translation = i18n_category["translations"][language]
                        localized_category.update({
                            "localized_name": translation.get("name", category_info.get("name", "")),
                            "localized_description": translation.get("description", category_info.get("description", "")),
                            "display_language": language
                        })
                
                localized_categories[category_id] = localized_category
            
            return {
                "status": "success",
                "categories": localized_categories
            }
            
        except Exception as e:
            logger.error(f"카테고리 현지화 실패: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }


# 전역 템플릿 선택 서비스 인스턴스
template_selection_service = TemplateSelectionService()