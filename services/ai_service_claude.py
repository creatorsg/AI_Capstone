"""Anthropic Claude API 기반 AI 응답 생성 (인텐트별 RAG 프롬프트 + multi-turn 지원)

파이프라인:
  [1] 시설 운영시간 조회 (심평원 API)
  [2] retrieve_with_analysis() → docs, analysis(intent/risk), child_profile
  [3] get_answer_prompt(intent) → 인텐트별 프롬프트 템플릿 선택
  [4] 프롬프트 포매팅 → Claude API 호출 (system + history + user)
  [5] apply_safety_prefix() → risk_level='high' 이면 안전 경고 문구 앞에 추가
"""

import os
from typing import Optional, List, Dict

from services.ai_common import build_system_prompt
from services.facility_hours_service import get_facility_hours_context


def get_ai_response_claude(
    question: str,
    context: dict,
    child_info: Optional[dict] = None,
    history: Optional[List[Dict[str, str]]] = None,
) -> str:
    """
    Claude API로 최종 답변을 생성합니다.

    Args:
        question   : 사용자 원본 질문 (현재 turn)
        context    : 역질문으로 수집된 맥락 (현재 turn)
        child_info : DB에서 조회한 아이 프로필 딕셔너리
        history    : 같은 세션의 직전 turn [{role, content}, ...] 순차
                     CHAT_HISTORY_TURNS 환경변수로 최대 개수 제한 (기본 10턴 = 20 메시지)

    Returns:
        AI 답변 문자열
    """
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")

    model_name        = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
    max_tokens        = int(os.getenv("CLAUDE_MAX_TOKENS", "1024"))
    max_history_turns = int(os.getenv("CHAT_HISTORY_TURNS", "10"))

    # ── [1] 운영시간 질문: 심평원 API 조회 ──────────────────────────────────
    hours_context = get_facility_hours_context(question)

    # ── [2] RAG: 인텐트 분석 + 문서 검색 + 리랭킹 ───────────────────────────
    from services.rag_service import retrieve_with_analysis
    from services.rag.rag_core import (
        build_context,
        apply_safety_prefix,
        format_child_context,
        format_recent_logs,
    )
    from services.rag.prompts import get_answer_prompt, format_chat_history

    docs, analysis, risk_level, child_profile = retrieve_with_analysis(
        query=question,
        child_info=child_info,
        top_k=5,
    )

    intent = analysis.get("intent", "unknown")

    # ── [3] 참고 문서 컨텍스트 조합 ─────────────────────────────────────────
    context_str = build_context(docs) if docs else "관련 문서를 찾지 못했습니다."
    if hours_context:
        context_str = f"[운영시간 정보]\n{hours_context}\n\n" + context_str
    if context:  # 역질문으로 수집된 추가 맥락
        extra = "\n".join(f"- {k}: {v}" for k, v in context.items())
        context_str += f"\n\n[수집된 추가 맥락]\n{extra}"

    # ── [4] 인텐트별 프롬프트 포매팅 ────────────────────────────────────────
    child_context_str = format_child_context(child_profile)
    recent_logs_str   = format_recent_logs(None)
    chat_history_str  = format_chat_history(history or [], max_turns=3)

    prompt_template = get_answer_prompt(intent)
    user_message = prompt_template.format_messages(
        child_context=child_context_str,
        recent_logs=recent_logs_str,
        chat_history=chat_history_str,
        context=context_str,
        question=question,
    )[0].content

    # ── Claude messages 배열: history(최근 N턴) + user ───────────────────────
    # Claude API는 system을 별도 파라미터로 전달
    system_prompt = build_system_prompt(child_info)
    messages: List[Dict[str, str]] = []
    if history:
        messages.extend(history[-(max_history_turns * 2):])
    messages.append({"role": "user", "content": user_message})

    # ── Claude API 호출 ──────────────────────────────────────────────────────
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    message = client.messages.create(
        model=model_name,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=messages,
    )

    if not message.content:
        raise RuntimeError("Claude 응답이 비어있습니다.")

    answer = message.content[0].text

    # ── [5] 고위험 질문이면 안전 경고 앞에 추가 ─────────────────────────────
    return apply_safety_prefix(answer, risk_level)
