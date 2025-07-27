#!/usr/bin/env python3
"""
EasyOCR 지원 언어 확인
"""

import easyocr

def check_supported_languages():
    """EasyOCR 지원 언어 목록 확인"""
    
    print("🌍 EasyOCR 지원 언어 목록")
    print("=" * 60)
    
    try:
        # EasyOCR Reader 객체 생성하지 않고 지원 언어만 확인
        reader = easyocr.Reader(['en'], gpu=False, verbose=False)  # 임시로 영어만
        
        # 지원되는 언어 목록 가져오기
        supported_langs = reader.lang_list
        
        print(f"📊 총 지원 언어: {len(supported_langs)}개")
        print("-" * 60)
        
        # 언어별 분류
        asian_languages = []
        european_languages = []
        middle_eastern = []
        others = []
        
        # 주요 언어들 분류
        for lang in supported_langs:
            if lang in ['ko', 'ja', 'ch_sim', 'ch_tra', 'th', 'vi', 'hi']:
                asian_languages.append(lang)
            elif lang in ['en', 'fr', 'de', 'es', 'it', 'pt', 'ru', 'nl', 'pl', 'cs', 'sk', 'hu', 'ro', 'hr', 'sl', 'bg', 'lt', 'lv', 'et', 'fi', 'sv', 'da', 'no', 'is']:
                european_languages.append(lang)
            elif lang in ['ar', 'fa', 'ur', 'he', 'tr']:
                middle_eastern.append(lang)
            else:
                others.append(lang)
        
        # 아시아 언어
        print("🇰🇷 아시아 언어:")
        for lang in asian_languages:
            lang_name = get_language_name(lang)
            print(f"   {lang}: {lang_name}")
        
        print()
        
        # 유럽 언어 (일부만 표시)
        print("🇪🇺 유럽 언어 (주요):")
        major_european = ['en', 'fr', 'de', 'es', 'it', 'pt', 'ru', 'nl']
        for lang in major_european:
            if lang in european_languages:
                lang_name = get_language_name(lang)
                print(f"   {lang}: {lang_name}")
        
        if len(european_languages) > len(major_european):
            print(f"   ... 및 {len(european_languages) - len(major_european)}개 유럽 언어 더")
        
        print()
        
        # 중동 언어
        if middle_eastern:
            print("🕌 중동/아랍 언어:")
            for lang in middle_eastern:
                lang_name = get_language_name(lang)
                print(f"   {lang}: {lang_name}")
            print()
        
        # 전체 목록
        print("📋 전체 지원 언어 목록:")
        print("-" * 60)
        
        # 10개씩 묶어서 출력
        for i in range(0, len(supported_langs), 10):
            row = supported_langs[i:i+10]
            print("   " + ", ".join(row))
        
        # 다중 언어 사용 예시
        print("\n💡 다중 언어 사용 예시:")
        print("-" * 60)
        print("# 한국어 + 영어 + 일본어")
        print("reader = easyocr.Reader(['ko', 'en', 'ja'])")
        print()
        print("# 한국어 + 중국어 간체 + 영어")
        print("reader = easyocr.Reader(['ko', 'ch_sim', 'en'])")
        print()
        print("# 다중 유럽 언어")
        print("reader = easyocr.Reader(['en', 'fr', 'de', 'es'])")
        print()
        print("# 아랍어 + 영어")
        print("reader = easyocr.Reader(['ar', 'en'])")
        
        return supported_langs
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        return []

def get_language_name(lang_code):
    """언어 코드를 한국어 이름으로 변환"""
    
    lang_names = {
        'ko': '한국어',
        'en': '영어',
        'ja': '일본어',
        'ch_sim': '중국어 간체',
        'ch_tra': '중국어 번체',
        'th': '태국어',
        'vi': '베트남어',
        'hi': '힌디어',
        'fr': '프랑스어',
        'de': '독일어',
        'es': '스페인어',
        'it': '이탈리아어',
        'pt': '포르투갈어',
        'ru': '러시아어',
        'nl': '네덜란드어',
        'pl': '폴란드어',
        'cs': '체코어',
        'sk': '슬로바키아어',
        'hu': '헝가리어',
        'ro': '루마니아어',
        'hr': '크로아티아어',
        'sl': '슬로베니아어',
        'bg': '불가리아어',
        'lt': '리투아니아어',
        'lv': '라트비아어',
        'et': '에스토니아어',
        'fi': '핀란드어',
        'sv': '스웨덴어',
        'da': '덴마크어',
        'no': '노르웨이어',
        'is': '아이슬란드어',
        'ar': '아랍어',
        'fa': '페르시아어',
        'ur': '우르두어',
        'he': '히브리어',
        'tr': '터키어'
    }
    
    return lang_names.get(lang_code, lang_code)

def test_multilingual_ocr():
    """다국어 OCR 테스트"""
    
    print("\n🧪 다국어 OCR 성능 테스트")
    print("=" * 60)
    
    # 다양한 언어 조합 테스트
    language_combinations = [
        (['ko', 'en'], "한국어 + 영어"),
        (['ko', 'en', 'ja'], "한국어 + 영어 + 일본어"),
        (['ko', 'ch_sim', 'en'], "한국어 + 중국어 간체 + 영어"),
        (['en', 'fr', 'de', 'es'], "다중 유럽어")
    ]
    
    for langs, description in language_combinations:
        try:
            print(f"\n🔍 테스트: {description}")
            print(f"   언어 코드: {langs}")
            
            # Reader 생성 시간 측정
            import time
            start_time = time.time()
            reader = easyocr.Reader(langs, gpu=False, verbose=False)
            init_time = time.time() - start_time
            
            print(f"   초기화 시간: {init_time:.1f}초")
            print(f"   ✅ 성공")
            
        except Exception as e:
            print(f"   ❌ 실패: {e}")

def save_language_info():
    """언어 정보를 파일로 저장"""
    
    try:
        reader = easyocr.Reader(['en'], gpu=False, verbose=False)
        supported_langs = reader.lang_list
        
        timestamp = __import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')
        info_file = f"/Users/kevin/Desktop/EasyOCR_지원언어_{timestamp}.txt"
        
        with open(info_file, 'w', encoding='utf-8') as f:
            f.write("EasyOCR 지원 언어 목록\n")
            f.write("=" * 30 + "\n")
            f.write(f"총 {len(supported_langs)}개 언어 지원\n\n")
            
            f.write("주요 아시아 언어:\n")
            f.write("- ko: 한국어\n")
            f.write("- ja: 일본어\n") 
            f.write("- ch_sim: 중국어 간체\n")
            f.write("- ch_tra: 중국어 번체\n")
            f.write("- th: 태국어\n")
            f.write("- vi: 베트남어\n")
            f.write("- hi: 힌디어\n\n")
            
            f.write("주요 유럽 언어:\n")
            f.write("- en: 영어\n")
            f.write("- fr: 프랑스어\n")
            f.write("- de: 독일어\n")
            f.write("- es: 스페인어\n")
            f.write("- it: 이탈리아어\n")
            f.write("- pt: 포르투갈어\n")
            f.write("- ru: 러시아어\n\n")
            
            f.write("전체 지원 언어:\n")
            for i, lang in enumerate(supported_langs, 1):
                f.write(f"{i:2d}. {lang}\n")
        
        print(f"\n📄 언어 정보 저장: {info_file}")
        
    except Exception as e:
        print(f"❌ 파일 저장 실패: {e}")

if __name__ == "__main__":
    print("🚀 EasyOCR 언어 지원 확인 시작")
    
    # 지원 언어 확인
    supported_languages = check_supported_languages()
    
    # 다국어 테스트
    test_multilingual_ocr()
    
    # 정보 저장
    save_language_info()
    
    print(f"\n🎉 완료! EasyOCR은 {len(supported_languages)}개 언어를 지원합니다.")
    print("   필요에 따라 여러 언어를 조합하여 사용할 수 있습니다.")