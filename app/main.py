# app/main.py

import streamlit as st
from rag import answer_question

st.set_page_config(page_title="RAG Chatbot Demo", page_icon="🤖")
st.title("RAG Chatbot Demo")

question = st.text_input("질문을 입력하세요")

if st.button("질문하기") and question:
    with st.spinner("답변 생성 중..."):
        answer, docs, debug_info = answer_question(question)

    st.subheader("답변")
    st.write(answer)

    with st.expander("분석 결과"):
        st.json(debug_info)

    with st.expander("참고한 문서 조각"):
        for i, doc in enumerate(docs, start=1):
            source = doc.metadata.get("source", "unknown")
            page = doc.metadata.get("page", "N/A")
            category = doc.metadata.get("category", "N/A")
            topic = doc.metadata.get("topic", "N/A")

            st.markdown(
                f"**{i}. source:** {source} / page: {page} / category: {category} / topic: {topic}"
            )
            st.write(doc.page_content[:1000])
            st.divider()