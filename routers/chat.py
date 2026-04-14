"""AI 채팅 API (세션 기반, JWT 인증, 소유권 검증)"""

import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models.chat import ChatHistory, ConversationSession
from models.child import Child, ChildProfile
from models.user import User
from schemas.chat import ChatMessageRequest, ChatMessageResponse
from services.ai_service import get_ai_response, get_pending_field
from services.auth_service import get_current_user

router = APIRouter(
    prefix="/chat",
    tags=["AI 채팅"]
)


# 소유권 검증 헬퍼
def _verify_child_owner(child_id: int, db: Session, current_user: User) -> Child:
    """child_id 가 current_user 소유인지 확인하고 Child 객체를 반환합니다."""
    child = db.query(Child).filter(Child.id == child_id).first()
    if not child:
        raise HTTPException(status_code=404, detail="아이 정보를 찾을 수 없습니다.")
    if child.user_id is not None and child.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="접근 권한이 없습니다.",
        )
    return child


def get_child_info(child_id: int, db: Session) -> dict | None:
    """
    아이 정보를 조회해 AI 프롬프트 컨텍스트용 딕셔너리로 반환합니다.

    반환 필드:
      - name, birth_date, gender
      - allergies (list), conditions (list), notes   → build_system_prompt 에서 사용
      - blood_type, medical_notes                     → ChildProfile 에서 조회
    """
    child = db.query(Child).filter(Child.id == child_id).first()
    profile = db.query(ChildProfile).filter(
        ChildProfile.child_id == child_id
    ).first()

    if not child and not profile:
        return None

    return {
        # Child 기본 정보
        "name":          child.name if child else None,
        "birth_date":    str(child.birth_date) if child and child.birth_date else None,
        "gender":        child.gender if child else None,
        "allergies":     child.allergies if child else [],
        "conditions":    child.conditions if child else [],
        "notes":         child.notes if child else "",
        # ChildProfile 민감 정보
        "blood_type":    profile.blood_type if profile else None,
        "medical_notes": profile.medical_notes if profile else None,
    }


# 채팅 엔드포인트

@router.post("/", response_model=ChatMessageResponse, summary="AI 채팅 (세션 기반)")
def chat(
    request: ChatMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    세션 기반 대화형 AI 채팅입니다.

    **첫 메시지 (새 대화 시작)**
    ```json
    { "child_id": 1, "message": "애가 열이 나요" }
    ```

    **이후 메시지 (대화 계속)**
    ```json
    { "session_id": "반환된-session-id", "message": "38.5도요" }
    ```

    서버가 대화 맥락을 자동으로 관리하므로, 프론트는 session_id만 유지하면 됩니다.

    헤더: `Authorization: Bearer <access_token>`
    """

    # 기존 세션 이어가기
    if request.session_id:
        session = db.query(ConversationSession).filter(
            ConversationSession.id == request.session_id
        ).first()
        if not session:
            raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다. 새 대화를 시작해주세요.")
        if session.status == "completed":
            raise HTTPException(status_code=400, detail="이미 완료된 대화입니다. 새 대화를 시작해주세요.")

        # 세션에 child_id 가 있으면 소유권 재확인
        if session.child_id:
            _verify_child_owner(session.child_id, db, current_user)

        # pending_field 가 있으면 현재 메시지가 그 필드의 답변
        if session.pending_field:
            context = dict(session.context or {})
            context[session.pending_field] = request.message
            session.context = context
            session.pending_field = None
            db.commit()

        question = session.original_question
        context = dict(session.context or {})
        child_id = session.child_id

    # 새 대화 시작
    else:
        # child_id 가 제공된 경우 소유권 검증
        if request.child_id:
            _verify_child_owner(request.child_id, db, current_user)

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

    # AI 응답 생성
    child_info = get_child_info(child_id, db) if child_id else None
    result = get_ai_response(
        question=question,
        context=context,
        child_info=child_info,
        child_id=child_id,
    )

    # 역질문 중이면 pending_field 저장
    if result["needs_more_context"]:
        pending = get_pending_field(question, context)
        session.pending_field = pending
        db.commit()

    # 최종 답변이면 기록 저장 + 세션 완료 처리
    else:
        session.status = "completed"

        history = ChatHistory(
            child_id=child_id,
            question=question,
            answer=result["answer"],
            context=result["context_collected"],
        )
        db.add(history)
        db.commit()

    return ChatMessageResponse(
        session_id=session.id,
        message=result["answer"],
        is_emergency=result["is_emergency"],
        needs_more_context=result["needs_more_context"],
        is_final=not result["needs_more_context"],
    )


@router.get("/history/{child_id}", summary="채팅 기록 조회")
def get_chat_history(
    child_id: int,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """아이별 과거 채팅 기록을 최신순으로 반환합니다."""
    _verify_child_owner(child_id, db, current_user)
    return (
        db.query(ChatHistory)
        .filter(ChatHistory.child_id == child_id)
        .order_by(ChatHistory.created_at.desc())
        .limit(limit)
        .all()
    )
