#!/usr/bin/env python3
"""
Enhanced Context Manager Test
확장된 컨텍스트 매니저 테스트
"""
import asyncio
import sys
import os

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


async def test_workbook_context():
    """WorkbookContext 테스트"""
    print("1. WorkbookContext 테스트")

    try:
        from app.services.context import WorkbookContext, CellInfo, SheetContext

        # SheetContext 생성
        sheet = SheetContext(
            name="Sheet1",
            cells={},
            row_count=100,
            column_count=26,
            data_ranges=[],
            named_ranges={},
        )

        # 셀 정보 추가
        cell1 = CellInfo(
            address="A1", sheet="Sheet1", value=100, formula=None, errors=[]
        )
        sheet.add_cell(cell1)

        cell2 = CellInfo(
            address="B1",
            sheet="Sheet1",
            value="#DIV/0!",
            formula="=A1/0",
            errors=[{"type": "DIV_ZERO", "message": "0으로 나누기"}],
        )
        sheet.add_cell(cell2)

        # WorkbookContext 생성
        workbook = WorkbookContext(
            file_id="test_file_001",
            file_name="test.xlsx",
            sheets={"Sheet1": sheet},
            global_errors=[],
            analysis_summary={},
        )

        print("   ✅ WorkbookContext 생성 성공")
        print(f"   - 파일: {workbook.file_name}")
        print(f"   - 시트 수: {len(workbook.sheets)}")
        print(f"   - 셀 수: {len(sheet.cells)}")

        # 셀 조회 테스트
        cell = workbook.get_cell("Sheet1", "A1")
        if cell:
            print(f"   ✅ 셀 조회 성공: {cell.address} = {cell.value}")

        # JSON 직렬화 테스트
        json_str = workbook.to_json()
        print(f"   ✅ JSON 직렬화 성공: {len(json_str)} bytes")

        return True

    except Exception as e:
        print(f"   ❌ WorkbookContext 테스트 실패: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_session_store():
    """SessionContextStore 테스트"""
    print("\n2. SessionContextStore 테스트")

    try:
        from app.services.context import get_session_store

        # Redis 연결 여부 확인
        try:
            store = await get_session_store()
            print("   ✅ SessionContextStore 초기화 성공")
        except Exception as e:
            print(f"   ⚠️  Redis 연결 실패 (로컬 캐시만 사용): {e}")
            return True  # Redis가 없어도 계속 진행

        # 세션 컨텍스트 저장
        session_id = "test_session_001"
        context_data = {
            "user_id": "user123",
            "file_info": {"name": "test.xlsx", "sheets": ["Sheet1", "Sheet2"]},
        }

        success = await store.save_session_context(session_id, context_data)
        print(f"   ✅ 세션 컨텍스트 저장: {success}")

        # 세션 컨텍스트 조회
        retrieved = await store.get_session_context(session_id)
        if retrieved:
            print("   ✅ 세션 컨텍스트 조회 성공")
            print(f"   - user_id: {retrieved.get('user_id')}")

        # 채팅 메시지 추가
        await store.add_chat_message(session_id, "user", "Excel 오류를 찾아주세요")
        await store.add_chat_message(
            session_id, "assistant", "A1 셀에 #DIV/0! 오류가 있습니다"
        )
        print("   ✅ 채팅 메시지 추가 성공")

        # 선택된 셀 업데이트
        cells = [{"address": "A1", "value": 100}, {"address": "B1", "value": "#DIV/0!"}]
        await store.update_selected_cells(session_id, cells)
        print("   ✅ 선택된 셀 업데이트 성공")

        return True

    except Exception as e:
        print(f"   ❌ SessionContextStore 테스트 실패: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_enhanced_context_manager():
    """EnhancedContextManager 테스트"""
    print("\n3. EnhancedContextManager 테스트")

    try:
        from app.services.context import get_enhanced_context_manager

        manager = get_enhanced_context_manager()
        print("   ✅ EnhancedContextManager 초기화 성공")

        # 분석 결과 시뮬레이션
        session_id = "test_session_002"
        analysis_result = {
            "sheets": {
                "Sheet1": {
                    "row_count": 10,
                    "column_count": 5,
                    "cells": {
                        "A1": {"value": 100, "formula": None},
                        "B1": {"value": 200, "formula": None},
                        "C1": {"value": "#DIV/0!", "formula": "=A1/0"},
                    },
                }
            },
            "errors": [
                {
                    "id": "error_001",
                    "type": "DIV_ZERO",
                    "sheet": "Sheet1",
                    "cell": "C1",
                    "message": "0으로 나누기 오류",
                }
            ],
            "summary": {"total_cells": 3, "total_errors": 1},
        }

        # 워크북 컨텍스트 초기화
        workbook_context = await manager.initialize_workbook_context(
            session_id=session_id,
            file_id="test_file_002",
            file_name="test_enhanced.xlsx",
            analysis_result=analysis_result,
        )

        print("   ✅ 워크북 컨텍스트 초기화 성공")
        print(f"   - 총 셀 수: {workbook_context.total_cells}")
        print(f"   - 총 오류 수: {workbook_context.total_errors}")

        # 멀티 셀 선택 테스트
        selected_cells = [
            {"address": "A1", "sheetName": "Sheet1", "value": 100},
            {"address": "B1", "sheetName": "Sheet1", "value": 200},
            {"address": "C1", "sheetName": "Sheet1", "value": "#DIV/0!"},
        ]

        context_info = await manager.update_multi_cell_selection(
            session_id, selected_cells
        )

        print("   ✅ 멀티 셀 선택 업데이트 성공")
        print(f"   - 선택된 셀 수: {context_info.get('cell_count')}")

        # 확장된 컨텍스트 조회
        enhanced_context = await manager.get_enhanced_context(session_id)
        print("   ✅ 확장된 컨텍스트 조회 성공")
        print(f"   - session_id: {enhanced_context.get('session_id')}")
        print(
            f"   - 워크북 컨텍스트 존재: {enhanced_context.get('workbook_context') is not None}"
        )

        return True

    except Exception as e:
        print(f"   ❌ EnhancedContextManager 테스트 실패: {e}")
        import traceback

        traceback.print_exc()
        return False


async def main():
    """메인 테스트 함수"""
    print("=" * 60)
    print("확장된 컨텍스트 매니저 테스트")
    print("=" * 60)

    # 1. WorkbookContext 테스트
    await test_workbook_context()

    # 2. SessionContextStore 테스트
    await test_session_store()

    # 3. EnhancedContextManager 테스트
    await test_enhanced_context_manager()

    print("\n" + "=" * 60)
    print("테스트 완료")
    print("=" * 60)


if __name__ == "__main__":
    # Redis URL 설정 (없으면 로컬 캐시만 사용)
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379")

    asyncio.run(main())
