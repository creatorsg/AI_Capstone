"""Anthropic Claude API 기반 AI 응답 생성"""

import os
from typing import Optional

from services.ai_common import build_system_prompt, build_rag_prompt
from services.rag_service import retrieve_relevant_docs


def get_ai_response_claude(
    question: str,
    context: dict,
    child_info: Optional[dict] = None,
) -> str:
    """
    Claude API 로 최종 답변을 생성합니다.

    Args:
        question   : 사용자 원본 질문
        context    : 역질문으로 수집된 맥락
        child_info : DB 에서 조회한 아이 프로필 딕셔너리

    Returns:
        AI 답변 문자열
    """
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY 가 설정되지 않았습니다. .env 파일을 확인하세요.")

    model_name  = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
    max_tokens  = int(os.getenv("CLAUDE_MAX_TOKENS", "1024"))

    # RAG 문서 검색 (context/child_info 기반 관련 문서 조회)
    age_months = context.get("age_months")
    retrieved_docs = retrieve_relevant_docs(
        query=question,
        child_age_months=int(age_months) if age_months else None,
    )

    user_message  = build_rag_prompt(question, context, retrieved_docs)
    system_prompt = build_system_prompt(child_info)

    # Anthropic SDK로 Claude API 호출
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    message = client.messages.create(
        model=model_name,
        max_tokens=max_tokens,
        system=system_prompt,          # Claude: 시스템 프롬프트를 별도 파라미터로 전달
        messages=[
            {"role": "user", "content": user_message}
        ],
    )

    # Claude 응답 텍스트 추출
    if not message.content:
        raise RuntimeError("Claude 응답이 비어있습니다.")

    return message.content[0].text
