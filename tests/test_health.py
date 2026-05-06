"""Health log & vaccination API tests.

Model/schema reference:
  - HealthLog.value : str  (e.g. "38.5", "150ml")
  - HealthLog.note  : str  (singular, not 'notes')
  - VaccinationRecord.next_due : date  (not 'next_due_date')
"""
import pytest


class TestHealthLog:

    def test_create_health_log(self, client, auth_headers, sample_child):
        child_id = sample_child["id"]
        resp = client.post("/health/logs/", json={
            "child_id": child_id,
            "log_type": "fever",
            "value":    "38.5",
            "note":     "afternoon measurement",
        }, headers=auth_headers)
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["child_id"] == child_id
        assert data["log_type"] == "fever"
        assert data["value"] == "38.5"

    def test_get_health_logs(self, client, auth_headers, sample_child):
        child_id = sample_child["id"]
        for value in ["37.8", "38.2"]:
            client.post("/health/logs/", json={
                "child_id": child_id,
                "log_type": "fever",
                "value":    value,
            }, headers=auth_headers)
        resp = client.get(f"/health/logs/{child_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_create_health_log_unauthorized(self, client, sample_child):
        resp = client.post("/health/logs/", json={
            "child_id": sample_child["id"],
            "log_type": "fever",
            "value":    "38.0",
        })
        assert resp.status_code == 401

    def test_get_health_logs_other_user(self, client, auth_headers, sample_child):
        client.post("/auth/register", json={
            "email": "other@example.com", "password": "OtherPass123!", "nickname": "other"
        })
        login = client.post("/auth/login", json={
            "email": "other@example.com", "password": "OtherPass123!"
        })
        other_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        resp = client.get(f"/health/logs/{sample_child['id']}", headers=other_headers)
        assert resp.status_code in (403, 404)

    def test_health_log_types(self, client, auth_headers, sample_child):
        child_id = sample_child["id"]
        logs = [
            {"log_type": "sleep",  "value": "8h"},
            {"log_type": "meal",   "value": "200ml"},
            {"log_type": "weight", "value": "8.5kg"},
        ]
        for log in logs:
            resp = client.post("/health/logs/", json={
                "child_id": child_id, **log
            }, headers=auth_headers)
            assert resp.status_code == 201, f"{log['log_type']} failed: {resp.text}"


class TestVaccination:

    def test_create_vaccination(self, client, auth_headers, sample_child):
        child_id = sample_child["id"]
        resp = client.post("/health/vaccinations/", json={
            "child_id":      child_id,
            "vaccine_name":  "BCG",
            "vaccinated_at": "2023-02-01",
            "next_due":      None,
            "note":          "4 weeks old",
        }, headers=auth_headers)
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["vaccine_name"] == "BCG"
        assert data["child_id"] == child_id

    def test_get_vaccinations(self, client, auth_headers, sample_child):
        child_id = sample_child["id"]
        for v in ["BCG", "HepB", "DTaP"]:
            client.post("/health/vaccinations/", json={
                "child_id":      child_id,
                "vaccine_name":  v,
                "vaccinated_at": "2023-03-01",
            }, headers=auth_headers)
        resp = client.get(f"/health/vaccinations/{child_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 3

    def test_vaccination_unauthorized(self, client, sample_child):
        resp = client.post("/health/vaccinations/", json={
            "child_id":      sample_child["id"],
            "vaccine_name":  "BCG",
            "vaccinated_at": "2023-02-01",
        })
        assert resp.status_code == 401

    def test_vaccination_next_due(self, client, auth_headers, sample_child):
        child_id = sample_child["id"]
        resp = client.post("/health/vaccinations/", json={
            "child_id":      child_id,
            "vaccine_name":  "DTaP 1st",
            "vaccinated_at": "2023-03-01",
            "next_due":      "2023-05-01",
        }, headers=auth_headers)
        assert resp.status_code == 201
        assert resp.json()["next_due"] == "2023-05-01"
