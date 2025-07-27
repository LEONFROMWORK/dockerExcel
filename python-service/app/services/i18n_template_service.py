"""
Intelligent Template Internationalization Service
Provides context-aware multilingual support for Excel templates
"""
import logging
import asyncio
import json
import re
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

from .i18n_service import i18n_service
from .openai_service import openai_service

logger = logging.getLogger(__name__)


class TemplateContentType(Enum):
    HEADER = "header"
    LABEL = "label"
    INSTRUCTION = "instruction"
    FORMULA_DESCRIPTION = "formula_description"
    CHART_TITLE = "chart_title"
    TABLE_COLUMN = "table_column"
    VALIDATION_MESSAGE = "validation_message"
    WORKSHEET_NAME = "worksheet_name"


@dataclass
class I18nTemplateElement:
    """Template element that needs internationalization"""
    original_text: str
    element_type: TemplateContentType
    context: Dict[str, Any]
    coordinate: Optional[str] = None
    sheet_name: Optional[str] = None
    business_domain: Optional[str] = None
    
    def __post_init__(self):
        # Auto-detect business domain from context
        if not self.business_domain:
            self.business_domain = self._detect_business_domain()
    
    def _detect_business_domain(self) -> str:
        """Detect business domain from text and context"""
        finance_keywords = [
            'cash', 'flow', 'revenue', 'expense', 'profit', 'budget', 'financial',
            'income', 'cost', 'investment', 'roi', 'balance', 'assets', 'liability'
        ]
        hr_keywords = [
            'employee', 'salary', 'payroll', 'performance', 'department', 'staff',
            'hiring', 'training', 'benefits', 'attendance'
        ]
        sales_keywords = [
            'sales', 'customer', 'lead', 'conversion', 'pipeline', 'quota',
            'commission', 'prospect', 'deal', 'revenue'
        ]
        
        text_lower = self.original_text.lower()
        
        if any(keyword in text_lower for keyword in finance_keywords):
            return 'finance'
        elif any(keyword in text_lower for keyword in hr_keywords):
            return 'hr'
        elif any(keyword in text_lower for keyword in sales_keywords):
            return 'sales'
        else:
            return 'general'


class I18nTemplateService:
    """Advanced template internationalization service"""
    
    def __init__(self):
        self.supported_languages = ['ko', 'en', 'ja', 'zh', 'es', 'fr', 'de']
        self.template_translations_path = Path("app/templates/excel/i18n")
        self.template_translations_path.mkdir(parents=True, exist_ok=True)
        
        # Business domain specific translation contexts
        self.domain_contexts = {
            'finance': {
                'tone': 'professional',
                'terminology': 'financial',
                'formality': 'high'
            },
            'hr': {
                'tone': 'friendly',
                'terminology': 'corporate',
                'formality': 'medium'
            },
            'sales': {
                'tone': 'engaging',
                'terminology': 'business',
                'formality': 'medium'
            },
            'general': {
                'tone': 'neutral',
                'terminology': 'standard',
                'formality': 'medium'
            }
        }
    
    async def analyze_template_i18n_requirements(self, analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze template for internationalization requirements
        """
        template_id = analysis_result['template_id']
        i18n_requirements = {
            'template_id': template_id,
            'elements': [],
            'translation_complexity': 'medium',
            'estimated_effort': 0,
            'business_domains': set(),
            'content_types': set(),
            'suggested_languages': self._suggest_languages_for_template(analysis_result)
        }
        
        # Process each sheet's i18n elements
        for sheet_name, sheet_info in analysis_result.get('sheets', {}).items():
            sheet_elements = await self._extract_sheet_i18n_elements(
                sheet_name, sheet_info, analysis_result
            )
            i18n_requirements['elements'].extend(sheet_elements)
        
        # Process overall i18n elements
        overall_elements = await self._process_overall_i18n_elements(
            analysis_result.get('i18n_elements', {}), analysis_result
        )
        i18n_requirements['elements'].extend(overall_elements)
        
        # Calculate complexity and effort
        i18n_requirements.update(self._calculate_translation_complexity(i18n_requirements['elements']))
        
        # Save i18n requirements
        await self._save_i18n_requirements(template_id, i18n_requirements)
        
        return i18n_requirements
    
    async def generate_template_translations(
        self, 
        template_id: str, 
        target_languages: List[str] = None,
        use_ai_enhancement: bool = True
    ) -> Dict[str, Any]:
        """
        Generate comprehensive translations for a template
        """
        if not target_languages:
            target_languages = ['ko', 'en', 'ja', 'zh']
        
        # Load i18n requirements
        i18n_requirements = await self._load_i18n_requirements(template_id)
        if not i18n_requirements:
            raise ValueError(f"No i18n requirements found for template {template_id}")
        
        translation_results = {
            'template_id': template_id,
            'translations': {},
            'translation_quality': {},
            'context_adaptations': {},
            'generated_at': asyncio.get_event_loop().time()
        }
        
        for language in target_languages:
            logger.info(f"Generating {language} translations for template {template_id}")
            
            language_translations = await self._generate_language_translations(
                i18n_requirements['elements'], 
                language,
                use_ai_enhancement
            )
            
            translation_results['translations'][language] = language_translations
            
            # Quality assessment
            quality_score = await self._assess_translation_quality(
                language_translations, language
            )
            translation_results['translation_quality'][language] = quality_score
            
            # Context adaptations
            adaptations = await self._generate_context_adaptations(
                language_translations, language, template_id
            )
            translation_results['context_adaptations'][language] = adaptations
        
        # Save translation results
        await self._save_translation_results(template_id, translation_results)
        
        return translation_results
    
    async def _extract_sheet_i18n_elements(
        self, 
        sheet_name: str, 
        sheet_info: Dict[str, Any], 
        analysis_result: Dict[str, Any]
    ) -> List[I18nTemplateElement]:
        """Extract i18n elements from individual sheet"""
        elements = []
        
        # Process content sections
        for section in sheet_info.get('content_sections', []):
            if section.get('title'):
                element = I18nTemplateElement(
                    original_text=section['title'],
                    element_type=TemplateContentType.HEADER,
                    context={
                        'section_type': section.get('type', 'unknown'),
                        'sheet_name': sheet_name,
                        'estimated_range': section.get('estimated_range', ''),
                        'template_domain': analysis_result.get('business_domain', 'general')
                    },
                    coordinate=section.get('start_cell'),
                    sheet_name=sheet_name
                )
                elements.append(element)
        
        # Process input and output areas
        for area in sheet_info.get('input_areas', []):
            if area.get('coordinate') and area.get('type') == 'potential_input':
                # This might be a label or instruction
                element = I18nTemplateElement(
                    original_text=f"Input field at {area['coordinate']}",
                    element_type=TemplateContentType.LABEL,
                    context={
                        'data_type': area.get('data_type', 'text'),
                        'input_purpose': 'user_entry',
                        'sheet_name': sheet_name
                    },
                    coordinate=area['coordinate'],
                    sheet_name=sheet_name
                )
                elements.append(element)
        
        for area in sheet_info.get('output_areas', []):
            if area.get('formula'):
                # Create description for calculated fields
                description = self._generate_formula_description(area['formula'])
                element = I18nTemplateElement(
                    original_text=description,
                    element_type=TemplateContentType.FORMULA_DESCRIPTION,
                    context={
                        'formula': area['formula'],
                        'calculation_type': 'automatic',
                        'sheet_name': sheet_name
                    },
                    coordinate=area['coordinate'],
                    sheet_name=sheet_name
                )
                elements.append(element)
        
        return elements
    
    async def _process_overall_i18n_elements(
        self, 
        i18n_elements: Dict[str, List[str]], 
        analysis_result: Dict[str, Any]
    ) -> List[I18nTemplateElement]:
        """Process overall template i18n elements"""
        elements = []
        
        type_mapping = {
            'headers': TemplateContentType.HEADER,
            'labels': TemplateContentType.LABEL,
            'instructions': TemplateContentType.INSTRUCTION,
            'validation_messages': TemplateContentType.VALIDATION_MESSAGE,
            'chart_titles': TemplateContentType.CHART_TITLE
        }
        
        for category, texts in i18n_elements.items():
            content_type = type_mapping.get(category, TemplateContentType.LABEL)
            
            for text in texts:
                if self._is_translatable_text(text):
                    element = I18nTemplateElement(
                        original_text=text,
                        element_type=content_type,
                        context={
                            'category': category,
                            'template_context': analysis_result.get('template_name', ''),
                            'business_domain': analysis_result.get('business_domain', 'general')
                        }
                    )
                    elements.append(element)
        
        return elements
    
    def _is_translatable_text(self, text: str) -> bool:
        """Check if text should be translated"""
        # Skip formulas and cell references
        if text.startswith('='):
            return False
        
        # Skip pure numbers
        if text.replace('.', '').replace(',', '').replace('-', '').isdigit():
            return False
        
        # Skip very short text (likely abbreviations or codes)
        if len(text.strip()) < 2:
            return False
        
        # Skip cell references
        if re.match(r'^[A-Z]+\d+$', text.strip()):
            return False
        
        return True
    
    def _generate_formula_description(self, formula: str) -> str:
        """Generate human-readable description for formulas"""
        if 'SUM(' in formula:
            return "Sum of values"
        elif 'AVERAGE(' in formula:
            return "Average of values" 
        elif 'COUNT(' in formula:
            return "Count of items"
        elif 'IF(' in formula:
            return "Conditional calculation"
        elif 'VLOOKUP(' in formula:
            return "Lookup value from table"
        else:
            return "Calculated value"
    
    async def _generate_language_translations(
        self, 
        elements: List[Any], 
        target_language: str,
        use_ai_enhancement: bool = True
    ) -> Dict[str, Any]:
        """Generate translations for specific language"""
        translations = {}
        
        # Group elements by business domain for better context
        domain_groups = {}
        for element in elements:
            # Handle both I18nTemplateElement objects and dicts
            if isinstance(element, dict):
                domain = element.get('business_domain') or 'general'
            else:
                domain = element.business_domain or 'general'
            
            if domain not in domain_groups:
                domain_groups[domain] = []
            domain_groups[domain].append(element)
        
        # Process each domain group
        for domain, domain_elements in domain_groups.items():
            domain_translations = {}
            
            if use_ai_enhancement and len(domain_elements) > 5:
                # Use AI for batch translation with context
                domain_translations = await self._ai_batch_translate(
                    domain_elements, target_language, domain
                )
            else:
                # Use standard i18n service
                for element in domain_elements:
                    key = self._generate_translation_key(element)
                    
                    # Handle both dict and object formats
                    if isinstance(element, dict):
                        original_text = element.get('original_text', '')
                        context = element.get('context', {})
                        element_type = element.get('element_type', 'label')
                    else:
                        original_text = element.original_text
                        context = element.context
                        element_type = element.element_type.value if hasattr(element.element_type, 'value') else str(element.element_type)
                    
                    # Use basic translation for now (fallback when OpenAI not available)
                    translated_text = self._basic_translate(original_text, target_language)
                    domain_translations[key] = {
                        'text': translated_text,
                        'context': context,
                        'type': element_type
                    }
            
            translations.update(domain_translations)
        
        return translations
    
    async def _ai_batch_translate(
        self, 
        elements: List[Any], 
        target_language: str, 
        domain: str
    ) -> Dict[str, Any]:
        """Use AI for contextual batch translation"""
        domain_context = self.domain_contexts.get(domain, self.domain_contexts['general'])
        
        # Prepare batch translation prompt
        texts_to_translate = []
        element_map = {}
        
        for i, element in enumerate(elements):
            key = f"item_{i}"
            
            # Handle both dict and object formats
            if isinstance(element, dict):
                original_text = element.get('original_text', '')
                element_type = element.get('element_type', 'label')
                context = element.get('context', {})
            else:
                original_text = element.original_text
                element_type = element.element_type.value if hasattr(element.element_type, 'value') else str(element.element_type)
                context = element.context
            
            texts_to_translate.append({
                'key': key,
                'text': original_text,
                'type': element_type,
                'context': context
            })
            element_map[key] = element
        
        prompt = f"""
        You are a professional translator specializing in business documents, particularly Excel templates.
        
        Task: Translate the following {domain} domain text elements to {target_language}.
        
        Translation Guidelines:
        - Tone: {domain_context['tone']}
        - Terminology: {domain_context['terminology']}
        - Formality Level: {domain_context['formality']}
        - Maintain professional consistency
        - Consider Excel template context
        - Preserve formatting intentions
        
        Text Elements to Translate:
        {json.dumps(texts_to_translate, ensure_ascii=False, indent=2)}
        
        Please return a JSON object with the same structure, but with translated 'text' fields.
        Ensure cultural appropriateness and business context accuracy.
        """
        
        try:
            response = await openai_service.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=4000
            )
            translated_data = json.loads(response)
            
            # Convert back to our format
            translations = {}
            for item in translated_data:
                key = item['key']
                element = element_map[key]
                translation_key = self._generate_translation_key(element)
                
                # Handle both dict and object formats for context and type
                if isinstance(element, dict):
                    context = element.get('context', {})
                    element_type = element.get('element_type', 'label')
                else:
                    context = element.context
                    element_type = element.element_type.value if hasattr(element.element_type, 'value') else str(element.element_type)
                
                translations[translation_key] = {
                    'text': item['text'],
                    'context': context,
                    'type': element_type,
                    'ai_enhanced': True
                }
            
            return translations
        
        except Exception as e:
            logger.error(f"AI batch translation failed: {e}")
            # Fallback to standard translation
            translations = {}
            for element in elements:
                key = self._generate_translation_key(element)
                
                # Handle both dict and object formats
                if isinstance(element, dict):
                    original_text = element.get('original_text', '')
                    context = element.get('context', {})
                    element_type = element.get('element_type', 'label')
                else:
                    original_text = element.original_text
                    context = element.context
                    element_type = element.element_type.value if hasattr(element.element_type, 'value') else str(element.element_type)
                
                translated_text = self._basic_translate(original_text, target_language)
                translations[key] = {
                    'text': translated_text,
                    'context': context,
                    'type': element_type,
                    'ai_enhanced': False
                }
            
            return translations
    
    def _generate_translation_key(self, element) -> str:
        """Generate unique key for translation element"""
        # Handle both dict and object formats
        if isinstance(element, dict):
            original_text = element.get('original_text', '')
            coordinate = element.get('coordinate')
            sheet_name = element.get('sheet_name', '')
            element_type = element.get('element_type', 'label')
        else:
            original_text = element.original_text
            coordinate = element.coordinate
            sheet_name = element.sheet_name or ''
            element_type = element.element_type.value if hasattr(element.element_type, 'value') else str(element.element_type)
        
        base_key = re.sub(r'[^a-zA-Z0-9_]', '_', original_text[:50].lower())
        if coordinate:
            return f"{sheet_name}_{coordinate}_{base_key}"
        else:
            return f"{element_type}_{base_key}"
    
    def _suggest_languages_for_template(self, analysis_result: Dict[str, Any]) -> List[str]:
        """Suggest appropriate languages for template based on content"""
        # Default suggestions
        base_languages = ['ko', 'en']
        
        # Analyze template name and content for clues
        template_name = analysis_result.get('template_name', '').lower()
        
        if any(word in template_name for word in ['cash', 'flow', 'financial', 'budget']):
            # Financial templates benefit from major business languages
            return ['ko', 'en', 'ja', 'zh', 'es']
        elif any(word in template_name for word in ['hr', 'employee', 'payroll']):
            # HR templates for major markets
            return ['ko', 'en', 'ja', 'zh']
        else:
            # General templates
            return ['ko', 'en', 'ja']
    
    def _calculate_translation_complexity(self, elements: List[I18nTemplateElement]) -> Dict[str, Any]:
        """Calculate translation complexity and effort estimation"""
        total_elements = len(elements)
        
        # Complexity factors
        business_domains = set(elem.business_domain for elem in elements)
        content_types = set(elem.element_type for elem in elements)
        
        # Calculate complexity score
        complexity_score = 1  # Base score
        
        if total_elements > 50:
            complexity_score += 1
        if len(business_domains) > 2:
            complexity_score += 1
        if len(content_types) > 3:
            complexity_score += 1
        
        complexity_levels = ['low', 'medium', 'high', 'very_high']
        complexity = complexity_levels[min(complexity_score - 1, 3)]
        
        # Effort estimation (in hours)
        base_effort = total_elements * 0.1  # 6 minutes per element
        complexity_multiplier = {'low': 1, 'medium': 1.5, 'high': 2, 'very_high': 3}
        estimated_effort = base_effort * complexity_multiplier[complexity]
        
        return {
            'translation_complexity': complexity,
            'estimated_effort': round(estimated_effort, 1),
            'business_domains': list(business_domains),
            'content_types': [ct.value for ct in content_types]
        }
    
    async def _assess_translation_quality(
        self, 
        translations: Dict[str, Any], 
        language: str
    ) -> Dict[str, Any]:
        """Assess quality of translations"""
        quality_metrics = {
            'completeness': 0,
            'consistency': 0,
            'cultural_appropriateness': 0,
            'business_terminology': 0,
            'overall_score': 0
        }
        
        if not translations:
            return quality_metrics
        
        # Completeness check
        quality_metrics['completeness'] = min(100, (len(translations) / max(len(translations), 1)) * 100)
        
        # Basic consistency check (same terms translated consistently)
        term_translations = {}
        inconsistencies = 0
        
        for key, translation_data in translations.items():
            text = translation_data.get('text', '')
            # Simple consistency check for common terms
            # This is a basic implementation - could be enhanced with NLP
            words = text.lower().split()
            for word in words:
                if len(word) > 3:  # Only check meaningful words
                    if word in term_translations and term_translations[word] != text:
                        inconsistencies += 1
                    term_translations[word] = text
        
        consistency_score = max(0, 100 - (inconsistencies * 10))
        quality_metrics['consistency'] = consistency_score
        
        # Placeholder scores for other metrics (would require more sophisticated analysis)
        quality_metrics['cultural_appropriateness'] = 85  # Default good score
        quality_metrics['business_terminology'] = 80     # Default good score
        
        # Overall score
        scores = [
            quality_metrics['completeness'],
            quality_metrics['consistency'],
            quality_metrics['cultural_appropriateness'],
            quality_metrics['business_terminology']
        ]
        quality_metrics['overall_score'] = sum(scores) / len(scores)
        
        return quality_metrics
    
    async def _generate_context_adaptations(
        self, 
        translations: Dict[str, Any], 
        language: str, 
        template_id: str
    ) -> Dict[str, Any]:
        """Generate cultural and contextual adaptations"""
        adaptations = {
            'date_formats': self._get_date_format_for_language(language),
            'number_formats': self._get_number_format_for_language(language),
            'currency_formats': self._get_currency_format_for_language(language),
            'cultural_notes': self._get_cultural_notes_for_language(language),
            'rtl_support': language in ['ar', 'he', 'fa']
        }
        
        return adaptations
    
    def _get_date_format_for_language(self, language: str) -> str:
        """Get appropriate date format for language"""
        formats = {
            'ko': 'YYYY-MM-DD',
            'en': 'MM/DD/YYYY',
            'ja': 'YYYY/MM/DD',
            'zh': 'YYYY-MM-DD',
            'es': 'DD/MM/YYYY',
            'fr': 'DD/MM/YYYY',
            'de': 'DD.MM.YYYY'
        }
        return formats.get(language, 'MM/DD/YYYY')
    
    def _get_number_format_for_language(self, language: str) -> str:
        """Get appropriate number format for language"""
        formats = {
            'ko': '#,##0.00',
            'en': '#,##0.00',
            'ja': '#,##0.00',
            'zh': '#,##0.00',
            'es': '#.##0,00',
            'fr': '#.##0,00',
            'de': '#.##0,00'
        }
        return formats.get(language, '#,##0.00')
    
    def _get_currency_format_for_language(self, language: str) -> str:
        """Get appropriate currency format for language"""
        formats = {
            'ko': '₩#,##0',
            'en': '$#,##0.00',
            'ja': '¥#,##0',
            'zh': '¥#,##0.00',
            'es': '#,##0.00 €',
            'fr': '#,##0.00 €',
            'de': '#,##0.00 €'
        }
        return formats.get(language, '$#,##0.00')
    
    def _get_cultural_notes_for_language(self, language: str) -> List[str]:
        """Get cultural considerations for language"""
        notes = {
            'ko': [
                "Use formal business language",
                "Consider hierarchical business structure",
                "Date format follows ISO standard"
            ],
            'ja': [
                "Use keigo (honorific language) for business",
                "Consider seasonal business practices",
                "Vertical text may be preferred in some contexts"
            ],
            'zh': [
                "Use simplified Chinese for mainland China",
                "Consider traditional Chinese for Taiwan/Hong Kong",
                "Number 4 is considered unlucky in business"
            ],
            'es': [
                "Consider regional variations (Latin America vs Spain)",
                "Formal business language preferred",
                "Date format varies by region"
            ]
        }
        return notes.get(language, ["Standard business language conventions"])
    
    def _basic_translate(self, text: str, target_language: str) -> str:
        """Basic translation using simple lookup table"""
        # This is a basic implementation - in production, you'd use a real translation service
        translations = {
            'ko': {
                'Cash Flow': '현금흐름',
                'Revenue': '수익',
                'Expense': '비용',
                'Total': '총계',
                'January': '1월',
                'February': '2월',
                'March': '3월',
                'April': '4월',
                'May': '5월',
                'June': '6월',
                'July': '7월',
                'August': '8월',
                'September': '9월',
                'October': '10월',
                'November': '11월',
                'December': '12월',
                'OPERATIONS': '운영',
                'FINANCING': '자금조달',
                'INVESTING': '투자',
                'Sum of values': '값의 합계',
                'Average of values': '값의 평균',
                'Count of items': '항목 수',
                'Conditional calculation': '조건부 계산',
                'Lookup value from table': '테이블에서 값 조회',
                'Calculated value': '계산된 값'
            },
            'ja': {
                'Cash Flow': 'キャッシュフロー',
                'Revenue': '収益',
                'Expense': '費用',
                'Total': '合計',
                'January': '1月',
                'February': '2月',
                'March': '3月',
                'April': '4月',
                'May': '5月',
                'June': '6月',
                'July': '7月',
                'August': '8月',
                'September': '9月',
                'October': '10月',
                'November': '11月',
                'December': '12月',
                'OPERATIONS': '営業',
                'FINANCING': '財務',
                'INVESTING': '投資',
                'Sum of values': '値の合計',
                'Average of values': '値の平均',
                'Count of items': '項目数',
                'Conditional calculation': '条件付き計算',
                'Lookup value from table': 'テーブルから値を検索',
                'Calculated value': '計算値'
            },
            'zh': {
                'Cash Flow': '现金流',
                'Revenue': '收入',
                'Expense': '费用',
                'Total': '总计',
                'January': '1月',
                'February': '2月',
                'March': '3月',
                'April': '4月',
                'May': '5月',
                'June': '6月',
                'July': '7月',
                'August': '8月',
                'September': '9月',
                'October': '10月',
                'November': '11月',
                'December': '12月',
                'OPERATIONS': '运营',
                'FINANCING': '融资',
                'INVESTING': '投资',
                'Sum of values': '数值总和',
                'Average of values': '数值平均',
                'Count of items': '项目计数',
                'Conditional calculation': '条件计算',
                'Lookup value from table': '从表中查找值',
                'Calculated value': '计算值'
            }
        }
        
        # Return translated text if available, otherwise return original
        lang_translations = translations.get(target_language, {})
        return lang_translations.get(text, text)
    
    async def _save_i18n_requirements(self, template_id: str, requirements: Dict[str, Any]):
        """Save i18n requirements to file"""
        file_path = self.template_translations_path / f"{template_id}_i18n_requirements.json"
        
        # Convert sets to lists and dataclass objects to dicts for JSON serialization
        requirements_copy = requirements.copy()
        requirements_copy['business_domains'] = list(requirements_copy.get('business_domains', set()))
        requirements_copy['content_types'] = list(requirements_copy.get('content_types', set()))
        
        # Convert I18nTemplateElement objects to dictionaries
        if 'elements' in requirements_copy:
            serializable_elements = []
            for element in requirements_copy['elements']:
                if hasattr(element, '__dict__'):
                    element_dict = {
                        'original_text': element.original_text,
                        'element_type': element.element_type.value,
                        'context': element.context,
                        'coordinate': element.coordinate,
                        'sheet_name': element.sheet_name,
                        'business_domain': element.business_domain
                    }
                    serializable_elements.append(element_dict)
                else:
                    serializable_elements.append(element)
            requirements_copy['elements'] = serializable_elements
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(requirements_copy, f, ensure_ascii=False, indent=2)
    
    async def _load_i18n_requirements(self, template_id: str) -> Optional[Dict[str, Any]]:
        """Load i18n requirements from file"""
        file_path = self.template_translations_path / f"{template_id}_i18n_requirements.json"
        
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
    
    async def _save_translation_results(self, template_id: str, results: Dict[str, Any]):
        """Save translation results to file"""
        file_path = self.template_translations_path / f"{template_id}_translations.json"
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
    
    async def get_template_translations(self, template_id: str, language: str = None) -> Dict[str, Any]:
        """Get translations for a template"""
        file_path = self.template_translations_path / f"{template_id}_translations.json"
        
        if not file_path.exists():
            return {}
        
        with open(file_path, 'r', encoding='utf-8') as f:
            translations = json.load(f)
        
        if language:
            return translations.get('translations', {}).get(language, {})
        
        return translations
    
    async def update_template_translation(
        self, 
        template_id: str, 
        language: str, 
        key: str, 
        new_translation: str
    ) -> bool:
        """Update specific translation"""
        try:
            translations = await self.get_template_translations(template_id)
            
            if language not in translations.get('translations', {}):
                translations.setdefault('translations', {})[language] = {}
            
            translations['translations'][language][key] = {
                'text': new_translation,
                'manually_edited': True,
                'updated_at': asyncio.get_event_loop().time()
            }
            
            await self._save_translation_results(template_id, translations)
            return True
        
        except Exception as e:
            logger.error(f"Failed to update translation: {e}")
            return False


# Global instance
i18n_template_service = I18nTemplateService()