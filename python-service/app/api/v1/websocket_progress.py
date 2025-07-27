"""
WebSocket 기반 실시간 진행률 API
WebSocket-based Real-time Progress API
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import HTMLResponse
import uuid
import logging

from ...services.websocket_manager import websocket_manager, ProgressWebSocketHandler
from ...services.progress_tracker import progress_tracker

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/progress")
async def websocket_progress_endpoint(
    websocket: WebSocket,
    user_id: str = Query(None, description="사용자 ID"),
    task_id: str = Query(None, description="추적할 작업 ID")
):
    """
    실시간 진행률 추적 WebSocket 엔드포인트
    
    사용법:
    - ws://localhost:8000/api/v1/ws/progress?user_id=user123
    - ws://localhost:8000/api/v1/ws/progress?task_id=task456
    - ws://localhost:8000/api/v1/ws/progress?user_id=user123&task_id=task456
    """
    
    connection_id = str(uuid.uuid4())
    
    try:
        # WebSocket 연결 수락 및 등록
        await websocket_manager.connect(
            websocket=websocket,
            connection_id=connection_id,
            user_id=user_id,
            task_id=task_id
        )
        
        # 기존 작업 상태 전송 (요청된 경우)
        if task_id:
            task_status = progress_tracker.get_task_status(task_id)
            if task_status:
                await websocket_manager.send_to_connection(connection_id, {
                    "type": "initial_status",
                    "task_id": task_id,
                    "data": task_status
                })
        
        # 사용자의 모든 작업 상태 전송 (요청된 경우)
        if user_id:
            user_tasks = progress_tracker.get_user_tasks(user_id)
            if user_tasks:
                await websocket_manager.send_to_connection(connection_id, {
                    "type": "user_tasks",
                    "user_id": user_id,
                    "data": user_tasks
                })
        
        # WebSocket 핸들러로 메시지 처리 위임
        handler = ProgressWebSocketHandler(websocket, connection_id)
        await handler.handle_connection()
        
    except WebSocketDisconnect:
        logger.info(f"WebSocket 연결 해제: {connection_id}")
    except Exception as e:
        logger.error(f"WebSocket 오류 ({connection_id}): {str(e)}")
    finally:
        websocket_manager.disconnect(connection_id)


@router.get("/progress/{task_id}")
async def get_task_progress(task_id: str):
    """
    작업 진행률 HTTP 조회 (WebSocket 미지원 환경용)
    """
    
    task_status = progress_tracker.get_task_status(task_id)
    
    if not task_status:
        return {
            "status": "error",
            "message": "작업을 찾을 수 없습니다",
            "task_id": task_id
        }
    
    return {
        "status": "success",
        "task_id": task_id,
        "data": task_status
    }


@router.get("/progress/user/{user_id}")
async def get_user_progress(user_id: str):
    """
    사용자의 모든 작업 진행률 조회
    """
    
    user_tasks = progress_tracker.get_user_tasks(user_id)
    
    return {
        "status": "success",
        "user_id": user_id,
        "tasks": user_tasks,
        "total_tasks": len(user_tasks)
    }


@router.get("/stats/connections")
async def get_connection_stats():
    """
    WebSocket 연결 통계 (개발/디버깅용)
    """
    
    return {
        "status": "success",
        "data": websocket_manager.get_connection_stats()
    }


@router.post("/cleanup/connections")
async def cleanup_inactive_connections():
    """
    비활성 WebSocket 연결 정리
    """
    
    cleaned_count = await websocket_manager.cleanup_inactive_connections()
    
    return {
        "status": "success",
        "message": f"{cleaned_count}개의 비활성 연결을 정리했습니다",
        "cleaned_connections": cleaned_count
    }


@router.get("/demo")
async def get_websocket_demo():
    """
    WebSocket 테스트용 HTML 페이지
    """
    
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Excel 파일 처리 진행률 모니터</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .container { max-width: 800px; margin: 0 auto; }
            .progress-bar { 
                width: 100%; 
                background-color: #f0f0f0; 
                border-radius: 10px; 
                overflow: hidden; 
                margin: 10px 0;
                height: 30px;
            }
            .progress-fill { 
                height: 100%; 
                background-color: #4CAF50; 
                transition: width 0.3s ease;
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
                font-weight: bold;
            }
            .status { 
                padding: 10px; 
                margin: 10px 0; 
                border-radius: 5px; 
                border: 1px solid #ddd;
            }
            .status.connected { background-color: #d4edda; border-color: #c3e6cb; }
            .status.error { background-color: #f8d7da; border-color: #f5c6cb; }
            .log { 
                background-color: #f8f9fa; 
                border: 1px solid #e9ecef; 
                border-radius: 5px; 
                padding: 10px; 
                height: 300px; 
                overflow-y: auto; 
                font-family: monospace; 
                font-size: 12px;
            }
            input, button { padding: 8px; margin: 5px; }
            button { background-color: #007bff; color: white; border: none; border-radius: 3px; cursor: pointer; }
            button:hover { background-color: #0056b3; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📊 Excel 파일 처리 진행률 모니터</h1>
            
            <div>
                <input type="text" id="taskId" placeholder="작업 ID (선택사항)" />
                <input type="text" id="userId" placeholder="사용자 ID (선택사항)" />
                <button onclick="connect()">연결</button>
                <button onclick="disconnect()">연결 해제</button>
            </div>
            
            <div id="connectionStatus" class="status">연결되지 않음</div>
            
            <div id="progressContainer" style="display: none;">
                <h3 id="taskTitle">작업 진행률</h3>
                <div class="progress-bar">
                    <div id="progressFill" class="progress-fill" style="width: 0%">0%</div>
                </div>
                <div id="currentOperation">대기 중...</div>
                <div id="timeInfo"></div>
            </div>
            
            <h3>실시간 로그</h3>
            <div id="log" class="log"></div>
            
            <button onclick="clearLog()">로그 지우기</button>
        </div>

        <script>
            let ws = null;
            let currentTaskId = null;

            function log(message) {
                const logDiv = document.getElementById('log');
                const timestamp = new Date().toLocaleTimeString();
                logDiv.innerHTML += `[${timestamp}] ${message}\\n`;
                logDiv.scrollTop = logDiv.scrollHeight;
            }

            function updateConnectionStatus(status, message, isError = false) {
                const statusDiv = document.getElementById('connectionStatus');
                statusDiv.textContent = `상태: ${status} - ${message}`;
                statusDiv.className = `status ${isError ? 'error' : 'connected'}`;
            }

            function updateProgress(progressData) {
                const container = document.getElementById('progressContainer');
                const fill = document.getElementById('progressFill');
                const title = document.getElementById('taskTitle');
                const operation = document.getElementById('currentOperation');
                const timeInfo = document.getElementById('timeInfo');

                container.style.display = 'block';
                
                const percentage = progressData.progress_percentage || 0;
                fill.style.width = `${percentage}%`;
                fill.textContent = `${percentage}%`;
                
                title.textContent = `${progressData.filename || '파일'} 처리 진행률`;
                operation.textContent = progressData.current_operation || '처리 중...';
                
                let timeText = '';
                if (progressData.elapsed_time) {
                    const elapsed = Math.round(progressData.elapsed_time);
                    timeText += `경과: ${elapsed}초`;
                }
                if (progressData.remaining_time) {
                    const remaining = Math.round(progressData.remaining_time);
                    timeText += ` | 남은 시간: ${remaining}초`;
                }
                timeInfo.textContent = timeText;
            }

            function connect() {
                const taskId = document.getElementById('taskId').value;
                const userId = document.getElementById('userId').value;
                
                let wsUrl = `ws://localhost:8000/api/v1/ws/progress`;
                const params = [];
                
                if (taskId) params.push(`task_id=${taskId}`);
                if (userId) params.push(`user_id=${userId}`);
                
                if (params.length > 0) {
                    wsUrl += `?${params.join('&')}`;
                }

                try {
                    ws = new WebSocket(wsUrl);
                    currentTaskId = taskId;

                    ws.onopen = function(event) {
                        updateConnectionStatus('연결됨', 'WebSocket 연결 성공');
                        log('WebSocket 연결됨');
                    };

                    ws.onmessage = function(event) {
                        const message = JSON.parse(event.data);
                        log(`수신: ${JSON.stringify(message, null, 2)}`);

                        if (message.type === 'progress_update') {
                            updateProgress(message.data);
                        } else if (message.type === 'task_completed') {
                            updateProgress({...message.data, progress_percentage: 100});
                            log('✅ 작업 완료!');
                        } else if (message.type === 'task_failed') {
                            log(`❌ 작업 실패: ${message.data.error_message}`);
                        }
                    };

                    ws.onclose = function(event) {
                        updateConnectionStatus('연결 해제됨', 'WebSocket 연결 종료', true);
                        log('WebSocket 연결 종료됨');
                    };

                    ws.onerror = function(error) {
                        updateConnectionStatus('오류', 'WebSocket 연결 오류', true);
                        log(`WebSocket 오류: ${error}`);
                    };

                } catch (error) {
                    updateConnectionStatus('오류', '연결 실패', true);
                    log(`연결 실패: ${error}`);
                }
            }

            function disconnect() {
                if (ws) {
                    ws.close();
                    ws = null;
                    currentTaskId = null;
                    document.getElementById('progressContainer').style.display = 'none';
                }
            }

            function clearLog() {
                document.getElementById('log').innerHTML = '';
            }
        </script>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html_content)