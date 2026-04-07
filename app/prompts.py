from langchain.prompts import ChatPromptTemplate

QUERY_ANALYZER_PROMPT = ChatPromptTemplate.from_template(
    """
당신은 0~5세 자녀를 둔 부모의 질문을 분석하는 분류기입니다.

아래 질문을 보고 반드시 JSON 형태로만 답하세요.
설명 문장, 코드블록, 마크다운은 절대 쓰지 마세요.

반드시 아래 키를 포함하세요:
- intent: development / daily_parenting / medical_basic / vaccination / policy / hospital_locator / unknown
- topic: 질문의 핵심 주제 (예: fever, sleep, language, food, vaccine, welfare, hospital)
- risk_level: low / medium / high
- needs_clarification: true / false

판단 기준:
- development: 발달, 말, 놀이, 사회성, 언어, 개월수별 성장 질문
- daily_parenting: 수면, 식사, 떼쓰기, 울음, 생활습관
- medical_basic: 열, 기침, 콧물, 구토, 설사, 기본 증상
- vaccination: 예방접종 일정, 접종 여부, 접종 시기
- policy: 정부지원, 복지, 지원금, 바우처
- hospital_locator: 병원, 소아과, 발달센터, 위치, 운영시간

high risk 예시:
- 경련
- 호흡 곤란
- 의식 저하
- 축 처짐
- 반복 구토
- 탈수 의심
- 발달 퇴행

needs_clarification = true 인 경우:
- 질문이 너무 짧고 맥락이 부족한 경우
- 예: "열이 나요", "애가 울어요", "밥을 안 먹어요"

질문:
{question}
"""
)

ANSWER_PROMPT = ChatPromptTemplate.from_template(
    """
You are a helpful assistant.
Use only the context below to answer the question.
If the answer is not in the context, say you don't know.

Context:
{context}

Question:
{question}
"""
)