"""
Excel Fix Execution API endpoints
오류 수정 실행을 위한 API 엔드포인트
"""

from fastapi import APIRouter, File, UploadFile, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
import tempfile
import os
from typing import Dict, Any, List, Optional
import logging
import shutil

from app.core.database import get_db
from app.core.config import settings
from app.core.i18n_dependencies import get_i18n_context, I18nContext
from app.services.detection.integrated_error_detector import IntegratedErrorDetector
from app.services.fixing.integrated_error_fixer import IntegratedErrorFixer
from app.services.workbook_loader import OpenpyxlWorkbookLoader
from app.core.interfaces import ExcelError

logger = logging.getLogger(__name__)

router = APIRouter()


class ApplyFixRequest(BaseModel):
    """단일 수정 적용 요청"""

    error_id: str
    fixed_formula: str
    apply_immediately: bool = False


class BatchFixRequest(BaseModel):
    """일괄 수정 요청"""

    fix_strategy: str = "safe"  # safe, aggressive, custom
    fix_types: List[str] = None  # 수정할 오류 타입들
    auto_save: bool = True
    create_backup: bool = True


@router.post("/apply-single-fix")
async def apply_single_fix(
    file: UploadFile = File(...),
    fix_request: ApplyFixRequest = None,
    db: AsyncSession = Depends(get_db),
    i18n: I18nContext = Depends(get_i18n_context),
) -> Dict[str, Any]:
    """
    단일 오류 수정 적용
    """
    # 파일 타입 검증
    if not any(file.filename.endswith(ext) for ext in settings.ALLOWED_EXTENSIONS):
        error_message = i18n.get_error_message(
            "invalid_file_type", extensions=", ".join(settings.ALLOWED_EXTENSIONS)
        )
        raise HTTPException(status_code=400, detail=error_message)

    # 임시 파일 저장
    with tempfile.NamedTemporaryFile(
        delete=False, suffix=os.path.splitext(file.filename)[1]
    ) as tmp_file:
        content = await file.read()
        tmp_file.write(content)
        tmp_path = tmp_file.name

    try:
        # 워크북 로드
        workbook_loader = OpenpyxlWorkbookLoader()
        workbook = await workbook_loader.load_workbook(tmp_path)

        # 오류 ID에서 시트와 셀 정보 추출
        # 예: "Sheet1_A1_DE_123456" -> sheet="Sheet1", cell="A1"
        parts = fix_request.error_id.split("_")
        if len(parts) >= 2:
            sheet_name = parts[0]
            cell_address = parts[1]
        else:
            raise HTTPException(status_code=400, detail="Invalid error ID format")

        # 셀에 수정된 수식 적용
        try:
            worksheet = workbook[sheet_name]
            cell = worksheet[cell_address]

            # 기존 값 백업
            original_value = cell.value

            # 새 수식 적용
            cell.value = fix_request.fixed_formula

            # 즉시 저장 옵션
            if fix_request.apply_immediately:
                workbook.save(tmp_path)

            # 수정 결과 확인
            success = True
            message = i18n.get_text("fix.applied_successfully")

        except Exception as e:
            success = False
            message = str(e)
            original_value = None

        finally:
            workbook.close()

        return {
            "status": "success" if success else "error",
            "message": message,
            "fix_details": {
                "error_id": fix_request.error_id,
                "location": f"{sheet_name}!{cell_address}",
                "original_value": str(original_value) if original_value else None,
                "new_value": fix_request.fixed_formula,
                "applied": success,
            },
            "file_path": tmp_path if success else None,
        }

    except Exception as e:
        logger.error(f"Error applying single fix: {str(e)}")
        error_message = i18n.get_error_message("fix_apply_failed", error=str(e))
        raise HTTPException(status_code=500, detail=error_message)
    finally:
        # 실패 시 임시 파일 정리
        if not success and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.post("/apply-batch-fixes")
async def apply_batch_fixes(
    file: UploadFile = File(...),
    batch_request: BatchFixRequest = BatchFixRequest(),
    db: AsyncSession = Depends(get_db),
    i18n: I18nContext = Depends(get_i18n_context),
) -> Dict[str, Any]:
    """
    일괄 오류 수정 적용
    """
    # 파일 타입 검증
    if not any(file.filename.endswith(ext) for ext in settings.ALLOWED_EXTENSIONS):
        error_message = i18n.get_error_message(
            "invalid_file_type", extensions=", ".join(settings.ALLOWED_EXTENSIONS)
        )
        raise HTTPException(status_code=400, detail=error_message)

    # 임시 파일 저장
    with tempfile.NamedTemporaryFile(
        delete=False, suffix=os.path.splitext(file.filename)[1]
    ) as tmp_file:
        content = await file.read()
        tmp_file.write(content)
        tmp_path = tmp_file.name

    # 백업 생성
    backup_path = None
    if batch_request.create_backup:
        backup_path = f"{tmp_path}.backup"
        shutil.copy2(tmp_path, backup_path)

    try:
        # 1. 오류 감지
        detector = IntegratedErrorDetector()
        detection_result = await detector.detect_all_errors(tmp_path)
        all_errors = detection_result["errors"]

        # 오류 타입 필터링
        if batch_request.fix_types:
            errors_to_fix = [
                error
                for error in all_errors
                if error["type"] in batch_request.fix_types
            ]
        else:
            errors_to_fix = all_errors

        # ExcelError 객체로 변환
        error_objects = []
        for error_dict in errors_to_fix:
            error_obj = ExcelError(
                id=error_dict["id"],
                type=error_dict["type"],
                sheet=error_dict["sheet"],
                cell=error_dict["cell"],
                formula=error_dict.get("formula"),
                value=error_dict.get("value"),
                message=error_dict["message"],
                severity=error_dict["severity"],
                is_auto_fixable=error_dict.get("is_auto_fixable", False),
                suggested_fix=error_dict.get("suggested_fix"),
                confidence=error_dict.get("confidence", 0.0),
            )
            error_objects.append(error_obj)

        # 2. 수정 적용
        fixer = IntegratedErrorFixer()
        fix_results = await fixer.fix_batch(
            errors=error_objects, strategy=batch_request.fix_strategy
        )

        # 3. 워크북에 수정 사항 적용
        if fix_results["success"] > 0 and batch_request.auto_save:
            workbook = await workbook_loader.load_workbook(tmp_path)

            applied_count = 0
            for result in fix_results["results"]:
                if result.success and not result.applied:
                    success = await fixer.apply_fix_to_workbook(workbook, result)
                    if success:
                        applied_count += 1

            # 저장
            if applied_count > 0:
                await workbook_loader.save_workbook(workbook, tmp_path)

            fix_results["applied_count"] = applied_count

        # 4. 재검증
        if fix_results["success"] > 0:
            revalidation_result = await detector.detect_all_errors(tmp_path)
            remaining_errors = len(revalidation_result["errors"])
        else:
            remaining_errors = len(all_errors)

        return {
            "status": "success",
            "message": i18n.get_text("fix.batch_complete"),
            "summary": {
                "total_errors": len(all_errors),
                "errors_to_fix": len(errors_to_fix),
                "successful_fixes": fix_results["success"],
                "failed_fixes": fix_results["failed"],
                "applied_fixes": fix_results.get("applied_count", 0),
                "remaining_errors": remaining_errors,
                "processing_time": fix_results["processing_time"],
            },
            "details": {
                "strategy_used": batch_request.fix_strategy,
                "fix_types": batch_request.fix_types or "all",
                "backup_created": batch_request.create_backup,
            },
            "file_paths": {"fixed_file": tmp_path, "backup_file": backup_path},
        }

    except Exception as e:
        logger.error(f"Error in batch fix: {str(e)}")

        # 백업에서 복구
        if backup_path and os.path.exists(backup_path):
            shutil.copy2(backup_path, tmp_path)

        error_message = i18n.get_error_message("batch_fix_failed", error=str(e))
        raise HTTPException(status_code=500, detail=error_message)
    finally:
        # 백업 파일 정리 (성공 시에만)
        if (
            backup_path
            and os.path.exists(backup_path)
            and fix_results.get("success", 0) > 0
        ):
            os.unlink(backup_path)


@router.post("/preview-fix")
async def preview_fix(
    error_type: str,
    original_formula: str,
    context: Optional[Dict[str, Any]] = None,
    i18n: I18nContext = Depends(get_i18n_context),
) -> Dict[str, Any]:
    """
    수정 미리보기 (실제 적용 없이)
    """
    try:
        # 임시 ExcelError 객체 생성
        temp_error = ExcelError(
            id="preview",
            type=error_type,
            sheet="Sheet1",
            cell="A1",
            formula=original_formula,
            value=None,
            message="Preview error",
            severity="medium",
            is_auto_fixable=True,
            suggested_fix=None,
            confidence=0.0,
        )

        # IntegratedErrorFixer로 수정 제안 생성
        fixer = IntegratedErrorFixer()

        # 해당 오류를 처리할 수 있는 전략 찾기
        strategy = fixer._find_strategy(temp_error)

        if not strategy:
            return {
                "status": "error",
                "message": i18n.get_text("fix.no_strategy_available"),
                "error_type": error_type,
                "can_fix": False,
            }

        # 수정 미리보기 생성
        fix_result = await strategy.apply_fix(temp_error, context)

        return {
            "status": "success",
            "preview": {
                "original_formula": original_formula,
                "suggested_fix": fix_result.fixed_formula,
                "confidence": fix_result.confidence,
                "explanation": fix_result.message,
                "can_fix": fix_result.success,
            },
            "strategy_used": strategy.__class__.__name__,
        }

    except Exception as e:
        logger.error(f"Error in fix preview: {str(e)}")
        return {
            "status": "error",
            "message": str(e),
            "error_type": error_type,
            "can_fix": False,
        }


@router.get("/fix-strategies")
async def get_available_fix_strategies(
    i18n: I18nContext = Depends(get_i18n_context),
) -> Dict[str, Any]:
    """
    사용 가능한 수정 전략 목록 조회
    """
    try:
        fixer = IntegratedErrorFixer()

        strategies = []
        for strategy in fixer.fix_strategies:
            strategy_info = {
                "name": strategy.__class__.__name__,
                "supported_errors": [],
                "description": (
                    strategy.__class__.__doc__.strip()
                    if strategy.__class__.__doc__
                    else ""
                ),
            }

            # 지원하는 오류 타입 확인
            test_errors = [
                "#DIV/0!",
                "#N/A",
                "#NAME?",
                "#REF!",
                "#VALUE!",
                "circular_reference",
            ]

            for error_type in test_errors:
                temp_error = ExcelError(
                    id="test",
                    type=error_type,
                    sheet="",
                    cell="",
                    formula="",
                    value=None,
                    message="",
                    severity="medium",
                    is_auto_fixable=True,
                    suggested_fix=None,
                    confidence=0.0,
                )
                if strategy.can_handle(temp_error):
                    strategy_info["supported_errors"].append(error_type)

            strategies.append(strategy_info)

        return {
            "status": "success",
            "total_strategies": len(strategies),
            "strategies": strategies,
            "fix_modes": {
                "safe": i18n.get_text("fix.mode.safe.description"),
                "aggressive": i18n.get_text("fix.mode.aggressive.description"),
                "custom": i18n.get_text("fix.mode.custom.description"),
            },
        }

    except Exception as e:
        logger.error(f"Error getting fix strategies: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=i18n.get_error_message("strategies_fetch_failed", error=str(e)),
        )
