"""Google Gemini API 기반 AI 응답 생성 (multi-turn + 심평원 API 지원)"""

import os
from typing import Optional, List, Dict

from services.ai_common import build_system_prompt, build_rag_prompt
from services.rag_service import retrieve_relevant_docs
from services.facility_hours_service import get_facility_hours_context


def get_ai_response_gemini(
    question: str,
    context: dict,
    child_info: Optional[dict] = None,
    history: Optional[List[Dict[str, str]]] = None,
) -> str:
    """
    Gemini API 로 최종 답변을 생성합니다.

    Args:
        question   : 사용자 원본 질문
        context    : 역질문으로 수집된 맥락 (예: {"temperature": "38.5", "duration": "2일째"})
        child_info : DB 에서 조회한 아이 프로필 딕셔너리
        history    : 같은 세션의 직전 turn 들 - [{role, content}, ...]
                     routers/chat.py 의 get_session_history() 반환값을 그대로 전달

    Returns:
        AI 답변 문자열
    """
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise ValueError("GEMINI_API_KEY 가 설정되지 않았습니다. .env 파일을 확인하세요.")

    model_name = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
    max_history_turns = int(os.getenv("CHAT_HISTORY_TURNS", "10"))

    # 운영시간 질문: 심평원 API에서 실제 데이터 조회 후 프롬프트에 주입
    hours_context = get_facility_hours_context(question)

    # RAG 문서 검색 (context/child_info 기반 관련 문서 조회)
    age_months = context.get("age_months")
    retrieved_docs = retrieve_relevant_docs(
        query=question,
        child_info=child_info,
        child_age_months=int(age_months) if age_months else None,
    )

    user_message = build_rag_prompt(question, context, retrieved_docs, hours_context=hours_context)
    system_prompt = build_system_prompt(child_info)

    # Google Gemini SDK로 API 호출
    from google import genai as google_genai
    from google.genai import types as genai_types

    client = google_genai.Client(api_key=api_key)

    # 멀티턴 히스토리 구성
    # Gemini contents 형식: [{"role": "user"|"model", "parts": [{"text": ...}]}, ...]
    # routers/chat.py 의 history 는 role="assistant" 를 사용하므로 "model" 로 변환
    contents: List[dict] = []
    if history:
        trimmed = history[-(max_history_turns * 2):]
        for msg in trimmed:
            gemini_role = "model" if msg["role"] == "assistant" else "user"
            contents.append({
                "role": gemini_role,
                "parts": [{"text": msg["content"]}],
            })

    # 현재 turn 의 user 메시지 추가
    contents.append({
        "role": "user",
        "parts": [{"text": user_message}],
    })

    response = client.models.generate_content(
        model=f"models/{model_name}",
        contents=contents,
        config=genai_types.GenerateContentConfig(
            system_instruction=system_prompt,
        ),
    )

    if not response.text:
        raise RuntimeError("Gemini 응답이 비어있습니다.")

    return response.text
