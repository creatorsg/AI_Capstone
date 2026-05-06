"""AI 서비스 공통 로직 (응급 감지, 역질문, 프롬프트 생성)"""

from typing import Optional

from services.emergency_dictionary import ALL_EMERGENCY_KEYWORDS, EMERGENCY_ONTOLOGY


# 응급 키워드 (services/emergency_dictionary.py 에서 통합 관리)

def check_emergency(question: str) -> bool:
    """응급 키워드 포함 여부 확인"""
    return any(keyword in question for keyword in ALL_EMERGENCY_KEYWORDS)


def get_emergency_type(question: str) -> str | None:
    """
    응급 유형 반환 (향후 유형별 대응 메시지 분기용)
    예: "NEUROLOGICAL_EMERGENCY", "RESPIRATORY_EMERGENCY"
    """
    for emergency_type, keywords in EMERGENCY_ONTOLOGY.items():
        if any(kw in question for kw in keywords):
            return emergency_type
    return None


# 역질문 (Back-Question) 로직

CONTEXT_FIELDS = {
    "fever": {
        "temperature":    "열이 몇 도인가요? (예: 38.5도)",
        "duration":       "열이 난 지 얼마나 됐나요? (예: 2일째)",
        "other_symptoms": "다른 증상(기침, 구토 등)이 있나요?",
    },
    "crying": {
        "duration":       "얼마나 오래 울고 있나요?",
        "last_meal":      "마지막으로 먹은 게 언제인가요?",
        "other_symptoms": "다른 증상(열, 구토 등)이 있나요?",
    },
    "sleep": {
        "age_months":  "아이가 몇 개월인가요?",
        "sleep_hours": "하루 평균 몇 시간 자고 있나요?",
    },
    "meal": {
        "age_months": "아이가 몇 개월인가요?",
        "food_type":  "어떤 음식을 먹였나요?",
    },
    "default": {
        "age_months": "아이가 몇 개월인가요?",
        "duration":   "언제부터 그런 증상이 있었나요?",
    },
}


TOPIC_KEYWORDS = {
    "fever":  ["열", "발열", "고열", "체온"],
    "crying": ["울어", "운다", "보챔", "보채", "칭얼"],
    "sleep":  ["잠", "수면", "안 자", "못 자"],
    "meal":   ["밥", "이유식", "분유", "모유", "먹", "수유"],
}

# 역질문 없이 바로 답변하는 키워드
SKIP_CONTEXT_KEYWORDS = [
    "이름", "나이", "생일", "정보", "알고", "기록", "예방접종",
    "발달", "놀이", "정책", "지원", "복지", "병원", "위치",
]


def detect_topic(question: str) -> str:
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(kw in question for kw in keywords):
            return topic
    return "default"


def needs_context_collection(question: str) -> bool:
    if any(kw in question for kw in SKIP_CONTEXT_KEYWORDS):
        return False
    symptom_keywords = [kw for keywords in TOPIC_KEYWORDS.values() for kw in keywords]
    return any(kw in question for kw in symptom_keywords)


def get_missing_context(question: str, context: dict) -> Optional[str]:
    """아직 모르는 컨텍스트 필드에 대한 역질문 문자열 반환"""
    topic = detect_topic(question)
    if topic == "default":
        return None
    for field, question_text in CONTEXT_FIELDS.get(topic, {}).items():
        if field not in context or not context[field]:
            return question_text
    return None


def get_pending_field(question: str, context: dict) -> Optional[str]:
    """현재 대기 중인 컨텍스트 필드명 반환 (세션 저장용)"""
    topic = detect_topic(question)
    if topic == "default":
        return None
    for field in CONTEXT_FIELDS.get(topic, {}):
        if field not in context or not context[field]:
            return field
    return None


# 프롬프트 생성

def build_system_prompt(child_info: Optional[dict] = None) -> str:
    """시스템 프롬프트 (AI 역할 + 오늘 날짜 + 아이 정보 컨텍스트)"""
    from datetime import date
    today_str = date.today().isoformat()
    base = (
        "당신은 초보 부모를 위한 육아 전문 AI 도우미입니다.\n"
        f"[오늘 날짜] {today_str}  ← 나이/개월 수 계산은 반드시 이 날짜를 기준으로 하세요.\n"
        "다음 원칙을 반드시 따르세요:\n"
        "1. 의학적 단정을 피하고, 항상 '소아과 전문의와 상담을 권장합니다'로 마무리하세요.\n"
        "2. 답변은 친근하고 이해하기 쉬운 언어로 작성하세요.\n"
        "3. 위험 증상이 감지되면 즉시 병원 방문을 권고하세요.\n"
        "4. AI 의 한계를 명시하고 정보를 과신하지 않도록 안내하세요.\n"
        "5. 모든 답변은 한국어로 작성하세요.\n"
        "6. 같은 대화 세션의 직전 메시지들이 messages 로 함께 전달됩니다.\n"
        "   사용자가 '전에 ~했던가?' 처럼 과거를 물으면 그 messages 만 보고 답하세요.\n"
        "   이전에 한 적이 없는 일을 한 것처럼 답하지 마세요."
    )
    if child_info:
        allergies  = ", ".join(child_info.get("allergies", [])) or "없음"
        conditions = ", ".join(child_info.get("conditions", [])) or "없음"
        blood_type    = child_info.get("blood_type") or "미입력"
        medical_notes = child_info.get("medical_notes") or "없음"
        height = child_info.get("height_cm")
        weight = child_info.get("weight_kg")
        child_ctx = (
            f"\n\n[현재 질문하는 아이 정보]\n"
            f"- 이름: {child_info.get('name', '미입력')}\n"
            f"- 생년월일: {child_info.get('birth_date', '미입력')}\n"
            f"- 성별: {child_info.get('gender', '미입력')}\n"
            f"- 키: {f'{height}cm' if height else '미입력'}\n"
            f"- 체중: {f'{weight}kg' if weight else '미입력'}\n"
            f"- 알레르기: {allergies}\n"
            f"- 기저질환: {conditions}\n"
            f"- 혈액형: {blood_type}\n"
            f"- 의료 특이사항: {medical_notes}\n"
            f"- 보호자 메모: {child_info.get('notes', '없음')}"
        )
        return base + child_ctx
    return base


def build_rag_prompt(
    question: str,
    context: dict,
    retrieved_docs: list[str],
    hours_context: str | None = None,
) -> str:
    """RAG 문서 + 수집 컨텍스트 + 운영시간 데이터를 포함한 최종 질문 프롬프트 생성"""
    context_str = "\n".join(f"- {k}: {v}" for k, v in context.items()) if context else "없음"

    parts = [f"사용자 질문: {question}", f"\n수집된 맥락:\n{context_str}"]

    # 운영시간 실제 데이터가 있으면 최우선으로 주입
    if hours