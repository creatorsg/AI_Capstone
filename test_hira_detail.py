"""
심평원 getHospDetailInfo API 테스트
- getHospBasisList로 ykiho 획득 → getHospDetailInfo로 상세정보 확인
실행: python test_hira_detail.py
"""
import httpx
import json
import os
from urllib.parse import unquote
from dotenv import load_dotenv

load_dotenv()

service_key = unquote(os.getenv("HIRA_SERVICE_KEY", ""))
BASE = "http://apis.data.go.kr/B551182/hospInfoServicev2"

def search_ykiho(name: str) -> tuple[str, str]:
    """getHospBasisList로 병원 검색 → (ykiho, 병원명) 반환"""
    resp = httpx.get(
        f"{BASE}/getHospBasisList",
        params={"serviceKey": service_key, "yadmNm": name,
                "numOfRows": 5, "pageNo": 1, "_type": "json"},
        timeout=15.0,
    )
    data = resp.json()
    raw = data.get("response", {}).get("body", {}).get("items")
    if not raw or not isinstance(raw, dict):
        return None, None
    items = raw.get("item", [])
    if isinstance(items, dict):
        items = [items]
    if not items:
        return None, None
    # 이름 일치 우선
    name_norm = name.replace(" ", "")
    for it in items:
        if it.get("yadmNm", "").replace(" ", "") == name_norm:
            return it.get("ykiho"), it.get("yadmNm")
    return items[0].get("ykiho"), items[0].get("yadmNm")


def get_detail(ykiho: str) -> dict:
    """getHospDetailInfo 호출 → 전체 응답 반환"""
    resp = httpx.get(
        f"{BASE}/getHospDetailInfo",
        params={"serviceKey": service_key, "ykiho": ykiho, "_type": "json"},
        timeout=15.0,
    )
    return resp.json()


# ── 테스트 대상 병원 ──────────────────────────────────────────
test_names = ["서울아산병원", "삼성서울병원", "연세이비인후과의원"]

for name in test_names:
    print(f"\n{'='*60}")
    print(f"검색: {name}")
    try:
        ykiho, matched = search_ykiho(name)
        if not ykiho:
            print("  ykiho 없음 (검색 결과 없음)")
            continue

        print(f"  매칭된 병원: {matched}")
        print(f"  ykiho: {ykiho}")

        detail = get_detail(ykiho)
        body = detail.get("response", {}).get("body", {})
        raw = body.get("items")
        print(f"  items type: {type(raw).__name__}")

        if isinstance(raw, dict):
            item = raw.get("item", {})
            if isinstance(item, list):
                item = item[0] if item else {}
            print(f"\n  [상세 정보 전체 필드]")
            for k, v in item.items():
                print(f"    {k}: {v!r}")

            # 진료시간 관련 필드만 따로 출력
            trmt = {k: v for k, v in item.items()
                    if any(kw in k.lower() for kw in ["trmt", "lunch", "rcv", "emyNgt", "time", "hour"])}
            if trmt:
                print(f"\n  ✅ 진료시간 관련 필드 발견:")
                for k, v in trmt.items():
                    print(f"    {k}: {v!r}")
            else:
                print(f"\n  ⚠️  진료시간 관련 필드 없음")
        else:
            print(f"  items 값: {repr(raw)[:100]}")

    except Exception as e:
        print(f"  오류: {e}")

print(f"\n{'='*60}")
