"""JWT 인증 엔드포인트 테스트"""

import pytest


# 회원가입

class TestRegister:
    def test_register_success(self, client):
        """정상 회원가입 → 201 + UserResponse (id, email, nickname, ...)"""
        resp = client.post("/auth/register", json={
            "email":    "new@example.com",
            "password": "Password123!",
            "nickname": "신규유저",
        })
        assert resp.status_code == 201
        body = resp.json()
        # register 는 토큰이 아닌 사용자 정보를 반환
        assert "id" in body
        assert body["email"] == "new@example.com"
        assert body["nickname"] == "신규유저"
        assert "password" not in body   # 비밀번호는 절대 노출 금지

    def test_register_duplicate_email(self, client):
        """이미 존재하는 이메일 → 409 Conflict"""
        payload = {
            "email":    "dup@example.com",
            "password": "Password123!",
            "nickname": "중복유저",
        }
        client.post("/auth/register", json=payload)               # 첫 번째
        resp = client.post("/auth/register", json=payload)        # 두 번째
        assert resp.status_code == 409

    def test_register_invalid_email(self, client):
        """이메일 형식 오류 → 422 Unprocessable Entity"""
        resp = client.post("/auth/register", json={
            "email":    "not-an-email",
            "password": "Password123!",
            "nickname": "형식오류",
        })
        assert resp.status_code == 422

    def test_register_short_password(self, client):
        """비밀번호가 너무 짧음 → 422"""
        resp = client.post("/auth/register", json={
            "email":    "short@example.com",
            "password": "123",
            "nickname": "짧은비번",
        })
        assert resp.status_code == 422


# ══════════════════════════════════════════════════════════════
# 로그인
# ══════════════════════════════════════════════════════════════

class TestLogin:
    @pytest.fixture(autouse=True)
    def setup_user(self, client):
        """각 테스트 전 사용자 생성"""
        client.post("/auth/register", json={
            "email":    "login@example.com",
            "password": "Correct123!",
            "nickname": "로그인테스트",
        })

    def test_login_success(self, client):
        """올바른 자격증명 → 200 + 토큰"""
        resp = client.post("/auth/login", json={
            "email":    "login@example.com",
            "password": "Correct123!",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert "refresh_token" in body

    def test_login_wrong_password(self, client):
        """틀린 비밀번호 → 401"""
        resp = client.post("/auth/login", json={
            "email":    "login@example.com",
            "password": "WrongPassword!",
        })
        assert resp.status_code == 401

    def test_login_unknown_email(self, client):
        """존재하지 않는 이메일 → 401"""
        resp = client.post("/auth/login", json={
            "email":    "nobody@example.com",
            "password": "Whatever123!",
        })
        assert resp.status_code == 401


# ══════════════════════════════════════════════════════════════
# 토큰 갱신
# ══════════════════════════════════════════════════════════════

class TestRefresh:
    def test_refresh_success(self, client):
        """유효한 refresh_token → 새 access_token 발급"""
        # 로그인으로 refresh_token 획득
        client.post("/auth/register", json={
            "email":    "refresh@example.com",
            "password": "Refresh123!",
            "nickname": "리프레시테스트",
        })
        login = client.post("/auth/login", json={
            "email":    "refresh@example.com",
            "password": "Refresh123!",
        })
        refresh_token = login.json()["refresh_token"]

        # 갱신 요청
        resp = client.post("/auth/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_refresh_invalid_token(self, client):
        """잘못된 토큰 → 401"""
        resp = client.post("/auth/refresh", json={"refresh_token": "totally.invalid.token"})
        assert resp.status_code == 401


# ══════════════════════════════════════════════════════════════
# 내 정보 조회
# ══════════════════════════════════════════════════════════════

class TestMe:
    def test_get_me_success(self, client, auth_headers):
        """유효한 토큰으로 내 정보 조회 → 200"""
        resp = client.get("/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert "email" in body
        assert "id" in body

    def test_get_me_without_token(self, client):
        """토큰 없이 접근 → 403 or 401"""
        resp = client.get("/auth/me")
        assert resp.status_code in (401, 403)

    def test_get_me_invalid_token(self, client):
        """만료/위조 토큰 → 401"""
        resp = client.get("/auth/me", headers={"Authorization": "Bearer fake.token.here"})
        assert resp.status_code == 401
