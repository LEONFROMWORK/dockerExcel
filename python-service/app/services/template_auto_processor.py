"""
Template Auto Processor Service
크롤링된 템플릿 자동 분석 및 AI 컨텍스트 생성 서비스
"""

import logging
import os
import re
from typing import Dict, List, Any, Optional
from datetime import datetime

from .template_analyzer import template_analyzer
from .i18n_template_service import i18n_template_service
from .ai_template_context_service import ai_template_context_service
from .korean_template_crawler import CrawledTemplate
from ..models.template_metadata import (
    EnhancedTemplateMetadata,
    TemplateCategory,
    TemplateComplexity,
    UsageContext,
)

logger = logging.getLogger(__name__)


class TemplateAutoProcessor:
    """크롤링된 템플릿 자동 처리 서비스"""

    def __init__(self):
        self.processed_templates = []
        self.processing_errors = []

        # 카테고리 매핑 (한국어 -> 시스템 카테고리)
        self.category_mapping = {
            "엑셀프로그램": {
                "가계부": TemplateCategory.FINANCE,
                "회계": TemplateCategory.FINANCE,
                "재무": TemplateCategory.FINANCE,
                "급여": TemplateCategory.HR,
                "인사": TemplateCategory.HR,
                "인사관리": TemplateCategory.HR,
                "영업": TemplateCategory.SALES,
                "마케팅": TemplateCategory.MARKETING,
                "판매": TemplateCategory.SALES,
                "재고": TemplateCategory.INVENTORY,
                "프로젝트": TemplateCategory.PROJECT_MANAGEMENT,
                "운영": TemplateCategory.OPERATIONS,
            },
            "엑셀템플릿": {
                "재무제표": TemplateCategory.FINANCE,
                "손익계산서": TemplateCategory.FINANCE,
                "현금흐름": TemplateCategory.FINANCE,
                "예산": TemplateCategory.FINANCE,
                "급여명세서": TemplateCategory.HR,
                "근태관리": TemplateCategory.HR,
                "고객관리": TemplateCategory.SALES,
                "영업실적": TemplateCategory.SALES,
                "재고관리": TemplateCategory.INVENTORY,
                "일정관리": TemplateCategory.PROJECT_MANAGEMENT,
            },
            "차트/대시보드": {
                "매출": TemplateCategory.SALES,
                "수익": TemplateCategory.FINANCE,
                "성과": TemplateCategory.OPERATIONS,
                "KPI": TemplateCategory.OPERATIONS,
                "분석": TemplateCategory.GENERAL,
            },
        }

        # 복잡도 판단 키워드
        self.complexity_keywords = {
            TemplateComplexity.BEGINNER: [
                "간단",
                "기본",
                "초보",
                "단순",
                "쉬운",
                "입문",
                "기초",
            ],
            TemplateComplexity.INTERMEDIATE: [
                "표준",
                "일반",
                "중급",
                "보통",
                "실무",
                "업무",
            ],
            TemplateComplexity.ADVANCED: [
                "고급",
                "전문",
                "상세",
                "복잡",
                "심화",
                "전문가",
            ],
            TemplateComplexity.EXPERT: [
                "마스터",
                "최고급",
                "완벽",
                "종합",
                "통합",
                "전체",
            ],
        }

    async def process_crawled_templates(
        self, crawled_templates: List[CrawledTemplate]
    ) -> Dict[str, Any]:
        """크롤링된 템플릿들을 자동으로 분석하고 처리"""
        logger.info(f"🔄 {len(crawled_templates)}개 크롤링된 템플릿 자동 처리 시작")

        processing_summary = {
            "total_templates": len(crawled_templates),
            "successfully_processed": 0,
            "analysis_completed": 0,
            "i18n_completed": 0,
            "ai_context_completed": 0,
            "errors": 0,
            "processing_time": 0,
            "start_time": datetime.now(),
        }

        for i, crawled_template in enumerate(crawled_templates):
            logger.info(
                f"📄 템플릿 처리 중 ({i+1}/{len(crawled_templates)}): {crawled_template.title}"
            )

            try:
                # 1. 템플릿 파일 분석
                analysis_result = await self._analyze_template_file(crawled_template)
                if analysis_result:
                    processing_summary["analysis_completed"] += 1

                # 2. 메타데이터 생성
                metadata = await self._generate_enhanced_metadata(
                    crawled_template, analysis_result
                )

                # 3. I18n 분석
                if metadata and analysis_result:
                    i18n_result = await self._process_i18n(metadata, analysis_result)
                    if i18n_result:
                        processing_summary["i18n_completed"] += 1

                # 4. AI 컨텍스트 생성
                if metadata:
                    ai_context = await self._generate_ai_context(metadata)
                    if ai_context:
                        processing_summary["ai_context_completed"] += 1

                # 처리 완료된 템플릿 기록
                self.processed_templates.append(
                    {
                        "original": crawled_template,
                        "analysis": analysis_result,
                        "metadata": metadata,
                        "processed_at": datetime.now().isoformat(),
                    }
                )

                processing_summary["successfully_processed"] += 1

            except Exception as e:
                logger.error(f"❌ 템플릿 처리 실패 ({crawled_template.title}): {e}")
                self.processing_errors.append(
                    {
                        "template": crawled_template.title,
                        "error": str(e),
                        "timestamp": datetime.now().isoformat(),
                    }
                )
                processing_summary["errors"] += 1

        # 처리 시간 계산
        processing_summary["processing_time"] = str(
            datetime.now() - processing_summary["start_time"]
        )
        processing_summary["success_rate"] = (
            round(
                (
                    processing_summary["successfully_processed"]
                    / processing_summary["total_templates"]
                )
                * 100,
                2,
            )
            if processing_summary["total_templates"] > 0
            else 0
        )

        logger.info(
            f"✅ 템플릿 자동 처리 완료: {processing_summary['successfully_processed']}/{processing_summary['total_templates']}"
        )

        return processing_summary

    async def _analyze_template_file(
        self, crawled_template: CrawledTemplate
    ) -> Optional[Dict[str, Any]]:
        """템플릿 파일 분석"""
        try:
            # 로컬 파일 경로 확인
            if (
                not hasattr(crawled_template, "local_path")
                or not crawled_template.local_path
            ):
                logger.warning(f"로컬 파일이 없음: {crawled_template.title}")
                return None

            local_path = crawled_template.local_path
            if not os.path.exists(local_path):
                logger.warning(f"파일이 존재하지 않음: {local_path}")
                return None

            # 템플릿 분석 실행
            analysis_result = await template_analyzer.analyze_template_file(
                local_path, crawled_template.title
            )

            logger.info(f"📊 분석 완료: {crawled_template.title}")
            return analysis_result

        except Exception as e:
            logger.error(f"템플릿 분석 실패: {e}")
            return None

    async def _generate_enhanced_metadata(
        self,
        crawled_template: CrawledTemplate,
        analysis_result: Optional[Dict[str, Any]],
    ) -> Optional[EnhancedTemplateMetadata]:
        """향상된 메타데이터 생성"""
        try:
            # 템플릿 카테고리 결정
            template_category = self._determine_template_category(
                crawled_template.category_major,
                crawled_template.category_minor,
                crawled_template.title,
                crawled_template.description,
            )

            # 복잡도 결정
            complexity = self._determine_complexity(
                crawled_template.title, crawled_template.description, analysis_result
            )

            # 사용 맥락 추론
            usage_contexts = self._infer_usage_contexts(
                template_category, crawled_template.description
            )

            # 메타데이터 생성
            metadata = EnhancedTemplateMetadata(
                template_id=self._generate_template_id(crawled_template),
                name=crawled_template.title,
                description=crawled_template.description,
                category=template_category,
                purpose=self._generate_purpose(crawled_template),
                subcategory=crawled_template.category_minor,
                business_use_cases=self._extract_use_cases(
                    crawled_template.description
                ),
                target_audience=self._infer_target_audience(
                    template_category, crawled_template.description
                ),
                usage_context=usage_contexts,
                complexity=complexity,
                estimated_completion_time=self._estimate_completion_time(
                    complexity, analysis_result
                ),
                prerequisites=self._generate_prerequisites(template_category),
                context_keywords=self._extract_keywords(
                    crawled_template.title, crawled_template.description
                ),
                semantic_tags=self._generate_semantic_tags(
                    template_category, crawled_template.description
                ),
                source=f"excel.yesform.com ({crawled_template.category_major}/{crawled_template.category_minor})",
            )

            logger.info(f"📋 메타데이터 생성 완료: {crawled_template.title}")
            return metadata

        except Exception as e:
            logger.error(f"메타데이터 생성 실패: {e}")
            return None

    def _determine_template_category(
        self, major_category: str, minor_category: str, title: str, description: str
    ) -> TemplateCategory:
        """템플릿 카테고리 결정"""
        # 1차: 중분류 기반 매핑
        if major_category in self.category_mapping:
            for keyword, category in self.category_mapping[major_category].items():
                if (
                    keyword in minor_category
                    or keyword in title
                    or keyword in description
                ):
                    return category

        # 2차: 제목과 설명에서 키워드 검색
        text_to_search = f"{title} {description}".lower()

        # 재무 관련
        if any(
            keyword in text_to_search
            for keyword in ["재무", "회계", "현금", "수익", "매출", "손익", "예산"]
        ):
            return TemplateCategory.FINANCE

        # 인사 관련
        if any(
            keyword in text_to_search
            for keyword in ["인사", "급여", "근태", "직원", "사원"]
        ):
            return TemplateCategory.HR

        # 영업 관련
        if any(
            keyword in text_to_search for keyword in ["영업", "고객", "판매", "마케팅"]
        ):
            return TemplateCategory.SALES

        # 운영 관련
        if any(
            keyword in text_to_search
            for keyword in ["운영", "관리", "프로젝트", "일정"]
        ):
            return TemplateCategory.OPERATIONS

        # 재고 관련
        if any(keyword in text_to_search for keyword in ["재고", "물류", "입출고"]):
            return TemplateCategory.INVENTORY

        return TemplateCategory.GENERAL

    def _determine_complexity(
        self, title: str, description: str, analysis_result: Optional[Dict[str, Any]]
    ) -> TemplateComplexity:
        """템플릿 복잡도 결정"""
        text_to_search = f"{title} {description}".lower()

        # 키워드 기반 복잡도 판단
        for complexity, keywords in self.complexity_keywords.items():
            if any(keyword in text_to_search for keyword in keywords):
                return complexity

        # 분석 결과 기반 복잡도 판단
        if analysis_result:
            complexity_score = analysis_result.get("overall_structure", {}).get(
                "complexity_score", 1
            )
            if complexity_score >= 8:
                return TemplateComplexity.EXPERT
            elif complexity_score >= 6:
                return TemplateComplexity.ADVANCED
            elif complexity_score >= 4:
                return TemplateComplexity.INTERMEDIATE
            else:
                return TemplateComplexity.BEGINNER

        return TemplateComplexity.INTERMEDIATE

    def _infer_usage_contexts(
        self, category: TemplateCategory, description: str
    ) -> List[UsageContext]:
        """사용 맥락 추론"""
        contexts = []

        if category == TemplateCategory.FINANCE:
            contexts.extend(
                [UsageContext.MONTHLY_REPORTS, UsageContext.QUARTERLY_ANALYSIS]
            )

        if category == TemplateCategory.HR:
            contexts.append(UsageContext.MONTHLY_REPORTS)

        if category == TemplateCategory.SALES:
            contexts.extend(
                [UsageContext.DAILY_OPERATIONS, UsageContext.MONTHLY_REPORTS]
            )

        if "년간" in description or "연간" in description:
            contexts.append(UsageContext.ANNUAL_PLANNING)

        if "일별" in description or "데일리" in description:
            contexts.append(UsageContext.DAILY_OPERATIONS)

        return contexts if contexts else [UsageContext.AD_HOC_ANALYSIS]

    def _generate_purpose(self, crawled_template: CrawledTemplate) -> str:
        """템플릿 목적 생성"""
        # 기본 목적 템플릿
        purpose_templates = {
            "재무": "재무 상황을 체계적으로 분석하고 관리하여 효율적인 자금 운용과 의사결정을 지원",
            "회계": "회계 업무의 정확성과 효율성을 높이고 재무 상태를 명확히 파악",
            "인사": "인사 관리 업무를 체계화하고 직원 정보 및 성과를 효과적으로 관리",
            "영업": "영업 활동을 체계적으로 관리하고 성과를 분석하여 매출 증대에 기여",
            "재고": "재고 현황을 실시간으로 파악하고 최적의 재고 수준을 유지",
            "프로젝트": "프로젝트 진행 상황을 체계적으로 관리하고 일정 및 자원을 효율적으로 배분",
        }

        # 카테고리별 기본 목적 찾기
        for keyword, purpose in purpose_templates.items():
            if (
                keyword in crawled_template.title
                or keyword in crawled_template.description
            ):
                return purpose

        # 기본 목적
        return (
            f"{crawled_template.title}을 통해 업무 효율성을 높이고 체계적인 관리를 지원"
        )

    def _extract_use_cases(self, description: str) -> List[str]:
        """사용 사례 추출"""
        use_cases = []

        # 일반적인 업무 패턴에서 사용 사례 추출
        if "관리" in description:
            use_cases.append("일상적인 업무 관리 및 모니터링")
        if "분석" in description:
            use_cases.append("데이터 분석 및 리포팅")
        if "계획" in description:
            use_cases.append("전략적 계획 수립 및 실행 관리")
        if "보고" in description or "리포트" in description:
            use_cases.append("정기적인 성과 보고서 작성")

        return use_cases if use_cases else ["업무 효율성 향상", "데이터 정리 및 관리"]

    def _infer_target_audience(
        self, category: TemplateCategory, description: str
    ) -> List[str]:
        """대상 사용자 추론"""
        audiences = []

        # 카테고리별 기본 대상
        category_audiences = {
            TemplateCategory.FINANCE: ["CFO", "재무담당자", "회계사", "경영진"],
            TemplateCategory.HR: ["인사담당자", "HR매니저", "팀장", "관리자"],
            TemplateCategory.SALES: [
                "영업담당자",
                "영업관리자",
                "마케팅팀",
                "사업개발팀",
            ],
            TemplateCategory.OPERATIONS: ["운영관리자", "프로젝트매니저", "팀장"],
            TemplateCategory.INVENTORY: ["재고관리자", "물류담당자", "구매팀"],
            TemplateCategory.PROJECT_MANAGEMENT: ["프로젝트매니저", "팀장", "기획자"],
            TemplateCategory.GENERAL: ["일반 사무직", "관리자", "팀원"],
        }

        audiences.extend(category_audiences.get(category, ["일반 사용자"]))

        # 설명에서 추가 대상 추출
        if "초보" in description or "입문" in description:
            audiences.append("업무 초보자")
        if "전문" in description or "고급" in description:
            audiences.append("전문가")

        return audiences

    def _estimate_completion_time(
        self, complexity: TemplateComplexity, analysis_result: Optional[Dict[str, Any]]
    ) -> str:
        """완성 시간 추정"""
        base_times = {
            TemplateComplexity.BEGINNER: "15-30분",
            TemplateComplexity.INTERMEDIATE: "30-60분",
            TemplateComplexity.ADVANCED: "1-2시간",
            TemplateComplexity.EXPERT: "2-4시간",
        }

        base_time = base_times.get(complexity, "30-60분")

        # 분석 결과가 있으면 더 정확한 추정
        if analysis_result:
            sheet_count = analysis_result.get("overall_structure", {}).get(
                "total_sheets", 1
            )
            if sheet_count > 3:
                return f"{base_time} (다중 시트로 인해 추가 시간 필요)"

        return base_time

    def _generate_prerequisites(self, category: TemplateCategory) -> List[str]:
        """사전 준비사항 생성"""
        prerequisites_map = {
            TemplateCategory.FINANCE: [
                "과거 재무 데이터",
                "회계 기본 지식",
                "관련 문서 및 자료",
            ],
            TemplateCategory.HR: ["직원 기본 정보", "급여 및 복리후생 정책", "조직도"],
            TemplateCategory.SALES: [
                "고객 정보",
                "제품/서비스 목록",
                "영업 프로세스 이해",
            ],
            TemplateCategory.OPERATIONS: [
                "업무 프로세스 이해",
                "관련 데이터",
                "조직 구조 파악",
            ],
            TemplateCategory.INVENTORY: ["제품 목록", "공급업체 정보", "창고 현황"],
            TemplateCategory.PROJECT_MANAGEMENT: [
                "프로젝트 범위 정의",
                "팀원 정보",
                "일정 계획",
            ],
        }

        return prerequisites_map.get(
            category, ["관련 데이터", "기본적인 엑셀 사용 능력"]
        )

    def _extract_keywords(self, title: str, description: str) -> List[str]:
        """키워드 추출"""
        # 한국어 특화 키워드 추출
        text = f"{title} {description}"

        # 일반적인 업무 키워드
        business_keywords = [
            "관리",
            "분석",
            "계획",
            "보고",
            "모니터링",
            "평가",
            "개선",
            "효율",
            "성과",
            "품질",
            "비용",
            "수익",
            "매출",
            "예산",
        ]

        found_keywords = []
        for keyword in business_keywords:
            if keyword in text:
                found_keywords.append(keyword)

        # 제목에서 명사 추출 (간단한 방식)
        title_words = re.findall(r"[가-힣]+", title)
        found_keywords.extend([word for word in title_words if len(word) >= 2])

        return list(set(found_keywords))[:10]  # 중복 제거 및 최대 10개

    def _generate_semantic_tags(
        self, category: TemplateCategory, description: str
    ) -> List[str]:
        """의미적 태그 생성"""
        base_tags = {
            TemplateCategory.FINANCE: ["재무관리", "회계", "자금운용"],
            TemplateCategory.HR: ["인사관리", "직원관리", "조직운영"],
            TemplateCategory.SALES: ["영업관리", "고객관리", "매출증대"],
            TemplateCategory.OPERATIONS: ["운영관리", "프로세스개선", "효율성"],
            TemplateCategory.INVENTORY: ["재고관리", "물류", "공급망"],
            TemplateCategory.PROJECT_MANAGEMENT: [
                "프로젝트관리",
                "일정관리",
                "자원배분",
            ],
        }

        tags = base_tags.get(category, ["업무관리"])

        # 설명에서 추가 태그 추출
        if "자동화" in description:
            tags.append("업무자동화")
        if "표준화" in description:
            tags.append("프로세스표준화")
        if "최적화" in description:
            tags.append("업무최적화")

        return tags

    def _generate_template_id(self, crawled_template: CrawledTemplate) -> str:
        """템플릿 ID 생성"""
        # 제목을 기반으로 ID 생성
        clean_title = re.sub(r"[^\w가-힣]", "_", crawled_template.title)
        timestamp = datetime.now().strftime("%Y%m%d")
        return f"kr_{clean_title}_{timestamp}"

    async def _process_i18n(
        self, metadata: EnhancedTemplateMetadata, analysis_result: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """I18n 처리"""
        try:
            i18n_requirements = (
                await i18n_template_service.analyze_template_i18n_requirements(
                    analysis_result
                )
            )

            # 한국어 템플릿이므로 영어, 일본어 번역 생성
            translations = await i18n_template_service.generate_template_translations(
                metadata.template_id,
                ["en", "ja"],
                use_ai_enhancement=False,  # 기본 번역 사용
            )

            return {"requirements": i18n_requirements, "translations": translations}

        except Exception as e:
            logger.error(f"I18n 처리 실패: {e}")
            return None

    async def _generate_ai_context(
        self, metadata: EnhancedTemplateMetadata
    ) -> Optional[Dict[str, Any]]:
        """AI 컨텍스트 생성"""
        try:
            ai_context = await ai_template_context_service.generate_ai_context(metadata)
            return ai_context

        except Exception as e:
            logger.error(f"AI 컨텍스트 생성 실패: {e}")
            return None


# 전역 인스턴스
template_auto_processor = TemplateAutoProcessor()
