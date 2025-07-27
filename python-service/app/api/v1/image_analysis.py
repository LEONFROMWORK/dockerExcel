from fastapi import APIRouter, HTTPException, UploadFile, File
from typing import Dict, Any, List, Optional
import tempfile
import os
from PIL import Image
import pytesseract
import pandas as pd
import numpy as np
import io
import base64
import json

from ...services.openai_service import OpenAIService
from ...services.multilingual_two_tier_service import MultilingualTwoTierService

router = APIRouter()

class ImageToExcelAnalyzer:
    def __init__(self):
        self.openai_service = OpenAIService()
        self.multilingual_ocr = MultilingualTwoTierService()
    
    async def analyze_image(self, image_path: str, analysis_type: str = "auto") -> Dict[str, Any]:
        """Analyze image and extract structured data"""
        try:
            # Open and preprocess image
            image = Image.open(image_path)
            
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            result = {
                "image_info": {
                    "width": image.width,
                    "height": image.height,
                    "format": image.format,
                    "mode": image.mode
                },
                "analysis_type": analysis_type,
                "extracted_data": None,
                "excel_structure": None,
                "confidence": 0.0
            }
            
            if analysis_type == "ocr" or analysis_type == "auto":
                # Use OCR to extract text
                result["extracted_data"] = self._perform_ocr(image)
            
            if analysis_type == "vision" or analysis_type == "auto":
                # Use OpenAI Vision API
                vision_result = await self._analyze_with_vision_api(image_path)
                if vision_result:
                    result["extracted_data"] = vision_result
                    result["analysis_type"] = "vision"
            
            # Convert extracted data to Excel structure
            if result["extracted_data"]:
                result["excel_structure"] = self._convert_to_excel_structure(result["extracted_data"])
            
            return result
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Image analysis failed: {str(e)}")
    
    def _perform_ocr(self, image) -> Dict[str, Any]:
        """Perform OCR on image"""
        try:
            # Extract text using Tesseract
            text = pytesseract.image_to_string(image)
            
            # Try to extract data in tabular format
            data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
            
            # Process OCR results
            lines = text.strip().split('\n')
            
            # Attempt to identify table structure
            table_data = self._extract_table_from_ocr(data)
            
            return {
                "type": "ocr",
                "raw_text": text,
                "lines": lines,
                "table_data": table_data,
                "confidence": self._calculate_ocr_confidence(data)
            }
        except Exception as e:
            return {
                "type": "ocr",
                "error": str(e),
                "raw_text": "",
                "lines": [],
                "table_data": []
            }
    
    async def _analyze_with_vision_api(self, image_path: str) -> Optional[Dict[str, Any]]:
        """Use OpenAI Vision API to analyze image"""
        try:
            # Convert image to base64
            with open(image_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
            
            prompt = """
            Analyze this image and extract any tabular data, charts, or structured information.
            If it contains a table, extract the data and provide it in a structured format.
            If it contains a chart, describe the data points.
            Return the result as a JSON structure that can be converted to Excel.
            
            Format the response as:
            {
                "data_type": "table|chart|mixed",
                "headers": ["col1", "col2", ...],
                "rows": [["val1", "val2", ...], ...],
                "chart_data": {...},
                "description": "Brief description of the content"
            }
            """
            
            # Call OpenAI Vision API (placeholder - actual implementation depends on API setup)
            response = await self.openai_service.analyze_image(base64_image, prompt)
            
            if response:
                return {
                    "type": "vision_api",
                    "data": response,
                    "confidence": 0.9  # Vision API typically has high confidence
                }
            
        except Exception as e:
            print(f"Vision API error: {e}")
            return None
    
    def _extract_table_from_ocr(self, ocr_data: Dict) -> List[List[str]]:
        """Extract table structure from OCR data"""
        # Group text by lines based on vertical position
        lines = {}
        for i in range(len(ocr_data['text'])):
            if ocr_data['text'][i].strip():
                top = ocr_data['top'][i]
                # Group items within 10 pixels as same line
                line_key = top // 10 * 10
                if line_key not in lines:
                    lines[line_key] = []
                lines[line_key].append({
                    'text': ocr_data['text'][i],
                    'left': ocr_data['left'][i]
                })
        
        # Sort each line by horizontal position
        table_data = []
        for line_key in sorted(lines.keys()):
            line_items = sorted(lines[line_key], key=lambda x: x['left'])
            row = [item['text'] for item in line_items]
            table_data.append(row)
        
        return table_data
    
    def _calculate_ocr_confidence(self, ocr_data: Dict) -> float:
        """Calculate average confidence of OCR results"""
        confidences = [conf for conf in ocr_data['conf'] if conf > 0]
        if confidences:
            return sum(confidences) / len(confidences) / 100.0
        return 0.0
    
    def _convert_to_excel_structure(self, extracted_data: Dict) -> Dict[str, Any]:
        """Convert extracted data to Excel-compatible structure"""
        excel_structure = {
            "sheets": [],
            "formulas": [],
            "formatting": []
        }
        
        if extracted_data.get("type") == "ocr":
            # Convert OCR table data to Excel sheet
            if extracted_data.get("table_data"):
                sheet = {
                    "name": "Extracted Data",
                    "data": extracted_data["table_data"],
                    "headers": extracted_data["table_data"][0] if extracted_data["table_data"] else []
                }
                excel_structure["sheets"].append(sheet)
        
        elif extracted_data.get("type") == "vision_api":
            # Convert Vision API data to Excel sheet
            data = extracted_data.get("data", {})
            if data.get("headers") and data.get("rows"):
                sheet = {
                    "name": "Imported Data",
                    "data": [data["headers"]] + data["rows"],
                    "headers": data["headers"]
                }
                excel_structure["sheets"].append(sheet)
                
                # Add formatting for headers
                excel_structure["formatting"].append({
                    "range": f"A1:{chr(65 + len(data['headers']) - 1)}1",
                    "bold": True,
                    "background_color": "#E0E0E0"
                })
        
        return excel_structure

@router.post("/analyze-image")
async def analyze_image(
    file: UploadFile = File(...),
    analysis_type: str = "auto"
):
    """Analyze image and extract data for Excel"""
    # Validate file type
    if not file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.tiff')):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Please upload an image file."
        )
    
    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp_file:
        content = await file.read()
        tmp_file.write(content)
        tmp_path = tmp_file.name
    
    try:
        analyzer = ImageToExcelAnalyzer()
        result = await analyzer.analyze_image(tmp_path, analysis_type)
        
        return {
            "filename": file.filename,
            "analysis": result
        }
        
    finally:
        # Clean up
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

@router.post("/images-to-excel")
async def images_to_excel(
    files: List[UploadFile] = File(...),
    merge_strategy: str = "separate_sheets"
):
    """Convert multiple images to a single Excel file"""
    all_results = []
    
    for file in files:
        if not file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.tiff')):
            continue
        
        # Save and analyze each image
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_path = tmp_file.name
        
        try:
            analyzer = ImageToExcelAnalyzer()
            result = await analyzer.analyze_image(tmp_path)
            all_results.append({
                "filename": file.filename,
                "data": result
            })
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    # Create Excel file based on merge strategy
    if merge_strategy == "separate_sheets":
        excel_data = {
            "sheets": []
        }
        for i, result in enumerate(all_results):
            if result["data"]["excel_structure"]:
                for sheet in result["data"]["excel_structure"]["sheets"]:
                    sheet["name"] = f"{result['filename']}_{i}"
                    excel_data["sheets"].append(sheet)
    
    elif merge_strategy == "single_sheet":
        # Combine all data into one sheet
        all_data = []
        for result in all_results:
            if result["data"]["excel_structure"]:
                for sheet in result["data"]["excel_structure"]["sheets"]:
                    all_data.extend(sheet["data"])
                    all_data.append([])  # Empty row between datasets
        
        excel_data = {
            "sheets": [{
                "name": "Combined Data",
                "data": all_data
            }]
        }
    
    return {
        "processed_images": len(all_results),
        "excel_structure": excel_data,
        "merge_strategy": merge_strategy
    }

@router.post("/two-tier-ocr")
async def two_tier_ocr_analysis(
    file: UploadFile = File(...),
    context_tags: str = "",
    force_tier3: bool = False
):
    """2단계 OCR 시스템으로 이미지 분석"""
    # Validate file type
    if not file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.tiff')):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Please upload an image file."
        )
    
    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp_file:
        content = await file.read()
        tmp_file.write(content)
        tmp_path = tmp_file.name
    
    try:
        # Use the same simple OCR logic as the standalone service
        results = []
        
        # Try PaddleOCR first (Tier 2)
        try:
            from paddleocr import PaddleOCR
            paddle_ocr = PaddleOCR(use_textline_orientation=True, lang='korean')
            
            paddle_result = paddle_ocr.ocr(tmp_path)
            if paddle_result and paddle_result[0]:
                texts = []
                confidences = []
                for line in paddle_result[0]:
                    if len(line) >= 2:
                        text = line[1][0]
                        confidence = line[1][1]
                        texts.append(text)
                        confidences.append(confidence)
                
                avg_confidence = sum(confidences) / len(confidences) if confidences else 0
                results.append({
                    'success': True,
                    'text': '\n'.join(texts),
                    'confidence': avg_confidence,
                    'method': 'paddleocr',
                    'tier': 'tier2'
                })
        except Exception as e:
            print(f"PaddleOCR failed: {e}")
        
        # Try OpenAI Vision if PaddleOCR failed or confidence is low
        should_try_openai = (
            not results or  # PaddleOCR failed
            (results and results[0]['confidence'] < 0.85) or  # Low confidence
            force_tier3  # Forced Tier 3
        )
        
        if should_try_openai:
            try:
                from openai import OpenAI
                import base64
                
                openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
                
                with open(tmp_path, 'rb') as image_file:
                    image_content = base64.b64encode(image_file.read()).decode('utf-8')
                
                response = openai_client.chat.completions.create(
                    model="gpt-4-vision-preview",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text", 
                                    "text": "이 이미지의 텍스트를 정확히 추출해주세요. 특히 한국어와 테이블 구조에 주의해주세요."
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{image_content}",
                                        "detail": "high"
                                    }
                                }
                            ]
                        }
                    ],
                    max_tokens=1000,
                    temperature=0.1
                )
                
                results.append({
                    'success': True,
                    'text': response.choices[0].message.content,
                    'confidence': 0.95,
                    'method': 'openai_vision',
                    'tier': 'tier3'
                })
                
            except Exception as e:
                print(f"OpenAI Vision failed: {e}")
        
        # Select best result
        if results:
            best_result = max(results, key=lambda x: x['confidence'])
            return {
                "filename": file.filename,
                "result": best_result,
                "all_results": results,
                "processing_tier": best_result['tier']
            }
        else:
            return {
                "filename": file.filename,
                "result": None,
                "error": "No OCR methods available",
                "processing_tier": "failed"
            }
        
    finally:
        # Clean up
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

@router.post("/batch-two-tier-ocr")
async def batch_two_tier_ocr(
    files: List[UploadFile] = File(...),
    context_tags: str = "",
    parallel_processing: bool = True
):
    """배치 2단계 OCR 처리"""
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    
    tags = [tag.strip() for tag in context_tags.split(",")] if context_tags else []
    ocr_service = MultilingualTwoTierService()
    results = []
    
    def process_single_image(file_data):
        filename, content = file_data
        
        # Save temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as tmp_file:
            tmp_file.write(content)
            tmp_path = tmp_file.name
        
        try:
            # Use multilingual OCR service with Korean priority
            with open(tmp_path, 'rb') as f:
                image_data = f.read()
            result = ocr_service.extract_text(image_data)
            return {
                "filename": filename,
                "result": result,
                "success": True
            }
        except Exception as e:
            return {
                "filename": filename,
                "result": None,
                "success": False,
                "error": str(e)
            }
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    # Prepare file data
    file_data_list = []
    for file in files:
        if file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.tiff')):
            content = await file.read()
            file_data_list.append((file.filename, content))
    
    # Process files
    if parallel_processing and len(file_data_list) > 1:
        # Parallel processing
        with ThreadPoolExecutor(max_workers=min(4, len(file_data_list))) as executor:
            results = list(executor.map(process_single_image, file_data_list))
    else:
        # Sequential processing
        results = [process_single_image(data) for data in file_data_list]
    
    # Statistics
    successful = sum(1 for r in results if r['success'])
    failed = len(results) - successful
    
    tier2_count = sum(1 for r in results if r['success'] and r['result']['processing_tier'] == 'tier2')
    tier3_count = sum(1 for r in results if r['success'] and r['result']['processing_tier'] in ['tier3', 'tier3_forced'])
    
    return {
        "total_processed": len(results),
        "successful": successful,
        "failed": failed,
        "tier_statistics": {
            "tier2_count": tier2_count,
            "tier3_count": tier3_count,
            "tier3_usage_rate": tier3_count / successful if successful > 0 else 0
        },
        "results": results,
        "service_stats": ocr_service.get_processing_stats()
    }

@router.get("/ocr-service-status")
async def get_ocr_service_status():
    """OCR 서비스 상태 확인"""
    # Check PaddleOCR availability
    paddle_available = False
    try:
        from paddleocr import PaddleOCR
        paddle_available = True
    except Exception:
        pass
    
    # Check OpenAI Vision availability
    openai_available = False
    try:
        from openai import OpenAI
        import os
        if os.getenv('OPENAI_API_KEY'):
            openai_available = True
    except Exception:
        pass
    
    return {
        "service_name": "TwoTierOCRService",
        "version": "1.0.0",
        "status": "ready" if (paddle_available or openai_available) else "degraded",
        "capabilities": {
            "tier2_paddleocr": paddle_available,
            "tier3_openai_vision": openai_available,
            "cache_enabled": False,
            "batch_processing": True
        },
        "service_info": {
            "available_tiers": [
                "tier2" if paddle_available else None,
                "tier3" if openai_available else None
            ],
            "recommended_usage": "Upload Korean Excel images for optimal OCR processing"
        }
    }

@router.post("/extract-chart-data")
async def extract_chart_data(file: UploadFile = File(...)):
    """Extract data from chart images"""
    # This is a placeholder for chart data extraction
    # Full implementation would require specialized chart recognition
    
    return {
        "status": "limited_support",
        "message": "Chart data extraction requires advanced computer vision",
        "suggestions": [
            "Use the original data source if available",
            "Manually input the approximate values",
            "Use specialized chart digitizer tools"
        ],
        "basic_analysis": {
            "chart_type": "unknown",
            "approximate_values": []
        }
    }