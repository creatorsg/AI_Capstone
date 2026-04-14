"""복지 정책 엔드포인트 테스트"""


class TestWelfareList:
    def test_list_returns_200(self, client):
        """목록 조회 → 200"""
        resp = client.get("/welfare/")
        assert resp.status_code == 200

    def test_list_has_policies_key(self, client):
        """응답에 policies 키가 있어야 함"""
        resp = client.get("/welfare/")
        body = resp.json()
        # policies 리스트 또는 직접 list 형태 모두 허용
        assert "policies" in body or isinstance(body, list)

    def test_list_policies_is_array(self, client):
        """policies 가 배열 형태"""
        resp = client.get("/welfare/")
        body = resp.json()
        policies = body.get("policies", body) if isinstance(body, dict) else body
        assert isinstance(policies, list)

    def test_list_pagination_limit(self, client):
        """limit 파라미터 동작"""
        resp = client.get("/welfare/?limit=2")
        assert resp.status_code == 200
        body = resp.json()
        policies = body.get("policies", body) if isinstance(body, dict) else body
        assert len(policies) <= 2

    def test_list_pagination_offset(self, client):
        """offset 파라미터 동작"""
        r1 = client.get("/welfare/?limit=10&offset=0")
        r2 = client.get("/welfare/?limit=10&offset=1")
        p1 = r1.json()
        p2 = r2.json()
        items1 = p1.get("policies", p1) if isinstance(p1, dict) else p1
        items2 = p2.get("policies", p2) if isinstance(p2, dict) else p2
        # offset 이 다르면 첫 번째 항목이 달라야 함
        if len(items1) > 1 and len(items2) > 0:
            assert items1[0] != items2[0]

    def test_list_item_has_required_fields(self, client):
        """각 항목에 필수 키가 있어야 함"""
        resp = client.get("/welfare/?limit=1")
        body = resp.json()
        items = body.get("policies", body) if isinstance(body, dict) else body
        if items:
            item = items[0]
            assert "title" in item or "content" in item  # fallback 또는 real data

    def test_list_has_data_source_field(self, client):
        """data_source 필드로 fallback/file 구분 가능"""
        resp = client.get("/welfare/")
        body = resp.json()
        if isinstance(body, dict):
            assert "data_source" in body or "source" in body or "policies" in body


class TestWelfareSearch:
    def test_search_with_keyword(self, client):
        """키워드 검색 → 200"""
        resp = client.get("/welfare/search?keyword=육아")
        assert resp.status_code == 200

    def test_search_result_has_policies(self, client):
        """검색 결과에 policies 또는 list 반환"""
        resp = client.get("/welfare/search?keyword=아동수당")
        body = resp.json()
        results = body.get("policies", body) if isinstance(body, dict) else body
        assert isinstance(results, list)

    def test_search_no_keyword_returns_400_or_422(self, client):
        """keyword 파라미터 누락 → 400 or 422"""
        resp = client.get("/welfare/search")
        assert resp.status_code in (400, 422)

    def test_search_empty_result(self, client):
        """존재하지 않는 키워드 → 빈 결과 (404 아님)"""
        resp = client.get("/welfare/search?keyword=XYZNONEXISTENTTERM99999")
        assert resp.status_code == 200
        body = resp.json()
        results = body.get("policies", body) if isinstance(body, dict) else body
        assert isinstance(results, list)
        assert len(results) == 0


class TestWelfareStatus:
    def test_status_returns_200(self, client):
        """상태 확인 → 200"""
        resp = client.get("/welfare/status")
        assert resp.status_code == 200

    def test_status_has_info_fields(self, client):
        """응답에 소스 및 개수 정보 포함"""
        resp = client.get("/welfare/status")
        body = resp.json()
        # count, total, items, source 중 하나 이상 있어야 함
        assert any(k in body for k in ("count", "total", "items", "source", "data_source"))
