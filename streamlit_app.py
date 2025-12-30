# streamlit_app.py
# -*- coding: utf-8 -*-

import os
import tempfile
import uuid

import streamlit as st

from proposal_engine import ProposalEngine

st.set_page_config(page_title="제안서 생성기 (Streamlit)", layout="wide")


@st.cache_resource
def get_engine() -> ProposalEngine:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return ProposalEngine(base_dir)


def _save_upload_to_temp(uploaded_file) -> str:
    """
    Streamlit 업로드 파일(메모리)을 임시 파일로 저장한 뒤 경로를 반환합니다.
    ProposalEngine.copy_resize_to_local()이 '경로'를 받기 때문에 필요합니다.
    """
    ext = os.path.splitext(uploaded_file.name)[1].lower()
    if not ext:
        ext = ".bin"

    tmp_dir = os.path.join(tempfile.gettempdir(), "proposal_uploads")
    os.makedirs(tmp_dir, exist_ok=True)

    tmp_path = os.path.join(tmp_dir, f"{uuid.uuid4().hex}{ext}")
    with open(tmp_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return tmp_path


engine = get_engine()

# Tkinter GUI의 기본값과 동일하게 시작(원하시면 바꿔도 됩니다)
# proposal_gui.py: 김포시청 / 뉴고려병원 / 031-980-9114 / #4A148C / #D4AF37 :contentReference[oaicite:4]{index=4}
default_recipient = "김포시청"
default_proposer = "뉴고려병원"
default_tel = "031-980-9114"
default_primary = "#4A148C"
default_accent = "#D4AF37"

st.title("제안서 생성기 (Streamlit)")

tab_basic, tab_layout, tab_images, tab_pages, tab_export = st.tabs(
    ["기본 정보", "레이아웃/공백", "이미지", "페이지 선택", "HTML 생성/다운로드"]
)

with tab_basic:
    col1, col2 = st.columns(2)
    with col1:
        recipient = st.text_input("수신(Recipient)", value=st.session_state.get("recipient", default_recipient))
        proposer = st.text_input("제안(Proposer)", value=st.session_state.get("proposer", default_proposer))
        tel = st.text_input("Tel", value=st.session_state.get("tel", default_tel))
    with col2:
        primary_color = st.color_picker("Primary Color", value=st.session_state.get("primary_color", default_primary))
        accent_color = st.color_picker("Accent Color", value=st.session_state.get("accent_color", default_accent))

    # 세션에 저장(리런 시 값 유지)
    st.session_state["recipient"] = recipient
    st.session_state["proposer"] = proposer
    st.session_state["tel"] = tel
    st.session_state["primary_color"] = primary_color
    st.session_state["accent_color"] = accent_color

with tab_layout:
    st.write("레이아웃(CSS 변수) 값을 조정합니다. 변경 후 적용하면 이미지 리사이즈에도 영향을 줄 수 있습니다.")
    current = engine.get_layout_settings()
    new_settings = {}

    # 보기 좋게 2열 배치
    keys = list(current.keys())
    left_keys = keys[0::2]
    right_keys = keys[1::2]
    c1, c2 = st.columns(2)

    for k in left_keys:
        new_settings[k] = c1.number_input(k, value=int(current[k]), step=1)

    for k in right_keys:
        new_settings[k] = c2.number_input(k, value=int(current[k]), step=1)

    if st.button("레이아웃 적용"):
        engine.set_layout_settings({k: int(v) for k, v in new_settings.items()})
        st.success("레이아웃이 적용되었습니다. (필요 시 이미지도 새 설정에 맞게 재생성됩니다.)")

with tab_images:
    st.write("각 이미지 키에 맞는 사진을 업로드하세요. 업로드된 파일은 엔진이 로컬에 복사/리사이즈하여 관리합니다. :contentReference[oaicite:5]{index=5}")

    for idx, (key, meta) in enumerate(engine.image_map.items()):
        st.subheader(key)
        up = st.file_uploader(
            f"업로드 ({key})",
            type=["jpg", "jpeg", "png", "webp", "bmp", "gif", "tif", "tiff"],
            key=f"upl_{idx}",
        )

        if up is not None:
            tmp_path = _save_upload_to_temp(up)
            resized_path = engine.copy_resize_to_local(key, tmp_path)
            engine.image_map[key]["path"] = resized_path
            engine.save_settings()
            st.success("업로드 및 리사이즈 완료")

        cur = engine.image_map.get(key, {}).get("path", "")
        if cur and os.path.exists(cur):
            st.image(cur, caption=f"현재 적용 이미지: {os.path.basename(cur)}", use_container_width=True)

with tab_pages:
    st.write("최종 HTML에 포함할 페이지를 선택합니다. (엔진은 선택된 페이지만 남겨서 출력합니다.) :contentReference[oaicite:6]{index=6}")

    pages = engine.get_pages()
    # page_enabled 길이가 안 맞으면 엔진이 build_output_html에서 보정하지만, UI에서도 안전하게 보정
    if (not engine.page_enabled) or (len(engine.page_enabled) != len(pages)):
        engine.page_enabled = [True] * len(pages)

    st.caption("체크 해제 = 해당 페이지 제외")
    changed = False
    new_enabled = []
    for i in range(len(pages)):
        v = st.checkbox(f"페이지 {i+1} 포함", value=bool(engine.page_enabled[i]), key=f"pg_en_{i}")
        new_enabled.append(bool(v))

    if new_enabled != engine.page_enabled:
        # 변경된 것만 반영
        for i, v in enumerate(new_enabled):
            if v != engine.page_enabled[i]:
                engine.set_page_enabled(i, v)
        changed = True

    if changed:
        st.success("페이지 포함 여부가 저장되었습니다.")

    st.divider()
    st.write("페이지 순서 이동 / 복제")
    sel = st.selectbox("대상 페이지", options=list(range(1, len(pages) + 1)))
    colA, colB, colC = st.columns(3)
    if colA.button("위로 이동"):
        engine.move_page(sel - 1, -1)
        st.rerun()
    if colB.button("아래로 이동"):
        engine.move_page(sel - 1, +1)
        st.rerun()
    if colC.button("선택 페이지 복제"):
        engine.duplicate_page(sel - 1)
        st.rerun()

with tab_export:
    st.write("입력값/이미지/페이지 선택을 반영해 최종 HTML을 생성합니다. (이미지는 Base64로 내장됩니다.) :contentReference[oaicite:7]{index=7}")

    recipient = st.session_state.get("recipient", default_recipient).strip()
    proposer = st.session_state.get("proposer", default_proposer).strip()
    tel = st.session_state.get("tel", default_tel).strip()
    primary_color = st.session_state.get("primary_color", default_primary)
    accent_color = st.session_state.get("accent_color", default_accent)

    if st.button("HTML 생성"):
        html_text = engine.build_output_html(
            recipient=recipient,
            proposer=proposer,
            tel=tel,
            primary_color=primary_color,
            accent_color=accent_color,
        )
        st.session_state["last_html"] = html_text
        st.success("HTML 생성 완료")

    html_text = st.session_state.get("last_html", "")
    if html_text:
        st.download_button(
            label="HTML 다운로드",
            data=html_text.encode("utf-8"),
            file_name="proposal_output.html",
            mime="text/html",
        )
        with st.expander("미리보기(브라우저 렌더)"):
            st.components.v1.html(html_text, height=900, scrolling=True)
