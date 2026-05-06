"""GPS 기반 주변 병원/시설/약국 검색 API (Kakao Maps 또는 정적 데이터)"""

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

_BASE_DIR = Path(__file__).resolve().parent.parent
_DATA_DIR  = _BASE_DIR / "data"

_DATA_FILES = {
    "소아청소년과":  _DATA_DIR / "data1_cleaned_pediatrics_hospitals.json",
    "야간소아과":    _DATA_DIR / "data2_geocoded_night_hospitals.json",
    "예방접종병원":  _DATA_DIR / "data4_geocoded_national_vaccine_hospitals_final.json",
    "아이돌봄센터":  _DATA_DIR / "data6_geocoded_childcare_facilities_final.json",
    "약국":          _DATA_DIR / "data8_national_pharmacies_full.json",
}

KAKAO_API_BASE = "https://dapi.kakao.com/v2/local/search"


def _haversine_m(lat1, lon1, lat2, lon2):
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


@lru_cache(maxsize=10)
def _load_static_data(category: str) -> list:
    path = _DATA_FILES.get(category)
    if path and path.exists():
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        print(f"[hospitals] {category} 데이터 로드: {len(data)}건")
        return data
    return []


def _get_all_static_data(categories: list) -> list:
    result = []
    for cat in categories:
        result.extend(_load_static_data(cat))
    return result


def _to_static_response(item: dict, distance_m=None) -> dict:
    meta   = item.get("metadata", {})
    loc    = meta.get("location", {})
    coords = loc.get("coordinates", [None, None])

    resp = {
        "place_name":   item.get("title", ""),
        "category":     item.get("category", ""),
        "address_name": meta.get("address", ""),
        "phone":        meta.get("phone", ""),
        "sido":         meta.get("sido", ""),
        "sggu":         meta.get("sggu", ""),
        "homepage":     meta.get("homepage", meta.get("url", "")),
        "x":            str(coords[0]) if coords[0] else "",
        "y":            str(coords[1]) if coords[1] else "",
        "distance":     f"{int(distance_m)}m" if distance_m is not None else "",
        "ykiho":        meta.get("ykiho", ""),
        "hpid":         meta.get("hpid", ""),
        "data_source":  "jaehwi_static",
    }
    if item.get("category") == "약국":
        resp["operating_hours"]  = meta.get("operating_hours", "")
        resp["hours_structured"] = meta.get("hours_structured", {})
    return resp


def _get_kakao_headers() -> dict:
    api_key = os.getenv("KAKAO_REST_API_KEY", "")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="KAKAO_REST_API_KEY 가 설정되지 않았습니다. /hospitals/static/* 엔드포인트를 사용하세요.",
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


@router.get("/nearby", summary="현재 위치 기반 주변 소아과/병원/약국 검색 (Kakao)")
async def search_nearby_hospitals(
    lat: float = Query(..., description="현재 위도 (예: 37.5665)"),
    lng: float = Query(..., description="현재 경도 (예: 126.9780)"),
    radius: int = Query(default=2000, ge=100, le=20000, description="검색 반경 (미터)"),
    category: str = Query(default="HP8", description="카테고리 코드: HP8=병원, PM9=약국"),
):
    """GPS 좌표 기반 주변 병원/약국을 Kakao Maps API로 검색합니다."""
    headers = _get_kakao_headers()
    params = {"category_group_code": category, "x": lng, "y": lat,
              "radius": radius, "sort": "distance", "size": 15}
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{KAKAO_API_BASE}/category.json", headers=headers, params=params)
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Kakao API 오류: {resp.status_code}")
    data = resp.json()
    return {
        "total_count": data.get("meta", {}).get("total_count", 0),
        "search_lat": lat, "search_lng": lng, "radius_m": radius,
        "data_source": "kakao_api",
        "hospitals": _parse_kakao_places(data),
    }


@router.get("/search", summary="키워드 기반 병원/약국 검색 (Kakao)")
async def search_hospitals_by_keyword(
    query: str = Query(..., description="검색어 (예: '소아과', '약국')"),
    lat: Optional[float] = Query(None),
    lng: Optional[float] = Query(None),
    radius: int = Query(default=5000, ge=100, le=20000),
):
    """키워드로 병원/약국을 Kakao Maps API로 검색합니다."""
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
        "query": query,
        "total_count": data.get("meta", {}).get("total_count", 0),
        "data_source": "kakao_api",
        "hospitals": _parse_kakao_places(data),
    }


_CATEGORY_MAP = {
    "소아청소년과": "소아청소년과",
    "야간소아과":   "야간소아과",
    "예방접종병원": "예방접종병원",
    "아이돌봄센터": "아이돌봄센터",
    "약국":         "약국",
    "all":          None,
}

_VALID_CATEGORIES = [k for k in _CATEGORY_MAP if k != "all"]


@router.get("/static/nearby", summary="GPS 기반 반경 내 시설/약국 검색 (정적 데이터)")
def search_static_nearby(
    lat: float = Query(..., description="현재 위도"),
    lng: float = Query(..., description="현재 경도"),
    radius: int = Query(default=3000, ge=100, le=50000, description="검색 반경 (미터)"),
    category: str = Query(
        default="소아청소년과",
        description="소아청소년과 | 야간소아과 | 예방접종병원 | 아이돌봄센터 | 약국 | all",
    ),
    limit: int = Query(default=20, ge=1, le=100),
):
    """
    jaehwi 정적 데이터(data1~data8)를 사용해 GPS 반경 내 시설/약국을 검색합니다.

    - 소아청소년과: data1 / 야간소아과: data2 / 예방접종병원: data4
    - 아이돌봄센터: data6 / 약국: data8 (25,217건 + 운영시간) / all: 전체
    """
    if category == "all":
        cats = _VALID_CATEGORIES
    elif category not in _CATEGORY_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 카테고리: {category}. 사용 가능: {_VALID_CATEGORIES + ['all']}",
        )
    else:
        cats = [category]

    items = _get_all_static_data(cats)
    if not items:
        return {
            "message": "데이터 파일이 없습니다. data/ 디렉토리에 jaehwi JSON 파일을 배치하세요.",
            "expected_files": [str(_DATA_FILES.get(c, "")) for c in cats],
            "total_count": 0, "hospitals": [],
        }

    results = []
    for item in items:
        meta   = item.get("metadata", {})
        coords = meta.get("location", {}).get("coordinates")
        if not coords or len(coords) < 2 or coords[0] is None or coords[1] is None:
            continue
        dist = _haversine_m(lat, lng, float(coords[1]), float(coords[0]))
        if dist <= radius:
            results.append((dist, item))

    results.sort(key=lambda x: x[0])
    return {
        "search_lat": lat, "search_lng": lng, "radius_m": radius,
        "category": category, "total_count": len(results),
        "data_source": "jaehwi_static",
        "hospitals": [_to_static_response(item, dist) for dist, item in results[:limit]],
    }


@router.get("/static/search", summary="지역명/키워드 기반 시설/약국 검색 (정적 데이터)")
def search_static_by_region(
    sido: Optional[str] = Query(None, description="시/도 (예: '서울특별시')"),
    sggu: Optional[str] = Query(None, description="시/군/구 (예: '강남구')"),
    keyword: Optional[str] = Query(None, description="이름 키워드"),
    category: str = Query(
        default="소아청소년과",
        description="소아청소년과 | 야간소아과 | 예방접종병원 | 아이돌봄센터 | 약국 | all",
    ),
    limit: int = Query(default=30, ge=1, le=200),
):
    """지역명 또는 키워드로 정적 데이터에서 시설/약국을 검색합니다."""
    if not sido and not sggu and not keyword:
        raise HTTPException(status_code=400, detail="sido, sggu, keyword 중 하나 이상 입력하세요.")

    if category == "all":
        cats = _VALID_CATEGORIES
    elif category not in _CATEGORY_MAP:
        raise HTTPException(status_code=400, detail=f"지원하지 않는 카테고리: {category}")
    else:
        cats = [category]

    items = _get_all_static_data(cats)
    if not items:
        return {"message": "데이터 파일이 없습니다.", "total_count": 0, "hospitals": []}

    results = []
    for item in items:
        meta = item.get("metadata", {})
        address = meta.get("address", "")
        if sido and sido not in meta.get("sido", address):
            continue
        if sggu and sggu not in meta.get("sggu", address):
            continue
        if keyword and keyword.lower() not in item.get("title", "").lower():
            continue
        results.append(item)

    return {
        "sido": sido, "sggu": sggu, "keyword": keyword,
        "category": category, "total_count": len(results),
        "data_source": "jaehwi_static",
        "hospitals": [_to_static_response(item) for item in results[:limit]],
    }


@router.get("/static/status", summary="정적 데이터 로드 상태 확인", include_in_schema=False)
def get_static_data_status():
    """jaehwi 데이터 파일 로드 상태 확인 (디버그용)"""
    return {
        cat: {
            "file":    str(path),
            "exists":  path.exists(),
            "size_mb": round(path.stat().st_size / 1024 / 1024, 1) if path.exists() else 0,
        }
        for cat, path in _DATA_FILES.items()
    }
