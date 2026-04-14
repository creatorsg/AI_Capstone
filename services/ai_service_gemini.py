"""Google Gemini API 기반 AI 응답 생성"""

import os
from typing import Optional

from services.ai_common import build_system_prompt, build_rag_prompt
from services.rag_service import retrieve_relevant_docs


def get_ai_response_gemini(
    question: str,
    context: dict,
    child_info: Optional[dict] = None,
) -> str:
    """
    Gemini API 로 최종 답변을 생성합니다.

    Args:
        question   : 사용자 원본 질문
        context    : 역질문으로 수집된 맥락 (예: {"temperature": "38.5", "duration": "2일째"})
        child_info : DB 에서 조회한 아이 프로필 딕셔너리

    Returns:
        AI 답변 문자열
    """
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise ValueError("GEMINI_API_KEY 가 설정되지 않았습니다. .env 파일을 확인하세요.")

    model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    # RAG 문서 검색 (context/child_info 기반 관련 문서 조회)
    age_months = context.get("age_months")
    retrieved_docs = retrieve_relevant_docs(
        query=question,
        child_age_months=int(age_months) if age_months else None,
    )

    full_prompt   = build_rag_prompt(question, context, retrieved_docs)
    system_prompt = build_system_prompt(child_info)

    # Google Gemini SDK로 API 호출
    from google import genai as google_genai
    client = google_genai.Client(api_key=api_key)

    response = client.models.generate_content(
        model=f"models/{model_name}",
        contents=f"{system_prompt}\n\n질문: {full_prompt}",
    )

    if not response.text:
        raise RuntimeError("Gemini 응답이 비어있습니다.")

    return response.text
