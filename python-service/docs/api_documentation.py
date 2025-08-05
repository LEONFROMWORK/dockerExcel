"""
API Documentation Generator
API 문서 생성기 - OpenAPI/Swagger 스키마
"""

from typing import Dict, Any


class APIDocumentation:
    """API 문서화 클래스"""

    @staticmethod
    def generate_openapi_schema() -> Dict[str, Any]:
        """OpenAPI 3.0 스키마 생성"""
        return {
            "openapi": "3.0.0",
            "info": {
                "title": "Excel Unified API",
                "description": "Excel 파일 분석, 오류 감지, AI 상담 통합 API",
                "version": "2.0.0",
                "contact": {
                    "name": "Excel Unified Team",
                    "email": "support@excel-unified.com",
                },
            },
            "servers": [
                {"url": "http://localhost:8000", "description": "개발 서버"},
                {
                    "url": "https://api.excel-unified.com",
                    "description": "프로덕션 서버",
                },
            ],
            "paths": {
                "/api/v1/excel/analyze": {
                    "post": {
                        "summary": "Excel 파일 분석",
                        "description": "Excel 파일을 업로드하고 종합적인 분석을 수행합니다.",
                        "tags": ["Excel Analysis"],
                        "requestBody": {
                            "required": True,
                            "content": {
                                "multipart/form-data": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "file": {
                                                "type": "string",
                                                "format": "binary",
                                                "description": "Excel 파일 (.xlsx, .xls)",
                                            },
                                            "user_query": {
                                                "type": "string",
                                                "description": "사용자 질문 (선택사항)",
                                            },
                                            "session_id": {
                                                "type": "string",
                                                "description": "세션 ID (선택사항)",
                                            },
                                        },
                                        "required": ["file"],
                                    }
                                }
                            },
                        },
                        "responses": {
                            "200": {
                                "description": "분석 성공",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "$ref": "#/components/schemas/FileAnalysisResponse"
                                        }
                                    }
                                },
                            },
                            "400": {
                                "description": "잘못된 요청",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "$ref": "#/components/schemas/ErrorResponse"
                                        }
                                    }
                                },
                            },
                        },
                    }
                },
                "/api/v1/excel/detect-errors": {
                    "post": {
                        "summary": "Excel 오류 감지",
                        "description": "IntegratedErrorDetector를 사용하여 Excel 파일의 오류를 감지합니다.",
                        "tags": ["Error Detection"],
                        "requestBody": {
                            "required": True,
                            "content": {
                                "multipart/form-data": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "file": {
                                                "type": "string",
                                                "format": "binary",
                                            },
                                            "session_id": {"type": "string"},
                                        },
                                        "required": ["file"],
                                    }
                                }
                            },
                        },
                        "responses": {
                            "200": {
                                "description": "오류 감지 완료",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "$ref": "#/components/schemas/ErrorDetectionResponse"
                                        }
                                    }
                                },
                            }
                        },
                    }
                },
                "/api/v1/ai/chat": {
                    "post": {
                        "summary": "AI 상담",
                        "description": "Excel 관련 질문에 대한 AI 상담을 제공합니다.",
                        "tags": ["AI Consultation"],
                        "requestBody": {
                            "required": True,
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/AIConsultationRequest"
                                    }
                                }
                            },
                        },
                        "responses": {
                            "200": {
                                "description": "상담 응답",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "$ref": "#/components/schemas/AIConsultationResponse"
                                        }
                                    }
                                },
                            }
                        },
                    }
                },
                "/api/v1/insights/get-insights": {
                    "post": {
                        "summary": "프로액티브 인사이트 조회",
                        "description": "패턴 분석, 오류 예측, 최적화 제안을 조회합니다.",
                        "tags": ["Insights"],
                        "requestBody": {
                            "required": True,
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "session_id": {"type": "string"},
                                            "insight_types": {
                                                "type": "array",
                                                "items": {
                                                    "type": "string",
                                                    "enum": [
                                                        "patterns",
                                                        "predictions",
                                                        "optimizations",
                                                    ],
                                                },
                                            },
                                        },
                                        "required": ["session_id"],
                                    }
                                }
                            },
                        },
                        "responses": {
                            "200": {
                                "description": "인사이트 조회 성공",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "$ref": "#/components/schemas/InsightsResponse"
                                        }
                                    }
                                },
                            }
                        },
                    }
                },
            },
            "components": {
                "schemas": {
                    "FileAnalysisResponse": {
                        "type": "object",
                        "properties": {
                            "status": {"type": "string"},
                            "data": {
                                "type": "object",
                                "properties": {
                                    "file_id": {"type": "string"},
                                    "filename": {"type": "string"},
                                    "file_analysis": {
                                        "$ref": "#/components/schemas/FileAnalysisResult"
                                    },
                                    "ai_insights": {"type": "object"},
                                    "advanced_analysis": {"type": "object"},
                                },
                            },
                            "message": {"type": "string"},
                            "timestamp": {"type": "string"},
                            "request_id": {"type": "string"},
                        },
                    },
                    "FileAnalysisResult": {
                        "type": "object",
                        "properties": {
                            "status": {"type": "string"},
                            "file_id": {"type": "string"},
                            "file_path": {"type": "string"},
                            "filename": {"type": "string"},
                            "timestamp": {"type": "string"},
                            "analysis_time": {"type": "number"},
                            "errors": {
                                "type": "array",
                                "items": {"$ref": "#/components/schemas/ErrorInfo"},
                            },
                            "summary": {"$ref": "#/components/schemas/AnalysisSummary"},
                        },
                    },
                    "ErrorInfo": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "type": {"type": "string"},
                            "severity": {
                                "type": "string",
                                "enum": ["critical", "high", "medium", "low", "info"],
                            },
                            "cell": {"type": "string"},
                            "sheet": {"type": "string"},
                            "message": {"type": "string"},
                            "is_auto_fixable": {"type": "boolean"},
                            "suggested_fix": {"type": "string", "nullable": True},
                            "confidence": {"type": "number", "nullable": True},
                        },
                    },
                    "AnalysisSummary": {
                        "type": "object",
                        "properties": {
                            "total_sheets": {"type": "integer"},
                            "total_rows": {"type": "integer"},
                            "total_cells_with_data": {"type": "integer"},
                            "total_errors": {"type": "integer"},
                            "has_errors": {"type": "boolean"},
                            "error_types": {"type": "object"},
                            "auto_fixable_count": {"type": "integer"},
                            "auto_fixable_percentage": {"type": "number"},
                        },
                    },
                    "AIConsultationRequest": {
                        "type": "object",
                        "properties": {
                            "prompt": {"type": "string"},
                            "cell_context": {"type": "object", "nullable": True},
                            "file_info": {"type": "object", "nullable": True},
                            "conversation_history": {
                                "type": "array",
                                "items": {"type": "object"},
                            },
                            "session_id": {"type": "string"},
                        },
                        "required": ["prompt"],
                    },
                    "AIConsultationResponse": {
                        "type": "object",
                        "properties": {
                            "response": {"type": "string"},
                            "suggestions": {
                                "type": "array",
                                "items": {"type": "object"},
                            },
                            "follow_up_questions": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "related_cells": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "action_items": {
                                "type": "array",
                                "items": {"type": "object"},
                            },
                            "model_used": {"type": "string"},
                            "cell_context_provided": {"type": "boolean"},
                        },
                    },
                    "ErrorResponse": {
                        "type": "object",
                        "properties": {
                            "status": {"type": "string", "example": "error"},
                            "message": {"type": "string"},
                            "error_code": {"type": "string", "nullable": True},
                            "details": {"type": "object", "nullable": True},
                            "timestamp": {"type": "string"},
                            "request_id": {"type": "string"},
                        },
                    },
                    "InsightsResponse": {
                        "type": "object",
                        "properties": {
                            "status": {"type": "string"},
                            "data": {
                                "type": "object",
                                "properties": {
                                    "session_id": {"type": "string"},
                                    "insights": {
                                        "type": "object",
                                        "properties": {
                                            "patterns": {"type": "array"},
                                            "predictions": {"type": "array"},
                                            "optimizations": {"type": "array"},
                                        },
                                    },
                                    "timestamp": {"type": "string"},
                                },
                            },
                        },
                    },
                }
            },
        }


# API 문서 마크다운 생성
def generate_api_docs_markdown() -> str:
    """API 문서를 마크다운 형식으로 생성"""
    return """
# Excel Unified API Documentation

## 개요
Excel Unified API는 Excel 파일 분석, 오류 감지, AI 상담을 통합한 RESTful API입니다.

## 주요 기능

### 1. Excel 파일 분석 (`POST /api/v1/excel/analyze`)
- Excel 파일 업로드 및 종합 분석
- IntegratedErrorDetector를 통한 오류 감지
- AI 인사이트 생성
- 차트 및 피벗 테이블 제안

### 2. 오류 감지 (`POST /api/v1/excel/detect-errors`)
- 수식 오류 감지
- 데이터 품질 검증
- 구조적 문제 식별
- VBA 코드 분석

### 3. AI 상담 (`POST /api/v1/ai/chat`)
- Excel 관련 질문 답변
- 컨텍스트 기반 상담
- 수정 제안 제공
- 다국어 지원

### 4. 프로액티브 인사이트 (`POST /api/v1/insights/get-insights`)
- 사용 패턴 분석
- 오류 예측
- 최적화 제안

## 인증
현재 API는 세션 기반 인증을 사용합니다. 향후 JWT 토큰 기반 인증이 추가될 예정입니다.

## 응답 형식
모든 응답은 표준화된 형식을 따릅니다:

### 성공 응답
```json
{
    "status": "success",
    "data": { ... },
    "message": "작업이 성공적으로 완료되었습니다",
    "timestamp": "2024-01-01T00:00:00Z",
    "request_id": "uuid"
}
```

### 오류 응답
```json
{
    "status": "error",
    "message": "오류 메시지",
    "error_code": "ERROR_CODE",
    "details": { ... },
    "timestamp": "2024-01-01T00:00:00Z",
    "request_id": "uuid"
}
```

## 제한 사항
- 최대 파일 크기: 50MB
- 지원 형식: .xlsx, .xls
- 요청 속도 제한: 분당 60회

## WebSocket 지원
실시간 업데이트를 위한 WebSocket 엔드포인트:
- `/ws/excel/{session_id}` - Excel 파일 실시간 분석
- `/ws/context/{session_id}` - 컨텍스트 동기화

## 예제 코드

### Python
```python
import requests

# 파일 분석
with open('example.xlsx', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/api/v1/excel/analyze',
        files={'file': f},
        data={'session_id': 'my-session'}
    )
    print(response.json())
```

### JavaScript
```javascript
const formData = new FormData();
formData.append('file', fileInput.files[0]);

fetch('/api/v1/excel/analyze', {
    method: 'POST',
    body: formData
})
.then(response => response.json())
.then(data => console.log(data));
```
"""


if __name__ == "__main__":
    # OpenAPI 스키마 생성
    schema = APIDocumentation.generate_openapi_schema()

    # JSON 파일로 저장
    import json

    with open("openapi_schema.json", "w", encoding="utf-8") as f:
        json.dump(schema, f, ensure_ascii=False, indent=2)

    # 마크다운 문서 생성
    docs = generate_api_docs_markdown()
    with open("API_DOCUMENTATION.md", "w", encoding="utf-8") as f:
        f.write(docs)

    print("API 문서가 생성되었습니다.")
