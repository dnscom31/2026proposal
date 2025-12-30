# streamlit_app.py
# -*- coding: utf-8 -*-

import os
import shutil
import tempfile
import uuid

import streamlit as st
import streamlit.components.v1 as components

from proposal_engine import ProposalEngine

st.set_page_config(page_title="2026 검진 제안서 생성기", layout="wide")

BASE_SRC_DIR = os.path.dirname(os.path.abspath(__file__))


def init_session_engine():
    """세션(사용자)마다 작업 폴더를 분리합니다."""
    session_id = st.session_state.get("session_id")
    if not session_id:
        session_id = str(uuid.uuid4())
        st.session_state["session_id"] = session_id

    if "temp_dir" not in st.session_state:
        st.session_state["temp_dir"] = tempfile.mkdtemp(prefix=f"proposal_{session_id}_")

    temp_dir = st.session_state["temp_dir"]
    assets_dir = os.path.join(temp_dir, "proposal_assets")
    os.makedirs(assets_dir, exist_ok=True)

    # 템플릿 복사 (레포에 있는 proposal_template.html -> 세션 폴더)
    src_template = os.path.join(BASE_SRC_DIR, "proposal_template.html")
    dst_template = os.path.join(assets_dir, "proposal_template.html")
    if os.path.exists(src_template) and not os.path.exists(dst_template):
        shutil.copy(src_template, dst_template)

    # GitHub(레포)에 올린 첨부 페이지 이미지 폴더
    attachments_src_dir = os.path.join(BASE_SRC_DIR, "attachment_pages")

    engine = ProposalEngine(base_dir=temp_dir, attachments_src_dir=attachments_src_dir)
    return engine


engine = init_session_engine()

st.title("2026 검진 제안서 HTML 생성기")

# -----------------------------
# Sidebar: 기본 정보 / 색상
# -----------------------------
st.sidebar.header("기본 정보")
recipient = st.sidebar.text_input("수신", value="수신기관명")
proposer = st.sidebar.text_input("제안", value="뉴고려병원")
tel = st.sidebar.text_input("전화번호(Tel.)", value="1833 - 9988")

st.sidebar.header("색상")
primary = st.sidebar.color_picker("메인 컬러(Primary)", value="#4A148C")
accent = st.sidebar.color_picker("포인트 컬러(Accent)", value="#D4AF37")

# -----------------------------
# Tabs
# -----------------------------
tab_layout, tab_images, tab_attachments, tab_export = st.tabs(
    ["레이아웃", "이미지 교체", "자료(첨부) 페이지", "내보내기"]
)

with tab_layout:
    st.subheader("레이아웃(여백/간격/크기)")

    c1, c2, c3 = st.columns(3)
    with c1:
        page_padding_mm = st.slider("페이지 여백(mm)", 0, 40, engine.layout_settings.get("page_padding_mm", 20))
        page_gap_px = st.slider("페이지 간격(px)", 0, 60, engine.layout_settings.get("page_gap_px", 20))
        user_block_gap_px = st.slider("블록 간격(px)", 0, 40, engine.layout_settings.get("user_block_gap_px", 12))
    with c2:
        img_box_height_px = st.slider("대표 이미지 박스 높이(px)", 120, 400, engine.layout_settings.get("img_box_height_px", 220))
        img_margin_v_px = st.slider("이미지 위/아래 여백(px)", 0, 40, engine.layout_settings.get("img_margin_v_px", 10))
        highlight_margin_v_px = st.slider("하이라이트 여백(px)", 0, 40, engine.layout_settings.get("highlight_margin_v_px", 15))
    with c3:
        table_margin_top_px = st.slider("표 상단 여백(px)", 0, 40, engine.layout_settings.get("table_margin_top_px", 10))
        table_cell_padding_px = st.slider("표 셀 패딩(px)", 0, 20, engine.layout_settings.get("table_cell_padding_px", 7))
        st.caption("이미지 고정 높이(템플릿에 따라 쓰일 수도 있습니다)")

    if st.button("레이아웃 적용"):
        engine.set_layout_settings(
            {
                "page_padding_mm": page_padding_mm,
                "page_gap_px": page_gap_px,
                "user_block_gap_px": user_block_gap_px,
                "img_box_height_px": img_box_height_px,
                "img_margin_v_px": img_margin_v_px,
                "highlight_margin_v_px": highlight_margin_v_px,
                "table_margin_top_px": table_margin_top_px,
                "table_cell_padding_px": table_cell_padding_px,
            }
        )
        st.success("레이아웃이 적용되었습니다. (세션 폴더에 저장)")

with tab_images:
    st.subheader("템플릿 내 기본 이미지(placeholder) 교체")

    st.info("여기서 업로드한 이미지는 GitHub 코드를 수정하지 않습니다. 현재 세션에서만 반영됩니다.")

    for slot in engine.image_slots:
        uploaded = st.file_uploader(
            f"{slot.key} 업로드 (권장 비율: {slot.target_size[0]}x{slot.target_size[1]})",
            type=["jpg", "jpeg", "png", "webp"],
            key=f"upload_{slot.key}",
        )
        if uploaded is not None:
            try:
                engine.save_uploaded_image(slot.key, uploaded.getvalue())
                st.success(f"'{slot.key}' 이미지가 적용되었습니다.")
            except Exception as e:
                st.error(f"이미지 처리 실패: {e}")

with tab_attachments:
    st.subheader("자료(첨부) 페이지 이미지 → 최종 HTML에 계속 추가")

    st.markdown(
        """
**GitHub에 올리는 방법(권장)**

1) 레포(프로젝트) 루트에 `attachment_pages` 폴더를 만듭니다.
2) 그 안에 자료 페이지 이미지를 넣고 커밋/푸시합니다.
   - 예: `attachment_pages/2026_뉴고려 검진 제안서_04.jpg`
3) 이 앱은 내보내기 시 `attachment_pages`의 이미지를 파일명 순서대로 모두 붙여서 최종 HTML을 만듭니다.

※ 최종 HTML에는 이미지가 base64로 포함되므로, HTML 파일만 따로 내려받아도 이미지가 깨지지 않습니다.
"""
    )

    files = engine.list_attachment_images()
    if not files:
        st.warning("레포에 attachment_pages 폴더가 없거나, 이미지 파일이 없습니다.")
    else:
        st.success(f"첨부 페이지 이미지 {len(files)}개를 찾았습니다.")
        st.write("정렬(추정) 순서:")
        for p in files[:30]:
            st.write("- ", os.path.basename(p))
        if len(files) > 30:
            st.write(f"... 외 {len(files)-30}개")

with tab_export:
    st.subheader("최종 HTML 생성/미리보기/다운로드")

    if st.button("최종 HTML 생성"):
        try:
            final_html = engine.build_output_html(
                recipient=recipient,
                proposer=proposer,
                tel=tel,
                primary=primary,
                accent=accent,
            )
            st.session_state["final_html"] = final_html
            st.success("생성이 완료되었습니다.")
        except Exception as e:
            st.error(f"생성 중 오류 발생: {e}")

    if "final_html" in st.session_state:
        final_html = st.session_state["final_html"]

        st.download_button(
            label="HTML 다운로드",
            data=final_html.encode("utf-8"),
            file_name="proposal_final.html",
            mime="text/html",
        )

        st.markdown("---")
        st.caption("미리보기(브라우저 렌더링)")

        # 높이는 필요에 따라 조절
        components.html(final_html, height=900, scrolling=True)
