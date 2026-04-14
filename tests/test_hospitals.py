"""병원 검색 엔드포인트 테스트"""


class TestStaticNearby:
    def test_nearby_valid_params(self, client):
        """서울 좌표, 올바른 파라미터 → 200"""
        resp = client.get(
            "/hospitals/static/nearby"
            "?lat=37.5665&lng=126.9780&radius=3000&category=소아청소년과"
        )
        assert resp.status_code == 200, resp.text

    def test_nearby_returns_list(self, client):
        """응답이 배열 또는 {hospitals: []} 형태 (데이터 파일 유무에 따라 다름)"""
        resp = client.get("/hospitals/static/nearby?lat=37.5665&lng=126.9780")
        assert resp.status_code == 200
        body = resp.json()
        # 데이터 파일 있을 때: list / 없을 때: {"hospitals": [], "message": ...}
        if isinstance(body, list):
            pass  # 정상 (데이터 있을 때)
        else:
            assert "hospitals" in body  # 데이터 없을 때 래퍼 구조

    def test_nearby_missing_lat(self, client):
        """lat 누락 → 422"""
        resp = client.get("/hospitals/static/nearby?lng=126.9780")
        assert resp.status_code == 422

    def test_nearby_missing_lng(self, client):
        """lng 누락 → 422"""
        resp = client.get("/hospitals/static/nearby?lat=37.5665")
        assert resp.status_code == 422

    def test_nearby_invalid_category_returns_400(self, client):
        """잘못된 category → 400"""
        resp = client.get(
            "/hospitals/static/nearby?lat=37.5665&lng=126.9780&category=존재안함"
        )
        assert resp.status_code == 400

    def test_nearby_result_has_distance_field(self, client):
        """결과 항목에 distance 필드 포함 (jaehwi 데이터 있을 때만 검증)"""
        resp = client.get(
            "/hospitals/static/nearby?lat=37.5665&lng=126.9780&radius=50000&category=소아청소년과"
        )
        assert resp.status_code == 200
        body = resp.json()
        # 데이터 파일 없을 때는 dict 구조 → 검증 생략
        if isinstance(body, list) and body:
            assert "distance_m" in body[0] or "distance" in body[0]


class TestStaticSearch:
    def test_search_with_keyword_returns_200(self, client):
        """keyword 파라미터로 검색 → 200"""
        resp = client.get("/hospitals/static/search?keyword=병원")
        assert resp.status_code == 200

    def test_search_with_sido_returns_200(self, client):
        """sido 파라미터로 검색 → 200"""
        resp = client.get("/hospitals/static/search?sido=서울특별시")
        assert resp.status_code == 200

    def test_search_returns_dict_with_hospitals_key(self, client):
        """응답이 hospitals 키를 포함한 dict"""
        resp = client.get("/hospitals/static/search?keyword=아이")
        assert resp.status_code == 200
        body = resp.json()
        # 데이터 없으면 {"message": ..., "hospitals": []} 반환
        assert "hospitals" in body or isinstance(body, list)

    def test_search_no_params_returns_400(self, client):
        """sido/sggu/keyword 모두 없으면 → 400"""
        resp = client.get("/hospitals/static/search")
        assert resp.status_code == 400

    def test_search_empty_result_no_error(self, client):
        """검색 결과 없어도 오류 없이 응답"""
        resp = client.get("/hospitals/static/search?keyword=ZZZNOMATCH99999")
        assert resp.status_code == 200

    def test_search_invalid_category_returns_400(self, client):
        """잘못된 category → 400"""
        resp = client.get("/hospitals/static/search?keyword=병원&category=없는카테고리")
        assert resp.status_code == 400


class TestStaticStatus:
    def test_status_returns_200(self, client):
        """정적 데이터 상태 조회 → 200"""
        resp = client.get("/hospitals/static/status")
        assert resp.status_code == 200

    def test_status_response_is_dict(self, client):
        """응답이 dict 형태"""
        resp = client.get("/hospitals/static/status")
        assert isinstance(resp.json(), dict)


class TestServerStatus:
    def test_root_health_check(self, client):
        """루트 헬스체크 → 200"""
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.json()["status"] == "FastAPI is Running!"
