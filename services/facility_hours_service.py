"""시설 운영시간 조회 서비스

채팅 파이프라인에서 호출:
  1. 운영시간 질문 여부 감지
  2. 질문에서 시설명 추출
  3. 정적 데이터(data1~data6)에서 ykiho 검색
  4. 심평원 API 동기 호출 → 실제 운영시간 획득
  5. 프롬프트 주입용 텍스트 반환
"""

import os
import re
import json
import httpx
from pathlib import Path
from typing import Optional

_BASE_DIR = Path(__file__).resolve().parent.parent
_DATA_DIR  = _BASE_DIR / "data"

_DATA_FILES = [
    _DATA_DIR / "data1_cleaned_pediatrics_hospitals.json",
    _DATA_DIR / "data2_geocoded_night_hospitals.json",
    _DATA_DIR / "data4_geocoded_national_vaccine_hospitals_final.json",
    _DATA_DIR / "data6_geocoded_childcare_facilities_final.json",
]

HIRA_API_URL = "http://apis.data.go.kr/B551182/MedicalHolidaysInfo/getMedicalHolidaysInfo"

# 운영시간 질문 감지 키워드
HOURS_KEYWORDS = [
    "운영시간", "영업시간", "진료시간", "진료 시간", "운영 시간",
    "몇시", "몇 시", "언제 열", "언제까지", "몇시까지",
    "문 열", "문 닫", "열어요", "닫아요", "열었나요", "닫혔나요",
    "진료해요", "진료 가능", "진료하나요", "진료 하나요",
    "오늘 열", "지금 열", "지금 진료",
]

# 병원/시설 유형 키워드 (이름 추출용)
FACILITY_TYPE_KEYWORDS = [
    "의원", "병원", "클리닉", "센터", "약국", "치과", "이비인후과",
    "소아과", "내과", "외과", "피부과", "정형외과", "안과", "산부인과",
    "비뇨기과", "신경과", "재활의학과", "정신건강의학과", "한의원",
    "한방병원", "요양병원", "종합병원",
]


# ── 1. 운영시간 질문 감지 ─────────────────────────────────────────────────────

def is_hours_question(question: str) -> bool:
    """운영시간 관련 질문 여부 감지"""
    return any(kw in question for kw in HOURS_KEYWORDS)


# ── 2. 시설명 추출 ────────────────────────────────────────────────────────────

def extract_facility_name(question: str) -> Optional[str]:
    """
    질문에서 시설명 추출.

    우선순위:
      1. 따옴표로 감싼 이름: '연세이비인후과', "삼성병원"
      2. 시설 유형 키워드가 포함된 단어: 연세이비인후과의원, 이치과의원
    """
    # 1순위: 따옴표
    match = re.search(r"['‘’“”\"]([\w\s]+?)['‘’“”\"]", question)
    if match:
        return match.group(1).strip()

    # 2순위: 시설 유형 키워드 포함 단어
    type_pattern = "|".join(FACILITY_TYPE_KEYWORDS)
    match = re.search(rf"(\S+(?:{type_pattern}))", question)
    if match:
        return match.group(1).strip()

    return None


# ── 3. 정적 데이터에서 ykiho 검색 ────────────────────────────────────────────

def search_facility_ykiho(name: str) -> Optional[str]:
    """
    시설명으로 정적 JSON 데이터를 검색해 ykiho 반환.
    완전 일치 우선, 부분 일치 fallback.
    """
    name_norm = name.lower().replace(" ", "")
    best_partial: Optional[str] = None

    for data_file in _DATA_FILES:
        if not data_file.exists():
            continue
        try:
            with open(data_file, encoding="utf-8") as f:
                items = json.load(f)
        except Exception:
            continue

        for item in items:
            title_norm = item.get("title", "").lower().replace(" ", "")
            ykiho = item.get("metadata", {}).get("ykiho", "")
            if not ykiho:
                continue
            # 완전 일치 → 즉시 반환
            if title_norm == name_norm:
                return ykiho
            # 부분 일치 → 후보로 저장
            if best_partial is None and (name_norm in title_norm or title_norm in name_norm):
                best_partial = ykiho

    return best_partial


# ── 4. 심평원 API 동기 호출 ───────────────────────────────────────────────────

def _fmt(t: Optional[str]) -> str:
    """'0900' → '09:00' 변환, 없으면 빈 문자열"""
    if not t or len(t) != 4:
        return ""
    return f"{t[:2]}:{t[2:]}"


def get_hira_hours_sync(ykiho: str) -> Optional[dict]:
    """심평원 API 동기 호출로 운영시간 데이터 반환"""
    service_key = os.getenv("HIRA_SERVICE_KEY", "")
    if not service_key:
        return None

    try:

        params = {
            "serviceKey": service_key,
            "ykiho": ykiho,
            "numOfRows": 1,
            "pageNo": 1,
            "_type": "json",
        }
        resp = httpx.get(HIRA_API_URL, params=params, timeout=8.0)
        if resp.status_code != 200:
            return None

        data = resp.json()
        item_list = (
            data.get("response", {})
                .get("body", {})
                .get("items", {})
                .get("item", [])
        )
        if isinstance(item_list, dict):
            item_list = [item_list]
        if not item_list:
            return None

        item = item_list[0]

        # 요일별 진료시간 (값이 있는 요일만 포함)
        days = {
            "월": (_fmt(item.get("trmtMonStart")), _fmt(item.get("trmtMonEnd"))),
            "화": (_fmt(item.get("trmtTueStart")), _fmt(item.get("trmtTueEnd"))),
            "수": (_fmt(item.get("trmtWedStart")), _fmt(item.get("trmtWedEnd"))),
            "목": (_fmt(item.get("trmtThuStart")), _fmt(item.get("trmtThuEnd"))),
            "금": (_fmt(item.get("trmtFriStart")), _fmt(item.get("trmtFriEnd"))),
            "토": (_fmt(item.get("trmtSatStart")), _fmt(item.get("trmtSatEnd"))),
            "일": (_fmt(item.get("trmtSunStart")), _fmt(item.get("trmtSunEnd"))),
        }
        hours = {
            day: f"{s} ~ {e}"
            for day, (s, e) in days.items()
            if s and e
        }

        lunch_s = _fmt(item.get("lunchWeek"))
        lunch_e = _fmt(item.get("lunchWeekEnd"))

        return {
            "place_name":      item.get("yadmNm", ""),
            "address":         item.get("addr", ""),
            "phone":           item.get("telno", ""),
            "hours":           hours,
            "lunch":           f"{lunch_s} ~ {lunch_e}" if lunch_s and lunch_e else None,
            "reception_week":  _fmt(item.get("rcvWeek")),
            "reception_sat":   _fmt(item.get("rcvSat")),
            "emergency_night": item.get("emyNgtYn") == "Y",
            "emergency_day":   item.get("emyDayYn") == "Y",
            "parking":         item.get("parkXpnsYn") == "Y",
        }
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("심평원 API 호출 실패: %s", e)
        return None


# ── 5. 프롬프트용 텍스트 포맷 ─────────────────────────────────────────────────

def format_hours_for_prompt(data: dict) -> str:
    """운영시간 데이터를 AI가 읽기 좋은 텍스트로 변환"""
    lines = [
        f"[실제 운영 정보: {data['place_name']}]",
        f"주소: {data['address']}",
        f"전화: {data['phone']}",
        "진료시간:",
    ]
    for day, time_range in data["hours"].items():
        lines.append(f"  {day}요일: {time_range}")

    if data.get("lunch"):
        lines.append(f"점심시간: {data['lunch']}")
    if data.get("reception_week"):
        lines.append(f"평일 접수 마감: {data['reception_week']}")
    if data.get("reception_sat"):
        lines.append(f"토요일 접수 마감: {data['reception_sat']}")
    if data.get("emergency_night"):
        lines.append("야간 응급 진료: 가능")
    if data.get("parking"):
        lines.append("주차: 가능")
    lines.append("※ 심평원 공공데이터 기준. 실제 운영과 다를 수 있으니 방문 전 전화 확인 권장.")
    return "\n".join(lines)


# ── 메인 진입점 ───────────────────────────────────────────────────────────────

def get_facility_hours_context(question: str) -> Optional[str]:
    """
    채팅 파이프라인에서 호출하는 메인 함수.

    운영시간 질문이면 실제 데이터를 조회해 프롬프트 주입용 텍스트 반환.
    해당 없거나 데이터 없으면 None 반환 → 기존 RAG 흐름 그대로 진행.
    """
    if not is_hours_question(question):
        return None

    name = extract_facility_name(question)
    if not name:
        return None

    ykiho = search_facility_ykiho(name)
    if not ykiho:
        return None

    hours_data = get_hira_hours_sync(ykiho)
    if not hours_data:
        return None

    return format_hours_for_prompt(hours_data)
