"""
템플릿 시스템 테스트
Template System Tests
"""

import pytest
import tempfile
import pandas as pd
import os
import json
from datetime import datetime
import numpy as np

from app.services.template_selection_service import template_selection_service
from app.services.template_excel_generator import template_excel_generator


class TestTemplateSelectionService:
    """템플릿 선택 서비스 테스트"""
    
    def test_load_templates_metadata(self):
        """템플릿 메타데이터 로드 테스트"""
        
        metadata = template_selection_service.templates_metadata
        
        # 기본 구조 확인
        assert "templates" in metadata
        assert "categories" in metadata
        assert len(metadata["templates"]) > 0
        assert len(metadata["categories"]) > 0
        
        # 필수 템플릿 존재 확인
        templates = metadata["templates"]
        assert "quarterly_financial_report" in templates
        assert "sales_performance_dashboard" in templates
        assert "project_timeline_tracker" in templates
        
        print(f"✅ 메타데이터 로드 테스트 통과: {len(templates)}개 템플릿")
    
    def test_get_template_categories(self):
        """템플릿 카테고리 조회 테스트"""
        
        result = template_selection_service.get_template_categories()
        
        assert result["status"] == "success"
        assert "categories" in result
        assert len(result["categories"]) > 0
        
        # 필수 카테고리 확인
        categories = result["categories"]
        expected_categories = [
            "financial_statements",
            "analytics_dashboard", 
            "project_management",
            "hr_management"
        ]
        
        for category in expected_categories:
            assert category in categories
            assert "name" in categories[category]
            assert "description" in categories[category]
        
        print("✅ 카테고리 조회 테스트 통과")
    
    def test_get_template_by_id(self):
        """템플릿 ID별 조회 테스트"""
        
        # 존재하는 템플릿 조회
        result = template_selection_service.get_template_by_id("quarterly_financial_report")
        
        assert result["status"] == "success"
        assert "template" in result
        
        template = result["template"]
        assert template["id"] == "quarterly_financial_report"
        assert template["name"] == "분기별 재무보고서"
        assert "triggers" in template
        assert "data_requirements" in template
        
        # 존재하지 않는 템플릿 조회
        result = template_selection_service.get_template_by_id("nonexistent_template")
        assert result["status"] == "error"
        
        print("✅ 템플릿 ID별 조회 테스트 통과")
    
    @pytest.mark.asyncio
    async def test_recommend_templates_text_only(self):
        """텍스트 기반 템플릿 추천 테스트"""
        
        # 재무 관련 요청
        financial_intent = "분기별 손익계산서와 매출 분석 보고서를 만들고 싶습니다"
        
        result = await template_selection_service.recommend_templates(
            user_intent=financial_intent,
            user_tier="pro",
            max_recommendations=3
        )
        
        assert result["status"] == "success"
        assert "recommendations" in result
        assert len(result["recommendations"]) > 0
        
        # 첫 번째 추천이 재무 관련인지 확인
        top_recommendation = result["recommendations"][0]
        assert "financial" in top_recommendation["category"] or "financial" in top_recommendation["template_id"]
        assert top_recommendation["match_score"] > 0
        
        print(f"✅ 텍스트 기반 추천 테스트 통과: {len(result['recommendations'])}개 추천")
    
    @pytest.mark.asyncio 
    async def test_recommend_templates_with_excel_file(self):
        """Excel 파일 포함 템플릿 추천 테스트"""
        
        # 테스트용 Excel 파일 생성
        sample_data = pd.DataFrame({
            '월': ['1월', '2월', '3월', '4월'],
            '매출': [100000, 120000, 110000, 150000],
            '비용': [60000, 70000, 65000, 80000],
            '이익': [40000, 50000, 45000, 70000]
        })
        
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_file:
            sample_data.to_excel(tmp_file.name, index=False)
            file_path = tmp_file.name
        
        try:
            sales_intent = "월별 영업 성과 분석 대시보드를 만들어주세요"
            
            result = await template_selection_service.recommend_templates(
                user_intent=sales_intent,
                excel_file_path=file_path,
                user_tier="basic",
                max_recommendations=5
            )
            
            assert result["status"] == "success"
            assert "data_analysis" in result
            assert result["data_analysis"] is not None
            
            # 데이터 구조가 반영되었는지 확인
            data_analysis = result["data_analysis"]
            assert data_analysis["numeric_columns"] >= 3  # 매출, 비용, 이익
            
            print("✅ Excel 파일 포함 추천 테스트 통과")
            
        finally:
            if os.path.exists(file_path):
                os.unlink(file_path)
    
    def test_text_similarity_calculation(self):
        """텍스트 유사도 계산 테스트"""
        
        # 의도 분석 데이터 준비
        intent_analysis = {
            "keywords": ["재무", "손익", "분기", "매출"],
            "category_scores": {"financial_statements": 0.8}
        }
        
        # 재무 템플릿
        financial_template = {
            "triggers": ["재무", "손익", "매출", "이익", "분기"],
            "category": "financial_statements"
        }
        
        # 유사도 점수 계산
        score = template_selection_service._calculate_text_similarity_score(
            intent_analysis, financial_template
        )
        
        assert 0 <= score <= 1
        assert score > 0.5  # 높은 유사도 예상
        
        print(f"✅ 텍스트 유사도 계산 테스트 통과: {score:.3f}")
    
    def test_tier_permission_check(self):
        """티어별 권한 확인 테스트"""
        
        # 높은 복잡도 템플릿 (Enterprise 전용)
        complex_template = {
            "complexity_score": 9,
            "category": "academic_research"
        }
        
        # Basic 티어는 접근 불가
        assert not template_selection_service._check_tier_permission(complex_template, "basic")
        
        # Pro 티어는 접근 가능
        assert template_selection_service._check_tier_permission(complex_template, "pro")
        
        # Enterprise 티어는 접근 가능
        assert template_selection_service._check_tier_permission(complex_template, "enterprise")
        
        print("✅ 티어별 권한 확인 테스트 통과")


class TestTemplateExcelGenerator:
    """템플릿 Excel 생성기 테스트"""
    
    @pytest.mark.asyncio
    async def test_generate_quarterly_financial_report(self):
        """분기별 재무보고서 생성 테스트"""
        
        # 샘플 사용자 데이터
        user_data = {
            "financial_data": [
                {"category": "매출액", "current": 500000, "previous": 450000},
                {"category": "영업이익", "current": 100000, "previous": 75000}
            ]
        }
        
        result = await template_excel_generator.generate_from_template(
            template_id="quarterly_financial_report",
            user_data=user_data
        )
        
        assert result["status"] == "success"
        assert "output_file" in result
        assert os.path.exists(result["output_file"])
        assert "sheets_created" in result
        assert len(result["sheets_created"]) >= 2
        
        print(f"✅ 재무보고서 생성 테스트 통과: {result['output_file']}")
        
        # 생성된 파일 정리
        if os.path.exists(result["output_file"]):
            os.unlink(result["output_file"])
    
    @pytest.mark.asyncio
    async def test_generate_sales_dashboard(self):
        """영업 대시보드 생성 테스트"""
        
        user_data = {
            "sales_team_data": [
                {"name": "김철수", "target": 100000, "actual": 120000, "rank": 1},
                {"name": "이영희", "target": 90000, "actual": 95000, "rank": 2}
            ],
            "monthly_sales": [50000, 60000, 55000, 70000, 80000, 75000]
        }
        
        result = await template_excel_generator.generate_from_template(
            template_id="sales_performance_dashboard",
            user_data=user_data
        )
        
        assert result["status"] == "success"
        assert os.path.exists(result["output_file"])
        
        print(f"✅ 영업 대시보드 생성 테스트 통과: {result['output_file']}")
        
        # 생성된 파일 정리
        if os.path.exists(result["output_file"]):
            os.unlink(result["output_file"])
    
    @pytest.mark.asyncio
    async def test_generate_generic_template(self):
        """범용 템플릿 생성 테스트"""
        
        # pandas DataFrame 데이터
        sample_df = pd.DataFrame({
            "제품명": ["제품A", "제품B", "제품C"],
            "판매량": [100, 150, 120],
            "매출": [1000000, 1500000, 1200000]
        })
        
        user_data = {"data": sample_df}
        
        result = await template_excel_generator.generate_from_template(
            template_id="nonexistent_template",  # 존재하지 않는 템플릿 -> 범용 템플릿 사용
            user_data=user_data
        )
        
        assert result["status"] == "success"
        assert os.path.exists(result["output_file"])
        
        print(f"✅ 범용 템플릿 생성 테스트 통과: {result['output_file']}")
        
        # 생성된 파일 정리
        if os.path.exists(result["output_file"]):
            os.unlink(result["output_file"])
    
    def test_sample_data_generation(self):
        """샘플 데이터 생성 테스트"""
        
        # 재무 데이터 생성
        financial_data = template_excel_generator._generate_sample_financial_data()
        assert len(financial_data) > 0
        assert all(key in financial_data[0] for key in ["category", "current", "previous"])
        
        # 영업 데이터 생성
        sales_data = template_excel_generator._generate_sample_sales_data()
        assert len(sales_data) > 0
        assert all(key in sales_data[0] for key in ["name", "target", "actual", "rank"])
        
        print("✅ 샘플 데이터 생성 테스트 통과")


class TestTemplateIntegration:
    """템플릿 시스템 통합 테스트"""
    
    @pytest.mark.asyncio
    async def test_end_to_end_template_workflow(self):
        """전체 템플릿 워크플로우 테스트"""
        
        # 1. 사용자 의도 설정
        user_intent = "매월 영업팀 성과를 추적할 수 있는 대시보드를 만들어주세요"
        
        # 2. 템플릿 추천
        recommendations = await template_selection_service.recommend_templates(
            user_intent=user_intent,
            user_tier="pro",
            max_recommendations=1
        )
        
        assert recommendations["status"] == "success"
        assert len(recommendations["recommendations"]) > 0
        
        # 3. 최적 템플릿 선택
        best_template = recommendations["recommendations"][0]
        template_id = best_template["template_id"]
        
        # 4. 템플릿 기반 Excel 생성
        generation_result = await template_excel_generator.generate_from_template(
            template_id=template_id
        )
        
        assert generation_result["status"] == "success"
        assert os.path.exists(generation_result["output_file"])
        
        print(f"✅ E2E 워크플로우 테스트 통과")
        print(f"   추천 템플릿: {best_template['name']}")
        print(f"   매칭 점수: {best_template['match_score']}")
        print(f"   생성 파일: {generation_result['output_file']}")
        
        # 생성된 파일 정리
        if os.path.exists(generation_result["output_file"]):
            os.unlink(generation_result["output_file"])
    
    def test_template_metadata_integrity(self):
        """템플릿 메타데이터 무결성 테스트"""
        
        metadata = template_selection_service.templates_metadata
        templates = metadata.get("templates", {})
        categories = metadata.get("categories", {})
        
        # 모든 템플릿이 유효한 카테고리를 가지는지 확인
        for template_id, template in templates.items():
            template_category = template.get("category")
            assert template_category in categories, f"Template {template_id} has invalid category: {template_category}"
            
            # 필수 필드 확인
            required_fields = ["name", "description", "triggers", "data_requirements"]
            for field in required_fields:
                assert field in template, f"Template {template_id} missing required field: {field}"
        
        print(f"✅ 메타데이터 무결성 테스트 통과: {len(templates)}개 템플릿")
    
    def test_template_matching_algorithm_performance(self):
        """템플릿 매칭 알고리즘 성능 테스트"""
        
        test_intents = [
            "재무제표 작성",
            "영업 실적 분석", 
            "프로젝트 일정 관리",
            "직원 성과 평가",
            "마케팅 ROI 분석"
        ]
        
        import time
        
        for intent in test_intents:
            start_time = time.time()
            
            # 키워드 추출 및 분류 테스트
            keywords = template_selection_service._extract_keywords(intent)
            category_scores = template_selection_service._classify_intent_category(intent)
            
            end_time = time.time()
            processing_time = end_time - start_time
            
            assert processing_time < 0.1  # 100ms 이내 처리
            assert len(keywords) > 0
            assert len(category_scores) > 0
            
            print(f"   '{intent}' 처리 시간: {processing_time*1000:.1f}ms")
        
        print("✅ 매칭 알고리즘 성능 테스트 통과")


if __name__ == "__main__":
    # 간단한 테스트 실행
    import asyncio
    
    async def run_basic_tests():
        print("🧪 템플릿 시스템 기본 테스트 실행")
        
        # 템플릿 메타데이터 로드 테스트
        test_selection = TestTemplateSelectionService()
        test_selection.test_load_templates_metadata()
        test_selection.test_get_template_categories()
        test_selection.test_get_template_by_id()
        
        # 추천 시스템 테스트
        await test_selection.test_recommend_templates_text_only()
        
        # 생성 시스템 테스트
        test_generator = TestTemplateExcelGenerator()
        await test_generator.test_generate_quarterly_financial_report()
        
        # 통합 테스트
        test_integration = TestTemplateIntegration()
        await test_integration.test_end_to_end_template_workflow()
        
        print("✅ 모든 기본 테스트 통과!")
    
    try:
        asyncio.run(run_basic_tests())
    except Exception as e:
        print(f"❌ 테스트 실패: {str(e)}")
        import traceback
        traceback.print_exc()