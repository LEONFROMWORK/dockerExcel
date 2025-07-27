"""
다국어 Two-Tier OCR 서비스
언어 자동 감지 + 언어별 최적화된 OCR 처리
"""

import os
import cv2
import numpy as np
import pytesseract
from PIL import Image
from typing import List, Dict, Any, Optional, Tuple
import logging
import langdetect
from collections import Counter
import json
import asyncio
from .ocr_cache_service import ocr_cache
from .ocr_retry_service import OCRRetryService, RetryConfig, FailureType
from app.data.arabic_financial_terms import get_arabic_financial_terms_by_category

logger = logging.getLogger(__name__)

class MultilingualTwoTierService:
    """
    다국어 Two-Tier OCR 서비스
    Tier 1: 언어별 맞춤 훈련 모델 (korean_finance, chi_sim_finance 등)
    Tier 2: 표준 언어 모델 fallback
    """
    
    def __init__(self):
        """다국어 OCR 서비스 초기화"""
        self.tessdata_dir = "/Users/kevin/excel-unified/tessdata_multilang"
        self.custom_models_dir = "/Users/kevin/excel-unified/tesstrain/data"
        
        # OCR 재시도 서비스 초기화
        retry_config = RetryConfig(
            max_attempts=3,
            base_delay=1.0,
            max_delay=30.0,
            backoff_multiplier=2.0,
            jitter=True,
            timeout=20.0
        )
        self.retry_service = OCRRetryService(retry_config)
        
        # 언어 매핑 설정
        self.language_mapping = {
            'ko': {
                'standard': 'kor',
                'custom': 'korean_finance',
                'name': '한국어',
                'confidence_threshold': 60
            },
            'zh-cn': {
                'standard': 'chi_sim',
                'custom': 'chi_sim_finance',
                'name': '중국어(간체)',
                'confidence_threshold': 65
            },
            'zh-tw': {
                'standard': 'chi_tra',
                'custom': 'chi_tra_finance',
                'name': '중국어(번체)',
                'confidence_threshold': 65
            },
            'ja': {
                'standard': 'jpn',
                'custom': 'jpn_finance',
                'name': '일본어',
                'confidence_threshold': 60
            },
            'es': {
                'standard': 'spa',
                'custom': 'spa_finance',
                'name': '스페인어',
                'confidence_threshold': 70
            },
            'pt': {
                'standard': 'por',
                'custom': 'por_finance',
                'name': '포르투갈어',
                'confidence_threshold': 70
            },
            'fr': {
                'standard': 'fra',
                'custom': 'fra_finance',
                'name': '프랑스어',
                'confidence_threshold': 70
            },
            'de': {
                'standard': 'deu',
                'custom': 'deu_finance',
                'name': '독일어',
                'confidence_threshold': 70
            },
            'vi': {
                'standard': 'vie',
                'custom': 'vie_finance',
                'name': '베트남어',
                'confidence_threshold': 65
            },
            'it': {
                'standard': 'ita',
                'custom': 'ita_finance',
                'name': '이탈리아어',
                'confidence_threshold': 70
            },
            'ar': {
                'standard': 'ara',
                'custom': 'ara_finance',
                'name': '아랍어',
                'confidence_threshold': 65,
                'rtl': True  # 오른쪽에서 왼쪽으로 읽는 언어
            }
        }
        
        # 재무 키워드 사전 (언어 감지용)
        self.financial_keywords = {
            'ko': ['재무제표', '손익계산서', '대차대조표', '매출액', '영업이익', '자산', '부채', '자본', '원'],
            'zh-cn': ['财务报表', '损益表', '资产负债表', '营业收入', '营业利润', '资产', '负债', '股东权益', '元'],
            'zh-tw': ['財務報表', '損益表', '資產負債表', '營業收入', '營業利潤', '資產', '負債', '股東權益', '元'],
            'ja': ['財務諸表', '損益計算書', '貸借対照表', '売上高', '営業利益', '資産', '負債', '純資産', '円'],
            'es': ['Estados Financieros', 'Estado de Resultados', 'Balance General', 'Ingresos', 'Utilidad', 'Activos', 'Pasivos', 'EUR'],
            'pt': ['Demonstrações Financeiras', 'Demonstração de Resultados', 'Balanço Patrimonial', 'Receitas', 'Lucro', 'Ativos', 'Passivos', 'EUR'],
            'fr': ['États Financiers', 'Compte de Résultat', 'Bilan', 'Chiffre d\'Affaires', 'Résultat', 'Actifs', 'Passifs', 'EUR'],
            'de': ['Jahresabschluss', 'Gewinn- und Verlustrechnung', 'Bilanz', 'Umsatzerlöse', 'Betriebsergebnis', 'Aktiva', 'Passiva', 'EUR'],
            'vi': ['Báo cáo tài chính', 'Báo cáo kết quả', 'Bảng cân đối', 'Doanh thu', 'Lợi nhuận', 'Tài sản', 'Nợ', 'VND'],
            'it': ['Bilancio', 'Conto Economico', 'Stato Patrimoniale', 'Ricavi', 'Utile Operativo', 'Utile Netto', 'Totale Attivo', 'Patrimonio Netto', 'EUR'],
            'ar': get_arabic_financial_terms_by_category()  # 포괄적인 아랍어 재무 용어 사전 사용
        }
        
        # Tesseract 설정
        pytesseract.pytesseract.tesseract_cmd = '/opt/homebrew/bin/tesseract'
        
        # 사용 가능한 모델 확인
        self.available_models = self._check_available_models()
        
        logger.info(f"MultilingualTwoTierService 초기화 완료")
        logger.info(f"사용 가능한 언어 모델: {list(self.available_models.keys())}")
    
    def _check_available_models(self) -> Dict[str, Dict[str, bool]]:
        """사용 가능한 모델들을 확인"""
        available = {}
        
        for lang_code, config in self.language_mapping.items():
            available[lang_code] = {
                'standard': os.path.exists(f"{self.tessdata_dir}/{config['standard']}.traineddata"),
                'custom': os.path.exists(f"{self.custom_models_dir}/{config['custom']}.traineddata")
            }
        
        return available
    
    def preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """이미지 전처리"""
        try:
            # 그레이스케일 변환
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image.copy()
            
            # 노이즈 제거
            denoised = cv2.fastNlMeansDenoising(gray)
            
            # 적응형 임계값 적용
            binary = cv2.adaptiveThreshold(
                denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY, 11, 2
            )
            
            return binary
            
        except Exception as e:
            logger.error(f"이미지 전처리 실패: {e}")
            return image
    
    def detect_language(self, image_text: str) -> Tuple[str, float]:
        """텍스트에서 언어 감지"""
        try:
            if not image_text or not image_text.strip():
                return 'ko', 0.5
            
            # 1. 아랍어 문자 패턴 우선 검사
            import re
            arabic_pattern = r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]'
            arabic_chars = re.findall(arabic_pattern, image_text)
            
            if len(arabic_chars) > 3:  # 아랍어 문자가 3개 이상이면 아랍어로 판단
                logger.info(f"아랍어 문자 감지: {len(arabic_chars)}개")
                return 'ar', 0.9
            
            # 2. 재무 키워드 기반 언어 감지 (더 정확함)
            keyword_scores = {}
            for lang_code, keywords in self.financial_keywords.items():
                score = 0
                for keyword in keywords:
                    if keyword in image_text:
                        score += len(keyword) * 2  # 키워드 길이만큼 점수 부여 (가중치 증가)
                keyword_scores[lang_code] = score
            
            # 3. 키워드 기반 결과가 있으면 우선 사용
            if max(keyword_scores.values()) > 0:
                detected_lang = max(keyword_scores, key=keyword_scores.get)
                confidence = min(0.95, 0.6 + (keyword_scores[detected_lang] / 200))
                logger.info(f"키워드 기반 언어 감지: {detected_lang} (점수: {keyword_scores[detected_lang]})")
                return detected_lang, confidence
            
            # 4. langdetect 라이브러리 사용 (키워드가 없을 때만)
            try:
                detected_lang = langdetect.detect(image_text)
                confidence = 0.7  # 기본 신뢰도
            except:
                detected_lang = 'ko'
                confidence = 0.5
            
            # 5. 언어 코드 정규화
            lang_mapping = {
                'ko': 'ko',
                'zh': 'zh-cn',
                'zh-cn': 'zh-cn',
                'zh-tw': 'zh-tw',
                'ja': 'ja',
                'es': 'es',
                'pt': 'pt',
                'fr': 'fr',
                'de': 'de',
                'vi': 'vi',
                'it': 'it',
                'ar': 'ar'
            }
            
            detected_lang = lang_mapping.get(detected_lang, 'ko')  # 기본값: 한국어
            
            return detected_lang, confidence
            
        except Exception as e:
            logger.warning(f"언어 감지 실패: {e}")
            return 'ko', 0.5  # 기본값: 한국어
    
    async def extract_text_with_language_with_retry(self, image: np.ndarray, lang_code: str, tier: int = 1) -> Dict[str, Any]:
        """재시도 로직이 적용된 언어별 텍스트 추출"""
        result = await self.retry_service.retry_with_backoff(
            self._extract_text_with_language_internal, image, lang_code, tier
        )
        
        if result.success:
            return result.data
        else:
            logger.error(f"재시도 후 OCR 실패 ({lang_code}): {result.error_message}")
            return {
                "success": False,
                "error": result.error_message,
                "failure_type": result.final_failure_type.value,
                "retry_attempts": len(result.attempts),
                "total_duration": result.total_duration
            }
    
    def extract_text_with_language(self, image: np.ndarray, lang_code: str, tier: int = 1) -> Dict[str, Any]:
        """동기 버전 - 기존 호환성 유지"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self.extract_text_with_language_with_retry(image, lang_code, tier)
            )
        finally:
            loop.close()
    
    def _extract_text_with_language_internal(self, image: np.ndarray, lang_code: str, tier: int = 1) -> Dict[str, Any]:
        """내부 OCR 처리 함수 (재시도 대상)"""
        try:
            if lang_code not in self.language_mapping:
                return {"success": False, "error": f"지원하지 않는 언어: {lang_code}"}
            
            lang_config = self.language_mapping[lang_code]
            processed_image = self.preprocess_image(image)
            pil_image = Image.fromarray(processed_image)
            
            # Tier 1: 맞춤 훈련 모델
            if tier == 1 and self.available_models[lang_code]['custom']:
                custom_model = lang_config['custom']
                
                # 아랍어 등 RTL 언어를 위한 특별 설정
                if lang_config.get('rtl', False):
                    config = f'--tessdata-dir {self.custom_models_dir} -l {custom_model} --psm 6 -c preserve_interword_spaces=1'
                else:
                    config = f'--tessdata-dir {self.custom_models_dir} -l {custom_model} --psm 6'
                
                try:
                    text = pytesseract.image_to_string(pil_image, config=config)
                    data = pytesseract.image_to_data(pil_image, config=config, output_type=pytesseract.Output.DICT)
                    
                    # 신뢰도 계산
                    confidences = [int(conf) for conf in data['conf'] if int(conf) > 0]
                    avg_confidence = sum(confidences) / len(confidences) if confidences else 0
                    
                    # 영역 정보 추출
                    regions = []
                    n_boxes = len(data['level'])
                    for i in range(n_boxes):
                        if int(data['conf'][i]) > 30:
                            x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
                            text_content = data['text'][i].strip()
                            if text_content:
                                regions.append({
                                    'text': text_content,
                                    'bbox': [x, y, x + w, y + h],
                                    'confidence': int(data['conf'][i])
                                })
                    
                    return {
                        "success": True,
                        "text": text.strip(),
                        "confidence": avg_confidence,
                        "regions": regions,
                        "method": f"Custom {lang_config['name']} Finance Model",
                        "language": lang_code,
                        "tier": 1
                    }
                    
                except Exception as e:
                    logger.warning(f"Tier 1 ({custom_model}) 실패: {e}")
            
            # Tier 2: 표준 언어 모델
            if self.available_models[lang_code]['standard']:
                standard_model = lang_config['standard']
                
                # RTL 언어를 위한 특별 설정
                if lang_config.get('rtl', False):
                    config = f'--tessdata-dir {self.tessdata_dir} -l {standard_model} --psm 6 -c preserve_interword_spaces=1'
                else:
                    config = f'--tessdata-dir {self.tessdata_dir} -l {standard_model} --psm 6'
                
                text = pytesseract.image_to_string(pil_image, config=config)
                data = pytesseract.image_to_data(pil_image, config=config, output_type=pytesseract.Output.DICT)
                
                # 신뢰도 계산
                confidences = [int(conf) for conf in data['conf'] if int(conf) > 0]
                avg_confidence = sum(confidences) / len(confidences) if confidences else 0
                
                # 영역 정보 추출
                regions = []
                n_boxes = len(data['level'])
                for i in range(n_boxes):
                    if int(data['conf'][i]) > 20:
                        x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
                        text_content = data['text'][i].strip()
                        if text_content:
                            regions.append({
                                'text': text_content,
                                'bbox': [x, y, x + w, y + h],
                                'confidence': int(data['conf'][i])
                            })
                
                return {
                    "success": True,
                    "text": text.strip(),
                    "confidence": avg_confidence,
                    "regions": regions,
                    "method": f"Standard {lang_config['name']} Model",
                    "language": lang_code,
                    "tier": 2
                }
            
            return {"success": False, "error": f"{lang_code} 모델을 사용할 수 없습니다"}
            
        except Exception as e:
            logger.error(f"언어별 텍스트 추출 실패 ({lang_code}): {e}")
            return {"success": False, "error": str(e)}
    
    def extract_text(self, image_data: bytes) -> Dict[str, Any]:
        """메인 다국어 텍스트 추출"""
        try:
            # 1. 캐시 확인
            image_hash = ocr_cache.generate_image_hash(image_data)
            cached_result = ocr_cache.get_cached_result(image_hash)
            
            if cached_result:
                logger.info(f"캐시에서 OCR 결과 반환: {image_hash[:12]}...")
                return cached_result
            
            # 이미지 디코딩
            nparr = np.frombuffer(image_data, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if image is None:
                return {
                    "success": False,
                    "error": "이미지 디코딩 실패",
                    "text": "",
                    "confidence": 0.0
                }
            
            logger.info("다국어 OCR 추출 시작")
            
            # 1단계: 빠른 언어 감지를 위한 기본 OCR (여러 언어 시도)
            quick_results = []
            test_languages = ['ko', 'ar', 'en']  # 한국어, 아랍어, 영어로 빠른 테스트
            
            detected_lang = 'ko'
            lang_confidence = 0.5
            best_quick_result = None
            
            for test_lang in test_languages:
                try:
                    quick_result = self.extract_text_with_language(image, test_lang, tier=2)
                    if quick_result["success"] and quick_result["text"].strip():
                        # 언어 감지 시도
                        test_detected_lang, test_confidence = self.detect_language(quick_result["text"])
                        
                        # 더 높은 신뢰도의 결과를 선택
                        if test_confidence > lang_confidence:
                            detected_lang = test_detected_lang
                            lang_confidence = test_confidence
                            best_quick_result = quick_result
                            logger.info(f"더 나은 언어 감지: {test_lang} -> {detected_lang} (신뢰도: {lang_confidence:.2f})")
                except Exception as e:
                    logger.warning(f"언어 {test_lang} 빠른 테스트 실패: {e}")
                    continue
            
            # 기본 결과가 없으면 한국어로 시도
            if best_quick_result is None:
                quick_result = self.extract_text_with_language(image, 'ko', tier=2)
                if not quick_result["success"]:
                    return quick_result
                detected_lang, lang_confidence = self.detect_language(quick_result["text"])
                best_quick_result = quick_result
            
            logger.info(f"최종 감지된 언어: {detected_lang} (신뢰도: {lang_confidence:.2f})")
            
            # 3단계: 감지된 언어로 정밀 OCR
            if detected_lang != 'ko' or lang_confidence > 0.8:
                precise_result = self.extract_text_with_language(image, detected_lang, tier=1)
                
                if precise_result["success"]:
                    lang_config = self.language_mapping[detected_lang]
                    
                    # Tier 1이 성공하고 신뢰도가 충분하면 사용
                    if (precise_result["tier"] == 1 and 
                        precise_result["confidence"] > lang_config["confidence_threshold"]):
                        precise_result["language_detection"] = {
                            "detected_language": detected_lang,
                            "confidence": lang_confidence,
                            "method": "financial_keywords_enhanced"
                        }
                        # 성공한 결과를 캐시에 저장
                        ocr_cache.cache_result(image_hash, precise_result)
                        return precise_result
                    
                    # Tier 2 결과 사용
                    elif precise_result["tier"] == 2:
                        precise_result["language_detection"] = {
                            "detected_language": detected_lang,
                            "confidence": lang_confidence,
                            "method": "financial_keywords_enhanced"
                        }
                        # 성공한 결과를 캐시에 저장
                        ocr_cache.cache_result(image_hash, precise_result)
                        return precise_result
            
            # 4단계: 기본 결과 반환 (한국어)
            final_result = self.extract_text_with_language(image, 'ko', tier=1)
            if final_result["success"]:
                final_result["language_detection"] = {
                    "detected_language": detected_lang,
                    "confidence": lang_confidence,
                    "fallback_to_korean": True
                }
                # 성공한 결과를 캐시에 저장
                ocr_cache.cache_result(image_hash, final_result)
                return final_result
            
            return {
                "success": False,
                "error": "모든 OCR 시도 실패",
                "text": "",
                "confidence": 0.0
            }
            
        except Exception as e:
            logger.error(f"다국어 OCR 추출 실패: {e}")
            return {
                "success": False,
                "error": str(e),
                "text": "",
                "confidence": 0.0
            }
    
    def analyze_multilingual_financial_content(self, text: str, language: str) -> Dict[str, Any]:
        """다국어 재무 콘텐츠 분석"""
        if language not in self.financial_keywords:
            language = 'ko'  # 기본값
        
        keywords = self.financial_keywords[language]
        found_keywords = [kw for kw in keywords if kw in text]
        
        # 숫자와 퍼센트 감지
        import re
        numbers = re.findall(r'[\d,]+(?:\.\d+)?', text)
        percentages = re.findall(r'[\d,]+(?:\.\d+)?%', text)
        
        # 언어별 통화 기호 감지
        currency_patterns = {
            'ko': r'[\d,]+(?:\.\d+)?\s*원',
            'zh-cn': r'[\d,]+(?:\.\d+)?\s*元',
            'zh-tw': r'[\d,]+(?:\.\d+)?\s*元',
            'ja': r'[\d,]+(?:\.\d+)?\s*円',
            'es': r'[\d,]+(?:\.\d+)?\s*EUR',
            'pt': r'[\d,]+(?:\.\d+)?\s*EUR',
            'fr': r'[\d,]+(?:\.\d+)?\s*EUR',
            'de': r'[\d,]+(?:\.\d+)?\s*EUR',
            'vi': r'[\d,]+(?:\.\d+)?\s*VND',
            'it': r'[\d,]+(?:\.\d+)?\s*EUR',
            'ar': r'[\d,]+(?:\.\d+)?\s*(?:ريال|درهم|دينار|جنيه)'
        }
        
        currency_amounts = []
        if language in currency_patterns:
            currency_amounts = re.findall(currency_patterns[language], text)
        
        return {
            "is_financial": len(found_keywords) > 0,
            "language": language,
            "financial_keywords": found_keywords,
            "numbers": numbers,
            "percentages": percentages,
            "currency_amounts": currency_amounts,
            "keyword_count": len(found_keywords),
            "financial_score": min(len(found_keywords) * 15 + len(currency_amounts) * 10, 100)
        }
    
    def get_service_info(self) -> Dict[str, Any]:
        """서비스 정보 반환"""
        return {
            "service_name": "MultilingualTwoTierService",
            "supported_languages": {
                code: {
                    "name": config["name"],
                    "standard_available": self.available_models[code]["standard"],
                    "custom_available": self.available_models[code]["custom"]
                }
                for code, config in self.language_mapping.items()
            },
            "tessdata_dir": self.tessdata_dir,
            "custom_models_dir": self.custom_models_dir,
            "capabilities": [
                "자동 언어 감지",
                "11개 언어 지원 (한국어, 중국어, 일본어, 스페인어, 포르투갈어, 프랑스어, 독일어, 베트남어, 이탈리아어, 아랍어)",
                "재무 특화 모델",
                "Two-tier fallback 시스템",
                "신뢰도 기반 모델 선택",
                "RTL(Right-to-Left) 언어 지원",
                "지수 백오프 재시도 로직",
                "Redis 기반 결과 캐싱"
            ]
        }