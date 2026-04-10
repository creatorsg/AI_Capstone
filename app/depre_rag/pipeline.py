import json
from dotenv import load_dotenv

from langchain_chroma import Chroma
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from prompts import QUERY_ANALYZER_PROMPT, ANSWER_PROMPT

load_dotenv()

PERSIST_DIR = "chroma_db"
COLLECTION_NAME = "parenting_docs"


def get_llm(model: str = "gpt-4o-mini"):
    return ChatOpenAI(model=model, temperature=0)


def get_embeddings():
    return OpenAIEmbeddings()


def get_vectorstore():
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=get_embeddings(),
        persist_directory=PERSIST_DIR,
    )


# -----------------------------
# 1. Query Analyzer
# -----------------------------
def analyze_query(question: str) -> dict:
    """
    사용자 질문을 intent / topic / risk_level / needs_clarification 으로 분석한다.
    실패 시 fallback 반환.
    """
    llm = get_llm()

    prompt = QUERY_ANALYZER_PROMPT.format(question=question)
    response = llm.invoke(prompt)
    raw_text = response.content.strip()

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        parsed = {
            "intent": "unknown",
            "topic": "general",
            "risk_level": "low",
            "needs_clarification": False,
        }

    # 키 누락 방지
    parsed.setdefault("intent", "unknown")
    parsed.setdefault("topic", "general")
    parsed.setdefault("risk_level", "low")
    parsed.setdefault("needs_clarification", False)

    return parsed


# -----------------------------
# 2. Intent-based Retriever Routing
# -----------------------------
def get_retriever_by_intent(intent: str):
    """
    intent에 따라 다른 retriever를 반환한다.
    metadata filter가 들어갈 수 있도록 구조를 먼저 잡아둔다.
    """
    vectorstore = get_vectorstore()

    if intent == "development":
        return vectorstore.as_retriever(
            search_kwargs={
                "k": 4,
                "filter": {"category": "development"},
            }
        )

    elif intent == "daily_parenting":
        return vectorstore.as_retriever(
            search_kwargs={
                "k": 4,
                "filter": {"category": "daily_parenting"},
            }
        )

    elif intent == "medical_basic":
        return vectorstore.as_retriever(
            search_kwargs={
                "k": 4,
                "filter": {"category": "medical_basic"},
            }
        )

    elif intent == "vaccination":
        return vectorstore.as_retriever(
            search_kwargs={
                "k": 4,
                "filter": {"category": "vaccination"},
            }
        )

    elif intent == "policy":
        return vectorstore.as_retriever(
            search_kwargs={
                "k": 4,
                "filter": {"category": "policy"},
            }
        )

    # hospital_locator 는 나중에 지도 API 쪽으로 보낼 것이므로
    # 지금은 fallback retriever를 태운다
    elif intent == "hospital_locator":
        return vectorstore.as_retriever(
            search_kwargs={"k": 4}
        )

    else:
        return vectorstore.as_retriever(
            search_kwargs={"k": 4}
        )


# -----------------------------
# 3. Optional: Clarification message
# -----------------------------
def build_clarification_message(analysis: dict) -> str | None:
    """
    아주 모호한 질문이면, 바로 답 대신 추가 확인 질문을 줄 수 있다.
    지금은 간단한 버전만 넣는다.
    """
    if not analysis.get("needs_clarification", False):
        return None

    intent = analysis.get("intent", "unknown")
    topic = analysis.get("topic", "general")

    if intent == "medical_basic" and topic == "fever":
        return (
            "조금 더 정확히 알려주시면 도움이 돼요.\n"
            "- 몇 도인지\n"
            "- 언제부터 열이 났는지\n"
            "- 기침/콧물/구토 같은 다른 증상이 있는지\n"
            "- 아이가 축 처져 보이는지"
        )

    if intent == "daily_parenting" and topic in ["sleep", "food", "crying", "general"]:
        return (
            "조금 더 상황을 알려주시면 더 정확히 안내할 수 있어요.\n"
            "- 아이 나이\n"
            "- 언제부터 그런지\n"
            "- 최근 수면/식사 변화가 있었는지"
        )

    return (
        "질문이 조금 짧아서 맥락이 부족해요.\n"
        "아이 나이와 현재 상황을 한두 줄만 더 알려주시면 더 정확히 도와드릴 수 있어요."
    )


# -----------------------------
# 4. Main QA
# -----------------------------
def answer_question(question: str):
    analysis = analyze_query(question)

    clarification = build_clarification_message(analysis)
    if clarification:
        # 지금 단계에서는 clarification만 먼저 반환
        return clarification, [], {"analysis": analysis}

    retriever = get_retriever_by_intent(analysis["intent"])
    docs = retriever.invoke(question)

    context = "\n\n".join([doc.page_content for doc in docs])

    llm = get_llm()
    prompt = ANSWER_PROMPT.format(context=context, question=question)
    response = llm.invoke(prompt)

    debug_info = {
        "analysis": analysis,
        "num_docs": len(docs),
    }

    return response.content, docs, debug_info