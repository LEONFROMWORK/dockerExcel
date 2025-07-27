"""
Korean Excel Template Crawler Service
한국어 엑셀 템플릿 크롤링 및 자동 분류 서비스
"""
import asyncio
import aiohttp
import aiofiles
import logging
import os
import re
import json
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin, urlparse
from dataclasses import dataclass, asdict
import hashlib

from bs4 import BeautifulSoup
from ..models.template_metadata import EnhancedTemplateMetadata, TemplateCategory, TemplateComplexity

logger = logging.getLogger(__name__)


@dataclass
class CrawledTemplate:
    """크롤링된 템플릿 정보"""
    title: str
    description: str
    download_url: str
    category_major: str
    category_minor: str
    file_name: str
    file_size: Optional[int] = None
    related_files: List[str] = None
    source_url: str = ""
    crawled_at: str = ""
    local_path: str = ""
    
    def __post_init__(self):
        if self.related_files is None:
            self.related_files = []
        if not self.crawled_at:
            self.crawled_at = datetime.now().isoformat()


class KoreanTemplateCrawler:
    """한국어 엑셀 템플릿 크롤러"""
    
    def __init__(self):
        self.base_url = "https://excel.yesform.com"
        self.login_url = "https://www.yesform.com/z_n/member/login.php"
        self.start_url = "https://excel.yesform.com/docs/formList.php?division=A12"
        
        # 실제 카테고리 URL 매핑
        self.category_urls = {
            "업무프로그램": "https://excel.yesform.com/docs/formList.php?division=A12B11",
            "업무템플릿": "https://excel.yesform.com/docs/formList.php?division=A12B12", 
            "차트/대시보드": "https://excel.yesform.com/docs/formList.php?division=A12B13"
        }
        
        # 로그인 정보
        self.username = "j1global"
        self.password = "wpdldnjs11!"
        
        # 저장 경로
        self.download_dir = Path("downloads/korean_templates")
        self.metadata_dir = Path("metadata/korean_templates")
        self.reports_dir = Path("reports/korean_templates")
        
        # 디렉토리 생성
        for directory in [self.download_dir, self.metadata_dir, self.reports_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        
        # 세션 및 상태
        self.session = None
        self.crawled_templates = []
        self.failed_downloads = []
        self.categories_mapping = {
            "엑셀프로그램": TemplateCategory.GENERAL,
            "엑셀템플릿": TemplateCategory.GENERAL,
            "차트/대시보드": TemplateCategory.GENERAL
        }
        
        # 진행 상황 추적
        self.progress = {
            "total_categories": 0,
            "processed_categories": 0,
            "total_templates": 0,
            "downloaded_templates": 0,
            "failed_downloads": 0,
            "start_time": None,
            "current_status": "준비 중"
        }
    
    async def start_crawling(self) -> Dict[str, Any]:
        """크롤링 시작"""
        logger.info("🚀 한국어 템플릿 크롤링 시작")
        self.progress["start_time"] = datetime.now()
        self.progress["current_status"] = "로그인 중"
        
        try:
            # 세션 초기화 및 로그인
            await self._initialize_session()
            await self._login()
            
            # 대분류 카테고리 수집
            major_categories = await self._get_major_categories()
            self.progress["total_categories"] = len(major_categories)
            
            logger.info(f"📂 발견된 대분류: {len(major_categories)}개")
            
            # 각 대분류별로 크롤링
            for major_category in major_categories:
                self.progress["current_status"] = f"처리 중: {major_category['name']}"
                await self._crawl_major_category(major_category)
                self.progress["processed_categories"] += 1
            
            # 결과 정리 및 저장
            await self._save_crawling_results()
            await self._generate_summary_report()
            
            self.progress["current_status"] = "완료"
            
            return {
                "status": "success",
                "message": "크롤링이 성공적으로 완료되었습니다",
                "summary": {
                    "total_templates": len(self.crawled_templates),
                    "successful_downloads": self.progress["downloaded_templates"],
                    "failed_downloads": self.progress["failed_downloads"],
                    "categories_processed": self.progress["processed_categories"],
                    "duration": str(datetime.now() - self.progress["start_time"])
                }
            }
        
        except Exception as e:
            logger.error(f"❌ 크롤링 중 오류 발생: {e}")
            self.progress["current_status"] = f"오류: {str(e)}"
            raise
        
        finally:
            if self.session:
                await self.session.close()
    
    async def _initialize_session(self):
        """HTTP 세션 초기화"""
        timeout = aiohttp.ClientTimeout(total=30)
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
        )
    
    async def _login(self):
        """사이트 로그인 - 사용자 제공 쿠키 우선 사용"""
        logger.info("🔐 로그인 시도 중...")
        
        # 외부 쿠키 파일 확인
        cookie_file = Path("user_cookies.txt")
        if cookie_file.exists():
            return await self._load_user_cookies()
        
        # 자동 로그인 시도
        return await self._auto_login()
    
    async def _load_user_cookies(self):
        """사용자가 제공한 쿠키 로드"""
        cookie_file = Path("user_cookies.txt")
        logger.info("🍪 사용자 제공 쿠키 로드 중...")
        
        try:
            async with aiofiles.open(cookie_file, 'r', encoding='utf-8') as f:
                cookie_data = await f.read()
            
            # 쿠키 형식 파싱 (name=value; name2=value2 형식)
            cookies_applied = 0
            from urllib.parse import urlparse
            
            for cookie_line in cookie_data.strip().split('\n'):
                if '=' in cookie_line and not cookie_line.strip().startswith('#'):
                    for cookie_pair in cookie_line.split(';'):
                        cookie_pair = cookie_pair.strip()
                        if '=' in cookie_pair:
                            name, value = cookie_pair.split('=', 1)
                            
                            # 수동으로 쿠키 헤더 설정
                            cookie_header = f"{name.strip()}={value.strip()}"
                            
                            # 세션의 기본 헤더에 쿠키 추가
                            if 'Cookie' not in self.session.headers:
                                self.session.headers['Cookie'] = cookie_header
                            else:
                                self.session.headers['Cookie'] += f"; {cookie_header}"
                            
                            cookies_applied += 1
                            logger.info(f"쿠키 설정: {name.strip()}={value.strip()[:10]}...")
            
            logger.info(f"총 {cookies_applied}개 쿠키 적용됨")
            
            # 쿠키 적용 확인을 위한 테스트 요청
            async with self.session.get(self.base_url) as response:
                logger.info(f"쿠키 테스트 응답: {response.status}")
                # 응답 내용 확인
                try:
                    content = await response.text(encoding='utf-8')
                except UnicodeDecodeError:
                    content_bytes = await response.read()
                    try:
                        content = content_bytes.decode('euc-kr')
                    except UnicodeDecodeError:
                        content = content_bytes.decode('cp949', errors='ignore')
                
                # 로그인 상태 확인 (로그아웃 링크가 있는지 확인)
                is_logged_in = '로그아웃' in content or 'logout' in content.lower()
                
                if is_logged_in:
                    logger.info("✅ 사용자 쿠키 적용 성공 - 로그인 상태 확인됨")
                    return True
                else:
                    logger.warning(f"⚠️  쿠키는 적용되었지만 로그인 상태 불확실")
                    # 일단 계속 진행해보기
                    return True
                    
        except Exception as e:
            logger.error(f"❌ 쿠키 로드 실패: {e}")
            return False
    
    async def _auto_login(self):
        """자동 로그인 시도"""
        try:
            # 먼저 메인 사이트에 접속하여 세션 생성
            async with self.session.get(self.base_url) as response:
                logger.info(f"메인 사이트 접속: {response.status}")
            
            # 로그인 페이지 접속
            async with self.session.get(self.login_url) as response:
                if response.status != 200:
                    raise Exception(f"로그인 페이지 접속 실패: {response.status}")
                
                # 한국어 사이트 인코딩 처리
                try:
                    login_page = await response.text(encoding='utf-8')
                except UnicodeDecodeError:
                    # 인코딩 오류 시 대체 방법 사용
                    content = await response.read()
                    try:
                        login_page = content.decode('euc-kr')
                    except UnicodeDecodeError:
                        login_page = content.decode('cp949', errors='ignore')
                
                soup = BeautifulSoup(login_page, 'html.parser')
                logger.info(f"로그인 페이지 로드 완료: {len(login_page)} 바이트")
                
                # 로그인 폼 찾기
                login_form = soup.find('form', {'name': 'login'}) or soup.find('form')
                if login_form:
                    action = login_form.get('action', self.login_url)
                    if not action.startswith('http'):
                        action = f"https://www.yesform.com{action}" if action.startswith('/') else f"https://www.yesform.com/z_n/member/{action}"
                    logger.info(f"로그인 액션 URL: {action}")
                else:
                    action = "https://www.yesform.com/z_n/member/login_check.php"
                    logger.info("기본 로그인 액션 URL 사용")
                
                # CSRF 토큰이나 히든 필드 확인
                hidden_inputs = soup.find_all('input', type='hidden')
                login_data = {
                    'pId': self.username,
                    'pPwd': self.password,
                }
                
                # 히든 필드 추가
                for hidden in hidden_inputs:
                    if hidden.get('name'):
                        login_data[hidden.get('name')] = hidden.get('value', '')
                        logger.info(f"히든 필드 추가: {hidden.get('name')} = {hidden.get('value', '')}")
            
            # 로그인 요청
            logger.info(f"로그인 데이터: {login_data}")
            async with self.session.post(action, data=login_data) as response:
                logger.info(f"로그인 응답 상태: {response.status}")
                logger.info(f"로그인 응답 URL: {response.url}")
                
                if response.status != 200:
                    raise Exception(f"로그인 요청 실패: {response.status}")
                
                # 응답 내용 확인
                try:
                    response_text = await response.text(encoding='utf-8')
                except UnicodeDecodeError:
                    content = await response.read()
                    try:
                        response_text = content.decode('euc-kr')
                    except UnicodeDecodeError:
                        response_text = content.decode('cp949', errors='ignore')
                
                # 로그인 성공 여부 확인
                if '로그인' in response_text and 'login' in str(response.url).lower():
                    logger.warning(f"로그인 실패 가능성 - URL: {response.url}")
                    logger.warning(f"응답 내용 일부: {response_text[:200]}")
                    # 일단 계속 진행해보기 - 실제 페이지 접근에서 판단
                else:
                    logger.info("로그인 응답 정상 - 로그인 성공 가능성 높음")
                
                logger.info("✅ 로그인 시도 완료")
                return True
        
        except Exception as e:
            logger.error(f"❌ 로그인 실패: {e}")
            raise
    
    async def _get_major_categories(self) -> List[Dict[str, str]]:
        """대분류 카테고리 수집"""
        logger.info("📂 대분류 카테고리 수집 중...")
        
        # 하드코딩된 카테고리 URL 사용 (실제 사이트 구조 기반)
        categories = []
        for name, url in self.category_urls.items():
            categories.append({
                'name': name,
                'url': url
            })
            
        logger.info(f"✅ 대분류 {len(categories)}개 수집: {[cat['name'] for cat in categories]}")
        return categories
    
    async def _crawl_major_category(self, major_category: Dict[str, str]):
        """대분류별 크롤링"""
        logger.info(f"🔍 '{major_category['name']}' 카테고리 크롤링 시작")
        
        try:
            # 대분류 페이지 접속
            async with self.session.get(major_category['url']) as response:
                if response.status != 200:
                    logger.error(f"대분류 페이지 접속 실패: {response.status}")
                    return
                
                # 한국어 사이트 인코딩 처리
                try:
                    page_content = await response.text(encoding='utf-8')
                except UnicodeDecodeError:
                    content = await response.read()
                    try:
                        page_content = content.decode('euc-kr')
                    except UnicodeDecodeError:
                        page_content = content.decode('cp949', errors='ignore')
                soup = BeautifulSoup(page_content, 'html.parser')
                
                # 중분류 수집 및 처리
                minor_categories = await self._get_minor_categories(soup, major_category['url'])
                logger.info(f"📁 '{major_category['name']}'에서 중분류 {len(minor_categories)}개 발견")
                
                if not minor_categories:
                    # 중분류가 없으면 직접 템플릿 수집
                    template_links = await self._get_template_links(soup)
                    logger.info(f"📋 '{major_category['name']}'에서 템플릿 {len(template_links)}개 발견")
                    
                    for template_link in template_links:
                        await self._process_template(major_category['name'], "일반", template_link)
                else:
                    # 각 중분류별로 템플릿 수집
                    for minor_category in minor_categories:
                        await self._crawl_minor_category_with_pagination(major_category['name'], minor_category)
        
        except Exception as e:
            logger.error(f"❌ '{major_category['name']}' 크롤링 실패: {e}")
    
    async def _get_minor_categories(self, soup: BeautifulSoup, base_url: str) -> List[Dict[str, str]]:
        """중분류 카테고리 수집"""
        minor_categories = []
        
        # 필터 섹션에서 중분류 찾기
        filter_section = soup.find('div', class_='filter__format')
        if not filter_section:
            logger.warning("중분류 필터 섹션을 찾을 수 없습니다")
            return minor_categories
        
        # input 요소들에서 카테고리 추출
        for input_elem in filter_section.find_all('input'):
            value = input_elem.get('value')
            next_label = input_elem.find_next_sibling('label')
            
            if value and next_label:
                category_name = next_label.get_text(strip=True)
                if category_name and value != 'all':  # 'all' 제외
                    minor_categories.append({
                        'name': category_name,
                        'value': value,
                        'base_url': base_url
                    })
        
        return minor_categories
    
    async def _crawl_minor_category(self, major_name: str, minor_category: Dict[str, str]):
        """중분류별 템플릿 크롤링"""
        logger.info(f"📄 중분류 '{minor_category['name']}' 템플릿 수집 중...")
        
        try:
            # 중분류 필터 적용된 URL 생성
            category_url = f"{minor_category['base_url']}&format={minor_category['value']}"
            
            async with self.session.get(category_url) as response:
                if response.status != 200:
                    logger.error(f"중분류 페이지 접속 실패: {response.status}")
                    return
                
                # 한국어 사이트 인코딩 처리
                try:
                    page_content = await response.text(encoding='utf-8')
                except UnicodeDecodeError:
                    content = await response.read()
                    try:
                        page_content = content.decode('euc-kr')
                    except UnicodeDecodeError:
                        page_content = content.decode('cp949', errors='ignore')
                soup = BeautifulSoup(page_content, 'html.parser')
                
                # 템플릿 목록 수집
                template_links = await self._get_template_links(soup)
                
                logger.info(f"📋 '{minor_category['name']}'에서 템플릿 {len(template_links)}개 발견")
                
                # 각 템플릿 상세 정보 수집 및 다운로드
                for template_link in template_links:
                    await self._process_template(major_name, minor_category['name'], template_link)
        
        except Exception as e:
            logger.error(f"❌ 중분류 '{minor_category['name']}' 처리 실패: {e}")
    
    async def _get_minor_categories(self, soup: BeautifulSoup, base_url: str) -> List[Dict[str, str]]:
        """중분류 카테고리 수집"""
        minor_categories = []
        
        try:
            # 필터 섹션에서 중분류 찾기
            filter_sections = soup.find_all('div', class_='filter__item')
            
            for section in filter_sections:
                section_title = section.find('h3')
                if not section_title or '카테고리' not in section_title.get_text():
                    continue
                
                # 카테고리 옵션들 찾기
                for label in section.find_all('label'):
                    input_elem = label.find('input')
                    if input_elem and input_elem.get('value') and input_elem.get('value') != 'all':
                        category_name = label.get_text(strip=True)
                        category_value = input_elem.get('value')
                        
                        minor_categories.append({
                            'name': category_name,
                            'value': category_value,
                            'base_url': base_url
                        })
            
            return minor_categories
        except Exception as e:
            logger.error(f"중분류 수집 실패: {e}")
            return []
    
    async def _crawl_minor_category_with_pagination(self, major_name: str, minor_category: Dict[str, str]):
        """중분류별 페이지네이션 포함 크롤링"""
        logger.info(f"🔍 중분류 '{minor_category['name']}' 페이지네이션 크롤링 시작")
        
        page = 1
        while True:
            try:
                # 페이지별 URL 생성
                if '?' in minor_category['base_url']:
                    page_url = f"{minor_category['base_url']}&category={minor_category['value']}&page={page}"
                else:
                    page_url = f"{minor_category['base_url']}?category={minor_category['value']}&page={page}"
                
                async with self.session.get(page_url) as response:
                    if response.status != 200:
                        break
                    
                    # 한국어 사이트 인코딩 처리
                    try:
                        page_content = await response.text(encoding='utf-8')
                    except UnicodeDecodeError:
                        content = await response.read()
                        try:
                            page_content = content.decode('euc-kr')
                        except UnicodeDecodeError:
                            page_content = content.decode('cp949', errors='ignore')
                    
                    soup = BeautifulSoup(page_content, 'html.parser')
                    
                    # 템플릿 링크 수집
                    template_links = await self._get_template_links(soup)
                    
                    if not template_links:
                        logger.info(f"📄 '{minor_category['name']}' 페이지 {page}: 더 이상 템플릿이 없음")
                        break
                    
                    logger.info(f"📄 '{minor_category['name']}' 페이지 {page}: {len(template_links)}개 템플릿 발견")
                    
                    # 각 템플릿 처리
                    for template_link in template_links:
                        await self._process_template(major_name, minor_category['name'], template_link)
                    
                    page += 1
                    
                    # 페이지 제한 (무한 루프 방지)
                    if page > 50:
                        logger.warning(f"⚠️  페이지 제한 도달: {minor_category['name']}")
                        break
                    
                    # 요청 간격 조절
                    await asyncio.sleep(1)
                    
            except Exception as e:
                logger.error(f"❌ 중분류 '{minor_category['name']}' 페이지 {page} 처리 실패: {e}")
                break
    
    async def _get_template_links(self, soup: BeautifulSoup) -> List[str]:
        """템플릿 링크 수집"""
        template_links = []
        
        # 리스트 섹션에서 템플릿 링크 찾기 (.ListSection 클래스 사용)
        list_section = soup.find('div', class_='ListSection')
        if not list_section:
            # 대체 선택자들 시도
            list_section = soup.find('div', id='ListSection') or soup.find('section', class_='list-section')
            if not list_section:
                logger.warning("템플릿 리스트 섹션을 찾을 수 없습니다")
                return template_links
        
        # xls로 시작하는 템플릿 링크 수집
        for link in list_section.find_all('a', href=True):
            href = link.get('href')
            if href and (href.startswith('/xls/') or 'xls' in href):
                full_url = urljoin(self.base_url, href)
                template_links.append(full_url)
                logger.info(f"템플릿 링크 발견: {href}")
        
        return list(set(template_links))  # 중복 제거
    
    async def _process_template(self, major_category: str, minor_category: str, template_url: str):
        """개별 템플릿 처리"""
        try:
            # 상세 페이지 접속
            async with self.session.get(template_url) as response:
                if response.status != 200:
                    logger.error(f"템플릿 상세 페이지 접속 실패: {response.status}")
                    return
                
                # 한국어 사이트 인코딩 처리
                try:
                    page_content = await response.text(encoding='utf-8')
                except UnicodeDecodeError:
                    content = await response.read()
                    try:
                        page_content = content.decode('euc-kr')
                    except UnicodeDecodeError:
                        page_content = content.decode('cp949', errors='ignore')
                soup = BeautifulSoup(page_content, 'html.parser')
                
                # 템플릿 정보 추출
                template_info = await self._extract_template_info(soup, template_url)
                if not template_info:
                    return
                
                # 카테고리 정보 추가
                template_info['category_major'] = major_category
                template_info['category_minor'] = minor_category
                
                # 템플릿 다운로드
                downloaded_path = await self._download_template(template_info)
                if downloaded_path:
                    template_info['local_path'] = str(downloaded_path)
                    self.progress["downloaded_templates"] += 1
                else:
                    self.progress["failed_downloads"] += 1
                    self.failed_downloads.append(template_info)
                
                # 연관 파일 처리
                related_files = await self._get_related_files(soup)
                template_info['related_files'] = related_files
                
                # 크롤링된 템플릿 목록에 추가
                crawled_template = CrawledTemplate(**template_info)
                self.crawled_templates.append(crawled_template)
                
                logger.info(f"✅ 템플릿 처리 완료: {template_info['title']}")
        
        except Exception as e:
            logger.error(f"❌ 템플릿 처리 실패 ({template_url}): {e}")
    
    async def _extract_template_info(self, soup: BeautifulSoup, source_url: str) -> Optional[Dict[str, str]]:
        """템플릿 정보 추출"""
        try:
            # 제목 추출
            title_elem = soup.find('h1')
            if not title_elem:
                title_elem = soup.find(class_='title')
                if title_elem:
                    title_elem = title_elem.find('h1')
            
            title = title_elem.get_text(strip=True) if title_elem else "제목 없음"
            
            # 설명 추출
            description_elem = soup.find('div', id='description')
            description = description_elem.get_text(strip=True) if description_elem else "설명 없음"
            
            # 다운로드 URL 추출 (사용자 제공 구조에 맞게 수정)
            download_url = None
            
            # format-List 섹션에서 Excel 다운로드 링크 찾기
            format_list = soup.find('ul', class_='format-List')
            if format_list:
                # Excel 아이콘이 있는 링크 찾기
                excel_links = format_list.find_all('a', href=True)
                for link in excel_links:
                    href = link.get('href')
                    # dw_form.php가 포함되고 sample 파라미터가 없는 링크 (메인 파일)
                    if href and 'dw_form.php' in href and 'sample=' not in href:
                        download_url = href
                        break
            
            # 대체 방법: img alt 속성으로 찾기
            if not download_url:
                download_elem = soup.find('img', alt='Microsoft Excel (xlsx)')
                if download_elem:
                    download_link = download_elem.find_parent('a')
                    download_url = download_link.get('href') if download_link else None
            
            if not download_url:
                logger.warning(f"다운로드 링크를 찾을 수 없습니다: {title}")
                return None
            
            # 파일명 생성 (제목 기반)
            safe_title = re.sub(r'[^\w\-_\.]', '_', title)
            file_name = f"{safe_title}.xlsx"
            
            # 다운로드 URL을 올바른 도메인으로 생성
            if download_url.startswith('/'):
                full_download_url = f"https://www.yesform.com{download_url}"
            elif download_url.startswith('http'):
                full_download_url = download_url
            else:
                full_download_url = f"https://www.yesform.com/z_n/forms/{download_url}"
            
            logger.info(f"생성된 다운로드 URL: {full_download_url}")
            
            return {
                'title': title,
                'description': description,
                'download_url': full_download_url,
                'file_name': file_name,
                'source_url': source_url
            }
        
        except Exception as e:
            logger.error(f"템플릿 정보 추출 실패: {e}")
            return None
    
    async def _download_template(self, template_info: Dict[str, str]) -> Optional[Path]:
        """템플릿 파일 다운로드"""
        try:
            download_url = template_info['download_url']
            file_name = template_info['file_name']
            
            # 카테고리별 디렉토리 생성
            category_dir = self.download_dir / template_info['category_major'] / template_info['category_minor']
            category_dir.mkdir(parents=True, exist_ok=True)
            
            # 파일 경로
            file_path = category_dir / file_name
            
            # 이미 다운로드된 파일이 있으면 스킵
            if file_path.exists():
                logger.info(f"⏭️  이미 존재하는 파일: {file_name}")
                return file_path
            
            # 다운로드 헤더 설정 (브라우저 시뮬레이션)
            download_headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
            
            logger.info(f"다운로드 시작: {download_url}")
            
            # 파일 다운로드
            async with self.session.get(download_url, headers=download_headers) as response:
                logger.info(f"다운로드 응답: {response.status}, Content-Type: {response.headers.get('Content-Type', 'unknown')}")
                
                if response.status != 200:
                    logger.error(f"파일 다운로드 실패: {response.status}")
                    return None
                
                # Content-Type 확인
                content_type = response.headers.get('Content-Type', '').lower()
                if 'text/html' in content_type:
                    logger.warning(f"HTML 응답 감지됨: {content_type}")
                    # HTML 내용 일부 로그
                    try:
                        html_content = await response.text(encoding='utf-8')
                        logger.warning(f"HTML 내용 일부: {html_content[:200]}")
                    except:
                        pass
                    return None
                
                # 파일 저장
                async with aiofiles.open(file_path, 'wb') as f:
                    async for chunk in response.content.iter_chunked(8192):
                        await f.write(chunk)
                
                # 다운로드된 파일이 실제 Excel 파일인지 확인
                if await self._verify_excel_file(file_path):
                    logger.info(f"💾 Excel 파일 다운로드 완료: {file_name}")
                    return file_path
                else:
                    # HTML 파일이나 잘못된 파일인 경우 삭제
                    file_path.unlink()
                    logger.warning(f"❌ 잘못된 파일 형식 (HTML/오류 페이지): {file_name}")
                    return None
        
        except Exception as e:
            logger.error(f"파일 다운로드 실패: {e}")
            return None
    
    async def _verify_excel_file(self, file_path: Path) -> bool:
        """다운로드된 파일이 실제 Excel 파일인지 확인"""
        try:
            # 파일 크기 확인 (너무 작으면 오류 페이지일 가능성)
            if file_path.stat().st_size < 1024:  # 1KB 미만
                return False
            
            # 파일 시그니처 확인 (Excel 파일은 ZIP 기반)
            with open(file_path, 'rb') as f:
                header = f.read(4)
                # Excel 2007+ 파일은 ZIP 형식 (PK로 시작)
                if header.startswith(b'PK'):
                    return True
                # Excel 97-2003 파일 시그니처
                elif header.startswith(b'\xd0\xcf\x11\xe0'):
                    return True
                # HTML 파일 체크
                elif header.startswith(b'<!DO') or header.startswith(b'<htm'):
                    return False
            
            return False
        except Exception:
            return False
    
    async def _get_related_files(self, soup: BeautifulSoup) -> List[str]:
        """연관 파일 목록 수집"""
        related_files = []
        
        try:
            # 연관 파일 섹션 찾기
            related_section = soup.find('div', class_='swiper-box reco')
            if not related_section:
                return related_files
            
            # 연관 파일 링크 수집
            for link in related_section.find_all('a', href=True):
                href = link.get('href')
                if href and 'view.php' in href:
                    related_files.append(urljoin(self.base_url, href))
        
        except Exception as e:
            logger.error(f"연관 파일 수집 실패: {e}")
        
        return related_files
    
    async def _save_crawling_results(self):
        """크롤링 결과 저장"""
        logger.info("💾 크롤링 결과 저장 중...")
        
        try:
            # JSON 형태로 저장
            results = {
                'crawling_info': {
                    'start_time': self.progress['start_time'].isoformat(),
                    'end_time': datetime.now().isoformat(),
                    'total_templates': len(self.crawled_templates),
                    'successful_downloads': self.progress['downloaded_templates'],
                    'failed_downloads': self.progress['failed_downloads']
                },
                'templates': [asdict(template) for template in self.crawled_templates],
                'failed_downloads': self.failed_downloads
            }
            
            results_file = self.metadata_dir / f"crawling_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            async with aiofiles.open(results_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(results, ensure_ascii=False, indent=2))
            
            logger.info(f"✅ 크롤링 결과 저장 완료: {results_file}")
        
        except Exception as e:
            logger.error(f"❌ 크롤링 결과 저장 실패: {e}")
    
    async def _generate_summary_report(self):
        """요약 보고서 생성"""
        logger.info("📊 요약 보고서 생성 중...")
        
        try:
            # 카테고리별 통계
            category_stats = {}
            for template in self.crawled_templates:
                major = template.category_major
                minor = template.category_minor
                
                if major not in category_stats:
                    category_stats[major] = {}
                if minor not in category_stats[major]:
                    category_stats[major][minor] = 0
                
                category_stats[major][minor] += 1
            
            # 보고서 내용 생성
            report_content = f"""
# 한국어 엑셀 템플릿 크롤링 보고서

## 크롤링 개요
- 시작 시간: {self.progress['start_time']}
- 종료 시간: {datetime.now()}
- 총 템플릿 수: {len(self.crawled_templates)}
- 성공한 다운로드: {self.progress['downloaded_templates']}
- 실패한 다운로드: {self.progress['failed_downloads']}

## 카테고리별 통계

"""
            
            for major, minors in category_stats.items():
                report_content += f"### {major}\n"
                total_in_major = sum(minors.values())
                report_content += f"- 총 {total_in_major}개 템플릿\n"
                
                for minor, count in minors.items():
                    report_content += f"  - {minor}: {count}개\n"
                report_content += "\n"
            
            # 실패한 다운로드 목록
            if self.failed_downloads:
                report_content += "## 실패한 다운로드\n\n"
                for failed in self.failed_downloads:
                    report_content += f"- {failed.get('title', 'Unknown')}\n"
                    report_content += f"  - URL: {failed.get('source_url', 'Unknown')}\n"
            
            # 보고서 파일 저장
            report_file = self.reports_dir / f"crawling_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            
            async with aiofiles.open(report_file, 'w', encoding='utf-8') as f:
                await f.write(report_content)
            
            logger.info(f"✅ 요약 보고서 생성 완료: {report_file}")
        
        except Exception as e:
            logger.error(f"❌ 요약 보고서 생성 실패: {e}")
    
    def get_progress(self) -> Dict[str, Any]:
        """현재 진행 상황 반환"""
        if self.progress['start_time']:
            duration = datetime.now() - self.progress['start_time']
            self.progress['duration'] = str(duration)
        
        return self.progress.copy()


# 전역 크롤러 인스턴스
korean_template_crawler = KoreanTemplateCrawler()