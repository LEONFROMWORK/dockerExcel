"""
WebSocket 메시지 타입 상수 정의
Python과 JavaScript 간 일관성 유지
"""


class WebSocketMessageType:
    """WebSocket 메시지 타입 상수"""

    # 일반 메시지
    WELCOME = "welcome"
    SUBSCRIBED = "subscribed"
    PING = "ping"
    PONG = "pong"
    ERROR = "error"

    # 진행 상황
    PROGRESS = "progress"
    TASK_START = "task_start"
    TASK_COMPLETE = "task_complete"

    # Excel 관련
    ERROR_DETECTED = "error_detected"
    ERROR_FIXED = "error_fixed"
    CELL_UPDATE = "cell_update"
    CELL_CHECK_RESULT = "cell_check_result"
    AI_SUGGESTION = "ai_suggestion"

    # 요청 타입
    ANALYZE_FILE = "analyze_file"
    CHECK_CELL = "check_cell"
    FIX_ERROR = "fix_error"
    UPDATE_CONTEXT = "update_context"
    AI_QUERY = "ai_query"


class WebSocketSessionStatus:
    """WebSocket 세션 상태"""

    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class WebSocketErrorType:
    """WebSocket 오류 타입"""

    CONNECTION_ERROR = "connection_error"
    AUTHENTICATION_ERROR = "authentication_error"
    VALIDATION_ERROR = "validation_error"
    PROCESSING_ERROR = "processing_error"
    TIMEOUT_ERROR = "timeout_error"
