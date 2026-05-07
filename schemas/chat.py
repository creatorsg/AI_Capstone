from pydantic import BaseModel
from typing import Optional


class ChatMessageRequest(BaseModel):
    """채팅 메시지 요청 (세션 기반 대화)"""
    child_id: Optional[int] = None
    session_id: Optional[str] = None   # 없으면 새 대화 시작
    message: str                        # 사용자 메시지


class ChatMessageResponse(BaseModel):
    """채팅 메시지 응답"""
    session_id: str         # 이후 요청에 계속 사용
    message: str            # AI 응답 (역질문 또는 최종 답변)
    is_emergency: bool = False
    needs_more_context: bool = False   # True이면 아직 역질문 중
    is_final: bool = False             # True이면 GPT 최종 답변 완료


# 하위 호환용 (기존 context 방식 - 제거 예정)
class ChatRequest(BaseModel):
    child_id: Optional[int] = None
    question: str
    context: dict = {}


class ChatResponse(BaseModel):
    child_id: Optional[int] = None
    question: str
    answer: str
    status: str = "success"
    is_emergency: bool = False
    needs_more_context: bool = False
    context_collected: dict = {}
