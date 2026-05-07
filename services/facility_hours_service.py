"""시설 운영시간 조회 서비스

채팅 파이프라인에서 호출:
  1. 운영시간 질문 여부 감지
  2. 질문에서 시설명 추출
  3. 정적 데이터에서 병원 메타(sido/sggu) 조회
  4. 심평원 getHospBasisList API로 이름+지역 검색 -> 진료시간 획득
  5. 프롬프트 주입용 텍스트 반환
"""

import os
import re
import json
import logging
import httpx
from pathlib import Path
from urllib.parse import unquote
from typing import Optional

logger = logging.getLogger(__name__)

_BASE_DIR = Path(__file__).resolve().parent.parent
_DATA_DIR  = _BASE_DIR / "data"

_DATA_FILES = [
    _DATA_DIR / "data1_cleaned_pediatrics_hospitals.json",
    _DATA_DIR / "data2_geocoded_night_hospitals.json",
    _DATA_DIR / "data4_geocoded_national_vaccine_hospitals_final.json",
    _DATA_DIR / "data6_geocoded_childcare_facilities_final.json",
]

# 병원목록 조회 API (이름 검색 + 진료시간 포함)
HIRA_HOSP_URL = "http://apis.data.go.kr/B551182/hospInfoServicev2/getHospBasisList"

HOURS_KEYWORDS = [
    "운영시간", "영업시간", "진료시간", "진료 시간", "운영 시간",
    "몇시", "몇 시", "언제 열", "언제까지", "몇시까지",
    "문 열", "문 닫", "열어요", "닫아요", "열었나요", "닫혔나요",
    "진료해요", "진료 가능", "진료하나요", "진료 하나요",
    "오늘 열", "지금 열", "지금 진료",
]

FACILITY_TYPE_KEYWORDS = [
    "의원", "병원", "클리닉", "센터", "약국", "치과", "이비인후과",
    "소아과", "내과", "외과", "피부과", "정형외과", "안과", "산부인과",
    "비뇨기과", "신경과", "재활의학과", "정신건강의학과", "한의원",
    "한방병원", "요양병원", "종합병원",
]

# 시도 이름 -> 심평원 API 코드 매핑
SIDO_CODE_MAP = {
    "서울": "110000", "부산": "210000", "대구": "220000", "인천": "230000",
    "광주": "240000", "대전": "250000", "울산": "260000", "세종": "290000",
    "경기": "410000", "강원": "420000", "충북": "430000", "충남": "440000",
    "전북": "450000", "전남": "460000", "경북": "470000", "경남": "480000",
    "제주": "500000",
}


# 1. 운영시간 질문 감지

def is_hours_question(question: str) -> bool:
    return any(kw in question for kw in HOURS_KEYWORDS)


# 2. 시설명 추출

def extract_facility_name(question: str) -> Optional[str]:
    """
    질문에서 시설명을 추출합니다.
    우선순위:
      1) 유니코드/ASCII 따옴표 쌍으로 둘러싸인 이름 (여는따옴표/닫는따옴표 쌍 구분)
      2) 시설 유형 키워드로 끝나는 단어
    """
    # 여는따옴표 -> 닫는따옴표 쌍 목록 (유니코드 곡선따옴표 포함)
    quote_pairs = [
        ('‘', '’'),  # ' '  (U+2018, U+2019)
        ('“', '”'),  # " "  (U+201C, U+201D)
        ("'", "'"),            # ASCII 작은따옴표
        ('"', '"'),            # ASCII 큰따옴표
    ]
    for open_q, close_q in quote_pairs:
        idx_open = question.find(open_q)
        if idx_open >= 0:
            idx_close = question.find(close_q, idx_open + 1)
            if idx_close > idx_open:
                name = question[idx_open + 1:idx_close].strip()
                if name:
                    return name

    # 따옴표 없으면 시설 유형 키워드 기반 추출
    type_pattern = "|".join(re.escape(k) for k in FACILITY_TYPE_KEYWORDS)
    match = re.search(rf"(\S+(?:{type_pattern}))", question)
    if match:
        return match.group(1).strip()

    return None


# 3. 정적 데이터에서 시설 메타정보 조회

def search_facility_meta(name: str) -> Optional[dict]:
    """
    이름으로 정적 데이터 검색 -> sido/sggu 등 메타 반환.
    완전 일치 우선, 부분 일치 fallback.
    """
    name_norm = name.lower().replace(" ", "")
    best: Optional[dict] = None

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
            meta = item.get("metadata", {})
            if title_norm == name_norm:
                return {"title": item["title"], **meta}
            if best is None and (name_norm in title_norm or title_norm in name_norm):
                best = {"title": item["title"], **meta}

    return best


# 4. 심평원 병원목록 API 호출 (이름 검색)

def _fmt(t: Optional[str]) -> str:
    if not t or len(t) != 4:
        return ""
    return f"{t[:2]}:{t[2:]}"


def search_hira_by_name(name: str, sido: str = None) -> Optional[dict]:
    """
    심평원 getHospBasisList API로 병원명 검색.
    sido 가 있으면 지역 필터 추가 -> 동명 병원 중 올바른 곳 선택.
    """
    service_key = unquote(os.getenv("HIRA_SERVICE_KEY", ""))
    if not service_key:
        logger.warning("HIRA_SERVICE_KEY 가 설정되지 않았습니다.")
        return None

    params = {
        "serviceKey": service_key,
        "yadmNm": name,
        "numOfRows": 10,
        "pageNo": 1,
        "_type": "json",
    }
    if sido and sido in SIDO_CODE_MAP:
        params["sidoCd"] = SIDO_CODE_MAP[sido]

    try:
        resp = httpx.get(HIRA_HOSP_URL, params=params, timeout=15.0)

        if resp.status_code != 200:
            logger.warning(
                "심평원 API 비정상 응답: status=%s name=%s body=%s",
                resp.status_code, name, resp.text[:300],
            )
            return None

        data = resp.json()

        # API 결과 없을 때 items 가 빈 문자열/None 으로 올 수 있어 방어 처리
        body = data.get("response", {}).get("body", {})
        raw_items = body.get("items")
        if not raw_items or not isinstance(raw_items, dict):
            logger.warning("심평원 API: 결과 없음 (items=%r) name=%s", raw_items, name)
            return None

        item_list = raw_items.get("item", [])
        if isinstance(item_list, dict):
            item_list = [item_list]
        if not item_list:
            logger.warning("심평원 API: 검색 결과 없음 name=%s", name)
            return None

        # 완전 일치 우선, 없으면 이름 포함 관계 확인 후 선택
        name_norm = name.replace(" ", "")
        chosen = None
        partial = None
        for it in item_list:
            it_name_norm = it.get("yadmNm", "").replace(" ", "")
            if it_name_norm == name_norm:
                chosen = it
                break
            # 검색어가 결과 이름에 포함되거나 반대인 경우 (부분 일치)
            if partial is None and (name_norm in it_name_norm or it_name_norm in name_norm):
                partial = it

        if chosen is None:
            if partial is not None:
                chosen = partial
                logger.warning(
                    "심평원 API: 완전 일치 없음, 부분 일치 사용 name=%s matched=%s",
                    name, chosen.get("yadmNm"),
                )
            else:
                logger.warning("심평원 API: 이름 불일치 (완전/부분 일치 모두 없음) name=%s", name)
                return None

        days = {
            "월": (_fmt(chosen.get("trmtMonStart")), _fmt(chosen.get("trmtMonEnd"))),
            "화": (_fmt(chosen.get("trmtTueStart")), _fmt(chosen.get("trmtTueEnd"))),
            "수": (_fmt(chosen.get("trmtWedStart")), _fmt(chosen.get("trmtWedEnd"))),
            "목": (_fmt(chosen.get("trmtThuStart")), _fmt(chosen.get("trmtThuEnd"))),
            "금": (_fmt(chosen.get("trmtFriStart")), _fmt(chosen.get("trmtFriEnd"))),
            "토": (_fmt(chosen.get("trmtSatStart")), _fmt(chosen.get("trmtSatEnd"))),
            "일": (_fmt(chosen.get("trmtSunStart")), _fmt(chosen.get("trmtSunEnd"))),
        }
        hours = {day: f"{s} ~ {e}" for day, (s, e) in days.items() if s and e}

        # 진료시간 정보가 없으면 유용한 데이터가 없으므로 None 반환
        if not hours:
            logger.warning(
                "심평원 API: 진료시간 정보 없음 name=%s matched=%s",
                name, chosen.get("yadmNm"),
            )
            return None

        lunch_s = _fmt(chosen.get("lunchWeek"))
        lunch_e = _fmt(chosen.get("lunchWeekEnd"))

        return {
            "place_name": chosen.get("yadmNm", name),
            "address":    chosen.get("addr", ""),
            "phone":      chosen.get("telno", ""),
            "hours":      hours,
            "lunch":      f"{lunch_s} ~ {lunch_e}" if lunch_s and lunch_e else None,
            "reception_week": _fmt(chosen.get("rcvWeek")),
            "reception_sat":  _fmt(chosen.get("rcvSat")),
            "emergency_night": chosen.get("emyNgtYn") == "Y",
            "parking":         chosen.get("parkXpnsYn") == "Y",
        }

    except Exception as e:
        logger.warning("심평원 API 호출 실패: %s", e)
        return None


# 5. 프롬프트용 텍스트 포맷

def format_meta_for_prompt(name: str, meta: dict) -> str:
    """심평원 API에서 진료시간을 가져오지 못했을 때 정적 데이터 정보만 제공."""
    lines = [
        f"[시설 기본 정보: {name}]",
        f"주소: {meta.get('address', '정보 없음')}",
        f"전화: {meta.get('phone', '정보 없음')}",
        "진료시간: 정확한 진료시간은 전화로 직접 확인 바랍니다.",
        "※ 운영시간은 변동될 수 있으니 방문 전 전화 확인 권장.",
    ]
    return "\n".join(lines)


def format_hours_for_prompt(data: dict) -> str:
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


# 메인 진입점

def get_facility_hours_context(question: str) -> Optional[str]:
    """
    채팅 파이프라인에서 호출하는 메인 함수.
    운영시간 질문이면 실제 데이터를 조회해 프롬프트 주입용 텍스트 반환.
    """
    if not is_hours_question(question):
        return None

    name = extract_facility_name(question)
    if not name:
        logger.warning("시설명 추출 실패: question=%s", question)
        return None

    # 정적 데이터에서 sido 정보 가져와 지역 필터로 활용
    meta = search_facility_meta(name)
    sido = meta.get("sido") if meta else None

    logger.warning("심평원 API 호출: name=%s sido=%s", name, sido)
    hours_data = search_hira_by_name(name, sido=sido)

    if hours_data:
        # 심평원 API에서 진료시간 정보 획득 성공
        return format_hours_for_prompt(hours_data)

    if meta:
        # 심평원 API 실패했지만 정적 데이터에 주소/전화 정보 있음
        logger.warning("심평원 API 실패 -> 정적 데이터 fallback: name=%s", name)
        return format_meta_for_prompt(name, meta)

    return None
