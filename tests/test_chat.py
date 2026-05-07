"""AI 채팅 API 테스트 (세션 기반, 멀티턴, 역질문)

AI_PROVIDER=mock 환경에서 실제 LLM 호출 없이 동작합니다.
conftest.py 에서 os.environ["AI_PROVIDER"] = "mock" 이 설정됩니다.
"""

import pytest
from unittest.mock import patch, MagicMock


# ── Mock 헬퍼 ──────────────────────────────────────────────────────────────────

def _mock_ai_response(answer: str = "테스트 답변입니다.", needs_more: bool = False):
    """get_ai_response 의 표준 반환값을 mock"""
    return {
        "answer":             answer,
        "is_emergency":       False,
        "needs_more_context": needs_more,
        "context_collected":  {},
    }


# ── 채팅 기본 동작 ─────────────────────────────────────────────────────────────

class TestChatBasic:

    def test_chat_new_session(self, client, auth_headers, sample_child):
        """새 세션으로 채팅 시작 → session_id 반환"""
        with patch("routers.chat.get_ai_response", return_value=_mock_ai_response()):
            resp = client.post("/chat/", json={
                "child_id": sample_child["id"],
                "message":  "아이가 열이 나요",
            }, headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data
        assert data["session_id"] is not None
        assert data["message"] == "테스트 답변입니다."
        assert data["is_emergency"] is False

    def test_chat_continue_session(self, client, auth_headers, sample_child):
        """기존 session_id 로 대화 이어가기"""
        with patch("routers.chat.get_ai_response", return_value=_mock_ai_response()):
            first = client.post("/chat/", json={
                "child_id": sample_child["id"],
                "message":  "아이가 열이 나요",
            }, headers=auth_headers)
        session_id = first.json()["session_id"]

        with patch("routers.chat.get_ai_response", return_value=_mock_ai_response("38.5도에요")):
            second = client.post("/chat/", json={
                "session_id": session_id,
                "message":    "38.5도예요",
            }, headers=auth_headers)

        assert second.status_code == 200
        assert second.json()["session_id"] == session_id

    def test_chat_invalid_session(self, client, auth_headers):
        """존재하지 않는 session_id → 404"""
        resp = client.post("/chat/", json={
            "session_id": "00000000-0000-0000-0000-000000000000",
            "message":    "테스트",
        }, headers=auth_headers)
        assert resp.status_code == 404

    def test_chat_unauthorized(self, client, sample_child):
        """인증 없이 채팅 → 401"""
        resp = client.post("/chat/", json={
            "child_id": sample_child["id"],
            "message":  "열이 나요",
        })
        assert resp.status_code == 401

    def test_chat_without_child(self, client, auth_headers):
        """child_id 없이 채팅도 허용 (일반 육아 질문)"""
        with patch("routers.chat.get_ai_response", return_value=_mock_ai_response()):
            resp = client.post("/chat/", json={
                "message": "이유식은 언제부터 시작하나요?",
            }, headers=auth_headers)
        assert resp.status_code == 200


# ── 역질문 시스템 ──────────────────────────────────────────────────────────────

class TestChatBackQuestion:

    def test_needs_more_context_flag(self, client, auth_headers, sample_child):
        """역질문 응답 시 needs_more_context=True, is_final=False"""
        with patch("routers.chat.get_ai_response", return_value=_mock_ai_response(
            answer="열이 몇 도인가요?", needs_more=True
        )):
            resp = client.post("/chat/", json={
                "child_id": sample_child["id"],
                "message":  "아이가 열이 나요",
            }, headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data["needs_more_context"] is True
        assert data["is_final"] is False

    def test_final_answer_after_context(self, client, auth_headers, sample_child):
        """역질문 답변 후 최종 답변 → is_final=True"""
        # 1턴: 역질문 발생
        with patch("routers.chat.get_ai_response", return_value=_mock_ai_response(
            answer="열이 몇 도인가요?", needs_more=True
        )):
            first = client.post("/chat/", json={
                "child_id": sample_child["id"],
                "message":  "아이가 열이 나요",
            }, headers=auth_headers)
        session_id = first.json()["session_id"]

        # 2턴: 답변 제공 → 최종 답변
        with patch("routers.chat.get_ai_response", return_value=_mock_ai_response(
            answer="38.5도는 미열입니다. 수분을 충분히 공급하세요."
        )):
            second = client.post("/chat/", json={
                "session_id": session_id,
                "message":    "38.5도예요",
            }, headers=auth_headers)

        assert second.status_code == 200
        assert second.json()["is_final"] is True


# ── 채팅 기록 조회 ─────────────────────────────────────────────────────────────

class TestChatHistory:

    def test_get_chat_history(self, client, auth_headers, sample_child):
        """채팅 후 기록 조회"""
        child_id = sample_child["id"]
        with patch("routers.chat.get_ai_response", return_value=_mock_ai_response("답변1")):
            client.post("/chat/", json={
                "child_id": child_id,
                "message":  "질문1",
            }, headers=auth_headers)

        resp = client.get(f"/chat/history/{child_id}", headers=auth_headers)
        assert resp.status_code == 200
        history = resp.json()
        assert isinstance(history, list)
        assert len(history) >= 1

    def test_get_session_history(self, client, auth_headers, sample_child):
        """세션별 대화 기록 조회"""
        with patch("routers.chat.get_ai_response", return_value=_mock_ai_response()):
            first = client.post("/chat/", json={
                "child_id": sample_child["id"],
                "message":  "첫 질문",
            }, headers=auth_headers)
        session_id = first.json()["session_id"]

        resp = client.get(f"/chat/sessions/{session_id}/history", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == session_id

    def test_history_other_user_forbidden(self, client, auth_headers, sample_child):
        """다른 유저는 채팅 기록 접근 불가"""
        client.post("/auth/register", json={
            "email": "other2@example.com", "password": "OtherPass123!", "nickname": "other2"
        })
        login = client.post("/auth/login", json={
            "email": "other2@example.com", "password": "OtherPass123!"
        })
        other_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        resp = client.get(f"/chat/history/{sample_child['id']}", headers=other_headers)
        assert resp.status_code in (403, 404)


# ── history 파라미터 전달 검증 ─────────────────────────────────────────────────

class TestChatHistoryPassthrough:

    def test_history_passed_to_ai_service(self, client, auth_headers, sample_child):
        """멀티턴 시 history 가 get_ai_response 에 전달되는지 확인"""
        call_kwargs = {}

        def capture_ai_call(**kwargs):
            call_kwargs.update(kwargs)
            return _mock_ai_response("첫 답변")

        with patch("routers.chat.get_ai_response", side_effect=capture_ai_call):
            first = client.post("/chat/", json={
                "child_id": sample_child["id"],
                "message":  "첫 질문",
            }, headers=auth_headers)
        session_id = first.json()["session_id"]

        def capture_second(**kwargs):
            call_kwargs.update(kwargs)
            return _mock_ai_response("두 번째 답변")

        with patch("routers.chat.get_ai_response", side_effect=capture_second):
            client.post("/chat/", json={
                "session_id": session_id,
                "message":    "두 번째 질문",
            }, headers=auth_headers)

        # 두 번째 호출에 history 파라미터가 전달됐는지 확인
        assert "history" in call_kwargs, "history 파라미터가 get_ai_response에 전달되지 않았습니다"
