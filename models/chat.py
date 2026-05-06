from sqlalchemy import Column, Integer, Text, DateTime, String, JSON, ForeignKey
from sqlalchemy.sql import func
from database import Base


class ChatHistory(Base):
    """AI 채팅 최종 기록 - 역질문 완료 후 저장"""
    __tablename__ = "chat_histories"

    id = Column(Integer, primary_key=True, index=True)
    child_id = Column(Integer, ForeignKey("children.id"), nullable=True)
    session_id = Column(String(36), nullable=True, index=True)  # 세션 연결 (0006 마이그레이션)
    question = Column(Text, nullable=False)   # 원본 질문
    answer = Column(Text, nullable=True)      # GPT 최종 답변
    context = Column(JSON, default=dict)      # 수집된 맥락 (기록용)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class ConversationSession(Base):
    """대화 세션 (역질문 흐름 상태 관리)"""
    __tablename__ = "conversation_sessions"

    id = Column(String, primary_key=True)                               # UUID
    child_id = Column(Integer, ForeignKey("children.id"), nullable=True)
    original_question = Column(Text, nullable=True)                     # 최초 질문 (유지됨)
    context = Column(JSON, default=dict)                                # 수집된 맥락 누적
    pending_field = Column(String, nullable=True)                       # 현재 기다리는 필드
    status = Column(String, default="active")                           # "active" | "completed"
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
