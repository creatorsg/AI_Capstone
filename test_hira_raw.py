"""
심평원 API raw 응답 직접 확인 (컨테이너 밖에서 실행)
실행: python test_hira_raw.py
"""
import httpx
import json
import os
from urllib.parse import unquote
from dotenv import load_dotenv

load_dotenv()

service_key = unquote(os.getenv("HIRA_SERVICE_KEY", ""))
if not service_key:
    print("❌ HIRA_SERVICE_KEY 없음 - .env 파일 확인")
    exit(1)

HIRA_URL = "http://apis.data.go.kr/B551182/hospInfoServicev2/getHospBasisList"

test_names = ["서울아산병원", "세브란스병원", "연세이비인후과의원"]

for name in test_names:
    print(f"\n{'='*60}")
    print(f"검색: {name}")
    try:
        resp = httpx.get(
            HIRA_URL,
            params={
                "serviceKey": service_key,
                "yadmNm": name,
                "numOfRows": 3,
                "pageNo": 1,
                "_type": "json",
            },
            timeout=20.0,
        )
        print(f"HTTP status: {resp.status_code}")
        data = resp.json()
        body = data.get("response", {}).get("body", {})
        raw_items = body.get("items")
        print(f"items type: {type(raw_items).__name__}  /  value: {repr(raw_items)[:80]}")

        if isinstance(raw_items, dict):
            item_list = raw_items.get("item", [])
            if isinstance(item_list, dict):
                item_list = [item_list]
            print(f"결과 수: {len(item_list)}")
            if item_list:
                first = item_list[0]
                print(f"\n[첫 번째 병원: {first.get('yadmNm')}]")
                # 진료시간 관련 필드만 출력
                trmt_fields = [k for k in first if "trmt" in k.lower() or "lunch" in k.lower() or "rcv" in k.lower()]
                if trmt_fields:
                    print("  진료시간 관련 필드:")
                    for k in trmt_fields:
                        print(f"    {k}: {first[k]!r}")
                else:
                    print("  ⚠️  진료시간 관련 필드 없음")
                print("  전체 필드 목록:", list(first.keys()))
        else:
            print(f"⚠️  items가 dict가 아님: {repr(raw_items)}")

    except httpx.TimeoutException:
        print("❌ 타임아웃 (20초)")
    except Exception as e:
        print(f"❌ 오류: {e}")
