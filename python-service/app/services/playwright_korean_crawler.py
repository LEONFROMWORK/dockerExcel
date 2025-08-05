"""
Playwright 기반 한국어 템플릿 크롤러
실제 브라우저 자동화를 통한 인증 및 다운로드
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime
import json
import re

try:
    from playwright.async_api import async_playwright
    from playwright_stealth import Stealth

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    try:
        from playwright.async_api import async_playwright

        PLAYWRIGHT_AVAILABLE = True
        Stealth = None  # stealth 없이도 동작
    except ImportError:
        PLAYWRIGHT_AVAILABLE = False

from .korean_template_crawler import CrawledTemplate

logger = logging.getLogger(__name__)


class PlaywrightKoreanCrawler:
    """Playwright 기반 한국어 템플릿 크롤러"""

    def __init__(self):
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError(
                "Playwright가 설치되지 않았습니다. pip install playwright playwright-stealth"
            )

        self.base_url = "https://excel.yesform.com"
        self.login_url = "https://www.yesform.com/z_n/member/login.php"

        # 로그인 정보
        self.username = "j1global"
        self.password = "wpdldnjs11!"

        # 저장 경로
        self.download_dir = Path("downloads/korean_templates_playwright")
        self.metadata_dir = Path("metadata/korean_templates_playwright")
        self.reports_dir = Path("reports/korean_templates_playwright")

        # 디렉토리 생성
        for directory in [self.download_dir, self.metadata_dir, self.reports_dir]:
            directory.mkdir(parents=True, exist_ok=True)

        # 상태 관리
        self.browser = None
        self.context = None
        self.page = None
        self.crawled_templates = []
        self.failed_downloads = []

        # 진행 상황 추적
        self.progress = {
            "total_templates": 0,
            "downloaded_templates": 0,
            "failed_downloads": 0,
            "current_status": "준비 중",
            "start_time": None,
        }

        # 카테고리 URL 매핑
        self.category_urls = {
            "업무프로그램": "https://excel.yesform.com/docs/formList.php?division=A12B11",
            "업무템플릿": "https://excel.yesform.com/docs/formList.php?division=A12B12",
            "차트/대시보드": "https://excel.yesform.com/docs/formList.php?division=A12B13",
        }

    async def start_crawling(self) -> Dict[str, Any]:
        """크롤링 시작"""
        logger.info("🚀 Playwright 기반 크롤링 시작")
        self.progress["start_time"] = datetime.now()
        self.progress["current_status"] = "브라우저 초기화 중"

        try:
            # 브라우저 초기화
            await self._initialize_browser()

            # 로그인
            self.progress["current_status"] = "로그인 중"
            await self._login()

            # 각 카테고리별 크롤링
            for category_name, category_url in self.category_urls.items():
                self.progress["current_status"] = f"처리 중: {category_name}"
                await self._crawl_category(category_name, category_url)

            # 결과 저장
            await self._save_results()

            self.progress["current_status"] = "완료"

            return {
                "status": "success",
                "message": "Playwright 크롤링이 성공적으로 완료되었습니다",
                "summary": {
                    "total_templates": len(self.crawled_templates),
                    "successful_downloads": self.progress["downloaded_templates"],
                    "failed_downloads": self.progress["failed_downloads"],
                    "duration": str(datetime.now() - self.progress["start_time"]),
                },
            }

        except Exception as e:
            logger.error(f"❌ 크롤링 중 오류 발생: {e}")
            self.progress["current_status"] = f"오류: {str(e)}"
            raise

        finally:
            await self._cleanup()

    async def _initialize_browser(self):
        """브라우저 초기화"""
        logger.info("🌐 브라우저 초기화 중...")

        playwright = await async_playwright().start()

        # 브라우저 시작 (headless=False로 디버깅 가능)
        self.browser = await playwright.chromium.launch(
            headless=True,  # False로 변경하면 브라우저가 화면에 나타남
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
        )

        # 컨텍스트 생성
        self.context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )

        # 페이지 생성
        self.page = await self.context.new_page()

        # 기본 봇 감지 방지 설정
        await self.page.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });

            // Chrome에서 automation 관련 요소들 숨기기
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
        """
        )

        logger.info("✅ 브라우저 초기화 완료")

    async def _login(self):
        """로그인"""
        logger.info("🔐 로그인 중...")

        try:
            # 로그인 페이지 접속
            await self.page.goto(self.login_url, wait_until="networkidle")

            # 페이지 스크린샷 (디버깅용)
            await self.page.screenshot(path="login_page.png")
            logger.info("📸 로그인 페이지 스크린샷 저장: login_page.png")

            # 페이지 내용 확인
            page_content = await self.page.content()
            logger.info(f"📄 로그인 페이지 길이: {len(page_content)} 문자")

            # 다양한 입력 필드 셀렉터 시도
            username_selectors = [
                'input[name="pId"]',
                'input[name="id"]',
                'input[name="userId"]',
                'input[name="user_id"]',
                'input[id="pId"]',
                'input[id="id"]',
                "#pId",
                "#id",
            ]

            password_selectors = [
                'input[name="pPw"]',  # 실제 필드명
                'input[name="pPwd"]',
                'input[name="pwd"]',
                'input[name="password"]',
                'input[name="passwd"]',
                'input[id="pPw"]',  # 실제 ID
                'input[id="pPwd"]',
                'input[id="pwd"]',
                "#pPw",  # 실제 ID 셀렉터
                "#pPwd",
                "#pwd",
            ]

            # 사용자명 입력 필드 찾기
            username_element = None
            for selector in username_selectors:
                try:
                    username_element = await self.page.wait_for_selector(
                        selector, timeout=2000
                    )
                    logger.info(f"✅ 사용자명 필드 발견: {selector}")
                    break
                except (KeyError, IndexError, AttributeError):
                    continue

            if not username_element:
                logger.error("❌ 사용자명 입력 필드를 찾을 수 없습니다")
                # 모든 input 요소 출력
                inputs = await self.page.query_selector_all("input")
                logger.info(f"페이지의 모든 input 요소: {len(inputs)}개")
                for i, input_elem in enumerate(inputs[:5]):
                    name = await input_elem.get_attribute("name") or "unnamed"
                    input_type = await input_elem.get_attribute("type") or "text"
                    logger.info(f"   {i+1}. name='{name}', type='{input_type}'")
                raise Exception("사용자명 입력 필드를 찾을 수 없습니다")

            # 비밀번호 입력 필드 찾기
            password_element = None
            for selector in password_selectors:
                try:
                    password_element = await self.page.wait_for_selector(
                        selector, timeout=2000
                    )
                    logger.info(f"✅ 비밀번호 필드 발견: {selector}")
                    break
                except (KeyError, IndexError, AttributeError):
                    continue

            if not password_element:
                logger.error("❌ 비밀번호 입력 필드를 찾을 수 없습니다")
                raise Exception("비밀번호 입력 필드를 찾을 수 없습니다")

            # 로그인 정보 입력
            await username_element.fill(self.username)
            await password_element.fill(self.password)
            logger.info("📝 로그인 정보 입력 완료")

            # 로그인 버튼 찾기 및 클릭
            submit_selectors = [
                'input[type="submit"]',
                'button[type="submit"]',
                ".btn-login",
                'button:has-text("로그인")',
                'input[value*="로그인"]',
                'form input[type="image"]',
            ]

            submit_clicked = False
            for selector in submit_selectors:
                try:
                    submit_button = await self.page.query_selector(selector)
                    if submit_button:
                        await submit_button.click()
                        logger.info(f"✅ 로그인 버튼 클릭: {selector}")
                        submit_clicked = True
                        break
                except (KeyError, IndexError, AttributeError):
                    continue

            if not submit_clicked:
                # 폼 서브밋으로 시도
                form = await self.page.query_selector("form")
                if form:
                    await self.page.keyboard.press("Enter")
                    logger.info("✅ 폼 서브밋 (Enter 키)")
                    submit_clicked = True

            if not submit_clicked:
                raise Exception("로그인 버튼을 찾을 수 없습니다")

            # 로그인 완료 대기
            await self.page.wait_for_load_state("networkidle", timeout=15000)

            # 로그인 성공 확인
            current_url = self.page.url
            page_content = await self.page.content()

            logger.info(f"🔗 로그인 후 URL: {current_url}")

            if "로그아웃" in page_content or "logout" in page_content.lower():
                logger.info("✅ 로그인 성공")
            else:
                logger.warning("⚠️ 로그인 상태 불확실")
                # 로그인 후 페이지 스크린샷
                await self.page.screenshot(path="after_login.png")
                logger.info("📸 로그인 후 페이지 스크린샷 저장: after_login.png")

        except Exception as e:
            logger.error(f"❌ 로그인 실패: {e}")
            # 오류 발생 시 스크린샷
            try:
                await self.page.screenshot(path="login_error.png")
                logger.info("📸 로그인 오류 스크린샷 저장: login_error.png")
            except (KeyError, IndexError, AttributeError):
                pass
            raise

    async def _crawl_category(self, category_name: str, category_url: str):
        """카테고리별 크롤링"""
        logger.info(f"📂 카테고리 '{category_name}' 크롤링 시작")

        try:
            # 카테고리 페이지 접속
            await self.page.goto(category_url, wait_until="networkidle")

            page = 1
            max_pages = 5  # 페이지 제한 (안정성을 위해)

            while page <= max_pages:
                logger.info(f"📄 {category_name} - 페이지 {page} 처리 중")

                # 템플릿 링크 수집
                template_links = await self._get_template_links()

                if not template_links:
                    logger.info(f"페이지 {page}에서 더 이상 템플릿을 찾을 수 없음")
                    break

                logger.info(f"📋 페이지 {page}에서 {len(template_links)}개 템플릿 발견")

                # 각 템플릿 처리 (처음 20개만 안정적으로)
                for i, template_url in enumerate(template_links[:20]):
                    try:
                        logger.info(f"🔍 처리 중: {i+1}/{min(len(template_links), 20)}")
                        await self._process_template(category_name, template_url)

                        # 템플릿 간 대기 시간
                        await asyncio.sleep(1)

                    except Exception as e:
                        logger.error(f"템플릿 처리 오류: {e}")
                        continue

                # 다음 페이지로 이동
                page += 1
                if page <= max_pages:
                    try:
                        next_page_url = f"{category_url}&page={page}"
                        await self.page.goto(
                            next_page_url, wait_until="networkidle", timeout=30000
                        )

                        # 페이지 간 대기 시간
                        await asyncio.sleep(3)

                    except Exception as e:
                        logger.error(f"페이지 이동 오류: {e}")
                        break

        except Exception as e:
            logger.error(f"❌ 카테고리 '{category_name}' 크롤링 실패: {e}")

    async def _get_template_links(self) -> List[str]:
        """현재 페이지에서 템플릿 링크 수집"""
        try:
            # 템플릿 링크 요소들 찾기
            link_elements = await self.page.query_selector_all('a[href*="/xls/"]')

            template_links = []
            for element in link_elements:
                href = await element.get_attribute("href")
                if href and "/xls/" in href and href.endswith(".html"):
                    if href.startswith("/"):
                        full_url = f"{self.base_url}{href}"
                    else:
                        full_url = href
                    template_links.append(full_url)

            # 중복 제거
            return list(set(template_links))

        except Exception as e:
            logger.error(f"템플릿 링크 수집 실패: {e}")
            return []

    async def _process_template(self, category_name: str, template_url: str):
        """개별 템플릿 처리"""
        try:
            logger.info(f"🔍 템플릿 처리: {template_url}")

            # 템플릿 상세 페이지 접속
            await self.page.goto(template_url, wait_until="networkidle")

            # 템플릿 정보 추출
            template_info = await self._extract_template_info(template_url)
            if not template_info:
                return

            template_info["category_major"] = category_name
            template_info["category_minor"] = "일반"

            # Excel 다운로드 시도
            downloaded_path = await self._download_excel_file(template_info)
            if downloaded_path:
                template_info["local_path"] = str(downloaded_path)
                self.progress["downloaded_templates"] += 1
                logger.info(f"✅ 다운로드 성공: {template_info['title']}")
            else:
                self.progress["failed_downloads"] += 1
                self.failed_downloads.append(template_info)
                logger.warning(f"❌ 다운로드 실패: {template_info['title']}")

            # 템플릿 목록에 추가
            crawled_template = CrawledTemplate(**template_info)
            self.crawled_templates.append(crawled_template)

        except Exception as e:
            logger.error(f"템플릿 처리 실패 ({template_url}): {e}")

    async def _extract_template_info(self, source_url: str) -> Optional[Dict[str, Any]]:
        """템플릿 정보 추출"""
        try:
            # 제목 추출
            title_element = await self.page.query_selector("h1, .title h1")
            title = await title_element.inner_text() if title_element else "제목 없음"

            # 설명 추출
            desc_element = await self.page.query_selector("#description, .description")
            description = (
                await desc_element.inner_text() if desc_element else "설명 없음"
            )

            # 파일명 생성
            safe_title = re.sub(r"[^\w\-_\.]", "_", title)
            file_name = f"{safe_title}.xlsx"

            return {
                "title": title.strip(),
                "description": description.strip(),
                "file_name": file_name,
                "source_url": source_url,
                "crawled_at": datetime.now().isoformat(),
                "download_url": "",  # Playwright에서는 직접 다운로드
                "local_path": "",
                "related_files": [],
            }

        except Exception as e:
            logger.error(f"템플릿 정보 추출 실패: {e}")
            return None

    async def _download_excel_file(
        self, template_info: Dict[str, Any]
    ) -> Optional[Path]:
        """Excel 파일 다운로드"""
        try:
            # 카테고리별 디렉토리 생성
            category_dir = self.download_dir / template_info["category_major"]
            category_dir.mkdir(parents=True, exist_ok=True)

            file_path = category_dir / template_info["file_name"]

            # 이미 다운로드된 파일 확인
            if file_path.exists():
                logger.info(f"⏭️ 이미 존재하는 파일: {template_info['file_name']}")
                return file_path

            # 페이지에서 다운로드 링크 직접 추출
            page_content = await self.page.content()

            # 파일 ID 추출을 위한 다양한 패턴 시도
            import re

            # 패턴 1: wlog_all 함수
            wlog_matches = re.findall(r"wlog_all\('form',\s*'(\d+)'\)", page_content)

            # 패턴 2: URL에서 ID 추출
            url_matches = re.findall(r"/xls/(\d+)\.html", template_info["source_url"])

            # 패턴 3: rowid 파라미터
            rowid_matches = re.findall(r"rowid[=:](\d+)", page_content)

            file_id = None
            if wlog_matches:
                file_id = wlog_matches[0]
                logger.info(f"📋 wlog_all에서 파일 ID 발견: {file_id}")
            elif url_matches:
                file_id = url_matches[0]
                logger.info(f"📋 URL에서 파일 ID 발견: {file_id}")
            elif rowid_matches:
                file_id = rowid_matches[0]
                logger.info(f"📋 rowid에서 파일 ID 발견: {file_id}")

            if not file_id:
                logger.warning("파일 ID를 찾을 수 없습니다")
                # Excel 다운로드 링크 직접 찾기 시도
                excel_links = re.findall(
                    r'href="([^"]*dw_form\.php[^"]*)"', page_content
                )
                if excel_links:
                    # 첫 번째 Excel 링크에서 rowid 추출
                    for link in excel_links:
                        rowid_match = re.search(r"rowid=(\d+)", link)
                        if rowid_match:
                            file_id = rowid_match.group(1)
                            logger.info(f"📋 다운로드 링크에서 파일 ID 발견: {file_id}")
                            break

                if not file_id:
                    return None

            # 직접 다운로드 URL 생성
            download_url = f"https://www.yesform.com/z_n/forms/dw_form.php?mtbl=form&rowid={file_id}&type=xlsx"
            logger.info(f"⬇️ 다운로드 URL: {download_url}")

            # 새 탭에서 다운로드 시도
            download_page = await self.context.new_page()

            try:
                # 다운로드 대기 설정
                async with download_page.expect_download(
                    timeout=30000
                ) as download_info:
                    # 다운로드 URL로 이동
                    await download_page.goto(download_url)

                download = await download_info.value

                # 다운로드된 파일 저장
                await download.save_as(file_path)

                # 파일 검증
                if await self._verify_excel_file(file_path):
                    logger.info(
                        f"💾 Excel 파일 다운로드 완료: {template_info['file_name']}"
                    )
                    return file_path
                else:
                    if file_path.exists():
                        file_path.unlink()  # 잘못된 파일 삭제
                    logger.warning(f"❌ 잘못된 파일 형식: {template_info['file_name']}")
                    return None

            except Exception as download_error:
                logger.warning(f"직접 다운로드 실패: {download_error}")

                # 대체 방법: 일반 HTTP 요청으로 다운로드
                response = await download_page.goto(
                    download_url, wait_until="networkidle"
                )

                if response and response.status == 200:
                    content_type = response.headers.get("content-type", "").lower()

                    if "html" not in content_type:
                        # 파일 내용 읽기
                        content = await response.body()

                        # 파일 저장
                        with open(file_path, "wb") as f:
                            f.write(content)

                        # 파일 검증
                        if await self._verify_excel_file(file_path):
                            logger.info(
                                f"💾 HTTP 다운로드 완료: {template_info['file_name']}"
                            )
                            return file_path
                        else:
                            if file_path.exists():
                                file_path.unlink()
                            logger.warning(
                                f"❌ HTTP 다운로드 파일 형식 오류: {template_info['file_name']}"
                            )
                            return None
                    else:
                        logger.warning(
                            f"❌ HTML 응답 반환 (인증 실패): {template_info['file_name']}"
                        )
                        return None
                else:
                    logger.warning(
                        f"❌ HTTP 요청 실패: {response.status if response else 'No response'}"
                    )
                    return None

            finally:
                await download_page.close()

        except Exception as e:
            logger.error(f"파일 다운로드 실패: {e}")
            return None

    async def _verify_excel_file(self, file_path: Path) -> bool:
        """Excel 파일 검증"""
        try:
            if not file_path.exists() or file_path.stat().st_size < 1024:
                return False

            with open(file_path, "rb") as f:
                header = f.read(4)
                # Excel 파일 시그니처 확인
                return header.startswith(b"PK") or header.startswith(  # XLSX (ZIP 기반)
                    b"\xd0\xcf\x11\xe0"
                )  # XLS (OLE 기반)

        except Exception:
            return False

    async def _save_results(self):
        """결과 저장"""
        logger.info("💾 크롤링 결과 저장 중...")

        try:
            results = {
                "crawling_info": {
                    "start_time": self.progress["start_time"].isoformat(),
                    "end_time": datetime.now().isoformat(),
                    "total_templates": len(self.crawled_templates),
                    "successful_downloads": self.progress["downloaded_templates"],
                    "failed_downloads": self.progress["failed_downloads"],
                    "method": "playwright",
                },
                "templates": [
                    {
                        "title": t.title,
                        "description": t.description,
                        "category_major": t.category_major,
                        "category_minor": t.category_minor,
                        "file_name": t.file_name,
                        "source_url": t.source_url,
                        "crawled_at": t.crawled_at,
                        "local_path": getattr(t, "local_path", ""),
                        "related_files": t.related_files,
                    }
                    for t in self.crawled_templates
                ],
                "failed_downloads": self.failed_downloads,
            }

            results_file = (
                self.metadata_dir
                / f"playwright_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )

            with open(results_file, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

            logger.info(f"✅ 크롤링 결과 저장 완료: {results_file}")

        except Exception as e:
            logger.error(f"❌ 결과 저장 실패: {e}")

    async def _cleanup(self):
        """리소스 정리"""
        logger.info("🧹 리소스 정리 중...")

        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
        except Exception as e:
            logger.error(f"리소스 정리 중 오류: {e}")

    def get_progress(self) -> Dict[str, Any]:
        """진행 상황 반환"""
        if self.progress["start_time"]:
            duration = datetime.now() - self.progress["start_time"]
            self.progress["duration"] = str(duration)

        return self.progress.copy()


# 전역 인스턴스
playwright_korean_crawler = PlaywrightKoreanCrawler()
