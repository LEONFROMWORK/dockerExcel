"""
이미지 Excel 통합 API 테스트
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from PIL import Image
import io

from main import app

client = TestClient(app)


@pytest.fixture
def sample_image():
    """테스트용 샘플 이미지 생성"""
    img = Image.new("RGB", (100, 100), color="white")
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format="PNG")
    img_byte_arr.seek(0)
    return img_byte_arr


class TestImageExcelIntegration:
    """이미지 Excel 통합 API 테스트"""

    def test_supported_formats(self):
        """지원 형식 조회 테스트"""
        response = client.get("/api/v1/image-excel-integration/supported-formats")
        assert response.status_code == 200

        data = response.json()
        assert "supported_image_formats" in data
        assert "supported_excel_formats" in data
        assert "features" in data
        assert "limits" in data

        # 이미지 형식 확인
        formats = [f["extension"] for f in data["supported_image_formats"]]
        assert ".png" in formats
        assert ".jpg" in formats

        # Excel 형식 확인
        assert "xlsx" in data["supported_excel_formats"]

        # 제한사항 확인
        assert data["limits"]["max_file_size_mb"] == 10
        assert data["limits"]["max_batch_files"] == 20

    @patch("app.api.v1.image_excel_integration.ImageExcelIntegrationService")
    def test_convert_single_image_success(self, mock_service, sample_image):
        """단일 이미지 변환 성공 테스트"""
        # Mock 설정
        mock_instance = mock_service.return_value
        mock_instance.process_image_with_error_detection = AsyncMock(
            return_value={
                "status": "success",
                "image_analysis": {
                    "type": "table",
                    "confidence": 0.95,
                    "ocr_method": "tier2",
                    "metadata": {"processing_time": 1.5},
                },
                "excel_conversion": {
                    "file_path": "/tmp/converted.xlsx",
                    "sheet_count": 1,
                    "total_cells": 100,
                    "warnings": [],
                },
                "error_detection": {
                    "summary": {"total_errors": 2, "auto_fixable": 1},
                    "errors": [],
                },
                "processing_time": 1.5,
            }
        )

        # 파일 업로드
        files = {"file": ("test.png", sample_image, "image/png")}
        response = client.post(
            "/api/v1/image-excel-integration/convert-and-analyze",
            files=files,
            params={"detect_errors": True},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "success"
        assert data["filename"] == "test.png"
        assert "excel_file" in data
        assert "image_analysis" in data
        assert "error_detection" in data

    def test_convert_invalid_file_type(self):
        """잘못된 파일 형식 테스트"""
        # 텍스트 파일 생성
        files = {"file": ("test.txt", b"Hello World", "text/plain")}

        response = client.post(
            "/api/v1/image-excel-integration/convert-and-analyze", files=files
        )

        assert response.status_code == 400
        assert "지원하지 않는 파일 형식" in response.json()["detail"]

    def test_convert_oversized_file(self):
        """파일 크기 초과 테스트"""
        # 10MB 초과 파일 시뮬레이션
        large_content = b"x" * (11 * 1024 * 1024)
        files = {"file": ("large.png", large_content, "image/png")}

        response = client.post(
            "/api/v1/image-excel-integration/convert-and-analyze", files=files
        )

        assert response.status_code == 400
        assert "10MB를 초과" in response.json()["detail"]

    @patch("app.api.v1.image_excel_integration.ImageExcelIntegrationService")
    def test_batch_convert_success(self, mock_service, sample_image):
        """일괄 변환 성공 테스트"""
        # Mock 설정
        mock_instance = mock_service.return_value
        mock_instance.batch_process_images = AsyncMock(
            return_value={
                "status": "completed",
                "total_images": 2,
                "successful": 2,
                "failed": 0,
                "merge_strategy": "separate_sheets",
                "merged_file": "/tmp/merged.xlsx",
                "error_detection": None,
                "individual_results": [
                    {
                        "status": "success",
                        "error_detection": {"summary": {"total_errors": 0}},
                    },
                    {
                        "status": "success",
                        "error_detection": {"summary": {"total_errors": 1}},
                    },
                ],
                "failures": [],
            }
        )

        # 여러 파일 업로드
        files = [
            ("files", ("test1.png", sample_image.getvalue(), "image/png")),
            ("files", ("test2.png", sample_image.getvalue(), "image/png")),
        ]

        response = client.post(
            "/api/v1/image-excel-integration/batch-convert",
            files=files,
            params={"merge_strategy": "separate_sheets"},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "completed"
        assert data["processed_files"] == 2
        assert data["merge_strategy"] == "separate_sheets"
        assert len(data["individual_results"]) == 2

    def test_batch_convert_too_many_files(self):
        """파일 개수 초과 테스트"""
        # 21개 파일 시뮬레이션
        files = []
        for i in range(21):
            files.append(("files", (f"test{i}.png", b"image data", "image/png")))

        response = client.post(
            "/api/v1/image-excel-integration/batch-convert", files=files
        )

        assert response.status_code == 400
        assert "최대 20개" in response.json()["detail"]

    def test_batch_convert_no_files(self):
        """파일 없이 일괄 변환 요청 테스트"""
        response = client.post(
            "/api/v1/image-excel-integration/batch-convert", files=[]
        )

        assert response.status_code == 422  # FastAPI validation error

    @patch("app.api.v1.image_excel_integration.ImageExcelIntegrationService")
    def test_analyze_image_type(self, mock_service, sample_image):
        """이미지 타입 분석 테스트"""
        # Mock 설정
        mock_instance = mock_service.return_value
        mock_instance._detect_image_type = AsyncMock(return_value="table")

        files = {"file": ("test.png", sample_image, "image/png")}
        response = client.post(
            "/api/v1/image-excel-integration/analyze-image-type", files=files
        )

        assert response.status_code == 200
        data = response.json()

        assert data["filename"] == "test.png"
        assert "image_info" in data
        assert "detected_type" in data
        assert "recommendation" in data
        assert "processing_suggestion" in data

    def test_auto_fix_option(self):
        """자동 수정 옵션 테스트"""
        # TODO: 자동 수정 기능이 구현되면 추가 테스트

    def test_error_handling(self):
        """에러 처리 테스트"""
        # TODO: 다양한 에러 시나리오 테스트


class TestImageProcessingIntegration:
    """이미지 처리 통합 테스트"""

    @pytest.mark.asyncio
    async def test_ocr_tier_selection(self):
        """OCR 티어 선택 로직 테스트"""
        # TODO: OCR 티어 선택 로직 테스트

    @pytest.mark.asyncio
    async def test_error_detection_integration(self):
        """오류 감지 통합 테스트"""
        # TODO: 오류 감지 통합 테스트
