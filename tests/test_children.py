"""아이 프로필 CRUD 엔드포인트 테스트"""

import pytest


# 아이 생성

class TestCreateChild:
    def test_create_success(self, client, auth_headers):
        """정상 생성 → 201"""
        resp = client.post("/children/", json={
            "name":       "박민준",
            "birth_date": "2022-05-10",
            "gender":     "male",        # ← "male" | "female" 만 허용
            "allergies":  ["땅콩"],
            "conditions": [],
        }, headers=auth_headers)
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["name"] == "박민준"
        assert body["gender"] == "male"
        assert "id" in body

    def test_create_without_auth(self, client):
        """토큰 없이 생성 → 403 or 401"""
        resp = client.post("/children/", json={
            "name":       "무인증",
            "birth_date": "2023-01-01",
            "gender":     "female",
        })
        assert resp.status_code in (401, 403)

    def test_create_missing_required_field(self, client, auth_headers):
        """필수 필드(name) 누락 → 422"""
        resp = client.post("/children/", json={
            "birth_date": "2023-01-01",
            "gender":     "female",
        }, headers=auth_headers)
        assert resp.status_code == 422

    def test_create_invalid_gender(self, client, auth_headers):
        """허용되지 않는 gender 값 → 422"""
        resp = client.post("/children/", json={
            "name":       "오류아이",
            "birth_date": "2023-01-01",
            "gender":     "남",           # 한글 입력 → 422
        }, headers=auth_headers)
        assert resp.status_code == 422


# ══════════════════════════════════════════════════════════════
# 아이 목록 조회
# ══════════════════════════════════════════════════════════════

class TestListChildren:
    def test_list_only_own_children(self, client, auth_headers):
        """자신의 아이만 반환"""
        for i in range(2):
            client.post("/children/", json={
                "name": f"아이{i}", "birth_date": "2023-01-01", "gender": "male"
            }, headers=auth_headers)

        resp = client.get("/children/", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 2

    def test_list_empty_without_auth(self, client):
        """인증 없이 목록 조회 → 401/403"""
        resp = client.get("/children/")
        assert resp.status_code in (401, 403)


# ══════════════════════════════════════════════════════════════
# 단일 조회
# ══════════════════════════════════════════════════════════════

class TestGetChild:
    def test_get_own_child(self, client, auth_headers, sample_child):
        """자신의 아이 조회 → 200"""
        child_id = sample_child["id"]
        resp = client.get(f"/children/{child_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == child_id

    def test_get_not_found(self, client, auth_headers):
        """존재하지 않는 ID → 404"""
        resp = client.get("/children/999999", headers=auth_headers)
        assert resp.status_code == 404

    def test_get_other_users_child(self, client, sample_child):
        """다른 유저 토큰으로 접근 → 403"""
        client.post("/auth/register", json={
            "email": "other@example.com",
            "password": "OtherPwd123!",
            "nickname": "다른유저",
        })
        login = client.post("/auth/login", json={
            "email": "other@example.com",
            "password": "OtherPwd123!",
        })
        other_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        child_id = sample_child["id"]
        resp = client.get(f"/children/{child_id}", headers=other_headers)
        assert resp.status_code == 403


# ══════════════════════════════════════════════════════════════
# 수정 / 삭제 (PATCH 방식)
# ══════════════════════════════════════════════════════════════

class TestUpdateDeleteChild:
    def test_update_child(self, client, auth_headers, sample_child):
        """이름 수정 → 200 + 변경된 값"""
        child_id = sample_child["id"]
        resp = client.patch(f"/children/{child_id}", json={
            "name": "수정된이름",
        }, headers=auth_headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["name"] == "수정된이름"

    def test_delete_child(self, client, auth_headers, sample_child):
        """삭제 → 200 후 조회 시 404"""
        child_id = sample_child["id"]
        del_resp = client.delete(f"/children/{child_id}", headers=auth_headers)
        assert del_resp.status_code == 200

        get_resp = client.get(f"/children/{child_id}", headers=auth_headers)
        assert get_resp.status_code == 404
