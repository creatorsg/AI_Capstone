# app/main.py

import streamlit as st
from rag import answer_question

st.set_page_config(page_title="육아 RAG 챗봇", page_icon="🧸")
st.title("초보 부모를 위한 육아 RAG 챗봇")

st.subheader("아이 프로필")
child_name = st.text_input("아이 이름", value="민지")
birth_date = st.text_input("생년월일 (YYYY-MM-DD)", value="2024-03-01")
sex = st.selectbox("성별", ["F", "M"])
allergies = st.text_input("알레르기 (쉼표로 구분)", value="")
conditions = st.text_input("기저질환 (쉼표로 구분)", value="")
notes = st.text_area("메모", value="밤에 자주 깨는 편")

child_profile = {
    "name": child_name,
    "birth_date": birth_date,
    "sex": sex,
    "allergies": [x.strip() for x in allergies.split(",") if x.strip()],
    "conditions": [x.strip() for x in conditions.split(",") if x.strip()],
    "notes": notes,
}

st.subheader("최근 기록")
sleep_log = st.text_area("최근 수면 기록", value="어제 밤 3번 깸\n낮잠 1시간")
food_log = st.text_area("최근 식사 기록", value="오늘 아침 식사량 적음")
fever_log = st.text_area("최근 발열 기록", value="오늘 오전 38.2도")

recent_logs = {
    "sleep": [line.strip() for line in sleep_log.split("\n") if line.strip()],
    "food": [line.strip() for line in food_log.split("\n") if line.strip()],
    "fever": [line.strip() for line in fever_log.split("\n") if line.strip()],
}

st.subheader("질문")
question = st.text_input("질문을 입력하세요", placeholder="예: 열이 나요 / 24개월인데 말을 잘 안 해요")

if st.button("질문하기") and question:
    with st.spinner("답변 생성 중..."):
        answer, docs, debug_info = answer_question(
            question=question,
            child_profile=child_profile,
            recent_logs=recent_logs,
        )

    st.subheader("답변")
    st.write(answer)

    with st.expander("분석 정보 보기"):
        st.json(debug_info)

    with st.expander("참고한 문서 조각"):
        for i, doc in enumerate(docs, start=1):
            st.markdown(f"**{i}. title:** {doc.metadata.get('title', 'N/A')}")
            st.markdown(
                f"- source: {doc.metadata.get('source', 'unknown')}\n"
                f"- category: {doc.metadata.get('category', 'N/A')}\n"
                f"- topic: {doc.metadata.get('topic', 'N/A')}\n"
                f"- age_group: {doc.metadata.get('age_group', 'N/A')}"
            )
            st.write(doc.page_content[:1000])
            st.divider()