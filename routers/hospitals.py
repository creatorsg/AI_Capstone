"""GPS 기반 주변 병원/시설 검색 API (Kakao Maps 또는 정적 데이터)"""

import os
import math
import json
from pathlib import Path
from functools import lru_cache
from typing import Optional, List

import httpx
from fastapi import APIRouter, Query, HTTPException

router = APIRouter(
    prefix="/hospitals",
    tags=["병원 검색"],
)

HIRA_API_BASE = "http://apis.data.go.kr/B551182/MedicalHolidaysInfo"

# 경로 설정
_BASE_DIR = Path(__file__).resolve().parent.parent
_DATA_DIR  = _BASE_DIR / "data"

_DATA_FILES = {
    "소아청소년과":  _DATA_DIR / "data1_cleaned_pediatrics_hospitals.json",
    "야간소아과":    _DATA_DIR / "data2_geocoded_night_hospitals.json",
    "예방접종병원":  _DATA_DIR / "data4_geocoded_national_vaccine_hospitals_final.json",
    "아이돌봄센터":  _DATA_DIR / "data6_geocoded_childcare_facilities_final.json",
}

KAKAO_API_BASE = "https://dapi.kakao.com/v2/local/search"


# 공통 유틸

def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """두 GPS 좌표 간 거리를 미터로 반환 (Haversine 공식)"""
    R = 6_371_000  # 지구 반지름 (미터)
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


@lru_cache(maxsize=10)
def _load_static_data(category: str) -> list[dict]:
    """jaehwi JSON 파일을 카테고리별로 로드 (최초 1회 캐싱)"""
    path = _DATA_FILES.get(category)
    if path and path.exists():
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        print(f"[hospitals] {category} 데이터 로드: {len(data)}건")
        return data
    return []


def _get_all_static_data(categories: list[str]) -> list[dict]:
    """여러 카테고리 데이터를 합쳐서 반환"""
    result = []
    for cat in categories:
        result.extend(_load_static_data(cat))
    return result


def _to_static_response(item: dict, distance_m: Optional[float] = None) -> dict:
    """jaehwi JSON 항목 → API 응답 형식"""
    meta = item.get("metadata", {})
    loc  = meta.get("location", {})
    coords = loc.get("coordinates", [None, None])  # [경도, 위도]
    return {
        "place_name":    item.get("title", ""),
        "category":      item.get("category", ""),
        "address_name":  meta.get("address", ""),
        "phone":         meta.get("phone", ""),
        "sido":          meta.get("sido", ""),
        "sggu":          meta.get("sggu", ""),
        "homepage":      meta.get("homepage", meta.get("url", "")),
        "x":             str(coords[0]) if coords[0] else "",  # 경도
        "y":             str(coords[1]) if coords[1] else "",  # 위도
        "distance":      f"{int(distance_m)}m" if distance_m is not None else "",
        "ykiho":         meta.get("ykiho", ""),   # 심평원 운영시간 조회용
        "data_source":   "jaehwi_static",
    }


# Kakao API 헬퍼
def _get_kakao_headers() -> dict:
    api_key = os.getenv("KAKAO_REST_API_KEY", "")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="KAKAO_REST_API_KEY 가 설정되지 않았습니다. .env 파일을 확인하거나 /hospitals/static/* 엔드포인트를 사용하세요.",
        )
    return {"Authorization": f"KakaoAK {api_key}"}


def _parse_kakao_places(data: dict) -> list:
    return [
        {
            "place_name":        doc.get("place_name", ""),
            "category_name":     doc.get("category_name", ""),
            "address_name":      doc.get("address_name", ""),
            "road_address_name": doc.get("road_address_name", ""),
            "phone":             doc.get("phone", ""),
            "distance":          doc.get("distance", ""),
            "place_url":         doc.get("place_url", ""),
            "x":                 doc.get("x", ""),
            "y":                 doc.get("y", ""),
            "data_source":       "kakao_api",
        }
        for doc in data.get("documents", [])
    ]


# Kakao 실시간 검색 엔드포인트

@router.get("/nearby", summary="현재 위치 기반 주변 소아과/병원 검색 (Kakao)")
async def search_nearby_hospitals(
    lat: float = Query(..., description="현재 위도 (예: 37.5665)"),
    lng: float = Query(..., description="현재 경도 (예: 126.9780)"),
    radius: int = Query(default=2000, ge=100, le=20000, description="검색 반경 (미터)"),
    category: str = Query(default="HP8", description="카테고리 코드: HP8=병원, PM9=약국"),
):
    """
    GPS 좌표 기반 주변 소아과/병원을 Kakao Maps API로 검색합니다.

    Kakao API Key 없이 사용하려면 `/hospitals/static/nearby` 를 이용하세요.
    """
    headers = _get_kakao_headers()
    params = {
        "category_group_code": category,
        "x": lng, "y": lat,
        "radius": radius,
        "sort": "distance",
        "size": 15,
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{KAKAO_API_BASE}/category.json", headers=headers, params=params)

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Kakao API 오류: {resp.status_code}")

    data = resp.json()
    return {
        "total_count":  data.get("meta", {}).get("total_count", 0),
        "search_lat":   lat, "search_lng": lng, "radius_m": radius,
        "data_source":  "kakao_api",
        "hospitals":    _parse_kakao_places(data),
    }


@router.get("/search", summary="키워드 기반 병원/아동발달센터 검색 (Kakao)")
async def search_hospitals_by_keyword(
    query: str = Query(..., description="검색어 (예: '소아과', '아동발달센터')"),
    lat: Optional[float] = Query(None),
    lng: Optional[float] = Query(None),
    radius: int = Query(default=5000, ge=100, le=20000),
):
    """
    키워드로 병원/시설을 Kakao Maps API로 검색합니다.

    Kakao API Key 없이 사용하려면 `/hospitals/static/search` 를 이용하세요.
    """
    headers = _get_kakao_headers()
    params: dict = {"query": query, "size": 15}
    if lat and lng:
        params.update({"x": lng, "y": lat, "radius": radius, "sort": "distance"})

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{KAKAO_API_BASE}/keyword.json", headers=headers, params=params)

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Kakao API 오류: {resp.status_code}")

    data = resp.json()
    return {
        "query":        query,
        "total_count":  data.get("meta", {}).get("total_count", 0),
        "data_source":  "kakao_api",
        "hospitals":    _parse_kakao_places(data),
    }


# jaehwi 정적 데이터 검색 (Kakao API Key 불필요)

_CATEGORY_MAP = {
    "소아청소년과": "소아청소년과",
    "야간소아과":   "야간소아과",
    "예방접종병원": "예방접종병원",
    "아이돌봄센터": "아이돌봄센터",
    "all":          None,  # 전체
}


@router.get("/static/nearby", summary="GPS 기반 반경 내 시설 검색 (jaehwi 정적 데이터)")
def search_static_nearby(
    lat: float = Query(..., description="현재 위도"),
    lng: float = Query(..., description="현재 경도"),
    radius: int = Query(default=3000, ge=100, le=50000, description="검색 반경 (미터)"),
    category: str = Query(
        default="소아청소년과",
        description="소아청소년과 | 야간소아과 | 예방접종병원 | 아이돌봄센터 | all",
    ),
    limit: int = Query(default=20, ge=1, le=100),
):
    """
    jaehwi 브랜치의 정적 데이터(data1~data6)를 사용해 GPS 반경 내 시설을 검색합니다.

    Kakao API Key 없이도 동작합니다.
    해당 JSON 파일이 `data/` 디렉토리에 없으면 빈 결과를 반환합니다.

    **카테고리 설명:**
    - 소아청소년과: data1 (약 1만 건의 전국 소아청소년과)
    - 야간소아과: data2 (야간·휴일 운영 소아과)
    - 예방접종병원: data4 (국가예방접종 지정 의료기관)
    - 아이돌봄센터: data6 (아이돌봄서비스 제공기관)
    - all: 위 4가지 전체

    **사용 예시:**
    ```
    GET /hospitals/static/nearby?lat=37.5665&lng=126.9780&radius=2000&category=소아청소년과
    GET /hospitals/static/nearby?lat=37.5665&lng=126.9780&radius=5000&category=야간소아과
    ```
    """
    if category == "all":
        cats = list(_CATEGORY_MAP.keys())[:-1]  # all 제외
    elif category not in _CATEGORY_MAP:
        raise HTTPException(status_code=400, detail=f"지원하지 않는 카테고리: {category}. 사용 가능: {list(_CATEGORY_MAP.keys())}")
    else:
        cats = [category]

    items = _get_all_static_data(cats)
    if not items:
        return {
            "message": f"데이터 파일이 없습니다. data/ 디렉토리에 jaehwi JSON 파일을 배치하세요.",
            "expected_files": [str(_DATA_FILES.get(c, "")) for c in cats],
            "total_count": 0, "hospitals": [],
        }

    results = []
    for item in items:
        meta  = item.get("metadata", {})
        loc   = meta.get("location", {})
        coords = loc.get("coordinates")
        if not coords or len(coords) < 2:
            continue
        item_lon, item_lat = coords[0], coords[1]
        if item_lon is None or item_lat is None:
            continue
        dist = _haversine_m(lat, lng, float(item_lat), float(item_lon))
        if dist <= radius:
            results.append((dist, item))

    # 거리순 정렬
    results.sort(key=lambda x: x[0])

    return {
        "search_lat":   lat,
        "search_lng":   lng,
        "radius_m":     radius,
        "category":     category,
        "total_count":  len(results),
        "data_source":  "jaehwi_static",
        "hospitals":    [_to_static_response(item, dist) for dist, item in results[:limit]],
    }


@router.get("/static/search", summary="지역명 기반 시설 검색 (jaehwi 정적 데이터)")
def search_static_by_region(
    sido: Optional[str] = Query(None, description="시/도 (예: '서울특별시', '경기도')"),
    sggu: Optional[str] = Query(None, description="시/군/구 (예: '강남구', '수원시')"),
    keyword: Optional[str] = Query(None, description="병원명 키워드 (예: '아이')"),
    category: str = Query(
        default="소아청소년과",
        description="소아청소년과 | 야간소아과 | 예방접종병원 | 아이돌봄센터 | all",
    ),
    limit: int = Query(default=30, ge=1, le=200),
):
    """
    지역명(시/도, 구/군) 또는 키워드로 jaehwi 정적 데이터에서 시설을 검색합니다.

    **사용 예시:**
    ```
    GET /hospitals/static/search?sido=서울특별시&sggu=강남구&category=소아청소년과
    GET /hospitals/static/search?sido=경기도&category=야간소아과
    GET /hospitals/static/search?keyword=삼성&category=예방접종병원
    ```
    """
    if not sido and not sggu and not keyword:
        raise HTTPException(status_code=400, detail="sido, sggu, keyword 중 하나 이상 입력하세요.")

    if category == "all":
        cats = list(_CATEGORY_MAP.keys())[:-1]
    elif category not in _CATEGORY_MAP:
        raise HTTPException(status_code=400, detail=f"지원하지 않는 카테고리: {category}")
    else:
        cats = [category]

    items = _get_all_static_data(cats)
    if not items:
        return {
            "message": "데이터 파일이 없습니다. data/ 디렉토리에 jaehwi JSON 파일을 배치하세요.",
            "total_count": 0, "hospitals": [],
        }

    results = []
    for item in items:
        meta = item.get("metadata", {})
        if sido and sido not in meta.get("sido", ""):
            continue
        if sggu and sggu not in meta.get("sggu", meta.get("district", "")):
            continue
        if keyword and keyword.lower() not in item.get("title", "").lower():
            continue
        results.append(item)

    return {
        "sido":         sido,
        "sggu":         sggu,
        "keyword":      keyword,
        "category":     category,
        "total_count":  len(results),
        "data_source":  "jaehwi_static",
        "hospitals":    [_to_static_response(item) for item in results[:limit]],
    }


@router.get("/static/status", summary="정적 데이터 로드 상태 확인", include_in_schema=False)
def get_static_data_status():
    """jaehwi 데이터 파일 로드 상태 확인 (디버그용)"""
    return {
        cat: {
            "file": str(path),
            "exists": pa