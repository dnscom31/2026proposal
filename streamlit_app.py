# streamlit_app.py
# 목적: "기본 정보/색상(CSS 변수)" + "레포 이미지(attachment_pages) 자동 임베딩" + "HTML 내보내기"
# 주의: 이미지 교체(UI) 기능은 제거된 버전입니다.

from __future__ import annotations

import json
import streamlit as st

from proposal_engine import ProposalEngine

st.set_page_config(page_title="소개서 HTML 생성기", layout="wide")

st.title("소개서 HTML 생성기")
st.caption("기본정보/색상/연락처(Email 포함)만 지원합니다. 이미지 업로드/교체 기능 없음")

engine = ProposalEngine(template_path="proposal_template.html")

# -----------------------------
# 세션 상태 초기화(결과/에러를 저장해서 UI 구조를 안정화)
if "final_html" not in st.session_state:
    st.session_state.final_html = ""
if "last_error" not in st.session_state:
    st.session_state.last_error = ""

# -----------------------------
# 1) 기본 정보 (form으로 묶어서 '버튼 눌렀을 때만' 생성)
with st.sidebar:
    st.header("기본 정보 / 색상")
    with st.form("proposal_form", clear_on_submit=False):
        recipient = st.text_input("수신", value="임직원 검진 담당자 제위")
        proposer = st.text_input("제안", value="뉴고려병원 이준원 팀장")
        tel = st.text_input("Tel.", value="1833 - 9988")
        email = st.text_input("Email.", value="")  # 비워두면 마지막 페이지 이메일 줄이 제거됩니다.

        st.subheader("색상(CSS 변수)")
        accent_blue = st.color_picker("--accent-blue", "#4A90E2")
        accent_gold = st.color_picker("--accent-gold", "#C9A227")
        accent_navy = st.color_picker("--accent-navy", "#0B2A4A")

        submitted = st.form_submit_button("견적서 생성하기")

# -----------------------------
# 2) 템플릿 로드 & 치환 & 이미지 임베딩 (submitted일 때만 수행)
if submitted:
    try:
        base_html = engine.load_template()
        base_html = engine.apply_basic_fields(
            base_html,
            recipient=recipient,
            proposer=proposer,
            tel=tel,
            email=email,
        )
        base_html = engine.apply_theme_vars(
            base_html,
            {
                "--accent-blue": accent_blue,
                "--accent-gold": accent_gold,
                "--accent-navy": accent_navy,
            },
        )

        # 3) 레포 이미지(attachment_pages) 자동 임베딩
        st.session_state.final_html = engine.embed_attachment_images(base_html)
        st.session_state.last_error = ""

    except Exception as e:
        # st.stop()로 UI가 사라지면 프런트엔드 deltaPath 오류가 더 잘 날 수 있어서,
        # 에러를 저장하고 화면 구조는 유지합니다.
        st.session_state.final_html = ""
        st.session_state.last_error = str(e)

# -----------------------------
# 3) 화면 출력 (성공/실패와 무관하게 항상 렌더해서 구조 고정)
if st.session_state.last_error:
    st.error(f"템플릿 처리 실패: {st.session_state.last_error}")

st.subheader("미리보기")
if st.session_state.final_html:
    st.components.v1.html(
        st.session_state.final_html,
        height=650,
        scrolling=True,
        key="preview_iframe",
    )
else:
    st.info("왼쪽에서 정보를 입력한 뒤, '견적서 생성하기'를 눌러 미리보기를 생성하세요.")

st.subheader("내보내기")
if st.session_state.final_html:
    st.download_button(
        label="최종 HTML 다운로드",
        data=st.session_state.final_html.encode("utf-8"),
        file_name="2026_뉴고려병원_제안서.html",
        mime="text/html",
        key="download_html",
    )
else:
    st.download_button(
        label="최종 HTML 다운로드",
        data="".encode("utf-8"),
        file_name="2026_뉴고려병원_제안서.html",
        mime="text/html",
        key="download_html_disabled",
        disabled=True,
    )

# 옵션: 현재 설정을 JSON으로 다운로드(다음 번에 동일 설정 재적용 용도)
settings = {
    "recipient": recipient,
    "proposer": proposer,
    "tel": tel,
    "email": email,
    "colors": {
        "--accent-blue": accent_blue,
        "--accent-gold": accent_gold,
        "--accent-navy": accent_navy,
    },
}
st.download_button(
    label="설정(JSON) 다운로드",
    data=json.dumps(settings, ensure_ascii=False, indent=2).encode("utf-8"),
    file_name="proposal_settings.json",
    mime="application/json",
    key="download_settings",
)
