import streamlit as st
import json
from pathlib import Path

# 파일 기반 사용자 데이터 저장 경로
USERS_FILE = Path("C:/Users/kbc02/OneDrive/바탕 화면/인공지능 캡스톤/AI_Capstone-byeongchan/users.json")

def load_users():
    """사용자 데이터를 파일에서 로드합니다."""
    if USERS_FILE.exists():
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_users(users_data):
    """사용자 데이터를 파일에 저장합니다."""
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users_data, f, ensure_ascii=False, indent=4)

st.set_page_config(page_title="육아 챗봇", page_icon="👶")

# 세션 상태 초기화
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "nickname" not in st.session_state: # 닉네임 세션 상태 추가
    st.session_state.nickname = ""
if "show_signup" not in st.session_state:
    st.session_state.show_signup = False # 로그인/회원가입 폼 전환용
if "show_child_info_page" not in st.session_state: # 아이 정보 페이지 전환용
    st.session_state.show_child_info_page = False

# 모의 사용자 데이터 (실제 백엔드에서는 DB에서 관리)
# 구조: {"아이디": {"password": "비밀번호", "nickname": "닉네임"}}
if "mock_users" not in st.session_state:
    st.session_state.mock_users = load_users()
    # 파일이 비어 있으면 기본 테스트 사용자 추가
    if not st.session_state.mock_users:
        st.session_state.mock_users["testuser"] = {"password": "testpass", "nickname": "테스트맘"}
        save_users(st.session_state.mock_users)

def login_form():
    st.title("로그인")
    with st.form("login_form"):
        username = st.text_input("아이디")
        password = st.text_input("비밀번호", type="password")
        login_button = st.form_submit_button("로그인")

        if login_button:
            st.session_state.mock_users = load_users() # 로그인 시 최신 사용자 데이터를 다시 로드하여 확인
            user_data = st.session_state.mock_users.get(username)
            if user_data and user_data["password"] == password:
                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.nickname = user_data["nickname"]
                st.success(f"로그인 성공! 환영합니다, {st.session_state.nickname}님!")
                st.rerun()
            else:
                st.error("잘못된 아이디 또는 비밀번호입니다.")
    st.write("---")
    if st.button("회원가입"):
        st.session_state.show_signup = True
        st.rerun()

def signup_form():
    st.title("회원가입")
    with st.form("signup_form"):
        new_username = st.text_input("새 아이디")
        new_password = st.text_input("새 비밀번호", type="password")
        confirm_password = st.text_input("비밀번호 확인", type="password")
        new_nickname = st.text_input("닉네임")
        signup_button = st.form_submit_button("회원가입")

        if signup_button:
            users = load_users() # 회원가입 시 최신 사용자 데이터를 다시 로드하여 확인
            if not new_username or not new_password or not confirm_password or not new_nickname:
                st.error("모든 필드를 입력해주세요.")
            elif new_password != confirm_password:
                st.error("비밀번호가 일치하지 않습니다.")
            elif new_username in users: # 파일에 저장된 사용자 데이터와 중복 확인
                st.error("이미 존재하는 아이디입니다.")
            else:
                users[new_username] = {"password": new_password, "nickname": new_nickname}
                save_users(users) # 새 사용자 데이터를 파일에 저장
                st.session_state.mock_users = users # 세션 상태도 업데이트
                st.success("회원가입 성공! 로그인 페이지로 이동합니다.")
                st.session_state.show_signup = False
                st.rerun()
    st.write("---")
    if st.button("로그인 페이지로 돌아가기"):
        st.session_state.show_signup = False
        st.rerun()

def child_info_page():
    st.title("아이 정보 관리")
    st.write("이곳에서 아이의 정보를 추가하고 수정할 수 있습니다.")
    st.info("이 페이지는 현재 기능 구현 전 단계입니다. (예: 아이 이름, 생년월일, 성별 등 입력 필드 추가 예정)")

    if st.button("대시보드로 돌아가기"):
        st.session_state.show_child_info_page = False
        st.rerun()


if not st.session_state.logged_in:
    if st.session_state.show_signup:
        signup_form()
    else:
        login_form()
else:
    if st.session_state.show_child_info_page:
        child_info_page()
    else:
        st.set_page_config(page_title="육아 챗봇 - 대시보드", page_icon="👶")

        st.sidebar.title(f"환영합니다, {st.session_state.nickname}님!") # 닉네임으로 환영 메시지 변경
        if st.sidebar.button("로그아웃"):
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.session_state.nickname = "" # 닉네임도 초기화
            st.session_state.show_child_info_page = False # 로그아웃 시 페이지 초기화
            st.rerun()
        if st.sidebar.button("아이 정보 관리"): # 아이 정보 관리 버튼 추가
            st.session_state.show_child_info_page = True
            st.rerun()

        st.title("육아 챗봇 대시보드")
        st.write("이곳에 다양한 육아 챗봇 기능들이 제공될 예정입니다.")

        # --- 채팅 UI 섹션 시작 ---
        st.subheader("챗봇과 대화하기")

        # 채팅 메시지 기록을 위한 세션 상태 초기화
        if "messages" not in st.session_state:
            st.session_state.messages = []

        # 예시 질문 목록
        example_questions = [
            "생후 6개월 아기 발달이 궁금해요",
            "아이가 열이 날 때 어떻게 해야 하나요?",
            "돌 전 아기에게 좋은 유아식 추천해주세요",
            "예방접종 일정 알려주세요",
            "아이돌봄 서비스 신청 방법이 궁금해요"
        ]

        # 예시 질문 버튼 표시
        st.write("궁금한 점이 있다면 다음 질문을 이용해보세요:")
        cols = st.columns(3) # 3개씩 컬럼 분할 (예시 질문이 5개이므로)
        for i, q in enumerate(example_questions):
            with cols[i % 3]:
                if st.button(q, key=f"example_q_{i}"):
                    # 예시 질문을 클릭하면 메시지로 처리
                    st.session_state.messages.append({"role": "user", "content": q})
                    with st.chat_message("user"):
                        st.markdown(q)

                    # 챗봇 응답 (모의 응답)
                    mock_response = "이 질문에 대한 답변 기능은 아직 구현되지 않았습니다. 곧 만나보실 수 있습니다! 😊"
                    st.session_state.messages.append({"role": "assistant", "content": mock_response})
                    with st.chat_message("assistant"):
                        st.markdown(mock_response)
                    st.rerun() # 메시지 업데이트를 위해 재실행

        # 채팅 메시지 표시
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        # 사용자 입력 처리
        if prompt := st.chat_input("메시지를 입력하세요..."):
            # 사용자 메시지를 채팅 기록에 추가
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            # 챗봇 응답 (모의 응답)
            # 실제 구현에서는 백엔드 API나 LLM을 호출하여 응답을 받습니다.
            mock_response = "아직은 구현되지 않은 기능입니다. 곧 만나보실 수 있습니다! 😊"
            st.session_state.messages.append({"role": "assistant", "content": mock_response})
            with st.chat_message("assistant"):
                st.markdown(mock_response)
        # --- 채팅 UI 섹션 끝 ---

        st.subheader("주요 기능")
        st.write("- 아이 성장 기록")
        st.write("- 맞춤형 정보 제공")

        st.subheader("최신 업데이트")
        st.info("새로운 기능들이 곧 추가될 예정입니다. 기대해주세요!")
