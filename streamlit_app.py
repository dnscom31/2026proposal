# streamlit_app.py
# 목적: "기본 설정/색상/레이아웃/이미지" + "자료 페이지(이미지) 분석 -> 텍스트로 추가" + "HTML 내보내기"

from __future__ import annotations

from pathlib import Path
import os
import json

import streamlit as st

from proposal_engine import ProposalEngine, ExtractedPage

# OpenAI Python SDK
# 공식 repo: https://github.com/openai/openai-python
from openai import OpenAI


# -----------------------------
# 기본 설정
# -----------------------------
st.set_page_config(page_title="2026 제안서 생성기", layout="wide")
engine = ProposalEngine(template_path="proposal_template.html")


def _get_openai_client() -> OpenAI | None:
    """
    Streamlit Secrets에 OPENAI_API_KEY를 넣으면 st.secrets로 읽을 수 있습니다.
    (Streamlit 공식 문서: Secrets management)
    """
    api_key = None

    # 1) Streamlit Cloud/Local secrets.toml
    if "OPENAI_API_KEY" in st.secrets:
        api_key = st.secrets["OPENAI_API_KEY"]

    # 2) 환경변수 fallback
    if not api_key:
        api_key = os.environ.get("OPENAI_API_KEY")

    if not api_key:
        return None

    return OpenAI(api_key=api_key)


def _list_repo_images(folder: str) -> list[Path]:
    root = Path(folder)
    if not root.exists():
        return []
    exts = {".png", ".jpg", ".jpeg", ".webp"}
    files = [p for p in sorted(root.iterdir()) if p.is_file() and p.suffix.lower() in exts]
    return files


# -----------------------------
# UI
# -----------------------------
st.title("제안서 HTML 생성기 (이미지 페이지 → 텍스트로 추출)")

with st.sidebar:
    st.header("1) 기본 정보")
    recipient = st.text_input("수신", value="임직원 검진 담당자 제위")
    proposer = st.text_input("제안", value="뉴고려병원 이준원 팀장")
    tel = st.text_input("Tel.", value="1833 - 9988")

    st.header("2) 색상(선택)")
    accent_blue = st.color_picker("accent blue", "#4A90E2")
    accent_gold = st.color_picker("accent gold", "#C9A227")
    accent_navy = st.color_picker("accent navy", "#0B2A4A")

    st.caption("색상은 템플릿의 CSS 변수(--accent-...)를 교체하는 방식입니다.")

st.subheader("A. 기존 템플릿 미리보기")
try:
    base_html = engine.load_template()
    base_html = engine.apply_basic_fields(base_html, recipient=recipient, proposer=proposer, tel=tel)
    base_html = engine.apply_theme(base_html, {
        "--accent-blue": accent_blue,
        "--accent-gold": accent_gold,
        "--accent-navy": accent_navy,
    })
except Exception as e:
    st.error(f"템플릿 로드/치환 실패: {e}")
    st.stop()

st.components.v1.html(base_html, height=600, scrolling=True)

st.divider()
st.subheader("B. 자료 페이지(이미지) → 텍스트 추출해서 추가")

col1, col2 = st.columns([1, 2])

with col1:
    st.write("방법 1) GitHub 폴더에서 읽기")
    folder = st.text_input("이미지 폴더 경로", value="source_pages")
    repo_images = _list_repo_images(folder)

    if repo_images:
        options = [p.name for p in repo_images]
        selected = st.multiselect("추출할 이미지 선택", options, default=options)
        selected_paths = [p for p in repo_images if p.name in set(selected)]
    else:
        st.info("폴더에 이미지가 없습니다. GitHub에 source_pages 폴더를 만들고 이미지를 넣어주세요.")
        selected_paths = []

    st.write("---")
    st.write("방법 2) 여기에서 업로드(선택)")
    uploads = st.file_uploader("이미지 업로드(여러 장 가능)", type=["png", "jpg", "jpeg", "webp"], accept_multiple_files=True)

with col2:
    st.write("추출 결과")
    if "extracted_pages" not in st.session_state:
        st.session_state.extracted_pages = []

    # 업로드 파일은 임시로 저장해서 처리
    upload_paths: list[Path] = []
    if uploads:
        tmp_dir = Path(".tmp_uploads")
        tmp_dir.mkdir(exist_ok=True)
        for f in uploads:
            p = tmp_dir / f.name
            p.write_bytes(f.getbuffer())
            upload_paths.append(p)

    images_to_process = selected_paths + upload_paths

    st.caption(f"선택/업로드된 이미지 수: {len(images_to_process)}장")

    client = _get_openai_client()
    if not client:
        st.warning("OPENAI_API_KEY가 설정되지 않았습니다. (Streamlit Cloud: App settings → Secrets)")
    else:
        model = st.selectbox("모델", ["gpt-4o-mini", "gpt-4o"], index=0)
        if st.button("AI로 내용 추출하기", type="primary", disabled=(len(images_to_process) == 0)):
            def prog(i, total, msg):
                st.write(f"[{i}/{total}] {msg}")

            pages = engine.extract_pages_from_images(client, images_to_process, model=model, progress=prog)
            st.session_state.extracted_pages = pages
            st.success("추출 완료")

    # JSON 보기
    if st.session_state.extracted_pages:
        st.json([p.to_dict() for p in st.session_state.extracted_pages], expanded=False)
    else:
        st.info("아직 추출 결과가 없습니다.")

st.divider()
st.subheader("C. 최종 HTML 생성 & 내보내기")

final_pages: list[ExtractedPage] = st.session_state.get("extracted_pages", [])

final_html = engine.append_pages(base_html, final_pages)

st.components.v1.html(final_html, height=600, scrolling=True)

st.download_button(
    label="최종 HTML 다운로드",
    data=final_html.encode("utf-8"),
    file_name="proposal_final.html",
    mime="text/html",
)
