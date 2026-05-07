"""
심평원 API + 운영시간 감지 디버깅 스크립트
PowerShell에서 실행: docker exec fastapi_app python3 /app/test_hours_debug.py
"""
import sys
sys.path.insert(0, '/app')

import os
import logging

# 로그를 stdout으로 출력
logging.basicConfig(level=logging.WARNING, format='%(levelname)s %(name)s: %(message)s')

from services.facility_hours_service import (
    is_hours_question,
    extract_facility_name,
    search_facility_meta,
    search_hira_by_name,
    format_hours_for_prompt,
    get_facility_hours_context,
    HOURS_KEYWORDS,
)

print("=" * 60)
print("[1] HOURS_KEYWORDS 목록")
print(", ".join(HOURS_KEYWORDS))
print()

questions = [
    "'연세이비인후과의원'의 운영시간이 어떻게 되나요?",
    "연세소아과 진료시간 알려줘",
    "모리소아과의원 몇시에 열어요?",
    "hello world",
]

print("[2] is_hours_question / extract_facility_name 테스트")
for q in questions:
    is_h = is_hours_question(q)
    name = extract_facility_name(q)
    print(f"  Q : {q}")
    print(f"  감지: {is_h}  |  시설명: {name}")
    print()

# ── 정적 데이터 메타 조회 ──────────────────────────────────────
test_names = ["연세이비인후과의원", "모리소아과의원"]

print("[3] search_facility_meta 테스트")
for nm in test_names:
    meta = search_facility_meta(nm)
    print(f"  이름: {nm}")
    print(f"  메타: {meta}")
    print()

# ── HIRA API KEY 확인 ──────────────────────────────────────────
HIRA_KEY = os.getenv("HIRA_SERVICE_KEY", "")
print(f"[4] HIRA_SERVICE_KEY: {'설정됨 (앞 10자: ' + HIRA_KEY[:10] + '...)' if HIRA_KEY else '없음 ❌'}")
print()

# ── sido 포함한 실제 파이프라인 시뮬레이션 ──────────────────────
print("[5] search_hira_by_name 테스트 (sido 포함 = 실제 파이프라인)")
tests = [
    ("연세이비인후과의원", "서울"),
    ("모리소아과의원", None),
]
for nm, sido in tests:
    print(f"  검색: {nm}  sido={sido}")
    result = search_hira_by_name(nm, sido=sido)
    if result:
        print(f"  병원명: {result['place_name']}")
        print(f"  주소: {result['address']}")
        print(f"  진료시간: {result['hours']}")
    else:
        print(f"  결과: None")
    print()

# ── 전체 end-to-end 테스트 ────────────────────────────────────
print("[6] get_facility_hours_context end-to-end 테스트")
e2e_questions = [
    "'연세이비인후과의원'의 운영시간이 어떻게 되나요?",
    "모리소아과의원 몇시에 열어요?",
]
for q in e2e_questions:
    print(f"  Q: {q}")
    ctx = get_facility_hours_context(q)
    if ctx:
        print(f"  결과:\n{ctx}")
    else:
        print(f"  결과: None (운영시간 정보 없음 또는 API 미응답)")
    print()

print("=" * 60)

# ── raw API 응답 직접 확인 ──────────────────────────────────────
import httpx
import json as _json
from urllib.parse import unquote as _unquote

HIRA_HOSP_URL = "http://apis.data.go.kr/B551182/hospInfoServicev2/getHospBasisList"
service_key = _unquote(os.getenv("HIRA_SERVICE_KEY", ""))

print("[7] 심평원 API raw 응답 확인 (서울아산병원)")
params = {
    "serviceKey": service_key,
    "yadmNm": "서울아산병원",
    "numOfRows": 3,
    "pageNo": 1,
    "_type": "json",
}
try:
    resp = httpx.get(HIRA_HOSP_URL, params=params, timeout=15.0)
    print(f"  HTTP status: {resp.status_code}")
    data = resp.json()
    items_raw = data.get("response", {}).get("body", {}).get("items")
    print(f"  items type: {type(items_raw)}")
    if isinstance(items_raw, dict):
        item_list = items_raw.get("item", [])
        if isinstance(item_list, dict):
            item_list = [item_list]
        print(f"  결과 수: {len(item_list)}")
        if item_list:
            first = item_list[0]
            print(f"\n  --- 첫 번째 병원 전체 필드 ---")
            for k, v in first.items():
                print(f"    {k}: {v}")
    else:
        print(f"  items 값: {items_raw}")
except Exception as e:
    print(f"  오류: {e}")

print()
print("=" * 60)
print("디버그 완료")
