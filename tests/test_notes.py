"""아이 노트 API 테스트 (CRUD + 빈도 분석)"""

from datetime import date, timedelta
import pytest


class TestNotesCRUD:

    def test_create_note_diary(self, client, auth_headers, sample_child):
        """일기 노트 생성"""
        resp = client.post(f"/notes/{sample_child['id']}", json={
            "category":  "diary",
            "note_date": str(date.today()),
            "title":     "오늘의 일기",
            "content":   "아이가 처음으로 혼자 앉았다.",
        }, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["category"] == "diary"
        assert data["content"] == "아이가 처음으로 혼자 앉았다."

    def test_create_note_symptom_with_value(self, client, auth_headers, sample_child):
        """증상 노트 (수치 포함) 생성"""
        resp = client.post(f"/notes/{sample_child['id']}", json={
            "category":  "symptom",
            "note_date": str(date.today()),
            "content":   "열이 남",
            "value":     38.5,
            "unit":      "°C",
            "severity":  "mild",
        }, headers=auth_headers)
        assert resp.status_code == 201
        assert resp.json()["value"] == 38.5

    def test_create_note_behavior(self, client, auth_headers, sample_child):
        """행동 발달 노트 생성"""
        resp = client.post(f"/notes/{sample_child['id']}", json={
            "category":  "behavior",
            "note_date": str(date.today()),
            "content":   "첫 걸음마를 뗐다.",
        }, headers=auth_headers)
        assert resp.status_code == 201

    def test_list_notes(self, client, auth_headers, sample_child):
        """노트 목록 조회"""
        client.post(f"/notes/{sample_child['id']}", json={
            "category": "diary", "note_date": str(date.today()), "content": "노트1",
        }, headers=auth_headers)
        client.post(f"/notes/{sample_child['id']}", json={
            "category": "snack", "note_date": str(date.today()), "content": "사과 반 개",
        }, headers=auth_headers)

        resp = client.get(f"/notes/{sample_child['id']}", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 2

    def test_list_notes_filter_category(self, client, auth_headers, sample_child):
        """카테고리 필터 조회"""
        client.post(f"/notes/{sample_child['id']}", json={
            "category": "diary", "note_date": str(date.today()), "content": "일기",
        }, headers=auth_headers)
        client.post(f"/notes/{sample_child['id']}", json={
            "category": "snack", "note_date": str(date.today()), "content": "간식",
        }, headers=auth_headers)

        resp = client.get(f"/notes/{sample_child['id']}?category=diary", headers=auth_headers)
        assert resp.status_code == 200
        assert all(n["category"] == "diary" for n in resp.json())

    def test_get_single_note(self, client, auth_headers, sample_child):
        """단건 조회"""
        create = client.post(f"/notes/{sample_child['id']}", json={
            "category": "diary", "note_date": str(date.today()), "content": "단건 테스트",
        }, headers=auth_headers)
        note_id = create.json()["id"]

        resp = client.get(f"/notes/{sample_child['id']}/{note_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == note_id

    def test_update_note(self, client, auth_headers, sample_child):
        """노트 수정"""
        create = client.post(f"/notes/{sample_child['id']}", json={
            "category": "symptom", "note_date": str(date.today()),
            "content": "기침", "value": 38.0, "unit": "°C",
        }, headers=auth_headers)
        note_id = create.json()["id"]

        resp = client.patch(f"/notes/{sample_child['id']}/{note_id}", json={
            "value": 38.9, "severity": "moderate",
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["value"] == 38.9
        assert resp.json()["severity"] == "moderate"

    def test_delete_note(self, client, auth_headers, sample_child):
        """노트 삭제"""
        create = client.post(f"/notes/{sample_child['id']}", json={
            "category": "diary", "note_date": str(date.today()), "content": "삭제 테스트",
        }, headers=auth_headers)
        note_id = create.json()["id"]

        resp = client.delete(f"/notes/{sample_child['id']}/{note_id}", headers=auth_headers)
        assert resp.status_code == 200

        resp2 = client.get(f"/notes/{sample_child['id']}/{note_id}", headers=auth_headers)
        assert resp2.status_code == 404

    def test_note_unauthorized(self, client, sample_child):
        """인증 없이 접근 → 401"""
        resp = client.get(f"/notes/{sample_child['id']}")
        assert resp.status_code == 401

    def test_note_other_user_forbidden(self, client, auth_headers, sample_child):
        """다른 유저 접근 → 403/404"""
        client.post("/auth/register", json={
            "email": "other_note@example.com", "password": "OtherPass123!", "nickname": "other"
        })
        login = client.post("/auth/login", json={
            "email": "other_note@example.com", "password": "OtherPass123!"
        })
        other_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        resp = client.get(f"/notes/{sample_child['id']}", headers=other_headers)
        assert resp.status_code in (403, 404)


class TestNotesAnalysis:

    def test_analysis_basic(self, client, auth_headers, sample_child):
        """빈도 분석 기본 동작"""
        for i in range(3):
            client.post(f"/notes/{sample_child['id']}", json={
                "category":  "symptom",
                "note_date": str(date.today() - timedelta(days=i)),
                "content":   "발열",
                "value":     38.0 + i * 0.2,
                "unit":      "°C",
            }, headers=auth_headers)

        resp = client.get(
            f"/notes/{sample_child['id']}/analysis/symptom?days=30",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_count"] == 3
        assert data["category"] == "symptom"
        assert data["avg_value"] is not None

    def test_analysis_invalid_days(self, client, auth_headers, sample_child):
        """잘못된 days 파라미터 → 400"""
        resp = client.get(
            f"/notes/{sample_child['id']}/analysis/symptom?days=14",
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_analysis_empty(self, client, auth_headers, sample_child):
        """노트 없을 때 분석 → total_count 0"""
        resp = client.get(
            f"/notes/{sample_child['id']}/analysis/behavior?days=7",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["total_count"] == 0
