"""OpenAI API 기반 AI 응답 생성 (multi-turn 지원)"""

import os
from typing import Optional, List, Dict

from services.ai_common import build_system_prompt, build_rag_prompt
from services.rag_service import retrieve_relevant_docs
from services.facility_hours_service import get_facility_hours_context


def get_ai_response_openai(
    question: str,
    context: dict,
    child_info: Optional[dict] = None,
    history: Optional[List[Dict[str, str]]] = None,
) -> str:
    """
    OpenAI API 로 최종 답변을 생성합니다.

    Args:
        question   : 사용자 원본 질문 (현재 turn)
        context    : 역질문으로 수집된 맥락 (현재 turn)
        child_info : DB 에서 조회한 아이 프로필 딕셔너리
        history    : 같은 세션의 직전 turn 들 - [{role, content}, ...] 순차

    Returns:
        AI 답변 문자열
    """
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        raise ValueError("OPENAI_API_KEY 가 설정되지 않았습니다. .env 파일을 확인하세요.")

    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    max_tokens = int(os.getenv("OPENAI_MAX_TOKENS", "1024"))
    max_history_turns = int(os.getenv("CHAT_HISTORY_TURNS", "10"))

    # ── 운영시간 질문: 심평원 API에서 실제 데이터 조회 후 프롬프트에 주입 ──
    hours_context = get_facility_hours_context(question)

    # RAG 문서 검색 (현재 질문 기준)
    age_months = context.get("age_months")
    retrieved_docs = retrieve_relevant_docs(
        query=question,
        child_info=child_info,
        child_age_months=int(age_months) if age_months else None,
    )

    user_message = build_rag_prompt(question, context, retrieved_docs, hours_context=hours_context)
    system_prompt = build_system_prompt(child_info)

    # messages 배열 구성: system + history (최근 N턴) + 현재 user message
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": system_prompt},
    ]
    if history:
        trimmed = history[-(max_history_turns * 2):]
        messages.extend(trimmed)
    messages.append({"role": "user", "content": user_message})

    from openai import OpenAI
    client = OpenAI(api_key=api_key)

    response = client.chat.completions.create(
        model=model_name,
        messages=messages,
        max_tokens=max_tokens,
    )

    if not response.choices:
        raise RuntimeError("OpenAI 응답이 비어있습니다.")

    return response.choices[0].message.content
