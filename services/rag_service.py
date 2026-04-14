"""RAG 서비스 인터페이스 (Vector DB 검색, fallback 포함)"""

from typing import Optional


# TODO: Vector DB 모듈 완성 후 아래 import 활성화
# from langchain_community.vectorstores import Chroma
# from langchain_openai import OpenAIEmbeddings
# from langchain.chains import RetrievalQA
# from langchain_openai import ChatOpenAI


def retrieve_relevant_docs(
    query: str,
    child_age_months: Optional[int] = None,
    top_k: int = 3
) -> list[str]:
    """
    Vector DB에서 관련 문서를 검색합니다.

    Args:
        query: 검색 쿼리 (사용자 질문 + 맥락)
        child_age_months: 아이 나이 (월령) - 필터링용
        top_k: 반환할 문서 수

    Returns:
        관련 문서 텍스트 리스트

    현재: fallback (빈 리스트) 반환
    임주형님 모듈 완성 후: 실제 Chroma 검색 결과 반환
    """

    # TODO: Vector DB 연동 (Chroma + LangChain)
    # vectorstore = Chroma(
    #     persist_directory="./chroma_db",
    #     embedding_function=OpenAIEmbeddings()
    # )
    # results = vectorstore.similarity_search(query, k=top_k)
    # return [doc.page_content for doc in results]

    # Fallback: 빈 리스트 반환 (RAG 없이 AI만으로 동작)
    return []


def build_rag_prompt(
    question: str,
    context: dict,
    retrieved_docs: list[str]
) -> str:
    """
    검색된 문서를 포함한 최종 프롬프트를 생성합니다.

    Args:
        question: 사용자 원본 질문
        context: 역질문으로 수집된 맥락
        retrieved_docs: Vector DB에서 검색된 관련 문서들

    Returns:
        GPT에 전달할 최종 프롬프트
    """
    context_str = "\n".join([f"- {k}: {v}" for k, v in context.items()])

    if retrieved_docs:
        docs_str = "\n\n".join([f"[참고 문서 {i+1}]\n{doc}" for i, doc in enumerate(retrieved_docs)])
        return f"""사용자 질문: {question}

수집된 맥락:
{context_str}

관련 육아 정보:
{docs_str}

위 정보를 바탕으로 답변해주세요."""
    else:
        # RAG 문서 없을 때
        return f"""사용자 질문: {question}

수집된 맥락:
{context_str}"""
