# streamlit_app.py
# 목적: "기본 정보/색상(CSS 변수)" + "레포 이미지(attachment_pages) 자동 임베딩" + "HTML 내보내기"
# 주의: 이미지 교체(UI) 기능은 제거된 버전입니다.

from __future__ import annotations

import json
import streamlit as st

from proposal_engine import ProposalEngine

st.set_page_config(page_title="제안서 HTML 생성기", layout="wide")

st.title("제안서 HTML 생성기")
st.caption("기본정보/색상/연락처(Email 포함)만 지원합니다. 이미지 업로드/교체 기능 없음")

engine = ProposalEngine(template_path="proposal_template.html")

# -----------------------------
# 1) 기본 정보
with st.sidebar:
    st.header("기본 정보")
    recipient = st.text_input("수신", value="임직원 검진 담당자 제위")
    proposer = st.text_input("제안", value="뉴고려병원 이준원 팀장")
    tel = st.text_input("Tel.", value="1833 - 9988")
    email = st.text_input("Email.", value="")  # 비워두면 마지막 페이지 이메일 줄이 제거됩니다.

    st.header("색상(CSS 변수)")
    accent_blue = st.color_picker("--accent-blue", "#4A90E2")
    accent_gold = st.color_picker("--accent-gold", "#C9A227")
    accent_navy = st.color_picker("--accent-navy", "#0B2A4A")

# -----------------------------
# 2) 템플릿 로드 & 치환
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
    final_html = engine.embed_attachment_images(base_html)

except Exception as e:
    st.error(f"템플릿 처리 실패: {e}")
    st.stop()

st.subheader("미리보기")
st.components.v1.html(final_html, height=650, scrolling=True)

st.subheader("내보내기")
st.download_button(
    label="최종 HTML 다운로드",
    data=final_html.encode("utf-8"),
    file_name="2026_뉴고려병원_제안서.html",
    mime="text/html",
)

# 옵션: 현재 설정을 JSON으로 다운로드(다음 번에 동일 설정 재적용 용도)
settings = {
    "recipient": recipient,
    "proposer": proposer,
    "tel": tel,
    "email": email,
    "colors": {"--accent-blue": accent_blue, "--accent-gold": accent_gold, "--accent-navy": accent_navy},
}
st.download_button(
    label="설정(JSON) 다운로드",
    data=json.dumps(settings, ensure_ascii=False, indent=2).encode("utf-8"),
    file_name="proposal_settings.json",
    mime="application/json",
)
