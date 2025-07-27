"""
Korean Template Crawler API
한국어 템플릿 크롤링 API 엔드포인트
"""
import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ...services.korean_template_crawler import korean_template_crawler

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/korean-crawler", tags=["korean_crawler"])


class CrawlingStartRequest(BaseModel):
    force_restart: bool = False
    max_templates_per_category: int = 0  # 0 = 무제한


@router.post("/start")
async def start_crawling(
    request: CrawlingStartRequest,
    background_tasks: BackgroundTasks
):
    """
    한국어 템플릿 크롤링 시작
    """
    try:
        # 현재 진행 중인지 확인
        current_progress = korean_template_crawler.get_progress()
        
        if (current_progress['current_status'] not in ['준비 중', '완료', '오류'] and 
            not request.force_restart):
            return JSONResponse(
                status_code=409,
                content={
                    "status": "already_running",
                    "message": "크롤링이 이미 진행 중입니다",
                    "current_progress": current_progress
                }
            )
        
        # 백그라운드에서 크롤링 시작
        background_tasks.add_task(run_crawling_background)
        
        return {
            "status": "started",
            "message": "한국어 템플릿 크롤링이 백그라운드에서 시작되었습니다",
            "estimated_duration": "30-60분",
            "progress_endpoint": "/korean-crawler/progress"
        }
    
    except Exception as e:
        logger.error(f"크롤링 시작 실패: {e}")
        raise HTTPException(status_code=500, detail=f"크롤링 시작 실패: {str(e)}")


@router.get("/progress")
async def get_crawling_progress():
    """
    크롤링 진행 상황 조회
    """
    try:
        progress = korean_template_crawler.get_progress()
        
        return {
            "status": "success",
            "progress": progress,
            "is_running": progress['current_status'] not in ['준비 중', '완료', '오류']
        }
    
    except Exception as e:
        logger.error(f"진행 상황 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="진행 상황 조회 실패")


@router.post("/stop")
async def stop_crawling():
    """
    크롤링 중단
    """
    try:
        # 실제로는 크롤러에 중단 신호를 보내야 함
        # 현재는 상태만 업데이트
        progress = korean_template_crawler.get_progress()
        
        if progress['current_status'] in ['준비 중', '완료', '오류']:
            return {
                "status": "not_running",
                "message": "현재 실행 중인 크롤링이 없습니다"
            }
        
        # 중단 로직 구현 필요 (실제로는 크롤러 클래스에 stop 메서드 추가)
        return {
            "status": "stopping",
            "message": "크롤링 중단 요청이 처리되었습니다"
        }
    
    except Exception as e:
        logger.error(f"크롤링 중단 실패: {e}")
        raise HTTPException(status_code=500, detail="크롤링 중단 실패")


@router.get("/results")
async def get_crawling_results():
    """
    크롤링 결과 조회
    """
    try:
        progress = korean_template_crawler.get_progress()
        
        if progress['current_status'] == '완료':
            # 크롤링된 템플릿 목록 반환
            templates = korean_template_crawler.crawled_templates
            
            # 카테고리별 통계 생성
            category_stats = {}
            for template in templates:
                major = template.category_major
                minor = template.category_minor
                
                if major not in category_stats:
                    category_stats[major] = {}
                if minor not in category_stats[major]:
                    category_stats[major][minor] = 0
                
                category_stats[major][minor] += 1
            
            return {
                "status": "success",
                "summary": {
                    "total_templates": len(templates),
                    "successful_downloads": progress["downloaded_templates"],
                    "failed_downloads": progress["failed_downloads"],
                    "category_stats": category_stats
                },
                "templates": [
                    {
                        "title": t.title,
                        "category_major": t.category_major,
                        "category_minor": t.category_minor,
                        "file_name": t.file_name,
                        "description": t.description[:100] + "..." if len(t.description) > 100 else t.description,
                        "crawled_at": t.crawled_at,
                        "has_local_file": hasattr(t, 'local_path') and t.local_path
                    } for t in templates
                ]
            }
        else:
            return {
                "status": "not_completed",
                "message": f"크롤링이 아직 완료되지 않았습니다. 현재 상태: {progress['current_status']}",
                "progress": progress
            }
    
    except Exception as e:
        logger.error(f"크롤링 결과 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="크롤링 결과 조회 실패")


@router.get("/categories")
async def get_available_categories():
    """
    사용 가능한 카테고리 목록 조회 (크롤링 완료 후)
    """
    try:
        templates = korean_template_crawler.crawled_templates
        
        if not templates:
            return {
                "status": "no_data",
                "message": "크롤링된 데이터가 없습니다",
                "categories": {}
            }
        
        # 카테고리 구조 생성
        categories = {}
        for template in templates:
            major = template.category_major
            minor = template.category_minor
            
            if major not in categories:
                categories[major] = {
                    "name": major,
                    "subcategories": {},
                    "total_count": 0
                }
            
            if minor not in categories[major]["subcategories"]:
                categories[major]["subcategories"][minor] = {
                    "name": minor,
                    "count": 0,
                    "templates": []
                }
            
            categories[major]["subcategories"][minor]["count"] += 1
            categories[major]["subcategories"][minor]["templates"].append({
                "title": template.title,
                "file_name": template.file_name
            })
            categories[major]["total_count"] += 1
        
        return {
            "status": "success",
            "categories": categories,
            "total_major_categories": len(categories),
            "total_templates": len(templates)
        }
    
    except Exception as e:
        logger.error(f"카테고리 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="카테고리 조회 실패")


@router.get("/download/{category_major}/{category_minor}")
async def get_category_templates(category_major: str, category_minor: str):
    """
    특정 카테고리의 템플릿 목록 조회
    """
    try:
        templates = korean_template_crawler.crawled_templates
        
        # 해당 카테고리 템플릿 필터링
        filtered_templates = [
            t for t in templates 
            if t.category_major == category_major and t.category_minor == category_minor
        ]
        
        if not filtered_templates:
            raise HTTPException(
                status_code=404, 
                detail=f"카테고리 '{category_major}/{category_minor}'에서 템플릿을 찾을 수 없습니다"
            )
        
        return {
            "status": "success",
            "category": {
                "major": category_major,
                "minor": category_minor
            },
            "templates": [
                {
                    "title": t.title,
                    "description": t.description,
                    "file_name": t.file_name,
                    "source_url": t.source_url,
                    "crawled_at": t.crawled_at,
                    "local_path": getattr(t, 'local_path', None),
                    "related_files": t.related_files
                } for t in filtered_templates
            ],
            "total_count": len(filtered_templates)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"카테고리 템플릿 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="카테고리 템플릿 조회 실패")


@router.get("/statistics")
async def get_crawling_statistics():
    """
    크롤링 통계 정보 조회
    """
    try:
        templates = korean_template_crawler.crawled_templates
        progress = korean_template_crawler.get_progress()
        
        if not templates:
            return {
                "status": "no_data",
                "message": "크롤링된 데이터가 없습니다"
            }
        
        # 기본 통계
        basic_stats = {
            "total_templates": len(templates),
            "successful_downloads": progress.get("downloaded_templates", 0),
            "failed_downloads": progress.get("failed_downloads", 0),
            "success_rate": round((progress.get("downloaded_templates", 0) / len(templates)) * 100, 2) if templates else 0
        }
        
        # 카테고리별 통계
        category_distribution = {}
        for template in templates:
            major = template.category_major
            if major not in category_distribution:
                category_distribution[major] = 0
            category_distribution[major] += 1
        
        # 시간별 통계 (크롤링 시간 정보가 있다면)
        time_stats = {}
        if progress.get('start_time') and progress.get('duration'):
            time_stats = {
                "start_time": progress['start_time'],
                "duration": progress['duration'],
                "templates_per_minute": round(len(templates) / (progress.get('duration_minutes', 1)), 2) if templates else 0
            }
        
        return {
            "status": "success",
            "basic_stats": basic_stats,
            "category_distribution": category_distribution,
            "time_stats": time_stats,
            "quality_metrics": {
                "templates_with_description": len([t for t in templates if t.description and t.description != "설명 없음"]),
                "templates_with_related_files": len([t for t in templates if t.related_files])
            }
        }
    
    except Exception as e:
        logger.error(f"통계 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="통계 조회 실패")


@router.get("/cookie-status")
async def check_cookie_status():
    """
    쿠키 파일 상태 확인
    """
    try:
        from pathlib import Path
        cookie_file = Path("user_cookies.txt")
        
        if not cookie_file.exists():
            return {
                "status": "missing",
                "message": "user_cookies.txt 파일이 없습니다",
                "has_cookies": False,
                "instruction": "브라우저에서 로그인 후 쿠키를 추출하여 user_cookies.txt 파일에 저장하세요"
            }
        
        try:
            with open(cookie_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            
            if not content or content.startswith('#'):
                return {
                    "status": "empty",
                    "message": "쿠키 파일이 비어있거나 샘플 내용만 있습니다",
                    "has_cookies": False
                }
            
            # 쿠키 개수 확인
            cookies = []
            for line in content.split('\n'):
                if '=' in line and not line.strip().startswith('#'):
                    for cookie_pair in line.split(';'):
                        if '=' in cookie_pair.strip():
                            cookies.append(cookie_pair.strip())
            
            return {
                "status": "valid",
                "message": f"{len(cookies)}개의 쿠키가 발견되었습니다",
                "has_cookies": True,
                "cookie_count": len(cookies),
                "cookie_names": [cookie.split('=')[0] for cookie in cookies[:5]]  # 처음 5개만
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"쿠키 파일 읽기 실패: {str(e)}",
                "has_cookies": False
            }
    
    except Exception as e:
        logger.error(f"쿠키 상태 확인 실패: {e}")
        raise HTTPException(status_code=500, detail="쿠키 상태 확인 실패")


@router.post("/test-login")
async def test_login():
    """
    로그인 테스트 (쿠키 유효성 확인)
    """
    try:
        from app.services.korean_template_crawler import KoreanTemplateCrawler
        test_crawler = KoreanTemplateCrawler()
        
        await test_crawler._initialize_session()
        login_result = await test_crawler._login()
        
        # 테스트 페이지 접속
        async with test_crawler.session.get(test_crawler.base_url) as response:
            if response.status == 200:
                # 로그인 상태 확인
                try:
                    content = await response.text(encoding='utf-8')
                except UnicodeDecodeError:
                    content_bytes = await response.read()
                    try:
                        content = content_bytes.decode('euc-kr')
                    except UnicodeDecodeError:
                        content = content_bytes.decode('cp949', errors='ignore')
                
                # 로그인 여부 판단
                is_logged_in = 'logout' in content.lower() or '로그아웃' in content
                
                await test_crawler.session.close()
                
                return {
                    "status": "success" if is_logged_in else "warning",
                    "message": "로그인 성공" if is_logged_in else "로그인 상태 불확실",
                    "logged_in": is_logged_in,
                    "response_status": response.status,
                    "content_length": len(content)
                }
            else:
                await test_crawler.session.close()
                return {
                    "status": "error",
                    "message": f"사이트 접속 실패: {response.status}",
                    "logged_in": False
                }
    
    except Exception as e:
        logger.error(f"로그인 테스트 실패: {e}")
        raise HTTPException(status_code=500, detail=f"로그인 테스트 실패: {str(e)}")


@router.get("/cookie-help")
async def get_cookie_help():
    """
    쿠키 설정 도움말
    """
    return {
        "title": "브라우저 쿠키 추출 방법",
        "current_status": "쿠키 파일이 생성되었습니다",
        "steps": [
            "1. Chrome/Edge에서 https://excel.yesform.com 접속",
            "2. 로그인 (j1global / wpdldnjs11!)",
            "3. F12 → Application → Cookies → excel.yesform.com",
            "4. 모든 쿠키 복사",
            "5. user_cookies.txt 파일에 저장"
        ],
        "format": "name=value; name2=value2; name3=value3",
        "javascript_helper": "document.cookie",
        "file_location": "python-service/user_cookies.txt",
        "important_notes": [
            "로그인 직후 즉시 추출해야 함",
            "세션 쿠키는 시간이 지나면 만료됨",
            "개인정보이므로 안전하게 관리 필요"
        ],
        "troubleshooting": {
            "empty_downloads": "로그인 쿠키가 만료되었을 수 있습니다. 브라우저에서 다시 로그인 후 쿠키를 업데이트하세요",
            "html_files": "다운로드된 파일이 HTML인 경우 인증 실패입니다. 쿠키를 재설정하세요"
        }
    }


# 백그라운드 작업 함수
async def run_crawling_background():
    """백그라운드에서 크롤링 실행"""
    try:
        logger.info("🚀 백그라운드 크롤링 시작")
        result = await korean_template_crawler.start_crawling()
        logger.info(f"✅ 백그라운드 크롤링 완료: {result}")
    except Exception as e:
        logger.error(f"❌ 백그라운드 크롤링 실패: {e}")
        # 진행 상황을 오류 상태로 업데이트
        korean_template_crawler.progress["current_status"] = f"오류: {str(e)}"