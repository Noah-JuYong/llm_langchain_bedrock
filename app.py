import streamlit as st
import requests as req

API_URL = "http://127.0.0.1:8000/chat"

st.set_page_config(page_title="식사 메뉴 해결사")
st.title("AI 식사 메뉴 해결사 - KING")
st.caption(
    "점심/저녁 등 시점, 날씨, 기분, 단체여부, 예산, MBTI 등을 알려주시면 메뉴를 추천해드리겠습니다."
)

# 대화 내용을 기억하는 공간 -> st.session_state 관리
#
if "messages" not in st.session_state:  # 1회만 수행
    # 기본 가이드
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "안녕하세요!. 오늘 식사는 어떤 메뉴가 땡기나요? 현재 상황, 기분 등을 알려주세요.",
        }
    ]

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 입력창 필요 -> 음성, 텍스트, ...
if prompt := st.chat_input("현재 상황을 자세하게 입력하세요."):
    st.session_state.messages.append({"role": "user", "conetnet": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        msg_holder = st.empty()
        msg_holder.markdown("심각한 고민중 ")

    try:
        res = req.post(API_URL, json={"query": prompt})
        if res.status_code == 200:  # 응답 성공
            result = res.json().get("response", "일시적 장애입니다.")
        else:
            result = f"서버측 오류 {res.status_code}"
    except Exception as e:
        print(e)
        result = f"오류 {e}"

    msg_holder.markdown(result)

    st.session_state.messages.append({"role": "assistant", "content": result})
