"""AI 채팅 API (세션 기반, JWT 인증, 소유권 검증, 멀티턴 history 전달)

세션 모델:
  - 세션은 "한 대화 스레드" 이며, 여러 턴(Q -> 역질문 -> 최종답변) 을 담을 수 있다.
  - 사용자가 명시적으로 새 세션을 만들기 전까지 절대 자동 종료되지 않는다.
  - LLM 호출 시 같은 session 의 직전 N개 turn 을 history 로 함께 전달
    -> "전에 ~했던가?" 같은 후속 질문을 정확히 이해함.
"""

import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from database import get_db
from models.chat import ChatHistory, ConversationSession
from models.child import Child, ChildProfile
from models.health import ChildNote
from models.user import User
from schemas.chat import ChatMessageRequest, ChatMessageResponse
from services.ai_service import get_ai_response
from services.ai_common import get_pending_field
from services.auth_service import get_current_user, verify_child_ownership

router = APIRouter(
    prefix="/chat",
    tags=["AI 채팅"]
)


def get_child_info(child_id: int, db: Session) -> dict | None:
    """아이 정보를 AI 프롬프트 컨텍스트용 딕셔너리로 반환."""
    from datetime import date, timedelta
    child = db.query(Child).filter(Child.id == child_id).first()
    profile = db.query(ChildProfile).filter(ChildProfile.child_id == child_id).first()

    if not child and not profile:
        return None

    # 최근 30일 아이 노트 요약 (behavior + symptom 위주로 AI 컨텍스트에 주입)
    recent_notes: list[str] = []
    since = date.today() - timedelta(days=30)
    notes = (
        db.query(ChildNote)
        .filter(
            ChildNote.child_id == child_id,
            ChildNote.note_date >= since,
            ChildNote.category.in_(["behavior", "symptom"]),
        )
        .order_by(ChildNote.note_date.desc())
        .limit(5)
        .all()
    )
    for n in notes:
        val_str = f" ({n.value}{n.unit})" if n.value else ""
        recent_notes.append(f"[{n.note_date} {n.category}]{val_str} {n.content[:80]}")

    return {
        "name":          child.name if child else None,
        "birth_date":    str(child.birth_date) if child and child.birth_date else None,
        "gender":        child.gender if child else None,
        "height_cm":     child.height_cm if child else None,
        "weight_kg":     child.weight_kg if child else None,
        "allergies":     child.allergies if child else [],
        "conditions":    child.conditions if child else [],
        "notes":         child.notes if child else "",
        "blood_type":    profile.blood_type if profile else None,
        "medical_notes": profile.medical_notes if profile else None,
        "recent_child_notes": recent_notes,   # 최근 30일 행동/증상 노트 → RAG 컨텍스트
    }


def get_session_history(session_id: str, db: Session, max_turns: int = 10) -> list[dict]:
    """
    같은 세션의 직전 turn 들을 LLM messages 형태로 반환.

    반환 예시:
        [
          {"role": "user", "content": "내 아이 이름이 뭐더라"},
          {"role": "assistant", "content": "인선이 입니다..."},
          {"role": "user", "content": "그럼 나이는?"},
          {"role": "assistant", "content": "..."},
        ]

    오래된 turn 부터 (생성 시각 오름차순) 정렬하여 반환.
    """
    rows = (
        db.query(ChatHistory)
        .filter(ChatHistory.session_id == session_id)
        .order_by(ChatHistory.created_at.desc())
        .limit(max_turns)
        .all()
    )
    # 최신 N개를 가져온 뒤 시간 오름차순으로 뒤집어서 LLM 에 전달
    rows.reverse()

    messages: list[dict] = []
    for h in rows:
        if h.question:
            messages.append({"role": "user", "content": h.question})
        if h.answer:
            messages.append({"role": "assistant", "content": h.answer})
    return messages


# ─────────────────────────────────────────────────────────────────────────
# 채팅 엔드포인트
# ─────────────────────────────────────────────────────────────────────────

@router.post("/", response_model=ChatMessageResponse, summary="AI 채팅 (세션 기반, 멀티턴)")
def chat(
    request: ChatMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    세션 기반 대화형 AI 채팅 엔드포인트.

    첫 메시지 (새 대화):
        { "child_id": 1, "message": "애가 열이 나요" }

    이후 메시지 (같은 세션 계속 / 새 질문 모두 가능):
        { "session_id": "받은-uuid", "message": "38.5도요" }

    같은 session_id 안의 직전 turn 들이 LLM 에 자동으로 전달되어
    "전에 ~했던가?" 같은 후속 질문이 자연스럽게 이어집니다.
    """
    max_history_turns = int(os.getenv("CHAT_HISTORY_TURNS", "10"))

    # ── 기존 세션 이어가기 ────────────────────────────────────────────
    if request.session_id:
        session = db.query(ConversationSession).filter(
            ConversationSession.id == request.session_id
        ).first()
        if not session:
            raise HTTPException(
                status_code=404,
                detail="세션을 찾을 수 없습니다. 새 대화를 시작해주세요.",
            )

        if session.child_id is not None:
            verify_child_ownership(session.child_id, db, current_user)

        if session.pending_field:
            # 역질문 답변 단계
            context = dict(session.context or {})
            context[session.pending_field] = request.message
            session.context = context
            session.pending_field = None
            db.commit()

            question = session.original_question
            context = dict(session.context or {})
            child_id = session.child_id
        else:
            # 이번 메시지를 새 turn 의 첫 질문으로
            session.original_question = request.message
            session.context = {}
            db.commit()

            question = request.message
            context = {}
            child_id = session.child_id

    # ── 새 대화 시작 ─────────────────────────────────────────────────
    else:
        if request.child_id is not None:
            verify_child_ownership(request.child_id, db, current_user)

        session = ConversationSession(
            id=str(uuid.uuid4()),
            child_id=request.child_id,
            original_question=request.message,
            context={},
        )
        db.add(session)
        db.commit()

        question = request.message
        context = {}
        child_id = request.child_id

    # ── 같은 세션의 직전 history 가져오기 ─────────────────────────────
    history = get_session_history(session.id, db, max_turns=max_history_turns)

    # ── AI 응답 생성 ─────────────────────────────────────────────────
    child_info = get_child_info(child_id, db) if child_id else None
    result = get_ai_response(
        question=question,
        context=context,
        child_info=child_info,
        child_id=child_id,
        history=history,
    )

    if result["needs_more_context"]:
        pending = get_pending_field(question, context)
        session.pending_field = pending
        db.commit()

    else:
        # 최종 답변 - ChatHistory 저장 (session_id 포함)
        history_row = ChatHistory(
            child_id=child_id,
            session_id=session.id,
            question=question,
            answer=result["answer"],
            context=result["context_collected"],
        )
        db.add(history_row)

        # 현재 turn 만 정리 (세션은 active 유지)
        session.original_question = None
        session.context = {}
        session.pending_field = None
        db.commit()

    return ChatMessageResponse(
        session_id=session.id,
        message=result["answer"],
        is_emergency=result["is_emergency"],
        needs_more_context=result["needs_more_context"],
        is_final=not result["needs_more_context"],
    )


@router.get("/history/{child_id}", summary="채팅 기록 조회 (아이별, 최신순)")
def get_chat_history(
    child_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """아이별 과거 채팅 기록을 최신순으로 반환합니다."""
    verify_child_ownership(child_id, db, current_user)
    return (
        db.query(ChatHistory)
        .filter(ChatHistory.child_id == child_id)
        .order_by(ChatHistory.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_200_OK,
    summary="세션 대화 기록 전체 삭제",
)
def delete_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    세션과 해당 세션의 모든 대화 기록(ChatHistory)을 삭제합니다.

    - 본인 소유 세션만 삭제 가능
    - ChatHistory → ConversationSession 순서로 삭제 (FK 제약 방지)
    """
    session = db.query(ConversationSession).filter(
        ConversationSession.id == session_id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    if session.child_id is not None:
        verify_child_ownership(session.child_id, db, current_user)

    # ChatHistory 먼저 삭제 후 세션 삭제
    deleted_count = (
        db.query(ChatHistory)
        .filter(ChatHistory.session_id == session_id)
        .delete(synchronize_session=False)
    )
    db.delete(session)
    db.commit()

    return {
        "message": f"세션({session_id}) 및 대화 기록 {deleted_count}건이 삭제되었습니다.",
        "deleted_turns": deleted_count,
    }


@router.get("/sessions/{session_id}/history", summary="세션별 대화 기록 조회 (오래된 순)")
def get_session_chat_history(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    한 세션의 모든 turn(Q+A)을 시간 순서대로 반환합니다.
    프론트엔드의 "이 대화 이어보기" 화면에 사용.
    """
    session = db.query(ConversationSession).filter(
        ConversationSession.id == session_id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    # 세션에 child_id 가 있으면 소유권 검증
    if session.child_id is not None:
        verify_child_ownership(session.child_id, db, current_user)

    rows = (
        db.query(ChatHistory)
        .filter(ChatHistory.session_id == session_id)
        .order_by(ChatHistory.created_at.asc())
        .all()
    )
    return {
        "session_id": session_id,
        "child_id": session.child_id,
        "status": session.status,
        "created_at": session.created_at,
        "turns": [
            {
                "id":         r.id,
                "question":   r.question,
                "answer":     r.answer,
                "created_at": r.created_at,
            }
            for r in rows
        ],
    }
