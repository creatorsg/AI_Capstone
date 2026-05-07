"""정부 육아 지원 복지 정책 안내 API (jaehwi 데이터 또는 fallback)"""

import json
import os
from pathlib import Path
from functools import lru_cache
from fastapi import APIRouter, Query
from typing import Optional

router = APIRouter(
    prefix="/welfare",
    tags=["정부 복지 정책"],
)

# jaehwi 데이터 파일 경로
_BASE_DIR = Path(__file__).resolve().parent.parent   # fount-project/
_DATA5_PATH = _BASE_DIR / "data" / "data5_welfare_childcare_kb.json"


@lru_cache(maxsize=1)
def _load_welfare_data() -> list[dict]:
    """
    data5_welfare_childcare_kb.json 로드 (서버 시작 후 최초 1회만 읽음).
    파일이 없으면 하드코딩 fallback 반환.
    """
    if _DATA5_PATH.exists():
        with open(_DATA5_PATH, encoding="utf-8") as f:
            raw = json.load(f)
        print(f"[welfare] jaehwi 데이터 로드 완료: {len(raw)}건 ({_DATA5_PATH})")
        return raw
    else:
        print(f"[welfare] jaehwi 데이터 파일 없음 → fallback 사용 ({_DATA5_PATH})")
        return []


def _to_response(item: dict, idx: int) -> dict:
    """jaehwi JSON 항목 → API 응답 형식으로 변환"""
    meta = item.get("metadata", {})
    return {
        "id":           idx,
        "title":        item.get("title", ""),
        "category":     item.get("category", "복지서비스"),
        "content":      item.get("content", ""),
        "department":   meta.get("department", ""),
        "contact":      meta.get("contact", ""),
        "url":          meta.get("url", ""),
        "service_id":   meta.get("service_id", ""),
        # fallback 데이터 호환 필드 (없으면 None)
        "target":               item.get("target"),
        "benefit":              item.get("benefit"),
        "how_to_apply":         item.get("how_to_apply"),
        "target_age_min_months": item.get("target_age_min_months"),
        "target_age_max_months": item.get("target_age_max_months"),
    }


def _get_policies() -> list[dict]:
    """jaehwi 데이터 또는 fallback 반환"""
    loaded = _load_welfare_data()
    if loaded:
        return [_to_response(item, i + 1) for i, item in enumerate(loaded)]
    return _WELFARE_FALLBACK


# 엔드포인트

@router.get("/", summary="전체 복지 정책 목록 조회")
def get_all_welfare_policies(
    limit: int = Query(default=50, ge=1, le=500, description="최대 반환 건수"),
    offset: int = Query(default=0, ge=0, description="건너뛸 항목 수 (페이지네이션)"),
):
    """
    육아/아동 관련 정부 복지 정책 목록을 반환합니다.

    jaehwi 브랜치의 data5 파일이 있으면 실제 공공데이터(수백 건),
    없으면 하드코딩 fallback 데이터(10건)를 반환합니다.
    """
    all_policies = _get_policies()
    sliced = all_policies[offset: offset + limit]
    return {
        "total_count": len(all_policies),
        "returned_count": len(sliced),
        "offset": offset,
        "data_source": "jaehwi_data5" if _DATA5_PATH.exists() else "fallback",
        "notice": "정책 내용은 변경될 수 있습니다. 최신 정보는 복지로(bokjiro.go.kr)에서 확인하세요.",
        "policies": sliced,
    }


@router.get("/search", summary="복지 정책 키워드 검색")
def search_welfare_policies(
    keyword: str = Query(..., description="검색 키워드 (예: '육아휴직', '보육료', '다자녀')"),
    limit: int = Query(default=20, ge=1, le=100),
):
    """
    제목 또는 내용에 키워드가 포함된 복지 정책을 검색합니다.

    **사용 예시:**
    ```
    GET /welfare/search?keyword=다자녀
    GET /welfare/search?keyword=출산
    ```
    """
    kw = keyword.lower()
    matched = [
        p for p in _get_policies()
        if kw in p["title"].lower() or kw in (p.get("content") or "").lower()
    ]
    return {
        "keyword": keyword,
        "total_count": len(matched),
        "policies": matched[:limit],
    }


@router.get("/age/{months}", summary="아이 월령별 해당 복지 정책 조회")
def get_welfare_by_age(
    months: int,
    category: Optional[str] = Query(None, description="카테고리 필터 (예: '복지서비스', '현금지원')"),
):
    """
    아이의 월령(개월 수)에 맞는 복지 정책을 반환합니다.

    jaehwi 실제 데이터에는 월령 필드가 없어 전체 반환됩니다.
    fallback 데이터는 월령 필터링이 적용됩니다.

    **사용 예시:**
    ```
    GET /welfare/age/6
    GET /welfare/age/36?category=현금지원
    ```
    """
    all_policies = _get_policies()

    if _DATA5_PATH.exists():
        # jaehwi 실제 데이터: 월령 필드 없음 → 전체 반환 (카테고리만 필터)
        filtered = all_policies
    else:
        # fallback 데이터: 월령 범위 필터링
        filtered = [
            p for p in all_policies
            if (p.get("target_age_min_months") is not None
                and p["target_age_min_months"] <= months <= p["target_age_max_months"])
        ]

    if category:
        filtered = [p for p in filtered if p.get("category") == category]

    return {
        "child_age_months": months,
        "total_count": len(filtered),
        "data_source": "jaehwi_data5" if _DATA5_PATH.exists() else "fallback",
        "notice": "정책 내용은 변경될 수 있습니다. 최신 정보는 복지로(bokjiro.go.kr)에서 확인하세요.",
        "policies": filtered[:50],
    }


@router.get("/categories", summary="복지 정책 카테고리 목록")
def get_welfare_categories():
    """사용 가능한 복지 정책 카테고리 목록을 반환합니다."""
    categories = sorted({p.get("category", "") for p in _get_policies() if p.get("category")})
    return {
        "categories": categories,
        "data_source": "jaehwi_data5" if _DATA5_PATH.exists() else "fallback",
    }


@router.get("/status", summary="복지 데이터 로드 상태 확인", include_in_schema=False)
def get_data_status():
    """jaehwi 데이터 파일 로드 여부 확인 (디버그용)"""
    loaded = _load_welfare_data()
    return {
        "data5_path": str(_DATA5_PATH),
        "file_exists": _DATA5_PATH.exists(),
        "loaded_count": len(loaded),
        "source": "jaehwi_data5" if loaded else "fallback_hardcoded",
    }


# Fallback 하드코딩 데이터 (jaehwi 파일 없을 때 사용)
# 출처: 복지로 (www.bokjiro.go.kr), 아이행복카드 (www.ihappy.or.kr) 2024~2025
_WELFARE_FALLBACK = [
    {
        "id": 1, "title": "부모급여", "category": "현금지원",
        "target": "만 0~1세 아동 가정",
        "target_age_min_months": 0, "target_age_max_months": 23,
        "benefit": "만 0세: 월 100만원 / 만 1세: 월 50만원 지급",
        "how_to_apply": "읍면동 주민센터 또는 복지로(bokjiro.go.kr) 온라인 신청",
        "content": "만 0~1세 아동 가정에 현금 지원하는 부모급여 서비스입니다.",
        "url": "https://www.bokjiro.go.kr",
        "department": "보건복지부", "contact": "129",
    },
    {
        "id": 2, "title": "아동수당", "category": "현금지원",
        "target": "만 8세 미만 아동",
        "target_age_min_months": 0, "target_age_max_months": 95,
        "benefit": "월 10만원 지급",
        "how_to_apply": "읍면동 주민센터 또는 복지로 온라인 신청",
        "content": "만 8세 미만 아동에게 매월 10만원을 지급하는 아동수당입니다.",
        "url": "https://www.bokjiro.go.kr",
        "department": "보건복지부", "contact": "129",
    },
    {
        "id": 3, "title": "영아기 집중 돌봄 지원 (영아 종일제 아이돌봄)", "category": "돌봄서비스",
        "target": "만 0~36개월 영아 가정",
        "target_age_min_months": 0, "target_age_max_months": 36,
        "benefit": "아이돌보미 가정 방문 종일 돌봄 서비스 제공 (소득 수준별 지원)",
        "how_to_apply": "아이돌봄서비스(idolbom.go.kr) 온라인 신청",
        "content": "만 0~36개월 영아 가정에 아이돌보미를 파견하는 종일제 아이돌봄 서비스입니다.",
        "url": "https://idolbom.go.kr",
        "department": "여성가족부", "contact": "1577-2514",
    },
    {
        "id": 4, "title": "어린이집 보육료 지원", "category": "보육지원",
        "target": "만 0~5세 어린이집 이용 아동",
        "target_age_min_months": 0, "target_age_max_months": 71,
        "benefit": "연령별 보육료 전액 또는 일부 지원 (국공립/민간/가정 어린이집)",
        "how_to_apply": "아이행복카드 발급 후 어린이집에서 결제 (복지로 신청)",
        "content": "만 0~5세 어린이집 이용 아동에게 보육료를 지원하는 서비스입니다.",
        "url": "https://www.ihappy.or.kr",
        "department": "보건복지부", "contact": "129",
    },
    {
        "id": 5, "title": "유아학비 지원 (유치원)", "category": "보육지원",
        "target": "만 3~5세 유치원 이용 아동",
        "target_age_min_months": 36, "target_age_max_months": 71,
        "benefit": "국공립: 월 6만원 / 사립: 월 28만원 지원",
        "how_to_apply": "아이행복카드 발급 후 유치원에서 결제",
        "content": "만 3~5세 유치원 이용 아동에게 유아학비를 지원하는 서비스입니다.",
        "url": "https://www.ihappy.or.kr",
        "department": "교육부", "contact": "1544-0079",
    },
    {
        "id": 6, "title": "첫만남이용권", "category": "현금지원",
        "target": "출생 아동 (2022.1.1 이후 출생)",
        "target_age_min_months": 0, "target_age_max_months": 12,
        "benefit": "출생 시 200만원 바우처 지급 (국민행복카드로 사용)",
        "how_to_apply": "읍면동 주민센터 또는 정부24(gov.kr) 온라인 신청",
        "content": "출생 아동에게 200만원 바우처를 지급하는 첫만남이용권 서비스입니다.",
        "url": "https://www.gov.kr",
        "department": "보건복지부", "contact": "129",
    },
    {
        "id": 7, "title": "산모·신생아 건강관리 지원", "category": "건강지원",
        "target": "출산 후 가정 (소득 기준 충족 시)",
        "target_age_min_months": 0, "target_age_max_months": 3,
        "benefit": "전문 건강관리사 가정 방문, 산모 회복 및 신생아 돌봄 지원",
        "how_to_apply": "임신 중 복지로 또는 보건소 신청",
        "content": "출산 후 가정에 건강관리사를 파견하는 산모·신생아 건강관리 지원 서비스입니다.",
        "url": "https://www.bokjiro.go.kr",
        "department": "보건복지부", "contact": "129",
    },
    {
        "id": 8, "title": "발달재활서비스 바우처", "category": "발달지원",
        "target": "발달장애 의심 또는 확진 아동 (만 18세 미만)",
        "target_age_min_months": 0, "target_age_max_months": 215,
        "benefit": "언어치료, 인지치료, 행동치료 등 재활서비스 바우처 월 25만원 지원",
        "how_to_apply": "읍면동 주민센터에 서비스 신청 (의사 진단서 필요)",
        "content": "발달장애 아동에게 재활서비스 바우처를 월 25만원 지원하는 서비스입니다.",
        "url": "https://www.bokjiro.go.kr",
        "department": "보건복지부", "contact": "129",
    },
    {
        "id": 9, "title": "임신·출산 진료비 지원 (국민행복카드)", "category": "의료지원",
        "target": "임산부 및 2세 미만 영아",
        "target_age_min_months": 0, "target_age_max_months": 24,
        "benefit": "임신 확인 후 100만원 바우처 지급 (분만 취약지 추가 20만원)",
        "how_to_apply": "건강보험공단 또는 카드사에서 국민행복카드 발급",
        "content": "임산부에게 진료비 100만원 바우처를 지급하는 국민행복카드 서비스입니다.",
        "url": "https://www.nhis.or.kr",
        "department": "보건복지부", "contact": "1577-1000",
    },
    {
        "id": 10, "title": "영유아 건강검진", "category": "의료지원",
        "target": "생후 14일 ~ 71개월 영유아",
        "target_age_min_months": 0, "target_age_max_months": 71,
        "benefit": "7차에 걸쳐 무료 건강검진 제공 (발달선별검사, 구강검진 포함)",
        "how_to_apply": "건강보험공단에서 검진표 발송 → 지정 의료기관 방문",
        "content": "생후 14일~71개월 영유아에게 무료 건강검진을 제공하는 서비스입니다.",
        "url": "https://www.nhis.or.kr",
        "department": "보건복지부", "contact": "1577-1000",
    },
]
