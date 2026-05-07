"""AI 서비스 팩토리 (Claude/Gemini 간 전환 가능)"""

import os
from typing import Optional, List, Dict

from services.ai_common import (
    check_emergency,
    needs_context_collection,
    get_missing_context,
    get_pending_field,     # routers/chat.py 에서 re-export 해서 사용
)


# 공개 인터페이스 (routers/chat.py 에서 호출)

def get_ai_response(
    question: str,
    context: dict = None,
    child_info: Optional[dict] = None,
    child_id: Optional[int] = None,                          # 하위 호환용 (현재 미사용)
    history: Optional[List[Dict[str, str]]] = None,          # 멀티턴 대화 히스토리
) -> dict:
    """
    AI 에게 질문을 보내고 표준 응답 딕셔너리를 반환합니다.

    Args:
        question   : 현재 사용자 질문
        context    : 역질문으로 수집된 맥락 (현재 turn)
        child_info : DB 에서 조회한 아이 프로필 딕셔너리
        child_id   : 하위 호환용 (현재 미사용)
        history    : 같은 세션의 직전 turn 들 - [{role, content}, ...]
                     routers/chat.py 의 get_session_history() 반환값을 그대로 전달

    반환 형태:
    {
        "answer":             str,   # AI 답변 또는 역질문
        "is_emergency":       bool,  # 응급 상황 여부
        "needs_more_context": bool,  # 역질문 중 여부
        "context_collected":  dict,  # 현재까지 수집된 컨텍스트
    }
    """
    if context is None:
        context = {}

    # 1단계: 응급 상황 즉시 응답
    if check_emergency(question):
        return {
            "answer": (
                "⚠️ 응급 상황이 의심됩니다!\n"
                "즉시 119 에 연락하거나 가까운 응급실을 방문하세요.\n"
                "전화: 119 (응급) / 1339 (의료 상담)"
            ),
            "is_emergency": True,
            "needs_more_context": False,
            "context_collected": context,
        }

    # 2단계: 역질문 (컨텍스트 부족 시)
    if needs_context_collection(question):
        missing = get_missing_context(question, context)
        if missing:
            return {
                "answer": missing,
                "is_emergency": False,
                "needs_more_context": True,
                "context_collected": context,
            }

    # 3단계: AI 본답변 생성
    provider = os.getenv("AI_PROVIDER", "claude").lower()

    try:
        if provider == "gemini":
            from services.ai_service_gemini import get_ai_response_gemini
            answer = get_ai_response_gemini(question, context, child_info, history=history)
        elif provider == "openai":
            from services.ai_service_openai import get_ai_response_openai
            answer = get_ai_response_openai(question, context, child_info, history=history)
        else:
            # 기본값: Claude (history 멀티턴 지원)
            from services.ai_service_claude import get_ai_response_claude
            answer = get_ai_response_claude(question, context, child_info, history=history)

        return {
            "answer":             answer,
            "is_emergency":       False,
            "needs_more_context": False,
            "context_collected":  context,
        }

    except Exception as e:
        error_msg = str(e)
        print(f"[AI Service Error] provider={provider} | {error_msg}")
        return {
            "answer": f"AI 응답 생성 중 오류가 발생했습니다.\n오류: {error_msg}",
            "is_emergency": False,
            "needs_more_context": False,
            "context_collected": context,
        }

