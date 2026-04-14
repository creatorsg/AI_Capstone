# app/rag.py

import json
from datetime import date
from dotenv import load_dotenv

import json
from datetime import date

from langchain_chroma import Chroma
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from prompts import (
    QUERY_ANALYZER_PROMPT,
    QUERY_REWRITE_PROMPT,
    ANSWER_PROMPT,
)
from vector_config import (
    FACILITY_COLLECTION_NAME,
    KNOWLEDGE_COLLECTION_NAME,
    PERSIST_DIR,
)

load_dotenv()


# ---------------------------
# LLM / Embeddings
# ---------------------------

def get_llm(model: str = "gpt-4o-mini"):
    return ChatOpenAI(model=model, temperature=0)


def get_embeddings():
    return OpenAIEmbeddings()


def get_vectorstore(collection_name: str):
    return Chroma(
        collection_name=collection_name,
        embedding_function=get_embeddings(),
        persist_directory=str(PERSIST_DIR),
    )


# ---------------------------
# Child context helpers
# ---------------------------

def calculate_age_months(birth_date_str: str | None) -> int | None:
    if not birth_date_str:
        return None

    y, m, d = map(int, birth_date_str.split("-"))
    birth = date(y, m, d)
    today = date.today()

    months = (today.year - birth.year) * 12 + (today.month - birth.month)
    if today.day < birth.day:
        months -= 1

    return max(months, 0)


def age_group_from_months(age_months: int | None) -> str | None:
    if age_months is None:
        return None
    if age_months < 6:
        return "0-6m"
    if age_months < 12:
        return "6-12m"
    if age_months < 24:
        return "12-24m"
    if age_months < 36:
        return "24-36m"
    return "36-60m"


def format_child_context(child_profile: dict | None) -> str:
    if not child_profile:
        return "등록된 아이 정보 없음"

    age_months = calculate_age_months(child_profile.get("birth_date"))
    parts = [
        f"이름: {child_profile.get('name', 'N/A')}",
        f"생년월일: {child_profile.get('birth_date', 'N/A')}",
        f"개월 수: {age_months if age_months is not None else 'N/A'}",
        f"성별: {child_profile.get('sex', 'N/A')}",
        f"알레르기: {', '.join(child_profile.get('allergies', [])) or '없음'}",
        f"기저질환: {', '.join(child_profile.get('conditions', [])) or '없음'}",
        f"메모: {child_profile.get('notes', '없음')}",
    ]
    return "\n".join(parts)


def format_recent_logs(recent_logs: dict | None) -> str:
    if not recent_logs:
        return "최근 기록 없음"

    lines = []

    sleep_logs = recent_logs.get("sleep", [])
    food_logs = recent_logs.get("food", [])
    fever_logs = recent_logs.get("fever", [])

    if sleep_logs:
        lines.append("[수면 기록]")
        for item in sleep_logs[:3]:
            lines.append(f"- {item}")

    if food_logs:
        lines.append("[식사 기록]")
        for item in food_logs[:3]:
            lines.append(f"- {item}")

    if fever_logs:
        lines.append("[발열 기록]")
        for item in fever_logs[:3]:
            lines.append(f"- {item}")

    return "\n".join(lines) if lines else "최근 기록 없음"


# ---------------------------
# Query analysis
# ---------------------------

def analyze_query(question: str) -> dict:
    llm = get_llm()

    prompt = QUERY_ANALYZER_PROMPT.format(question=question)
    response = llm.invoke(prompt)

    text = response.content.strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = {
            "intent": "unknown",
            "topic": "general",
            "risk_level": "low",
            "needs_clarification": False,
        }

    return parsed


def rewrite_query(question: str, child_profile: dict | None, analysis: dict) -> str:
    llm = get_llm()

    child_context = format_child_context(child_profile)
    prompt = QUERY_REWRITE_PROMPT.format(
        question=question,
        child_context=child_context,
        intent=analysis.get("intent", "unknown"),
        topic=analysis.get("topic", "general"),
    )
    response = llm.invoke(prompt)
    return response.content.strip()


# ---------------------------
# Rule-based safety / risk
# ---------------------------

HIGH_RISK_KEYWORDS = [
    "경련", "숨을 못", "호흡이", "의식", "축 처", "축 처짐", "반응이 없다",
    "반응이 없", "반복 구토", "탈수", "피가", "발달 퇴행", "퇴행"
]


def detect_high_risk_keywords(question: str) -> bool:
    q = question.replace(" ", "")
    for kw in HIGH_RISK_KEYWORDS:
        if kw.replace(" ", "") in q:
            return True
    return False


def normalize_risk_level(question: str, analysis: dict) -> str:
    if detect_high_risk_keywords(question):
        return "high"

    llm_risk = analysis.get("risk_level", "low")
    if llm_risk not in {"low", "medium", "high"}:
        return "low"
    return llm_risk


# ---------------------------
# Retriever routing
# ---------------------------

def get_retriever(intent: str):
    collection_name = (
        FACILITY_COLLECTION_NAME if intent == "hospital_locator" else KNOWLEDGE_COLLECTION_NAME
    )
    vectorstore = get_vectorstore(collection_name)

    # Chroma filter는 너무 복잡하게 잡기보다 category 기준부터 안정적으로
    if intent == "development":
        return vectorstore.as_retriever(
            search_kwargs={"k": 6, "filter": {"category": "development"}}
        )
    elif intent == "daily_parenting":
        return vectorstore.as_retriever(
            search_kwargs={"k": 6, "filter": {"category": "daily_parenting"}}
        )
    elif intent == "medical_basic":
        return vectorstore.as_retriever(
            search_kwargs={"k": 6, "filter": {"category": "medical_basic"}}
        )
    elif intent == "vaccination":
        return vectorstore.as_retriever(
            search_kwargs={"k": 5, "filter": {"category": "vaccination"}}
        )
    elif intent == "policy":
        return vectorstore.as_retriever(
            search_kwargs={"k": 5, "filter": {"category": "policy"}}
        )
    elif intent == "hospital_locator":
        return vectorstore.as_retriever(
            search_kwargs={"k": 5, "filter": {"category": "hospital_locator"}}
        )
    else:
        return vectorstore.as_retriever(search_kwargs={"k": 5})


# ---------------------------
# Simple reranking
# ---------------------------

def simple_rerank(docs, intent: str, topic: str | None = None, age_group: str | None = None):
    rescored = []

    for doc in docs:
        score = 0
        meta = doc.metadata

        if meta.get("category") == intent:
            score += 3
        if topic and meta.get("topic") == topic:
            score += 2
        if age_group and meta.get("age_group") == age_group:
            score += 2
        if meta.get("source") == "curated":
            score += 1

        rescored.append((score, doc))

    rescored.sort(key=lambda x: x[0], reverse=True)
    return [doc for _, doc in rescored]


# ---------------------------
# Generation
# ---------------------------

def build_context(docs) -> str:
    return "\n\n".join(
        [
            f"[문서{i+1}] title={doc.metadata.get('title', 'N/A')} "
            f"category={doc.metadata.get('category', 'N/A')} "
            f"source={doc.metadata.get('source', 'N/A')}\n"
            f"{doc.page_content}"
            for i, doc in enumerate(docs)
        ]
    )


def apply_safety_prefix(answer: str, risk_level: str) -> str:
    if risk_level == "high":
        prefix = (
            "중요: 현재 설명만으로는 응급 가능성을 배제할 수 없습니다. "
            "아이 상태가 나쁘거나 질문에 포함된 위험 신호가 실제로 있다면, "
            "즉시 소아과 또는 응급실 진료를 우선적으로 고려하세요.\n\n"
        )
        return prefix + answer
    return answer


def answer_question(
    question: str,
    child_profile: dict | None = None,
    recent_logs: dict | None = None,
):
    analysis = analyze_query(question)
    risk_level = normalize_risk_level(question, analysis)

    rewritten_query = rewrite_query(question, child_profile, analysis)

    retriever = get_retriever(analysis.get("intent", "unknown"))
    docs = retriever.invoke(rewritten_query)

    age_months = calculate_age_months(child_profile.get("birth_date")) if child_profile else None
    age_group = age_group_from_months(age_months)

    docs = simple_rerank(
        docs,
        intent=analysis.get("intent", "unknown"),
        topic=analysis.get("topic"),
        age_group=age_group,
    )

    top_docs = docs[:4]
    context = build_context(top_docs)

    child_context = format_child_context(child_profile)
    logs_context = format_recent_logs(recent_logs)

    llm = get_llm()

    prompt = ANSWER_PROMPT.format(
        child_context=child_context,
        recent_logs=logs_context,
        context=context,
        question=question,
    )
    response = llm.invoke(prompt)
    answer = apply_safety_prefix(response.content, risk_level)

    debug_info = {
        "analysis": analysis,
        "risk_level": risk_level,
        "rewritten_query": rewritten_query,
    }

    return answer, top_docs, debug_info
