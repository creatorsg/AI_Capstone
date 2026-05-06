"""RAG 서비스 - juhyeong ChromaDB 파이프라인 연동

흐름:
  질문 → analyze_query() → rewrite_query() → Chroma 검색 → simple_rerank()
  → 문서 텍스트 리스트 반환 → ai_service_claude.py 에서 Claude로 최종 답변 생성

ChromaDB / OpenAI API 가 설정되지 않은 경우 빈 리스트 반환 (graceful fallback).
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def retrieve_relevant_docs(
    query: str,
    child_info: Optional[dict] = None,
    child_age_months: Optional[int] = None,
    top_k: int = 3,
) -> list[str]:
    """
    juhyeong의 RAG 파이프라인으로 관련 문서를 검색해 텍스트 리스트로 반환합니다.

    Args:
        query            : 사용자 질문
        child_info       : DB에서 조회한 아이 정보 딕셔너리 (fount-project 형식)
                           - 'gender' 키를 juhyeong 형식 'sex'로 자동 변환
        child_age_months : child_info가 없을 때 대체로 사용할 월령 정수
        top_k            : 반환할 최대 문서 수

    Returns:
        관련 문서 텍스트 리스트. 검색 실패 시 빈 리스트 반환.
    """
    try:
        from services.rag.rag_core import (
            analyze_query,
            rewrite_query,
            get_retriever,
            simple_rerank,
            calculate_age_months,
            age_group_from_months,
        )

        # fount-project 'gender' → juhyeong 'sex' 필드 변환
        child_profile: Optional[dict] = None
        if child_info:
            child_profile = dict(child_info)
            if "gender" in child_profile and "sex" not in child_profile:
                child_profile["sex"] = child_profile.pop("gender")

        # 1. 쿼리 의도 분석
        analysis = analyze_query(query)

        # 2. 검색용 쿼리 재작성
        rewritten = rewrite_query(query, child_profile, analysis)

        # 3. 인텐트 기반 리트리버 라우팅 + 문서 검색
        retriever = get_retriever(analysis.get("intent", "unknown"))
        docs = retriever.invoke(rewritten)

        # 4. 월령 기반 리랭킹
        age_months = (
            calculate_age_months(child_profile.get("birth_date")) if child_profile
            else child_age_months
        )
        age_group = age_group_from_months(age_months)
        docs = simple_rerank(
            docs,
            intent=analysis.get("intent", "unknown"),
            topic=analysis.get("topic"),
            age_group=age_group,
        )

        # 5. 상위 k개 문서의 텍스트 추출
        return [doc.page_content for doc in docs[:top_k]]

    except Exception as exc:
        logger.warning("RAG 검색 실패, 빈 결과로 fallback: %s", exc)
        return []


def build_rag_prompt(
    question: str,
    context: dict,
    retrieved_docs: list[str],
    hours_context: str | None = None,
) -> str:
    """
    검색된 문서를 포함한 최종 프롬프트를 생성합니다.
    (ai_common.build_rag_prompt 와 동일한 인터페이스 — 하위 호환용)
    """
    context_str = "\n".join(f"- {k}: {v}" for k, v in context.items()) if context else "없음"

    if retrieved_docs:
        docs_str = "\n\n".join(
            f"[참고 문서 {i+1}]\n{doc}" for i, doc in enumerate(retrieved_docs)
        )
        return (
            f"사용자 질문: {question}\n\n"
            f"수집된 맥락:\n{context_str}\n\n"
            f"관련 육아 정보:\n{docs_str}\n\n"
            "위 정보를 바탕으로 답변해주세요."
        )
    # RAG 문서 없을 때: 질문 + 맥락만으로 프롬프트 구성
    return (
        f"사용자 질문: {question}\n\n"
        f"수집된 맥락:\n{context_str}"
    )
