import streamlit as st
import requests
import json
from datetime import date # date 객체를 사용하기 위해 import

# 백엔드 API의 기본 URL
BACKEND_URL = "http://localhost:8000"

st.set_page_config(page_title="육아 챗봇", page_icon="👶", layout="wide")

# 세션 상태 초기화
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state: # 이메일 저장
    st.session_state.username = ""
if "nickname" not in st.session_state:
    st.session_state.nickname = ""
if "access_token" not in st.session_state:
    st.session_state.access_token = None
if "refresh_token" not in st.session_state:
    st.session_state.refresh_token = None
if "show_signup" not in st.session_state:
    st.session_state.show_signup = False
if "show_child_info_page" not in st.session_state:
    st.session_state.show_child_info_page = False
if "messages" not in st.session_state:
    st.session_state.messages = []
if "chat_session_id" not in st.session_state:
    st.session_state.chat_session_id = None
if "selected_child_id" not in st.session_state: # 선택된 아이 ID (None으로 초기화)
    st.session_state.selected_child_id = None
if "children_list" not in st.session_state: # 사용자의 아이 목록
    st.session_state.children_list = []
if "editing_child_id" not in st.session_state: # 수정 중인 아이 ID
    st.session_state.editing_child_id = None


# --- API 호출 헬퍼 함수 ---
def api_call(method, path, headers=None, json_data=None):
    try:
        response = requests.request(
            method,
            f"{BACKEND_URL}{path}",
            headers=headers,
            json=json_data
        )
        response.raise_for_status() # HTTP 오류 발생 시 예외 발생
        return response.json()
    except requests.exceptions.ConnectionError:
        st.error("백엔드 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인하세요.")
        return None
    except requests.exceptions.HTTPError as e:
        st.error(f"API 오류: {e.response.status_code} - {e.response.json().get('detail', '알 수 없는 오류')}")
        return None
    except Exception as e:
        st.error(f"오류 발생: {e}")
        return None

def get_auth_headers():
    if st.session_state.access_token:
        return {"Authorization": f"Bearer {st.session_state.access_token}"}
    return {}

# --- 인증 관련 함수 ---
def login_form():
    st.title("로그인")
    with st.form("login_form"):
        email = st.text_input("이메일")
        password = st.text_input("비밀번호", type="password")
        login_button = st.form_submit_button("로그인")

        if login_button:
            response_data = api_call("POST", "/auth/login", json_data={"email": email, "password": password})
            if response_data:
                st.session_state.access_token = response_data["access_token"]
                st.session_state.refresh_token = response_data["refresh_token"]

                user_data = api_call("GET", "/auth/me", headers=get_auth_headers())
                if user_data:
                    st.session_state.logged_in = True
                    st.session_state.username = user_data["email"]
                    st.session_state.nickname = user_data["nickname"]
                    st.success(f"로그인 성공! 환영합니다, {st.session_state.nickname}님!")
                    st.rerun()
                else:
                    st.error("사용자 정보를 가져오는 데 실패했습니다.")

    st.write("---")
    if st.button("회원가입"):
        st.session_state.show_signup = True
        st.rerun()

def signup_form():
    st.title("회원가입")
    with st.form("signup_form"):
        email = st.text_input("이메일 (아이디로 사용)")
        password = st.text_input("비밀번호", type="password")
        confirm_password = st.text_input("비밀번호 확인", type="password")
        nickname = st.text_input("닉네임")
        signup_button = st.form_submit_button("회원가입")

        if signup_button:
            if not email or not password or not confirm_password or not nickname:
                st.error("모든 필드를 입력해주세요.")
            elif password != confirm_password:
                st.error("비밀번호가 일치하지 않습니다.")
            else:
                response_data = api_call(
                    "POST",
                    "/auth/register",
                    json_data={"email": email, "password": password, "nickname": nickname}
                )
                if response_data:
                    st.success("회원가입 성공! 로그인 페이지로 이동합니다.")
                    st.session_state.show_signup = False
                    st.rerun()
    st.write("---")
    if st.button("로그인 페이지로 돌아가기"):
        st.session_state.show_signup = False
        st.rerun()

# --- 아이 정보 관리 함수 ---
def load_children():
    children_data = api_call("GET", "/children/", headers=get_auth_headers())
    if children_data:
        st.session_state.children_list = children_data
    else:
        st.session_state.children_list = []

def display_child_list():
    st.subheader("등록된 아이 목록")
    if not st.session_state.children_list:
        st.info("등록된 아이가 없습니다. 새로 추가해주세요.")
        return

    for child in st.session_state.children_list:
        col1, col2, col3, col4 = st.columns([0.4, 0.2, 0.2, 0.2])
        with col1:
            st.write(f"**{child['name']}** ({child['gender'] if child['gender'] else '성별미상'}, {child['birth_date']})")
        with col2:
            if st.button("수정", key=f"edit_child_{child['id']}"):
                st.session_state.editing_child_id = child['id']
                st.rerun()
        with col3:
            if st.button("삭제", key=f"delete_child_{child['id']}"):
                if st.warning(f"정말로 {child['name']} 아이 정보를 삭제하시겠습니까?"):
                    response_data = api_call("DELETE", f"/children/{child['id']}", headers=get_auth_headers())
                    if response_data:
                        st.success(f"{child['name']} 아이 정보가 삭제되었습니다.")
                        load_children() # 목록 새로고침
                        if st.session_state.selected_child_id == child['id']:
                            st.session_state.selected_child_id = None # 선택된 아이 초기화
                        st.rerun()
        with col4:
            if st.session_state.selected_child_id == child['id']:
                st.success("선택됨")
            else:
                if st.button("선택", key=f"select_child_{child['id']}"):
                    st.session_state.selected_child_id = child['id']
                    st.success(f"{child['name']} (을)를 선택했습니다.")
                    st.rerun()


def add_child_form():
    st.subheader("새 아이 정보 등록")
    with st.form("add_child_form"):
        name = st.text_input("이름")
        birth_date = st.date_input("생년월일", value=date(2023, 1, 1))
        gender = st.selectbox("성별", ["미입력", "남", "여"], index=0)
        allergies_input = st.text_input("알레르기 (쉼표로 구분)")
        conditions_input = st.text_input("기저질환 (쉼표로 구분)")
        notes = st.text_area("특이사항")
        
        submit_button = st.form_submit_button("등록")

        if submit_button:
            allergies = [a.strip() for a in allergies_input.split(',') if a.strip()]
            conditions = [c.strip() for c in conditions_input.split(',') if c.strip()]
            
            child_data = {
                "name": name,
                "birth_date": birth_date.isoformat(),
                "gender": gender if gender != "미입력" else None,
                "allergies": allergies,
                "conditions": conditions,
                "notes": notes,
            }
            response_data = api_call("POST", "/children/", headers=get_auth_headers(), json_data=child_data)
            if response_data:
                st.success(f"{name} 아이 정보가 성공적으로 등록되었습니다.")
                st.session_state.editing_child_id = None # 등록 후 폼 초기화
                load_children() # 목록 새로고침
                st.rerun()

def edit_child_form(child_id):
    st.subheader(f"아이 정보 수정 (ID: {child_id})")
    
    current_child = None
    for child in st.session_state.children_list:
        if child['id'] == child_id:
            current_child = child
            break

    if not current_child:
        st.error("수정할 아이 정보를 찾을 수 없습니다.")
        st.session_state.editing_child_id = None
        return

    with st.form(f"edit_child_form_{child_id}"):
        name = st.text_input("이름", value=current_child.get('name', ''))
        birth_date_val = date.fromisoformat(current_child['birth_date']) if current_child.get('birth_date') else date(2023,1,1)
        birth_date = st.date_input("생년월일", value=birth_date_val)
        gender_options = ["미입력", "남", "여"]
        current_gender_index = gender_options.index(current_child.get('gender') or "미입력")
        gender = st.selectbox("성별", gender_options, index=current_gender_index)
        allergies_input = st.text_input("알레르기 (쉼표로 구분)", value=", ".join(current_child.get('allergies', [])))
        conditions_input = st.text_input("기저질환 (쉼표로 구분)", value=", ".join(current_child.get('conditions', [])))
        notes = st.text_area("특이사항", value=current_child.get('notes', ''))
        
        col1, col2 = st.columns(2)
        with col1:
            submit_button = st.form_submit_button("수정 완료")
        with col2:
            cancel_button = st.form_submit_button("취소")

        if submit_button:
            allergies = [a.strip() for a in allergies_input.split(',') if a.strip()]
            conditions = [c.strip() for c in conditions_input.split(',') if c.strip()]

            updated_data = {
                "name": name,
                "birth_date": birth_date.isoformat(),
                "gender": gender if gender != "미입력" else None,
                "allergies": allergies,
                "conditions": conditions,
                "notes": notes,
            }
            response_data = api_call("PATCH", f"/children/{child_id}", headers=get_auth_headers(), json_data=updated_data)
            if response_data:
                st.success(f"{name} 아이 정보가 성공적으로 수정되었습니다.")
                st.session_state.editing_child_id = None
                load_children() # 목록 새로고침
                st.rerun()
        
        if cancel_button:
            st.session_state.editing_child_id = None
            st.rerun()


def child_info_page():
    st.title("아이 정보 관리")
    st.write("이곳에서 아이의 정보를 추가, 수정, 삭제할 수 있습니다.")

    load_children() # 페이지 로드 시 아이 목록 로드

    if st.session_state.editing_child_id:
        edit_child_form(st.session_state.editing_child_id)
    else:
        add_child_form()
    
    st.write("---")
    display_child_list()

    if st.button("대시보드로 돌아가기"):
        st.session_state.show_child_info_page = False
        st.rerun()


# --- 메인 앱 로직 ---
if not st.session_state.logged_in:
    if st.session_state.show_signup:
        signup_form()
    else:
        login_form()
else:
    # 아이 정보 페이지가 활성화된 경우
    if st.session_state.show_child_info_page:
        child_info_page()
    else:
        st.set_page_config(page_title="육아 챗봇 - 대시보드", page_icon="👶", layout="wide")

        st.sidebar.title(f"환영합니다, {st.session_state.nickname}님!")
        
        # 아이 목록 로드 및 선택 UI
        load_children()
        if st.session_state.children_list:
            child_names = {child['name']: child['id'] for child in st.session_state.children_list}
            selected_child_name = st.sidebar.selectbox(
                "대화할 아이를 선택하세요",
                list(child_names.keys()),
                index=0 if st.session_state.selected_child_id is None else 
                      list(child_names.values()).index(st.session_state.selected_child_id) if st.session_state.selected_child_id in child_names.values() else 0
            )
            st.session_state.selected_child_id = child_names[selected_child_name]
        else:
            st.sidebar.warning("등록된 아이가 없습니다. 아이 정보를 먼저 등록해주세요.")
            st.session_state.selected_child_id = None

        if st.sidebar.button("로그아웃"):
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.session_state.nickname = ""
            st.session_state.access_token = None
            st.session_state.refresh_token = None
            st.session_state.show_child_info_page = False
            st.session_state.messages = []
            st.session_state.chat_session_id = None
            st.session_state.selected_child_id = None
            st.session_state.children_list = []
            st.rerun()
        if st.sidebar.button("아이 정보 관리"):
            st.session_state.show_child_info_page = True
            st.rerun()
        
        st.title("육아 챗봇 대시보드")
        st.write("이곳에 다양한 육아 챗봇 기능들이 제공될 예정입니다.")

        # --- 채팅 UI 섹션 시작 ---
        st.subheader("챗봇과 대화하기")

        if st.session_state.selected_child_id is None:
            st.info("먼저 대화할 아이를 선택하거나 등록해주세요.")
        else:
            # 채팅 메시지 표시
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

            # 사용자 입력 처리
            if prompt := st.chat_input("메시지를 입력하세요..."):
                st.session_state.messages.append({"role": "user", "content": prompt})
                with st.chat_message("user"):
                    st.markdown(prompt)

                headers = get_auth_headers()
                payload = {
                    "message": prompt,
                    "child_id": st.session_state.selected_child_id,
                    "session_id": st.session_state.chat_session_id,
                }
                response_data = api_call("POST", "/chat/", headers=headers, json_data=payload)
                if response_data:
                    st.session_state.chat_session_id = response_data["session_id"]
                    
                    ai_message = response_data["message"]
                    if response_data["is_emergency"]:
                        ai_message = "🚨 긴급 상황 가능성 🚨
" + ai_message
                    if response_data["needs_more_context"]:
                        ai_message += "

(AI가 추가 정보가 필요하다고 합니다. 이어서 질문해주세요.)"

                    st.session_state.messages.append({"role": "assistant", "content": ai_message})
                    with st.chat_message("assistant"):
                        st.markdown(ai_message)
                st.rerun()

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
            cols = st.columns(3)
            for i, q in enumerate(example_questions):
                with cols[i % 3]:
                    if st.button(q, key=f"example_q_{i}"):
                        st.session_state.messages.append({"role": "user", "content": q})
                        with st.chat_message("user"):
                            st.markdown(q)

                        headers = get_auth_headers()
                        payload = {
                            "message": q,
                            "child_id": st.session_state.selected_child_id,
                            "session_id": st.session_state.chat_session_id,
                        }
                        response_data = api_call("POST", "/chat/", headers=headers, json_data=payload)
                        if response_data:
                            st.session_state.chat_session_id = response_data["session_id"]
                            
                            ai_message = response_data["message"]
                            if response_data["is_emergency"]:
                                ai_message = "🚨 긴급 상황 가능성 🚨
" + ai_message
                            if response_data["needs_more_context"]:
                                ai_message += "

(AI가 추가 정보가 필요하다고 합니다. 이어서 질문해주세요.)"
                            
                            st.session_state.messages.append({"role": "assistant", "content": ai_message})
                            with st.chat_message("assistant"):
                                st.markdown(ai_message)
                        st.rerun()

        st.subheader("주요 기능")
        st.write("- 아이 성장 기록 (백엔드 연동 예정)")
        st.write("- 맞춤형 정보 제공 (백엔드 연동 예정)")

        st.subheader("최신 업데이트")
        st.info("새로운 기능들이 곧 추가될 예정입니다. 기대해주세요!")
