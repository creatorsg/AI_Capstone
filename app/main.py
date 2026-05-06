# app/main.py

import streamlit as st
from rag import answer_question

st.set_page_config(page_title="육아 RAG 챗봇", page_icon="🧸", layout="wide")

# ---------------------------
# Sidebar: 아이 프로필 + 최근 기록
# ---------------------------

with st.sidebar:
    st.header("아이 프로필")
    child_name = st.text_input("아이 이름", value="민지")
    birth_date = st.text_input("생년월일 (YYYY-MM-DD)", value="2024-03-01")
    sex = st.selectbox("성별", ["F", "M"])
    allergies = st.text_input("알레르기 (쉼표로 구분)", value="")
    conditions = st.text_input("기저질환 (쉼표로 구분)", value="")
    notes = st.text_area("메모", value="밤에 자주 깨는 편")

    st.divider()

    st.header("최근 기록")
    sleep_log = st.text_area("수면 기록", value="어제 밤 3번 깸\n낮잠 1시간")
    food_log = st.text_area("식사 기록", value="오늘 아침 식사량 적음")
    fever_log = st.text_area("발열 기록", value="오늘 오전 38.2도")

    st.divider()

    if st.button("대화 초기화", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

child_profile = {
    "name": child_name,
    "birth_date": birth_date,
    "sex": sex,
    "allergies": [x.strip() for x in allergies.split(",") if x.strip()],
    "conditions": [x.strip() for x in conditions.split(",") if x.strip()],
    "notes": notes,
}

recent_logs = {
    "sleep": [line.strip() for line in sleep_log.split("\n") if line.strip()],
    "food": [line.strip() for line in food_log.split("\n") if line.strip()],
    "fever": [line.strip() for line in fever_log.split("\n") if line.strip()],
}

# ---------------------------
# Main: 채팅 인터페이스
# ---------------------------

st.title("초보 부모를 위한 육아 RAG 챗봇")
st.caption("아이 정보와 최근 기록은 왼쪽 사이드바에서 입력하세요.")

if "messages" not in st.session_state:
    st.session_state.messages = []

# 이전 대화 렌더링
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if msg.get("debug_info"):
            with st.expander("분석 정보"):
                st.json(msg["debug_info"])
        if msg.get("docs"):
            with st.expander("참고 문서"):
                for i, doc in enumerate(msg["docs"], start=1):
                    st.markdown(f"**{i}. {doc['title']}**")
                    st.caption(
                        f"category: {doc['category']} | "
                        f"topic: {doc['topic']} | "
                        f"source: {doc['source']}"
                    )
                    st.write(doc["content"])
                    st.divider()

# 입력창
if question := st.chat_input("질문을 입력하세요 (예: 열이 나요 / 24개월인데 말을 잘 안 해요)"):
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.write(question)

    # chat_history: 현재 질문 직전까지의 대화
    history_for_rag = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.messages[:-1]
    ]

    with st.chat_message("assistant"):
        with st.spinner("답변 생성 중..."):
            answer, docs, debug_info = answer_question(
                question=question,
                child_profile=child_profile,
                recent_logs=recent_logs,
                chat_history=history_for_rag,
            )

        st.write(answer)

        with st.expander("분석 정보"):
            st.json(debug_info)

        doc_summaries = [
            {
                "title": doc.metadata.get("title", "N/A"),
                "category": doc.metadata.get("category", "N/A"),
                "topic": doc.metadata.get("topic", "N/A"),
                "source": doc.metadata.get("source", "N/A"),
                "content": doc.page_content[:800],
            }
            for doc in docs
        ]

        with st.expander("참고 문서"):
            for i, doc in enumerate(doc_summaries, start=1):
                st.markdown(f"**{i}. {doc['title']}**")
                st.caption(
                    f"category: {doc['category']} | "
                    f"topic: {doc['topic']} | "
                    f"source: {doc['source']}"
                )
                st.write(doc["content"])
                st.divider()

    st.session_state.messages.append({
        "role": "assistant",
        "content": answer,
        "debug_info": debug_info,
        "docs": doc_summaries,
    })
