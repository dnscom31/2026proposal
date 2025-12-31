# streamlit_app.py
# 목적: "기본 설정/색상/레이아웃(=CSS 변수)" + "이미지(src) 교체" + "HTML 내보내기"
# 주의: '자료 이미지 분석(텍스트 추출)' 기능은 제거된 버전입니다.

from __future__ import annotations

import json
from typing import List

import streamlit as st

from proposal_engine import ProposalEngine, ImageReplacement

st.set_page_config(page_title="제안서 HTML 생성기", layout="wide")

st.title("제안서 HTML 생성기")
st.caption("기본정보/색상/이미지 교체만 지원합니다. (이미지 분석/텍스트 추출 기능 없음)")

engine = ProposalEngine(template_path="proposal_template.html")

# -----------------------------
# 세션 상태
if "img_replacements" not in st.session_state:
    st.session_state.img_replacements = []  # type: ignore

# -----------------------------
# 1) 기본 정보
with st.sidebar:
    st.header("기본 정보")
    recipient = st.text_input("수신", value="임직원 검진 담당자 제위")
    proposer = st.text_input("제안", value="뉴고려병원 이준원 팀장")
    tel = st.text_input("Tel.", value="1833 - 9988")

    st.header("색상(CSS 변수)")
    accent_blue = st.color_picker("--accent-blue", "#4A90E2")
    accent_gold = st.color_picker("--accent-gold", "#C9A227")
    accent_navy = st.color_picker("--accent-navy", "#0B2A4A")

# -----------------------------
# 2) 템플릿 로드 & 1차 치환
try:
    base_html = engine.load_template()
    base_html = engine.apply_basic_fields(base_html, recipient=recipient, proposer=proposer, tel=tel)
    base_html = engine.apply_theme_vars(
        base_html,
        {
            "--accent-blue": accent_blue,
            "--accent-gold": accent_gold,
            "--accent-navy": accent_navy,
        },
    )
except Exception as e:
    st.error(f"템플릿 처리 실패: {e}")
    st.stop()

# -----------------------------
# 3) 이미지 교체 UI
st.subheader("이미지 교체")
srcs = engine.list_image_srcs(base_html)

if not srcs:
    st.info("현재 템플릿에서 <img src=\"...\"> 를 찾지 못했습니다. 템플릿의 이미지 태그를 확인하세요.")
else:
    col_a, col_b = st.columns([1, 2])

    with col_a:
        target_src = st.selectbox("교체할 이미지(src) 선택", options=srcs)
        up = st.file_uploader("새 이미지 업로드(JPG/PNG/WebP)", type=["jpg", "jpeg", "png", "webp"])
        if st.button("선택 이미지 교체 추가", type="primary", disabled=(up is None)):
            if up is not None:
                mime = up.type or "image/jpeg"
                rpl = engine.make_image_replacement(target_src, up.getvalue(), mime)
                st.session_state.img_replacements.append(rpl)  # type: ignore
                st.success("이미지 교체 항목이 추가되었습니다.")

    with col_b:
        st.markdown("### 현재 이미지 교체 목록")
        reps: List[ImageReplacement] = st.session_state.img_replacements  # type: ignore
        if not reps:
            st.write("- (없음)")
        else:
            for i, r in enumerate(reps):
                st.write(f"{i+1}. {r.original_src}  →  ({r.mime}) data URL")
            if st.button("이미지 교체 목록 초기화"):
                st.session_state.img_replacements = []  # type: ignore
                st.success("초기화 완료")

# -----------------------------
# 4) 최종 HTML 생성
final_html = engine.replace_images(base_html, st.session_state.img_replacements)  # type: ignore

st.subheader("미리보기")
st.components.v1.html(final_html, height=650, scrolling=True)

st.subheader("내보내기")
st.download_button(
    label="최종 HTML 다운로드",
    data=final_html.encode("utf-8"),
    file_name="proposal_final.html",
    mime="text/html",
)

# 옵션: 현재 설정을 JSON으로 다운로드(다음 번에 동일 설정 재적용 용도)
settings = {
    "recipient": recipient,
    "proposer": proposer,
    "tel": tel,
    "colors": {"--accent-blue": accent_blue, "--accent-gold": accent_gold, "--accent-navy": accent_navy},
    "image_replacements": [{"original_src": r.original_src, "mime": r.mime} for r in st.session_state.img_replacements],  # type: ignore
}
st.download_button(
    label="설정(JSON) 다운로드",
    data=json.dumps(settings, ensure_ascii=False, indent=2).encode("utf-8"),
    file_name="proposal_settings.json",
    mime="application/json",
)
