# app/rag.py

import json
import os
import time
from datetime import date
from functools import lru_cache
from dotenv import load_dotenv

from langchain_chroma import Chroma
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from prompts import (
    QUERY_ANALYZER_PROMPT,
    QUERY_PREPROCESS_PROMPT,
    QUERY_REWRITE_PROMPT,
    format_chat_history,
    get_answer_prompt,
)
from vector_config import (
    EMBEDDING_MODEL,
    FACILITY_COLLECTION_NAME,
    KNOWLEDGE_COLLECTION_NAME,
    MANIFEST_PATH,
    PERSIST_DIR,
)

load_dotenv()

DEFAULT_MODEL = "gpt-5.4-mini"
DEFAULT_K = 6
DEFAULT_TOP_K = 5

# E5 토글: True = analyze+rewrite 통합 1회 호출, False = 기존 2회 호출
USE_UNIFIED_PREPROCESS = True

# P3.5.1: env-driven model selection
CLASSIFIER_MODEL = os.getenv("CLASSIFIER_MODEL", DEFAULT_MODEL)
GENERATOR_MODEL  = os.getenv("GENERATOR_MODEL",  DEFAULT_MODEL)


# ---------------------------
# Embedding model guard
# ---------------------------

_embedding_checked = False


def _check_embedding_model() -> None:
    """DB 생성 시 사용한 임베딩 모델과 현재 코드의 모델이 일치하는지 확인한다."""
    global _embedding_checked
    if _embedding_checked:
        return
    _embedding_checked = True

    if not MANIFEST_PATH.exists():
        import warnings
        warnings.warn(
            f"[RAG] {MANIFEST_PATH} 없음 — 임베딩 모델 일치 여부 미확인.\n"
            "ingest.py를 실행하면 매니페스트가 자동 생성됩니다.",
            stacklevel=3,
        )
        return

    with MANIFEST_PATH.open(encoding="utf-8") as f:
        manifest = json.load(f)

    stored = manifest.get("embedding_model")
    if stored != EMBEDDING_MODEL:
        raise RuntimeError(
            f"임베딩 모델 불일치 — 검색 결과가 완전히 잘못됩니다.\n"
            f"  DB에 저장된 모델 : {stored}\n"
            f"  현재 코드 모델   : {EMBEDDING_MODEL}\n"
            f"  해결: chroma_db/ 를 삭제하고 ingest.py를 다시 실행하세요."
        )


# ---------------------------
# LLM / Embeddings
# ---------------------------

@lru_cache(maxsize=8)
def get_llm(model: str = DEFAULT_MODEL, temperature: float = 0.0, max_tokens: int | None = None):
    kwargs = {"model": model, "temperature": temperature}
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    return ChatOpenAI(**kwargs)


@lru_cache(maxsize=1)
def get_embeddings():
    return OpenAIEmbeddings(model=EMBEDDING_MODEL)


@lru_cache(maxsize=2)
def get_vectorstore(collection_name: str):
    _check_embedding_model()
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

def preprocess_query(
    question: str,
    child_profile: dict | None,
    model: str = CLASSIFIER_MODEL,
) -> dict:
    """analyze + rewrite 통합 1회 호출 (E5). _fallback=True 이면 JSON 파싱 실패."""
    llm = get_llm(model=model, max_tokens=200)
    child_context = format_child_context(child_profile)
    prompt = QUERY_PREPROCESS_PROMPT.format(
        question=question,
        child_context=child_context,
    )
    response = llm.invoke(prompt)
    text = response.content.strip()

    try:
        parsed = json.loads(text)
        parsed.setdefault("_fallback", False)
    except json.JSONDecodeError:
        parsed = {
            "intent": "unknown",
            "topic": "general",
            "risk_level": "low",
            "needs_clarification": False,
            "rewritten_query": question,
            "_fallback": True,
        }

    return parsed


def analyze_query(question: str, model: str = DEFAULT_MODEL) -> dict:
    llm = get_llm(model=model, max_tokens=150)

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


def rewrite_query(
    question: str,
    child_profile: dict | None,
    analysis: dict,
    model: str = DEFAULT_MODEL,
) -> str:
    llm = get_llm(model=model, max_tokens=80)

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
    "경련", "숨을 못", "숨 못", "호흡이", "의식", "축 처", "축 처짐", "반응이 없다",
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
# hospital_locator는 facility 컬렉션, 나머지는 knowledge 컬렉션 사용
# ---------------------------

def get_retriever(intent: str, k: int = DEFAULT_K):
    if intent == "hospital_locator":
        vectorstore = get_vectorstore(FACILITY_COLLECTION_NAME)
        return vectorstore.as_retriever(search_kwargs={"k": k})

    vectorstore = get_vectorstore(KNOWLEDGE_COLLECTION_NAME)

    intent_filter_map = {
        "development": {"category": "development"},
        "daily_parenting": {"category": "daily_parenting"},
        "medical_basic": {"category": "medical_basic"},
        "vaccination": {"category": "vaccination"},
        "policy": {"category": "policy"},
    }

    search_filter = intent_filter_map.get(intent)
    if search_filter:
        return vectorstore.as_retriever(
            search_kwargs={"k": k, "filter": search_filter}
        )

    return vectorstore.as_retriever(search_kwargs={"k": k})


# ---------------------------
# Reranking
# ---------------------------

RERANK_WEIGHTS = {
    "category_match": 3,
    "topic_match": 2,
    "age_group_match": 2,
    "curated_source": 1,
}


def simple_rerank(
    docs,
    intent: str,
    topic: str | None = None,
    age_group: str | None = None,
    weights: dict | None = None,
):
    w = weights or RERANK_WEIGHTS
    rescored = []

    for doc in docs:
        score = 0
        meta = doc.metadata

        if meta.get("category") == intent:
            score += w.get("category_match", 3)
        if topic and meta.get("topic") == topic:
            score += w.get("topic_match", 2)
        if age_group and meta.get("age_group") == age_group:
            score += w.get("age_group_match", 2)
        if meta.get("source") == "curated":
            score += w.get("curated_source", 1)

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
    chat_history: list[dict] | None = None,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.0,
    k: int = DEFAULT_K,
    top_k: int = DEFAULT_TOP_K,
    rerank_weights: dict | None = None,
):
    timings = {}
    t0 = time.perf_counter()
    json_fallback = False

    if USE_UNIFIED_PREPROCESS:
        preprocessed = preprocess_query(question, child_profile)  # uses CLASSIFIER_MODEL
        json_fallback = preprocessed.get("_fallback", False)
        rewritten_query = preprocessed.get("rewritten_query", question)
        analysis = {
            k: preprocessed[k]
            for k in ("intent", "topic", "risk_level", "needs_clarification")
            if k in preprocessed
        }
        timings["preprocess_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    else:
        analysis = analyze_query(question, model=model)
        timings["analyze_query_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        t = time.perf_counter()
        rewritten_query = rewrite_query(question, child_profile, analysis, model=model)
        timings["rewrite_query_ms"] = round((time.perf_counter() - t) * 1000, 1)

    risk_level = normalize_risk_level(question, analysis)
    intent = analysis.get("intent", "unknown")

    t = time.perf_counter()
    retriever = get_retriever(intent, k=k)
    docs = retriever.invoke(rewritten_query)
    timings["retrieval_ms"] = round((time.perf_counter() - t) * 1000, 1)

    age_months = calculate_age_months(child_profile.get("birth_date")) if child_profile else None
    age_group = age_group_from_months(age_months)

    t = time.perf_counter()
    docs = simple_rerank(
        docs,
        intent=intent,
        topic=analysis.get("topic"),
        age_group=age_group,
        weights=rerank_weights,
    )
    top_docs = docs[:top_k]
    context = build_context(top_docs)
    timings["rerank_build_ms"] = round((time.perf_counter() - t) * 1000, 1)

    child_context = format_child_context(child_profile)
    logs_context = format_recent_logs(recent_logs)
    history_text = format_chat_history(chat_history or [])

    llm = get_llm(model=GENERATOR_MODEL, temperature=temperature, max_tokens=600)
    answer_prompt = get_answer_prompt(intent)

    prompt = answer_prompt.format(
        child_context=child_context,
        recent_logs=logs_context,
        chat_history=history_text,
        context=context,
        question=question,
    )

    t = time.perf_counter()
    response = llm.invoke(prompt)
    timings["generate_ms"] = round((time.perf_counter() - t) * 1000, 1)

    timings["total_ms"] = round((time.perf_counter() - t0) * 1000, 1)

    answer = apply_safety_prefix(response.content, risk_level)

    debug_info = {
        "intent": intent,
        "topic": analysis.get("topic"),
        "risk_level": risk_level,
        "needs_clarification": analysis.get("needs_clarification", False),
        "rewritten_query": rewritten_query,
        "retrieved_docs_count": len(docs),
        "top_k_used": top_k,
        "model": model,
        "preprocess_model": CLASSIFIER_MODEL,
        "generator_model": GENERATOR_MODEL,
        "json_fallback": json_fallback,
        "timings": timings,
    }

    return answer, top_docs, debug_info
